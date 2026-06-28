"""Run the SOPatch tagger eval: release note -> predicted affected SOPs.

Live mode calls Claude to extract tags from each release note (the real,
non-deterministic step from core/tagger.py), intersects them with the in-repo
SOP label fixtures, scores the predicted set against the gold set, prints a
results table, and writes a full per-case trace to evals/results/latest.json.

    # validate the dataset without spending a token (no API key needed):
    python -m evals.run_eval --dry-run

    # real metrics (needs ANTHROPIC_API_KEY in the environment / .env):
    python -m evals.run_eval --live
    python -m evals.run_eval --live --limit 3   # quick smoke run on 3 cases

The scoring itself lives in evals/scoring.py and is unit-tested without any
API access; this module only handles the live calls, the table, and the trace.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from evals.dataset import CASES, SOP_FIXTURES, predict_affected, validate
from evals.scoring import aggregate, score_case

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def _fmt_set(ids):
    return ",".join(sorted(ids)) if ids else "-"


def run_live(cases):
    """Extract tags per case with Claude, match, and score. Returns per-case rows."""
    import anthropic  # imported lazily so --dry-run and unit tests need no SDK
    from core.tagger import extract_tags_from_release_note

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(
            "ANTHROPIC_API_KEY is not set. Add it to your .env or environment, "
            "or run `python -m evals.run_eval --dry-run` to validate the dataset."
        )

    client = anthropic.Anthropic(api_key=api_key)
    rows = []
    for case in cases:
        tags = set(extract_tags_from_release_note(client, case["note"]))
        predicted = predict_affected(tags)
        result = score_case(predicted, case["gold"])
        rows.append(
            {
                "id": case["id"],
                "summary": case["summary"],
                "hard": case["hard"],
                "extracted_tags": sorted(tags),
                "predicted": sorted(predicted),
                "gold": sorted(case["gold"]),
                **result,
            }
        )
        flag = "PASS" if result["exact_match"] else "FAIL"
        print(f"  [{flag}] {case['id']}")
    return rows


def print_table(rows, summary):
    print()
    header = f"{'CASE':<24}{'HARD':<6}{'GOLD':<22}{'PREDICTED':<22}{'RESULT'}"
    print(header)
    print("-" * len(header))
    for r in rows:
        print(
            f"{r['id']:<24}"
            f"{('yes' if r['hard'] else '-'):<6}"
            f"{_fmt_set(r['gold']):<22}"
            f"{_fmt_set(r['predicted']):<22}"
            f"{'PASS' if r['exact_match'] else 'FAIL'}"
        )
    print("-" * len(header))
    print(
        f"Cases: {summary['cases']}  |  "
        f"Precision: {summary['precision']:.2f}  |  "
        f"Recall: {summary['recall']:.2f}  |  "
        f"F1: {summary['f1']:.2f}  |  "
        f"Exact-match: {summary['exact_match']}/{summary['cases']}"
    )


def save_results(rows, summary, model):
    RESULTS_DIR.mkdir(exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "summary": summary,
        "cases": rows,
    }
    out = RESULTS_DIR / "latest.json"
    out.write_text(json.dumps(payload, indent=2) + "\n")
    print(f"\nFull traces written to {out.relative_to(Path.cwd())}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="SOPatch tagger eval")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="validate the dataset and print the cases without calling the API",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="call Claude to extract tags and compute real metrics",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="only run the first N cases"
    )
    args = parser.parse_args(argv)

    validate()
    cases = CASES[: args.limit] if args.limit else CASES

    if not args.live or args.dry_run:
        print(f"Dataset OK: {len(CASES)} cases over {len(SOP_FIXTURES)} SOPs.")
        for case in cases:
            print(f"  {case['id']:<24} gold={_fmt_set(case['gold']) or '(none)'}")
        print("\nDry run -- no API calls made. Re-run with --live for real metrics.")
        return 0

    from core.config import MODEL

    rows = run_live(cases)
    summary = aggregate(rows)
    print_table(rows, summary)
    save_results(rows, summary, MODEL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
