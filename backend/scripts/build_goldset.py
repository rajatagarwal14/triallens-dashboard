#!/usr/bin/env python
"""
Build an UNLABELLED gold-set template for eligibility-extraction validation.

Fetches real trials from ClinicalTrials.gov and writes one JSONL row per trial
containing the eligibility text plus a `label` block of nulls for a human to
fill in. The labels must come from a clinician — a gold set written by the same
model you are evaluating measures self-consistency, not accuracy.

Usage:
    python scripts/build_goldset.py --condition "myelofibrosis" --n 40
    # then hand the file to a reviewer, who fills in every `label` field
    # finally: python scripts/validate_extraction.py
"""
from __future__ import annotations

import argparse
import asyncio
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services import ct_gov  # noqa: E402

GOLDSET = pathlib.Path(__file__).resolve().parent.parent / "goldset" / "goldset.jsonl"

# Mirrors ExtractedEligibility. null = "not yet labelled" and is skipped by the
# validator, so a partially-labelled file is still usable.
LABEL_TEMPLATE = {
    "line_of_therapy": None,        # treatment_naive|first_line|relapsed_refractory|later_line|unspecified
    "prior_therapy_required": None,  # true|false
    "refractory_to": None,           # list[str], [] if none
    "biomarker_selected": None,      # true|false
    "biomarkers_required": None,     # list[str], [] if none
    "disease_stage": None,           # str, "not_stated" if absent
    "stage_system": None,            # tnm|iss|dipss|ann_arbor|binet_rai|other|not_stated
}


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--out", type=pathlib.Path, default=GOLDSET)
    args = ap.parse_args()

    result = await ct_gov.search_studies(condition=args.condition, page_size=min(args.n * 3, 1000))
    studies = [s for s in result["studies"] if (s.get("eligibility") or {}).get("criteria")]
    if not studies:
        print(f"No trials with eligibility text for '{args.condition}'.", file=sys.stderr)
        return 1
    studies = studies[: args.n]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if args.out.exists():
        for line in args.out.read_text().splitlines():
            if line.strip():
                existing.add(json.loads(line)["nctId"])

    added = 0
    with args.out.open("a") as fh:
        for s in studies:
            if s["nctId"] in existing:
                continue
            fh.write(json.dumps({
                "nctId": s["nctId"],
                "condition_query": args.condition,
                "title": s.get("title", ""),
                "conditions": s.get("conditions") or [],
                "eligibility_criteria": (s.get("eligibility") or {}).get("criteria", ""),
                "label": dict(LABEL_TEMPLATE),
            }) + "\n")
            added += 1

    print(f"Wrote {added} unlabelled rows to {args.out} ({len(existing)} already present).")
    print("Next: have a clinical reviewer fill in every `label` field, then run")
    print("      python scripts/validate_extraction.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
