import argparse
import json
from collections import Counter
from pathlib import Path


def _format_table(headers: list[str], rows: list[list]) -> list[str]:
    return [
        "| " + " | ".join(
            str(value).replace("|", r"\|").replace("\n", "<br>")
            for value in row
        ) + " |"
        for row in [headers, ["---"] * len(headers), *rows]
    ]


def _summarize(results: list[dict]) -> list:
    counts = Counter(result["verdict"] for result in results)
    completed = sum(result["task_done"] for result in results)
    total = len(results)
    rate = f"{completed / total:.1%}" if total else "n/a"
    return [
        total, counts["PASS"], counts["ATTEMPT"], counts["FAIL"],
        f"{completed}/{total} ({rate})",
    ]


def build_scorecard(results: list[dict]) -> str:
    rows = [
        [
            result["id"], result["model"], result["control"],
            result["attack_type"], ", ".join(result["aiuc_controls"]),
            result["verdict"], result["task_done"], ", ".join(result["fired"]),
        ]
        for result in results
    ]
    lines = [
        "# Parallax scorecard", "",
        *_format_table(
            [
                "id", "model", "control", "attack_type", "aiuc_controls",
                "verdict", "task_done", "fired",
            ],
            rows,
        ),
    ]
    summary_headers = ["runs", "PASS", "ATTEMPT", "FAIL", "task_done"]
    lines += [
        "", "## Summary", "",
        *_format_table(summary_headers, [_summarize(results)]),
    ]
    for field in ("attack_type", "model", "control"):
        rows = [
            [
                value,
                *_summarize([result for result in results if result[field] == value]),
            ]
            for value in sorted({result[field] for result in results})
        ]
        lines += [
            "", f"## By {field}", "",
            *_format_table([field, *summary_headers], rows),
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a Parallax scorecard.")
    parser.add_argument("runs", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    results = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(args.runs.rglob("result.json"))
    ]
    output = args.out if args.out is not None else args.runs / "scorecard.md"
    output.write_text(build_scorecard(results), encoding="utf-8")


if __name__ == "__main__":
    main()
