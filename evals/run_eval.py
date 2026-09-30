from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from skill_gate.classifier import classify


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the binary classifier.")
    parser.add_argument("--dataset", default="evals/coding_non_coding.jsonl")
    parser.add_argument("--cwd", default=".")
    args = parser.parse_args()

    rows = [
        json.loads(line)
        for line in Path(args.dataset).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    results: list[tuple[str, str, str]] = []
    for row in rows:
        expected = str(row["mode"])
        actual = classify(str(row["text"]), cwd=Path(args.cwd)).mode
        results.append((expected, actual, str(row["text"])))

    correct = sum(expected == actual for expected, actual, _ in results)
    coding_total = sum(expected == "coding" for expected, _, _ in results)
    non_coding_total = sum(expected == "non_coding" for expected, _, _ in results)
    coding_tp = sum(expected == actual == "coding" for expected, actual, _ in results)
    non_coding_tp = sum(expected == actual == "non_coding" for expected, actual, _ in results)
    coding_recall = coding_tp / coding_total if coding_total else 0.0
    non_coding_recall = non_coding_tp / non_coding_total if non_coding_total else 0.0
    accuracy = correct / len(results) if results else 0.0

    print(f"examples: {len(results)}")
    print(f"accuracy: {accuracy:.3f}")
    print(f"coding recall: {coding_recall:.3f}")
    print(f"non-coding recall: {non_coding_recall:.3f}")
    for expected, actual, text in results:
        if expected != actual:
            print(f"MISS expected={expected} actual={actual}: {text}")

    return 0 if coding_recall >= 0.95 and non_coding_recall >= 0.90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
