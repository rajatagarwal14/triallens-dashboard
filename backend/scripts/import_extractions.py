#!/usr/bin/env python
"""
Import eligibility extractions produced in Claude Science into the TrialLens cache.

This is the handoff point. Claude Science does the extraction (on your own plan,
on your own machine); this script validates the output against the canonical
schema and writes it into the per-NCT cache that the cohort engine reads. After
import, TrialLens uses the structured fields with **no API key and no network
call** — it is reading local files.

Accepts either JSONL (one object per line) or a JSON array. Each record:

    {
      "nctId": "NCT01234567",
      "prompt_version": "v1",              # optional; warns on mismatch
      "extraction": { ...ExtractedEligibility fields... }
    }

A flat record (extraction fields at the top level alongside "nctId") also works.

Usage:
    python scripts/import_extractions.py extractions.jsonl
    python scripts/import_extractions.py extractions.jsonl --dry-run
    python scripts/import_extractions.py extractions.jsonl --overwrite
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services import claude_extract as cx  # noqa: E402


def _load(path: pathlib.Path) -> list[dict]:
    text = path.read_text().strip()
    if not text:
        return []
    if text.lstrip().startswith("["):
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("top-level JSON must be an array of records")
        return data
    rows = []
    for i, line in enumerate(text.splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                raise ValueError(f"line {i} is not valid JSON: {e}") from e
    return rows


def _split(rec: dict) -> tuple[str, dict, str | None]:
    """Return (nct_id, extraction_payload, declared_prompt_version)."""
    nct = rec.get("nctId") or rec.get("nct_id") or rec.get("custom_id") or ""
    ver = rec.get("prompt_version")
    payload = rec.get("extraction") or rec.get("fields")
    if payload is None:
        # flat form: everything except the envelope keys is the extraction
        payload = {k: v for k, v in rec.items()
                   if k not in {"nctId", "nct_id", "custom_id", "prompt_version"}}
    return nct, payload, ver


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=pathlib.Path, help="JSONL or JSON array from Claude Science")
    ap.add_argument("--dry-run", action="store_true", help="validate only; write nothing")
    ap.add_argument("--overwrite", action="store_true", help="replace already-cached trials")
    args = ap.parse_args()

    if not args.path.exists():
        print(f"No such file: {args.path}", file=sys.stderr)
        return 1

    try:
        records = _load(args.path)
    except ValueError as e:
        print(f"Could not parse {args.path}: {e}", file=sys.stderr)
        return 1
    if not records:
        print(f"{args.path} is empty.", file=sys.stderr)
        return 1

    imported = skipped = rejected = 0
    version_warned = False
    errors: list[str] = []

    for rec in records:
        nct, payload, declared = _split(rec)

        if not nct.upper().startswith("NCT"):
            rejected += 1
            errors.append(f"{nct or '<missing nctId>'}: not a valid NCT id")
            continue

        if declared and declared != cx.PROMPT_VERSION and not version_warned:
            print(f"  ! prompt_version mismatch: file says '{declared}', "
                  f"this build expects '{cx.PROMPT_VERSION}'. Importing anyway, but the\n"
                  f"    fields may not match the current schema — re-extract if results look off.")
            version_warned = True

        if not args.overwrite and cx.cached(nct) is not None:
            skipped += 1
            continue

        try:
            value = cx.ExtractedEligibility(**payload)
        except Exception as e:
            rejected += 1
            # keep the message short — pydantic errors are verbose
            errors.append(f"{nct}: {str(e).splitlines()[0]}")
            continue

        if not args.dry_run:
            cx._store(nct, value)
        imported += 1

    verb = "would import" if args.dry_run else "imported"
    print(f"\n{verb}: {imported}   already cached (skipped): {skipped}   rejected: {rejected}")
    if errors:
        print("\nRejected records:")
        for e in errors[:20]:
            print(f"  - {e}")
        if len(errors) > 20:
            print(f"  … and {len(errors) - 20} more")

    if not args.dry_run and imported:
        print(f"\nCache: {cx._CACHE_ROOT / cx.PROMPT_VERSION}")
        print("TrialLens will now read these structured fields with no API key and no network call.")

    return 0 if imported or skipped else 1


if __name__ == "__main__":
    raise SystemExit(main())
