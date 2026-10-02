"""Full-retrieval behaviour (services/datasets.py), proven against a fake registry."""
import asyncio
import time

import pytest

from services import datasets
from services.ct_gov import CTGovError
from services.datasets import DatasetManager, Filters
from conftest import make_study


class FakeRegistry:
    """Serves `n` studies in pages of `page`, with scriptable failures."""

    def __init__(self, n=2500, page=1000, fail=None, dup_every=None):
        self.n, self.page, self.fail = n, page, dict(fail or {})
        self.calls = []                 # (token, kwargs)
        self.dup_every = dup_every

    async def __call__(self, *, page_size=1000, page_token=None, client=None, **filters):
        self.calls.append((page_token, filters))
        idx = len(self.calls)
        if idx in self.fail:
            raise self.fail[idx]
        start = int(page_token.split("-")[1]) if page_token else 0
        end = min(start + self.page, self.n)
        studies = [make_study(f"NCT{i:08d}") for i in range(start, end)]
        if self.dup_every and start:
            studies.append(make_study(f"NCT{0:08d}"))        # a duplicate of an earlier record
        nxt = f"tok-{end}" if end < self.n else None
        return {"studies": studies, "totalCount": self.n, "nextPageToken": nxt}


def mgr(tmp_path, reg, **kw):
    sleeps = []
    async def fake_sleep(s):
        sleeps.append(s)
        await asyncio.sleep(0)
    m = DatasetManager(fetch_page=reg, cache_dir=tmp_path, sleep=fake_sleep, page_delay=0, **kw)
    m._sleeps = sleeps
    return m


async def drain(m, f, timeout=5):
    """Wait until retrieval has finished AND its background task has fully wound down
    (including the final save to disk)."""
    end = time.time() + timeout
    while time.time() < end:
        st = m.status(f)
        ds = m._mem.get(f.key())
        busy = ds is not None and m._running(ds)
        if st["state"] not in ("retrieving", "new") and not busy:
            return st
        await asyncio.sleep(0.01)
    raise AssertionError(f"still retrieving: {m.status(f)}")


F = Filters(condition="melanoma")


def test_retrieves_every_page_and_marks_complete(tmp_path):
    async def go():
        reg = FakeRegistry(n=2500)
        m = mgr(tmp_path, reg)
        first = await m.snapshot(F)                       # returns once page 1 is in
        assert 0 < len(first.studies) <= 2500
        st = await drain(m, F)
        snap = await m.snapshot(F)
        assert st["state"] == "complete" and st["isComplete"] is True
        assert len(snap.studies) == 2500 and snap.coverage["total"] == 2500
        assert [c[0] for c in reg.calls] == [None, "tok-1000", "tok-2000"]   # token chain followed
    asyncio.run(go())


def test_partial_is_labelled_partial_until_last_page(tmp_path):
    async def go():
        reg = FakeRegistry(n=3000)
        m = mgr(tmp_path, reg)
        first = await m.snapshot(F)
        if first.state == "retrieving":
            assert first.coverage["isComplete"] is False
            assert first.coverage["analyzed"] < first.coverage["total"] or first.coverage["total"] == 3000
        await drain(m, F)
        assert m.status(F)["isComplete"] is True
    asyncio.run(go())


def test_duplicate_nct_ids_are_stored_once(tmp_path):
    async def go():
        m = mgr(tmp_path, FakeRegistry(n=2500, dup_every=1))
        await m.snapshot(F); await drain(m, F)
        snap = await m.snapshot(F)
        ids = [s["nctId"] for s in snap.studies]
        assert len(ids) == len(set(ids)) == 2500
    asyncio.run(go())


def test_rate_limit_waits_for_retry_after_then_continues(tmp_path):
    async def go():
        reg = FakeRegistry(n=2500, fail={2: CTGovError("slow down", status=429, retry_after=17)})
        m = mgr(tmp_path, reg)
        await m.snapshot(F); await drain(m, F)
        assert m.status(F)["state"] == "complete"
        assert any(17 <= s < 17.6 for s in m._sleeps), f"Retry-After not honoured: {m._sleeps}"
    asyncio.run(go())


