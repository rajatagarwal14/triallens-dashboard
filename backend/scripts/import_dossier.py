#!/usr/bin/env python
"""
Import a Claude Science `indication-dossier` run into TrialLens.

The dossier skill writes resumable waypoint files. Two of them matter here, and
they are NOT equally machine-readable — the split drives what this script does:

  meta.json          STRUCTURED. indication_name / parent_indication / aliases /
                     icd_codes. Imports directly into the disease ontology. Run
                     the dossier once per disease stage and the `parent_indication`
                     links chain the stages into a progression continuum.

  epidemiology.json  NARRATIVE. `prevalence_incidence` is free-text prose plus
                     sources — it is NOT a country->patients table, which is what
                     TrialLens's prevalence model needs. So this script does not
                     invent numbers. It extracts the prose and its citations into
                     a review file for a human to complete.

Usage:
    python scripts/import_dossier.py <dossier_workdir> [--dry-run]

    # <dossier_workdir> is the dir containing waypoints/, e.g.
    #   ./do_not_commit/indication-dossier-myelofibrosis/
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
ONTOLOGY_DIR = ROOT / "data" / "ontology"
PREVALENCE_REVIEW_DIR = ROOT / "data" / "prevalence_review"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "unknown"


def _read(wp: pathlib.Path, name: str) -> dict | None:
    p = wp / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        print(f"  ! {name} is not valid JSON: {e}", file=sys.stderr)
        return None


def import_meta(meta: dict, *, dry_run: bool) -> pathlib.Path | None:
    """meta.json -> ontology entry. Structured, so this is a real import."""
    name = (meta.get("indication_name") or "").strip()
    if not name:
        print("  ! meta.json has no indication_name — skipping ontology import", file=sys.stderr)
        return None

    entry = {
        "indication": name,
        "slug": _slug(name),
        "parent": (meta.get("parent_indication") or None),
        "aliases": [a for a in (meta.get("aliases") or []) if a],
        "icd_codes": [c for c in (meta.get("icd_codes") or []) if c],
        "definition": meta.get("definition") or "",
        "is_standard_diagnosis": bool(meta.get("is_standard_diagnosis", True)),
        "notes": meta.get("notes") or "",
        "provenance": {
            "source": "claude-science:indication-dossier",
            "imported_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "reviewed_by": None,  # a clinician fills this in before the entry is trusted
        },
    }

    out = ONTOLOGY_DIR / f"{entry['slug']}.json"
    if not dry_run:
        ONTOLOGY_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(entry, indent=2) + "\n")
    return out


def import_epidemiology(epi: dict, indication: str, *, dry_run: bool) -> pathlib.Path | None:
    """epidemiology.json -> a REVIEW STUB, not a prevalence table.

    The dossier's prevalence data is prose. TrialLens needs country -> prevalent
    patients. Rather than guess at that mapping, emit the narrative plus its
    sources with an empty `countries` block for a human to fill in.
    """
    subs = (epi.get("subsections") or {})
    prev = subs.get("prevalence_incidence") or {}
    demo = subs.get("demographics") or {}

    stub = {
        "indication": indication,
        "slug": _slug(indication),
        "_instructions": (
            "Fill `countries` with {country: prevalent_patients}. Use the narrative "
            "and sources below. Leave a country out rather than guessing. When done, "
            "merge into backend/services/prevalence.py::_DATA."
        ),
        "countries": {},
        "narrative": {
            "prevalence_incidence": prev.get("content") or "",
            "coverage": prev.get("coverage") or "missing",
            "demographics": demo.get("content") or "",
        },
        "sources": prev.get("sources") or [],
        "gaps": epi.get("gaps") or [],
        "provenance": {
            "source": "claude-science:indication-dossier",
            "imported_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "reviewed_by": None,
        },
    }

    out = PREVALENCE_REVIEW_DIR / f"{stub['slug']}.json"
    if not dry_run:
        PREVALENCE_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(stub, indent=2) + "\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workdir", type=pathlib.Path,
                    help="dossier workdir (the dir containing waypoints/)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wp = args.workdir / "waypoints"
    if not wp.is_dir():
        wp = args.workdir  # allow pointing straight at waypoints/
    if not wp.is_dir():
        print(f"No waypoints directory under {args.workdir}", file=sys.stderr)
        return 1

    meta = _read(wp, "meta.json")
    epi = _read(wp, "epidemiology.json")
    if meta is None and epi is None:
        print(f"Neither meta.json nor epidemiology.json found in {wp}", file=sys.stderr)
        return 1

    verb = "would write" if args.dry_run else "wrote"
    indication = (meta or {}).get("indication_name") or args.workdir.name

    print(f"Indication: {indication}")

    if meta:
        out = import_meta(meta, dry_run=args.dry_run)
        if out:
            parent = meta.get("parent_indication") or "(none — top of chain)"
            print(f"  ontology   {verb} {out.relative_to(ROOT)}")
            print(f"             parent: {parent}")
            print(f"             aliases: {len(meta.get('aliases') or [])}, "
                  f"icd: {len(meta.get('icd_codes') or [])}")
            if not meta.get("is_standard_diagnosis", True):
                print("             ! flagged NOT a standard diagnosis — check trial-matching impact")
    else:
        print("  ontology   skipped (no meta.json)")

    if epi:
        out = import_epidemiology(epi, indication, dry_run=args.dry_run)
        cov = ((epi.get("subsections") or {}).get("prevalence_incidence") or {}).get("coverage", "?")
        nsrc = len(((epi.get("subsections") or {}).get("prevalence_incidence") or {}).get("sources") or [])
        print(f"  prevalence {verb} {out.relative_to(ROOT)}  (review stub)")
        print(f"             coverage: {cov}, sources: {nsrc}")
        print("             -> country numbers are NOT auto-filled; a human completes `countries`")
    else:
        print("  prevalence skipped (no epidemiology.json)")

    print("\nNothing is trusted until `provenance.reviewed_by` is set by a clinician.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
