"""
Complete-dataset retrieval.

Instead of analysing only the first 1,000 studies of a search, this retrieves EVERY
page ClinicalTrials.gov offers for that search, stores the studies locally keyed by
NCT ID, and lets every analytics endpoint compute over the full set.

    search → first page (≤1,000 studies) ─┐
             nextPageToken? ── yes ──► next page ──┐   (sequential, polite delay)
                              └─ no ──► complete   │
             save each page to disk, merge by NCT ID ◄┘

Behaviour (each rule is covered by tests/test_datasets.py):

  * Progress is visible: coverage says "retrieved N of M"; analytics computed from a
    partial set are labelled partial (isComplete=False) until the last page lands.
  * A failed request is retried with back-off. HTTP 429 honours the server's
    Retry-After. Studies already retrieved are kept; if retries run out the dataset
    goes to state "error" with the message, still serving what it has, and resumes
    from the saved page token on the next request.
  * Changing filters pauses the old retrieval (it keeps its token and can resume) and
    starts/loads the dataset for the new filters.
  * Repeating a search re-uses the local copy while it is fresh.
  * One record per NCT ID, always.
  * Older complete datasets are refreshed incrementally (only records changed since
    the last retrieval are fetched and merged by NCT ID) and periodically reconciled
    with a full re-retrieval, because a changed condition/status can make a trial
    enter or leave the result set.
  * A safety cap (TRIALLENS_MAX_STUDIES, default 20,000) stops giant searches such as
    "Cancer" (>120k studies) from exhausting memory or hammering the registry. A capped
    dataset is labelled as such and the user can lift the cap explicitly.

"Complete" means every page was retrieved for that search at the time shown. The public
registry can still change during retrieval.

No LLM and no API key: this only talks to the public ClinicalTrials.gov v2 API.
"""
from __future__ import annotations

import asyncio
import collections
import dataclasses
import datetime
import gzip
import hashlib
import json
import logging
import os
import pathlib
import random
import threading
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

from services.http import client as http_client
from services import ct_gov
from services.ct_gov import CTGovError

log = logging.getLogger("triallens.datasets")