def test_exhausted_retries_keep_partial_results_and_surface_the_error(tmp_path):
    async def go():
        always = {i: CTGovError("upstream down", status=503) for i in range(2, 30)}
        m = mgr(tmp_path, FakeRegistry(n=3000, fail=always))
        await m.snapshot(F)
        st = await drain(m, F)
        assert st["state"] == "error" and "upstream down" in st["error"]
        assert st["retrieved"] == 1000                     # page 1 retained, not thrown away
        snap = await m.snapshot(F)                         # still served (partial)
        assert len(snap.studies) == 1000 and snap.coverage["isComplete"] is False
    asyncio.run(go())


def test_error_before_any_data_raises_with_upstream_status(tmp_path):
    async def go():
        m = mgr(tmp_path, FakeRegistry(fail={i: CTGovError("bad", status=400) for i in range(1, 5)}))
        with pytest.raises(CTGovError) as e:
            await m.snapshot(F)
        assert e.value.status == 400
    asyncio.run(go())


def test_error_dataset_resumes_from_saved_token(tmp_path, monkeypatch):
    async def go():
        monkeypatch.setattr(datasets, "ERROR_RETRY_AFTER_S", 0)
        reg = FakeRegistry(n=3000, fail={i: CTGovError("down", status=503) for i in range(2, 9)})
        m = mgr(tmp_path, reg)
        await m.snapshot(F)
        st = await drain(m, F)
        assert st["state"] == "error" and st["retrieved"] == 1000
        reg.fail.clear()
        await m.snapshot(F)                                # next request resumes
        st = await drain(m, F)
        assert st["state"] == "complete" and st["retrieved"] == 3000
        assert "tok-1000" in [c[0] for c in reg.calls][-3:]   # resumed from the token, not page 1
    asyncio.run(go())


def test_changing_filters_pauses_old_retrieval_and_it_can_resume(tmp_path):
    async def go():
        slow = FakeRegistry(n=5000)
        orig = slow.__call__
        async def slow_fetch(**kw):
            await asyncio.sleep(0.05)
            return await orig(**kw)
        m = mgr(tmp_path, slow_fetch)
        a, b = Filters(condition="melanoma"), Filters(condition="lung cancer")
        await m.snapshot(a)
        await m.snapshot(b)                                # filters changed
        await asyncio.sleep(0.02)
        assert m.status(a)["state"] == "paused"            # cancelled, not lost
        kept = m.status(a)["retrieved"]
        assert kept >= 1000
        await drain(m, b)
        await m.snapshot(a)                                # back to the first search → resumes
        st = await drain(m, a, timeout=10)
        assert st["state"] == "complete" and st["retrieved"] == 5000 and st["retrieved"] >= kept
    asyncio.run(go())


def test_repeat_search_reuses_fresh_local_copy_without_network(tmp_path):
    async def go():
        reg = FakeRegistry(n=2500)
        m1 = mgr(tmp_path, reg)
        await m1.snapshot(F); await drain(m1, F)
        calls = len(reg.calls)
        m2 = mgr(tmp_path, reg)                            # "restart": new process, same disk cache
        snap = await m2.snapshot(F)
        assert len(snap.studies) == 2500 and snap.state == "complete"
        assert len(reg.calls) == calls                     # nothing downloaded again
    asyncio.run(go())


def test_equivalent_filters_share_one_dataset():
    assert Filters.from_query(condition=" Melanoma ", phases="PHASE2,PHASE3").key() == \
           Filters.from_query(condition="melanoma", phases="PHASE3,PHASE2").key()
    assert Filters.from_query(condition="melanoma").key() != Filters.from_query(condition="melanoma", country="India").key()


