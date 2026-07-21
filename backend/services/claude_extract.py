"""
Claude-powered eligibility extraction (v2, OPTIONAL enrichment tier).

Turns free-text ClinicalTrials.gov eligibility criteria into structured,
mCODE-aligned cohort fields (line of therapy, refractoriness, biomarker
selection, disease stage) that the cohort engine can group on.

Design rules — these are load-bearing, not stylistic:

  1. OPT-IN. With no ANTHROPIC_API_KEY the whole module is inert: `enabled()`
     returns False and every caller falls back to the v1 rule-based path. The
     product's "no AI key required" guarantee is preserved exactly.
  2. NEVER AUTHORITATIVE. Extracted values carry a confidence score and the
     verbatim evidence snippet that produced them. Precedence is
     measured > curated > extracted > modeled — callers must not let an
     extracted value overwrite a measured or curated one.
  3. CACHED PER TRIAL. A trial's eligibility text is immutable in practice, so
     extraction is a one-time cost per (NCT id, prompt version). Results are
     memoised to disk; re-running a search costs nothing.
  4. REPRODUCIBLE. PROMPT_VERSION is part of the cache key, so changing the
     prompt or schema invalidates old results instead of silently mixing them.

Cost shape at 1000 studies/search: the instruction+ontology prefix is shared
across every trial, so it is marked for prompt caching (~0.1x on reads); bulk
runs go through the Batch API (50% off). See `extract_batch`.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Iterable, Literal, Optional

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

MODEL = "claude-opus-4-8"
# Bump whenever INSTRUCTIONS or the schema changes — it is part of the cache key.
PROMPT_VERSION = "v1"

_CACHE_ROOT = pathlib.Path(__file__).resolve().parent.parent / ".cache" / "extract"


# ── Output schema (mCODE-aligned) ────────────────────────────────────────────
class Evidence(BaseModel):
    """Which verbatim phrase justified a given field. Enables human review."""
    field: str = Field(description="Name of the field this snippet supports.")
    snippet: str = Field(description="Verbatim phrase copied from the criteria.")


class ExtractedEligibility(BaseModel):
    line_of_therapy: Literal[
        "treatment_naive", "first_line", "relapsed_refractory", "later_line", "unspecified"
    ] = Field(description="Treatment line the trial recruits. 'unspecified' if not stated.")
    prior_therapy_required: bool = Field(
        description="True only if prior systemic therapy is an explicit inclusion requirement."
    )
    refractory_to: list[str] = Field(
        description="Drugs or drug classes the patient must be refractory/resistant to. Empty if none."
    )
    biomarker_selected: bool = Field(
        description="True if eligibility gates on a molecular marker, mutation, or expression level."
    )
    biomarkers_required: list[str] = Field(
        description="Required markers as written, e.g. 'JAK2 V617F', 'EGFR exon 19del'. Empty if all-comers."
    )
    disease_stage: str = Field(
        description="Disease stage/phase as stated, e.g. 'metastatic', 'blast phase', 'chronic phase'. "
                    "Use 'not_stated' if absent."
    )
    stage_system: Literal[
        "tnm", "iss", "dipss", "ann_arbor", "binet_rai", "other", "not_stated"
    ] = Field(description="Which staging system the criteria reference, if any.")
    confidence: float = Field(
        description="0.0-1.0 self-assessed confidence that these fields reflect the criteria."
    )
    evidence: list[Evidence] = Field(
        description="One entry per non-default field, quoting the phrase that justified it."
    )


# ── Shared, cacheable instruction prefix ─────────────────────────────────────
# This block is identical for every trial, so it is the prompt-cache prefix.
# NOTE: Opus 4.8 has a 4096-token minimum cacheable prefix — a shorter prefix
# silently will not cache. `last_usage()` reports cache_read_input_tokens so you
# can verify hits rather than assume them.
INSTRUCTIONS = """\
You extract structured cohort fields from clinical trial eligibility criteria.
Your output feeds a clinical-planning tool used for feasibility analysis, so
precision matters far more than completeness.

Rules:
- Extract ONLY what the criteria state. Never infer from the disease name, the
  trial title, or typical practice. If the criteria are silent on a field, use
  its "unspecified" / "not_stated" / empty-list / false default.
- Quote evidence verbatim from the criteria. Do not paraphrase in `snippet`.
- `line_of_therapy`: "relapsed_refractory" requires explicit relapsed/refractory
  or prior-progression language. "treatment_naive" requires explicit untreated /
  treatment-naive / newly-diagnosed language. Prior therapy merely being
  *permitted* is NOT "relapsed_refractory" — that is "unspecified".
- `refractory_to`: list only agents/classes the patient must have failed. An
  agent listed as prohibited concomitant medication is NOT refractoriness.
- `biomarker_selected`: true only when a marker gates enrollment. A marker
  measured as a baseline lab, stratification factor, or exploratory endpoint
  does NOT count as selection.
- `disease_stage`: copy the stage/phase term the criteria use. Do not translate
  between staging systems.
- `confidence`: reflect genuine uncertainty. Vague, templated, or internally
  contradictory criteria should score low. Do not default to a high value.

