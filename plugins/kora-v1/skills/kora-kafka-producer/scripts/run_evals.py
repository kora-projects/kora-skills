#!/usr/bin/env python3
"""
Kora Kafka Producer Evals Runner

Loads evals/evals.json (Anthropic rubric format) and prints each eval's query
and expected_behavior checklist for manual or LLM-judge review.

Usage:
    python run_evals.py [--verbose]
"""

import json
import sys
from pathlib import Path


def load_evals() -> dict:
    """Load evals from ../evals/evals.json relative to this script."""
    evals_path = Path(__file__).resolve().parent.parent / "evals" / "evals.json"
    with open(evals_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Show kora-kafka-producer evals")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    print("=== Kora Kafka Producer Evals ===\n")

    data = load_evals()
    evals = data.get("evals", [])

    for ev in evals:
        print(f"[{ev['id']}] tags={', '.join(ev.get('tags', []))}")
        print(f"  query: {ev['query']}")
        if args.verbose:
            print("  expected_behavior:")
            for item in ev.get("expected_behavior", []):
                print(f"    - {item}")
        print()

    print("=" * 50)
    print(f"Total evals: {len(evals)}")
    print("These evals are a rubric: judge a skill response against each")
    print("expected_behavior item (use --verbose to list them).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