def test_safety_cap_stops_and_labels_then_can_be_lifted(tmp_path):
    async def go():
        reg = FakeRegistry(n=5000)
        m = mgr(tmp_path, reg, max_studies=2000)
        await m.snapshot(F)
        st = await drain(m, F)
        assert st["state"] == "capped" and st["capped"] and st["retrieved"] == 2000 and st["isComplete"] is False
        await m.lift_cap(F)
        st = await drain(m, F)
        assert st["state"] == "complete" and st["retrieved"] == 5000
    asyncio.run(go())


def test_zero_results_complete_immediately(tmp_path):
    async def go():
        m = mgr(tmp_path, FakeRegistry(n=0))
        snap = await m.snapshot(F)
        assert snap.studies == [] and (await drain(m, F))["state"] == "complete"
    asyncio.run(go())


def test_stale_dataset_is_refreshed_incrementally_and_merged_by_nct(tmp_path, monkeypatch):
    async def go():
        monkeypatch.setattr(datasets, "FRESH_HOURS", 0)
        reg = FakeRegistry(n=1500)
        m = mgr(tmp_path, reg)
        await m.snapshot(F); await drain(m, F)
        changed = {"updates": 0}
        orig = reg.__call__
        async def updating(*, page_size=1000, page_token=None, client=None, **filters):
            if filters.get("last_update_from"):
                changed["updates"] += 1
                return {"studies": [make_study("NCT00000007", status="COMPLETED"),
                                    make_study("NCT99999999")], "totalCount": 2, "nextPageToken": None}
            return await orig(page_size=page_size, page_token=page_token, client=client, **filters)
        m._fetch_page = updating
        m._mem[F.key()].completed_at = time.time() - 10        # make it stale
        await m.snapshot(F)                                    # triggers the incremental update
        await drain(m, F)
        snap = await m.snapshot(F)
        by = {s["nctId"]: s for s in snap.studies}
        assert changed["updates"] == 1
        assert by["NCT00000007"]["status"] == "COMPLETED"       # changed record replaced
        assert "NCT99999999" in by and len(by) == 1501           # new record added, nothing duplicated
    asyncio.run(go())


def test_compute_is_memoised_per_dataset_version(tmp_path):
    async def go():
        m = mgr(tmp_path, FakeRegistry(n=1200))
        await m.snapshot(F); await drain(m, F)
        snap = await m.snapshot(F)
        n = {"calls": 0}
        def fn(studies):
            n["calls"] += 1
            return {"count": len(studies)}
        a = await m.compute(snap, "x", (), fn)
        b = await m.compute(snap, "x", (), fn)
        assert a == b == {"count": 1200} and n["calls"] == 1
    asyncio.run(go())


def test_total_survives_pages_that_omit_total_count(tmp_path):
    """The real API sends totalCount on page 1 only; later pages must not reset it to 0."""
    async def go():
        class FirstPageOnly(FakeRegistry):
            async def __call__(self, **kw):
                out = await super().__call__(**kw)
                if kw.get("page_token"):
                    out["totalCount"] = 0
                return out
        m = mgr(tmp_path, FirstPageOnly(n=2500))
        await m.snapshot(F)
        st = await drain(m, F)
        assert st["total"] == 2500 and st["analyzed"] == 2500 and st["isComplete"]
    asyncio.run(go())


def test_task_cancelled_before_first_step_does_not_wedge_the_dataset(tmp_path):
    async def go():
        m = mgr(tmp_path, FakeRegistry(n=1500))
        ds = await m._aget(F)
        m._start(ds, "retrieve")
        ds.task.cancel()                       # cancelled before _run ever executed
        await asyncio.sleep(0)
        assert ds.state == "retrieving" and ds.task.cancelled()
        snap = await m.snapshot(F)             # must notice and resume
        st = await drain(m, F)
        assert st["state"] == "complete" and st["analyzed"] == 1500
    asyncio.run(go())