def _env_num(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


PAGE_SIZE = 1000                                              # API maximum
PAGE_DELAY_S = _env_num("TRIALLENS_PAGE_DELAY", 0.4)          # politeness between pages
MAX_STUDIES = int(_env_num("TRIALLENS_MAX_STUDIES", 20000))   # auto-retrieval cap
FRESH_HOURS = _env_num("TRIALLENS_DATASET_FRESH_HOURS", 6)    # serve as-is below this age
RECONCILE_DAYS = _env_num("TRIALLENS_RECONCILE_DAYS", 7)      # full re-retrieval beyond this
CACHE_MAX_MB = _env_num("TRIALLENS_CACHE_MB", 1024)
MAX_RETRIES = 6
FIRST_PAGE_TIMEOUT_S = 120.0
ERROR_RETRY_AFTER_S = 10.0
MEMORY_DATASETS = 2                                           # parsed datasets kept in RAM

DEFAULT_CACHE_DIR = pathlib.Path(__file__).resolve().parent.parent / ".cache" / "datasets"

PageFetcher = Callable[..., Awaitable[dict]]


# ── Filters / dataset identity ──────────────────────────────────────────────
def _csv(v: Optional[str]) -> Tuple[str, ...]:
    return tuple(x.strip() for x in v.split(",") if x.strip()) if v else ()


@dataclasses.dataclass(frozen=True)
class Filters:
    condition: Optional[str] = None
    status: Tuple[str, ...] = ()
    phases: Tuple[str, ...] = ()
    study_types: Tuple[str, ...] = ()
    sponsor_classes: Tuple[str, ...] = ()
    country: Optional[str] = None
    from_year: Optional[int] = None
    completion_from: Optional[str] = None
    completion_to: Optional[str] = None
    geo_lat: Optional[float] = None
    geo_lng: Optional[float] = None
    geo_miles: Optional[float] = None

    @classmethod
    def from_query(cls, *, condition=None, status=None, phases=None, studyTypes=None,
                   sponsorClasses=None, country=None, fromYear=None, completionFrom=None,
                   completionTo=None, geoLat=None, geoLng=None, geoMiles=None) -> "Filters":
        return cls(
            condition=(condition or "").strip() or None,
            status=_csv(status), phases=_csv(phases), study_types=_csv(studyTypes),
            sponsor_classes=_csv(sponsorClasses), country=(country or "").strip() or None,
            from_year=fromYear, completion_from=completionFrom, completion_to=completionTo,
            geo_lat=geoLat, geo_lng=geoLng, geo_miles=geoMiles,
        )

    def canonical(self) -> dict:
        """Order/case-insensitive form, so equivalent searches share one dataset."""
        return {
            "condition": " ".join((self.condition or "").lower().split()) or None,
            "status": sorted(x.upper() for x in self.status),
            "phases": sorted(x.upper() for x in self.phases),
            "study_types": sorted(x.upper() for x in self.study_types),
            "sponsor_classes": sorted(x.upper() for x in self.sponsor_classes),
            "country": (self.country or "").lower() or None,
            "from_year": self.from_year,
            "completion_from": self.completion_from, "completion_to": self.completion_to,
            "geo": [self.geo_lat, self.geo_lng, self.geo_miles],
        }

    def key(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True).encode()
        return hashlib.sha1(blob).hexdigest()[:20]

    def api_kwargs(self) -> dict:
        return {
            "condition": self.condition,
            "status": list(self.status) or None,
            "phases": list(self.phases) or None,
            "study_types": list(self.study_types) or None,
            "sponsor_classes": list(self.sponsor_classes) or None,
            "country": self.country, "from_year": self.from_year,
            "completion_from": self.completion_from, "completion_to": self.completion_to,
            "geo_lat": self.geo_lat, "geo_lng": self.geo_lng, "geo_miles": self.geo_miles,
        }


# ── Public snapshot ─────────────────────────────────────────────────────────
@dataclasses.dataclass
class Snapshot:
    key: str
    studies: List[dict]
    total: int
    state: str
    version: int
    coverage: dict


def _iso(ts: Optional[float]) -> Optional[str]:
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds") if ts else None


class Dataset:
    def __init__(self, filters: Filters, cap: int):
        self.filters = filters
        self.key = filters.key()
        self.studies: Dict[str, dict] = {}
        self.total: Optional[int] = None
        # new | retrieving | complete | capped | paused | error
        self.state = "new"
        self.next_token: Optional[str] = None
        self.pages = 0
        self.cap = cap
        self.uncapped = False
        self.error: Optional[str] = None
        self.error_status: Optional[int] = None
        self.error_at = 0.0
        self.note: Optional[str] = None       # e.g. "rate-limited, retrying in 12s"
        self.completed_at: Optional[float] = None
        self.last_page_at: Optional[float] = None
        self.refreshing = False
        self.bg_attempt_at = 0.0               # last background update/reconcile start
        self.needs_rewrite = False             # cache file was truncated → compact on resume
        self.version = 0
        self.task: Optional["asyncio.Task"] = None
        # Created lazily ON the event loop: Python 3.9's asyncio.Event binds to the loop of the
        # thread that creates it, and datasets may be built in a worker thread (disk load).
        self._first_page: Optional[asyncio.Event] = None
        self._first_ready = False
        self.last_access = time.time()
        self.last_touch = 0.0

    @property
    def first_page(self) -> "asyncio.Event":
        if self._first_page is None:
            self._first_page = asyncio.Event()
            if self._first_ready:
                self._first_page.set()
        return self._first_page

    def coverage(self) -> dict:
        n = len(self.studies)
        total = self.total if self.total is not None else n
        return {
            "analyzed": n,
            "total": max(total, 0),
            "isComplete": self.state == "complete",
            "state": self.state,
            "retrieved": n,
            "capped": self.state == "capped",
            "refreshing": self.refreshing,
            "retrievedAt": _iso(self.last_page_at),
            "completedAt": _iso(self.completed_at),
            "error": self.error,
            "note": self.note,
            "pages": self.pages,
        }


# ── Manager ─────────────────────────────────────────────────────────────────
class DatasetManager:
    def __init__(self, fetch_page: Optional[PageFetcher] = None,
                 cache_dir: Optional[pathlib.Path] = None,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 page_delay: Optional[float] = None, max_studies: Optional[int] = None):
        self._fetch_page: PageFetcher = fetch_page or ct_gov.fetch_page
        self.cache_dir = pathlib.Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self._sleep = sleep
        self.page_delay = PAGE_DELAY_S if page_delay is None else page_delay
        self.max_studies = MAX_STUDIES if max_studies is None else max_studies
        self._mem: "collections.OrderedDict[str, Dataset]" = collections.OrderedDict()
        self._memo: "collections.OrderedDict[tuple, Any]" = collections.OrderedDict()
        self._io_lock = threading.Lock()   # one writer at a time (meta/data files)

    # -- public API ----------------------------------------------------------
    async def snapshot(self, filters: Filters, *, wait_first: bool = True) -> Snapshot:
        ds = await self._aget(filters)
        ds.last_access = time.time()
        self._touch_disk(ds)
        self._ensure_running(ds)
        if wait_first and ds.version == 0 and ds.state in ("new", "retrieving"):
            try:
                await asyncio.wait_for(ds.first_page.wait(), timeout=FIRST_PAGE_TIMEOUT_S)
            except asyncio.TimeoutError:
                pass
        if ds.version == 0 and ds.state == "error":
            raise CTGovError(ds.error or "Could not retrieve data from ClinicalTrials.gov.",
                             status=ds.error_status or 502)
        return self._snap(ds)

    def status(self, filters: Filters) -> dict:
        """Cheap progress probe for polling — never starts a retrieval."""
        ds = self._peek(filters)
        if ds is None:
            meta = self._peek_meta(filters)
            if meta:
                n = meta.get("count") or 0
                state = meta.get("state", "paused")
                if state in ("retrieving", "new"):
                    state = "paused"
                return {"state": state, "analyzed": n, "total": meta.get("total") or n,
                        "isComplete": state == "complete", "retrieved": n,
                        "capped": state == "capped", "refreshing": False,
                        "retrievedAt": _iso(meta.get("last_page_at")),
                        "completedAt": _iso(meta.get("completed_at")),
                        "error": None, "note": None, "pages": meta.get("pages", 0), "version": 0}
            return {"state": "none", "analyzed": 0, "total": 0, "isComplete": False,
                    "retrieved": 0, "capped": False, "refreshing": False, "retrievedAt": None,
                    "completedAt": None, "error": None, "note": None, "pages": 0, "version": 0}
        return {**ds.coverage(), "version": ds.version}

    async def lift_cap(self, filters: Filters) -> dict:
        """User chose to retrieve everything beyond the safety cap."""
        ds = await self._aget(filters)
        ds.uncapped = True
        ds.cap = 10 ** 9
        if ds.state == "capped":
            ds.state = "paused"
        self._ensure_running(ds)
        return {**ds.coverage(), "version": ds.version}

    async def refresh(self, filters: Filters) -> dict:
        """Force an incremental update now (changed records merged by NCT ID)."""
        ds = await self._aget(filters)
        if ds.state in ("complete", "capped") and not (ds.task and not ds.task.done()):
            self._start(ds, "update")
        else:
            self._ensure_running(ds)
        return {**ds.coverage(), "version": ds.version}

    async def compute(self, snap: Snapshot, name: str, extra: tuple, fn: Callable[[List[dict]], Any]) -> Any:
        """Run CPU-bound analytics off the event loop, memoised per dataset version so
        repeated polls of an unchanged dataset are free. Returns a payload that callers
        must treat as read-only."""
        key = (name, snap.key, snap.version, snap.state, extra)
        if key in self._memo:
            self._memo.move_to_end(key)
            return self._memo[key]
        result = await asyncio.to_thread(fn, snap.studies)
        self._memo[key] = result
        while len(self._memo) > 96:
            self._memo.popitem(last=False)
        return result

    async def shutdown(self) -> None:
        for ds in list(self._mem.values()):
            if ds.task and not ds.task.done():
                ds.task.cancel()
        await asyncio.gather(*[d.task for d in self._mem.values() if d.task], return_exceptions=True)

    # -- dataset lookup / persistence ---------------------------------------
    def _snap(self, ds: Dataset) -> Snapshot:
        studies = list(ds.studies.values())
        total = ds.total if ds.total is not None else len(studies)
        return Snapshot(ds.key, studies, total, ds.state, ds.version, ds.coverage())

    def _peek(self, filters: Filters) -> Optional[Dataset]:
        return self._mem.get(filters.key())

    def _peek_meta(self, filters: Filters) -> Optional[dict]:
        """Progress for a dataset that is only on disk — reads the small meta file, never
        the (large) study file."""
        try:
            return json.loads(self._meta_path(filters.key()).read_text())
        except Exception:
            return None

    async def _aget(self, filters: Filters) -> Dataset:
        """Like _get, but parses a stored dataset off the event loop (a 20k-study file takes
        seconds and would freeze every other request, including /health)."""
        key = filters.key()
        if key not in self._mem and self._meta_path(key).exists():
            loaded = await asyncio.to_thread(self._load_from_disk, filters)
            if key not in self._mem:          # another request may have loaded it meanwhile
                self._mem[key] = loaded
        return self._get(filters)

    def _get(self, filters: Filters) -> Dataset:
        key = filters.key()
        ds = self._mem.get(key)
        if ds is None:
            ds = self._load_from_disk(filters) if self._meta_path(key).exists() else Dataset(filters, self.max_studies)
            self._mem[key] = ds
        self._mem.move_to_end(key)
        self._trim_memory(keep=key)
        return ds

    def _trim_memory(self, keep: str) -> None:
        while len(self._mem) > MEMORY_DATASETS:
            for k, d in self._mem.items():
                running = d.task is not None and not d.task.done()
                if k != keep and not running and d.state != "new":
                    del self._mem[k]
                    break
            else:
                return

    def _meta_path(self, key: str) -> pathlib.Path:
        return self.cache_dir / f"{key}.meta.json"

    def _data_path(self, key: str) -> pathlib.Path:
        return self.cache_dir / f"{key}.jsonl.gz"

    def _load_from_disk(self, filters: Filters) -> Dataset:
        ds = Dataset(filters, self.max_studies)
        try:
            meta = json.loads(self._meta_path(ds.key).read_text())
            ds.total = meta.get("total")
            ds.state = meta.get("state", "paused")
            ds.next_token = meta.get("next_token")
            ds.pages = meta.get("pages", 0)
            ds.completed_at = meta.get("completed_at")
            ds.last_page_at = meta.get("last_page_at")
            ds.uncapped = bool(meta.get("uncapped"))
            if ds.uncapped:
                ds.cap = 10 ** 9
        except Exception:
            log.warning("unreadable dataset meta for %s — starting fresh", ds.key)
            return Dataset(filters, self.max_studies)

        path = self._data_path(ds.key)
        if path.exists():
            try:
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        if line.strip():
                            rec = json.loads(line)
                            ds.studies[rec["nctId"]] = rec       # later lines win (updates)
            except (EOFError, OSError, ValueError):
                # A crash mid-write can truncate the last page; keep everything read so far
                # and resume from the start of that page by re-fetching (dedupe handles it).
                log.warning("dataset %s truncated — keeping %d records", ds.key, len(ds.studies))
                ds.state, ds.next_token = "paused", None
                ds.needs_rewrite = True
        if ds.state in ("retrieving", "new"):
            ds.state = "paused"          # the process died mid-retrieval
        if not ds.studies and ds.state == "complete" and ds.total:
            ds.state, ds.next_token = "paused", None
        if ds.studies and (not ds.total or ds.total < len(ds.studies)):
            ds.total = len(ds.studies)   # repairs caches written by the earlier total=0 bug
        ds.version = 1 if ds.studies or ds.state == "complete" else 0
        if ds.version:
            ds._first_ready = True
        return ds

    def _write_page(self, ds_key: str, filters: Filters, new: List[dict], meta: dict) -> None:
        with self._io_lock:
            self._write_page_locked(ds_key, filters, new, meta)

    def _write_page_locked(self, ds_key: str, filters: Filters, new: List[dict], meta: dict) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        if new:
            blob = gzip.compress("\n".join(json.dumps(s, separators=(",", ":")) for s in new).encode("utf-8") + b"\n")
            with open(self._data_path(ds_key), "ab") as fh:   # one gzip member per page
                fh.write(blob)
        meta = {**meta, "filters": filters.canonical()}
        tmp = self._meta_path(ds_key).with_suffix(".tmp")
        tmp.write_text(json.dumps(meta))
        os.replace(tmp, self._meta_path(ds_key))

    def _rewrite_all(self, ds_key: str, filters: Filters, studies: List[dict], meta: dict) -> None:
        """Compaction after reconcile: replace the file with exactly the current set."""
        with self._io_lock:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = self._data_path(ds_key).with_suffix(".tmp")
            with gzip.open(tmp, "wt", encoding="utf-8") as fh:
                for s in studies:
                    fh.write(json.dumps(s, separators=(",", ":")) + "\n")
            os.replace(tmp, self._data_path(ds_key))
            self._write_page_locked(ds_key, filters, [], meta)

    def _meta(self, ds: Dataset) -> dict:
        return {"key": ds.key, "total": ds.total, "state": ds.state, "next_token": ds.next_token,
                "pages": ds.pages, "completed_at": ds.completed_at, "last_page_at": ds.last_page_at,
                "uncapped": ds.uncapped, "count": len(ds.studies), "saved_at": time.time()}

    def _touch_disk(self, ds: Dataset) -> None:
        now = time.time()
        if now - ds.last_touch > 60:
            ds.last_touch = now
            try:
                os.utime(self._meta_path(ds.key), None)
            except OSError:
                pass

    def _evict_if_needed(self, keep: set) -> None:
        try:
            metas = list(self.cache_dir.glob("*.meta.json"))
            def size(m: pathlib.Path) -> int:
                k = m.name[: -len(".meta.json")]
                d = self._data_path(k)
                return m.stat().st_size + (d.stat().st_size if d.exists() else 0)
            total = sum(size(m) for m in metas)
            limit = CACHE_MAX_MB * 1024 * 1024
            for m in sorted(metas, key=lambda x: x.stat().st_mtime):
                if total <= limit:
                    break
                k = m.name[: -len(".meta.json")]
                if k in keep or k in self._mem:
                    continue
                total -= size(m)
                self._data_path(k).unlink(missing_ok=True) if hasattr(pathlib.Path, "unlink") else None
                m.unlink(missing_ok=True)
        except Exception:
            log.exception("cache eviction failed (ignored)")

    # -- scheduling ----------------------------------------------------------
    def _running(self, ds: Dataset) -> bool:
        return ds.task is not None and not ds.task.done()

    def _ensure_running(self, ds: Dataset) -> None:
        if self._running(ds):
            return
        now = time.time()
        if ds.state == "retrieving":
            # No live task but still marked retrieving: it was cancelled before its first
            # step ran (the except-handler never executed). Treat as paused and resume.
            ds.state = "paused"
        if ds.state in ("new", "paused"):
            self._start(ds, "retrieve")
        elif ds.state == "error":
            if now - ds.error_at >= ERROR_RETRY_AFTER_S:
                self._start(ds, "retrieve")
        elif ds.state == "complete" and ds.completed_at:
            if now - ds.bg_attempt_at < ERROR_RETRY_AFTER_S:
                return                      # a recent background refresh failed — back off
            age = now - ds.completed_at
            if age > RECONCILE_DAYS * 86400:
                self._start(ds, "reconcile")
            elif age > FRESH_HOURS * 3600:
                self._start(ds, "update")
        # "retrieving" with no live task (shouldn't happen) and "capped": nothing to do

    def _start(self, ds: Dataset, mode: str) -> None:
        if self._running(ds):
            return
        # Changing filters pauses the other retrievals; they keep their token and resume later.
        for other in self._mem.values():
            if other is not ds and self._running(other):
                other.task.cancel()
        if mode in ("update", "reconcile"):
            ds.bg_attempt_at = time.time()
        if mode == "retrieve":
            if ds.version == 0:
                ds.first_page.clear()      # so wait_first really waits after an earlier failure
            # Flip to "retrieving" NOW, not when the task first runs — otherwise a status
            # poll in between reports "paused"/"error" for a dataset that is resuming.
            ds.state, ds.error = "retrieving", None
        ds.task = asyncio.get_running_loop().create_task(self._run(ds, mode))

    # -- the retrieval loop --------------------------------------------------
    async def _page_with_retry(self, ds: Dataset, token: Optional[str], client, extra: dict) -> dict:
        attempt = 0
        while True:
            try:
                page = await self._fetch_page(page_size=PAGE_SIZE, page_token=token, client=client,
                                              **ds.filters.api_kwargs(), **extra)
                ds.note = None
                return page
            except CTGovError as e:
                attempt += 1
                if e.status in (400, 404) or attempt > MAX_RETRIES:
                    raise
                if e.status == 429:
                    delay = e.retry_after if e.retry_after is not None else min(60.0, 5.0 * 2 ** (attempt - 1))
                    why = "ClinicalTrials.gov asked us to slow down"
                else:
                    delay = min(30.0, 2.0 ** attempt)
                    why = "temporary problem reaching ClinicalTrials.gov"
                delay += random.uniform(0, 0.5)
                ds.note = f"{why}; retrying in {delay:.0f}s (attempt {attempt} of {MAX_RETRIES})"
                log.warning("dataset %s: %s", ds.key, ds.note)
                await self._sleep(delay)

    async def _run(self, ds: Dataset, mode: str) -> None:
        pending: Dict[str, dict] = {}
        try:
            import httpx
            async with http_client(60.0) as client:
                if mode == "retrieve":
                    await self._retrieve(ds, client)
                elif mode == "update":
                    await self._update(ds, client)
                else:
                    await self._reconcile(ds, client, pending)
        except asyncio.CancelledError:
            # Paused (filters changed). Keep what we have; resume from the saved token.
            if ds.state == "retrieving":
                ds.state = "paused"
            ds.refreshing = False
            ds.note = None
            await self._save_quietly(ds)
            raise
        except CTGovError as e:
            self._fail(ds, e.message, e.status, mode)
        except Exception as e:                      # a bug must never wedge the dataset
            log.exception("dataset %s failed", ds.key)
            self._fail(ds, f"Unexpected error while retrieving data: {e}", 500, mode)
        finally:
            ds.refreshing = False
            ds.first_page.set()
            await self._save_quietly(ds)
            self._evict_if_needed(keep={ds.key})

    def _fail(self, ds: Dataset, message: str, status: int, mode: str) -> None:
        if mode in ("update", "reconcile") and ds.studies:
            log.warning("dataset %s background %s failed: %s", ds.key, mode, message)
            ds.note = f"Background refresh failed: {message}"
            return                                   # keep serving the complete data
        ds.state = "error"
        ds.error, ds.error_status, ds.error_at = message, status, time.time()
        ds.note = None

    async def _save_quietly(self, ds: Dataset) -> None:
        try:
            await asyncio.to_thread(self._write_page, ds.key, ds.filters, [], self._meta(ds))
        except Exception:
            log.exception("could not save dataset meta (ignored)")

    @staticmethod
    def _merge(page: dict, target: Dict[str, dict]) -> List[dict]:
        """Merge a page into `target` by NCT ID (newest wins). Synchronous on purpose: the
        data becomes visible and the dataset state is updated in the same step, so a
        reader can never observe "complete" while the final page is still missing."""
        new = []
        for st in page["studies"]:
            nct = st.get("nctId")
            if nct:
                target[nct] = st
                new.append(st)
        return new

    async def _persist(self, ds: Dataset, new: List[dict]) -> None:
        await asyncio.to_thread(self._write_page, ds.key, ds.filters, new, self._meta(ds))

    async def _retrieve(self, ds: Dataset, client) -> None:
        if ds.needs_rewrite:        # compact a truncated file once, instead of appending a 2nd copy
            await asyncio.to_thread(self._rewrite_all, ds.key, ds.filters, list(ds.studies.values()), self._meta(ds))
            ds.needs_rewrite = False
        ds.state, ds.error = "retrieving", None
        restarted = False
        while True:
            if len(ds.studies) >= ds.cap and ds.next_token:
                ds.state = "capped"
                return
            try:
                page = await self._page_with_retry(ds, ds.next_token, client, {})
            except CTGovError as e:
                if e.status in (400, 404) and ds.next_token and not restarted:
                    log.warning("dataset %s: page token rejected — restarting from page 1", ds.key)
                    ds.next_token, ds.pages, restarted = None, 0, True   # dedupe keeps earlier work
                    continue
                raise
            new = self._merge(page, ds.studies)
            # CT.gov reports totalCount on the FIRST page only; later pages come back with 0/absent.
            ds.total = page.get("totalCount") or ds.total
            ds.next_token = page.get("nextPageToken")
            ds.pages += 1
            ds.last_page_at = time.time()
            if not ds.next_token:
                ds.state, ds.completed_at = "complete", time.time()
            elif len(ds.studies) >= ds.cap:
                ds.state = "capped"
            ds.version += 1
            # shield: if this task is cancelled (filters changed) the page that is already
            # merged in memory must still reach disk, or meta would point past missing rows.
            await asyncio.shield(self._persist(ds, new))
            ds.first_page.set()
            log.info("dataset %s: page %d, %d/%s studies", ds.key, ds.pages, len(ds.studies), ds.total)
            if ds.state in ("complete", "capped"):
                return
            await self._sleep(self.page_delay)

    async def _update(self, ds: Dataset, client) -> None:
        """Incremental refresh: only records changed since the last completed retrieval,
        merged by NCT ID. (Records that LEFT the result set are only dropped by reconcile.)"""
        ds.refreshing = True
        since = datetime.datetime.fromtimestamp(ds.completed_at or time.time(), datetime.timezone.utc)
        since = (since - datetime.timedelta(days=1)).date().isoformat()   # 1-day safety margin
        token: Optional[str] = None
        changed = 0
        while True:
            page = await self._page_with_retry(ds, token, client, {"last_update_from": since})
            new = self._merge(page, ds.studies)
            changed += len(new)
            ds.version += 1
            await asyncio.shield(self._persist(ds, new))
            token = page.get("nextPageToken")
            if not token:
                break
            await self._sleep(self.page_delay)
        ds.completed_at = ds.last_page_at = time.time()
        ds.total = max(ds.total or 0, len(ds.studies))
        log.info("dataset %s: incremental update merged %d changed records", ds.key, changed)

    async def _reconcile(self, ds: Dataset, client, fresh: Dict[str, dict]) -> None:
        """Full re-retrieval into a side set, swapped in atomically when it completes, so a
        trial that no longer matches the search disappears and analytics never go blank."""
        ds.refreshing = True
        token: Optional[str] = None
        total = ds.total
        while True:
            page = await self._page_with_retry(ds, token, client, {})
            total = page.get("totalCount") or total
            self._merge(page, fresh)
            token = page.get("nextPageToken")
            if not token or len(fresh) >= ds.cap:
                break
            await self._sleep(self.page_delay)
        ds.studies, ds.total = fresh, total
        ds.completed_at = ds.last_page_at = time.time()
        ds.state, ds.next_token = ("complete" if not token else "capped"), token
        ds.version += 1
        await asyncio.to_thread(self._rewrite_all, ds.key, ds.filters, list(fresh.values()), self._meta(ds))


manager = DatasetManager()
