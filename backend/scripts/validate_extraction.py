#!/usr/bin/env python
"""
Measure eligibility-extraction accuracy against a human-labelled gold set.

Run this BEFORE trusting extracted fields for planning decisions. It reports
per-field accuracy, set-valued precision/recall, and — importantly — whether
the model's self-reported confidence is calibrated, i.e. whether low-confidence
answers really are the wrong ones. An extractor that is confidently wrong is
worse than no extractor.

Usage:
    export ANTHROPIC_API_KEY=...
    python scripts/validate_extraction.py [--goldset PATH] [--limit N]

Exit codes: 0 = report produced, 1 = unusable (no key / no labels).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services import claude_extract as cx  # noqa: E402

GOLDSET = pathlib.Path(__file__).resolve().parent.parent / "goldset" / "goldset.jsonl"

SCALAR_FIELDS = [
    "line_of_therapy", "prior_therapy_required",
    "biomarker_selected", "disease_stage", "stage_system",
]
SET_FIELDS = ["refractory_to", "biomarkers_required"]


def _norm_set(v) -> set[str]:
    return {str(x).strip().lower() for x in (v or []) if str(x).strip()}


def _norm_scalar(v):
    return str(v).strip().lower() if isinstance(v, str) else v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--goldset", type=pathlib.Path, default=GOLDSET)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not cx.enabled():
        print("ANTHROPIC_API_KEY is not set — extraction is disabled, nothing to validate.",
              file=sys.stderr)
        return 1
    if not args.goldset.exists():
        print(f"No gold set at {args.goldset}. Build one first:\n"
              f"  python scripts/build_goldset.py --condition '<indication>' --n 40",
              file=sys.stderr)
        return 1

    rows = [json.loads(l) for l in args.goldset.read_text().splitlines() if l.strip()]
    # Only rows a human actually labelled (at least one non-null label field).
    labelled = [r for r in rows if any(v is not None for v in (r.get("label") or {}).values())]
    if not labelled:
        print(f"{len(rows)} rows found but none are labelled yet — fill in the `label` "
              f"blocks in {args.goldset} first.", file=sys.stderr)
        return 1
    if args.limit:
        labelled = labelled[: args.limit]

    print(f"Validating against {len(labelled)} labelled trials "
          f"(of {len(rows)} in the gold set)\n")

    scalar_hits = {f: [0, 0] for f in SCALAR_FIELDS}   # [correct, scored]
    set_stats = {f: [0, 0, 0] for f in SET_FIELDS}     # [tp, predicted, actual]
    calib: list[tuple[float, bool]] = []               # (confidence, all-fields-correct)
    skipped = 0

    for r in labelled:
        study = {
            "nctId": r["nctId"],
            "title": r.get("title", ""),
            "conditions": r.get("conditions") or [],
            "eligibility": {"criteria": r.get("eligibility_criteria", "")},
        }
        pred = cx.extract(study)
        if pred is None:
            skipped += 1
            continue

        label = r["label"]
        row_correct = True

        for f in SCALAR_FIELDS:
            truth = label.get(f)
            if truth is None:
                continue  # unlabelled field — not scored
            scalar_hits[f][1] += 1
            if _norm_scalar(getattr(pred, f)) == _norm_scalar(truth):
                scalar_hits[f][0] += 1
            else:
                row_correct = False

        for f in SET_FIELDS:
            truth = label.get(f)
            if truth is None:
                continue
            t, p = _norm_set(truth), _norm_set(getattr(pred, f))
            set_stats[f][0] += len(t & p)
            set_stats[f][1] += len(p)
            set_stats[f][2] += len(t)
            if t != p:
                row_correct = False

        calib.append((float(pred.confidence), row_correct))

    if not calib:
        print("No trials could be extracted (all skipped). Check the API key and logs.",
              file=sys.stderr)
        return 1

    print("Per-field accuracy")
    print("-" * 52)
    for f in SCALAR_FIELDS:
        correct, scored = scalar_hits[f]
        if scored:
            print(f"  {f:<24} {correct/scored:6.1%}   ({correct}/{scored})")
        else:
            print(f"  {f:<24}      —   (unlabelled)")

    print("\nSet-valued fields (precision / recall / F1)")
    print("-" * 52)
    for f in SET_FIELDS:
        tp, npred, nact = set_stats[f]
        if not (npred or nact):
            print(f"  {f:<24}      —   (unlabelled or all empty)")
            continue
        prec = tp / npred if npred else 1.0
        rec = tp / nact if nact else 1.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        print(f"  {f:<24} {prec:6.1%} / {rec:6.1%} / {f1:6.1%}")

    exact = sum(1 for _, ok in calib if ok)
    print(f"\nWhole-row exact match: {exact/len(calib):.1%} ({exact}/{len(calib)})")
    if skipped:
        print(f"Skipped (no extraction returned): {skipped}")

    # Calibration: confidence is only useful if high-confidence rows are righter
    # than low-confidence ones. If these two numbers are close, the score is noise.
    hi = [ok for c, ok in calib if c >= 0.7]
    lo = [ok for c, ok in calib if c < 0.7]
    print("\nConfidence calibration")
    print("-" * 52)
    print(f"  confidence >= 0.7:  {sum(hi)/len(hi):6.1%} correct   (n={len(hi)})"
          if hi else "  confidence >= 0.7:      —   (n=0)")
    print(f"  confidence <  0.7:  {sum(lo)/len(lo):6.1%} correct   (n={len(lo)})"
          if lo else "  confidence <  0.7:      —   (n=0)")
    if hi and lo and (sum(hi)/len(hi) - sum(lo)/len(lo)) < 0.10:
        print("  ⚠  High- and low-confidence rows score alike — treat `confidence`"
              "\n     as uninformative and gate on human review instead.")

    print("\nInterpret before adopting: a field is safe to group cohorts on only if "
          "\nits accuracy clears the bar your planning decisions require.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
