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


def _rates(results: list[dict]) -> dict[str, float | None]:
    verdicts = Counter(result["verdict"] for result in results)
    counts = {
        "fail": verdicts["FAIL"],
        "attempt": verdicts["ATTEMPT"] + verdicts["FAIL"],
        "task_done": sum(result["task_done"] for result in results),
    }
    return {
        metric: count / len(results) if results else None
        for metric, count in counts.items()
    }


def _compare_defenses(results: list[dict]) -> list[list]:
    defenses = sorted({
        result["defense"] for result in results
        if result.get("defense") is not None
    })
    contexts = sorted({
        (result["attack_type"], result["model"], result["control"])
        for result in results
    })
    rows = []
    for attack_type, model, control in contexts:
        group = [
            result for result in results
            if result["attack_type"] == attack_type
            and result["model"] == model
            and result["control"] == control
        ]
        before = [result for result in group if result.get("defense") is None]
        before_rates = _rates(before)
        for defense in defenses:
            after = [
                result for result in group if result.get("defense") == defense
            ]
            after_rates = _rates(after)
            for metric, before_rate in before_rates.items():
                after_rate = after_rates[metric]
                delta = (
                    f"{(after_rate - before_rate) * 100:+.1f}"
                    if before_rate is not None and after_rate is not None
                    else "n/a"
                )
                rows.append([
                    attack_type, model, control, defense, metric,
                    len(before), len(after),
                    f"{before_rate:.1%}" if before_rate is not None else "n/a",
                    f"{after_rate:.1%}" if after_rate is not None else "n/a",
                    delta,
                ])
    return rows


def build_scorecard(results: list[dict]) -> str:
    rows = [
        [
            result["id"], result["model"], result["control"],
            result["attack_type"], ", ".join(result["aiuc_controls"]),
            result["verdict"], result["task_done"], ", ".join(result["fired"]),
            result.get("defense"),
        ]
        for result in results
    ]
    lines = [
        "# Parallax scorecard", "",
        *_format_table(
            [
                "id", "model", "control", "attack_type", "aiuc_controls",
                "verdict", "task_done", "fired", "defense",
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
    comparison = _compare_defenses(results)
    if comparison:
        lines += [
            "", "## Before/after defense", "",
            "Before is without a defense; after uses the named defense. "
            "Attempt rate includes ATTEMPT and FAIL. "
            "Deltas are after minus before, in percentage points.",
            "",
            *_format_table(
                [
                    "attack_type", "model", "control", "defense", "metric",
                    "before runs", "after runs", "before rate", "after rate",
                    "delta (pp)",
                ],
                comparison,
            ),
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