Set confidence below 0.5 whenever you are guessing; a low-confidence answer is
useful, a confidently wrong one is not.
"""


# ── Feature flag ─────────────────────────────────────────────────────────────
def enabled() -> bool:
    """True only when an API key is configured. Everything degrades to v1 otherwise."""
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _client():
    import anthropic  # imported lazily so the app runs without the dep installed
    return anthropic.Anthropic()


# ── Disk cache, keyed by (prompt version, NCT id) ────────────────────────────
def _cache_path(nct_id: str) -> pathlib.Path:
    return _CACHE_ROOT / PROMPT_VERSION / f"{nct_id}.json"


def cached(nct_id: str) -> Optional[ExtractedEligibility]:
    p = _cache_path(nct_id)
    if not p.exists():
        return None
    try:
        return ExtractedEligibility(**json.loads(p.read_text()))
    except Exception:
        log.warning("discarding unreadable extract cache for %s", nct_id)
        return None


def _store(nct_id: str, value: ExtractedEligibility) -> None:
    p = _cache_path(nct_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(value.model_dump_json())


_last_usage: dict[str, Any] = {}


def last_usage() -> dict:
    """Usage from the most recent live call — inspect cache_read_input_tokens
    to confirm the shared prefix is actually caching."""
    return dict(_last_usage)


def _system_blocks() -> list[dict]:
    # cache_control on the last (only) block caches the whole instruction prefix.
    return [{"type": "text", "text": INSTRUCTIONS, "cache_control": {"type": "ephemeral"}}]


def _user_text(study: dict) -> str:
    elig = (study.get("eligibility") or {}).get("criteria", "") or ""
    conds = ", ".join(study.get("conditions") or []) or "not stated"
    return (
        f"Conditions: {conds}\n"
        f"Title: {study.get('title', '')}\n\n"
        f"ELIGIBILITY CRITERIA:\n{elig.strip() or '(none provided)'}"
    )


# ── Single-trial extraction ──────────────────────────────────────────────────
def extract(study: dict, *, use_cache: bool = True) -> Optional[ExtractedEligibility]:
    """Extract one trial. Returns None when disabled or when there is no
    criteria text to read — callers fall back to the rule-based path."""
    nct = study.get("nctId") or ""
    if not enabled() or not nct:
        return None
    if use_cache and (hit := cached(nct)):
        return hit
    if not (study.get("eligibility") or {}).get("criteria"):
        return None

    try:
        resp = _client().messages.parse(
            model=MODEL,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=_system_blocks(),
            messages=[{"role": "user", "content": _user_text(study)}],
            output_format=ExtractedEligibility,
        )
    except Exception as e:  # never let enrichment break the request path
        log.warning("extraction failed for %s: %s", nct, e)
        return None

    global _last_usage
    _last_usage = resp.usage.model_dump() if hasattr(resp.usage, "model_dump") else {}
    result = resp.parsed_output
    if result is not None:
        _store(nct, result)
    return result


# ── Bulk extraction via the Batch API (50% cheaper) ──────────────────────────
def _json_schema() -> dict:
    """Structured-outputs-compliant schema: every object needs
    additionalProperties:false, and unsupported constraint keywords are stripped."""
    schema = ExtractedEligibility.model_json_schema()
    unsupported = {
        "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
        "minLength", "maxLength", "pattern", "minItems", "maxItems", "uniqueItems",
    }

    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            node = {k: walk(v) for k, v in node.items() if k not in unsupported}
            if node.get("type") == "object" and "additionalProperties" not in node:
                node["additionalProperties"] = False
            return node
        if isinstance(node, list):
            return [walk(v) for v in node]
        return node

    return walk(schema)


def submit_batch(studies: Iterable[dict]) -> Optional[str]:
    """Queue uncached trials for extraction. Returns a batch id, or None if
    disabled / nothing to do. Poll with `collect_batch`."""
    if not enabled():
        return None
    pending = [
        s for s in studies
        if s.get("nctId")
        and (s.get("eligibility") or {}).get("criteria")
        and cached(s["nctId"]) is None
    ]
    if not pending:
        return None

    schema = _json_schema()
    requests = [
        {
            "custom_id": s["nctId"],
            "params": {
                "model": MODEL,
                "max_tokens": 4096,
                "thinking": {"type": "adaptive"},
                "system": _system_blocks(),
                "messages": [{"role": "user", "content": _user_text(s)}],
                "output_config": {"format": {"type": "json_schema", "schema": schema}},
            },
        }
        for s in pending
    ]
    batch = _client().messages.batches.create(requests=requests)
    log.info("submitted extraction batch %s (%d trials)", batch.id, len(requests))
    return batch.id


def collect_batch(batch_id: str) -> dict[str, int]:
    """Fetch a finished batch and write results into the per-NCT cache.
    Returns counts; `pending` > 0 means the batch has not ended yet."""
    if not enabled():
        return {"stored": 0, "failed": 0, "pending": 0}
    client = _client()
    batch = client.messages.batches.retrieve(batch_id)
    if batch.processing_status != "ended":
        return {"stored": 0, "failed": 0, "pending": 1}

    stored = failed = 0
    for res in client.messages.batches.results(batch_id):
        if res.result.type != "succeeded":
            failed += 1
            continue
        try:
            text = next(b.text for b in res.result.message.content if b.type == "text")
            _store(res.custom_id, ExtractedEligibility(**json.loads(text)))
            stored += 1
        except Exception as e:
            log.warning("could not store batch result %s: %s", res.custom_id, e)
            failed += 1
    return {"stored": stored, "failed": failed, "pending": 0}
