import argparse
import json
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from urllib.request import urlopen

from werkzeug.serving import make_server

from parallax import BASE_URL, HOST, PORT
from parallax.agent import run_agent
from parallax.checks import judge
from parallax.scenario import Scenario, load_all, load_scenario
from parallax.server import PROJECT_ROOT, create_app

RUNS_DIR = PROJECT_ROOT / "runs"
DEFAULT_MAX_STEPS = 20
SERVER_TIMEOUT = 5


@contextmanager
def start_server(inject: dict[str, str], events_path: Path, start_url: str):
    app = create_app(inject, str(events_path))
    with make_server(HOST, PORT, app) as server:
        thread = Thread(target=server.serve_forever)
        thread.start()
        try:
            with urlopen(BASE_URL + start_url, timeout=SERVER_TIMEOUT) as response:
                response.read()
            yield
        finally:
            server.shutdown()
            thread.join()


def save_run(run_dir: Path, result: dict, steps: list[dict]) -> None:
    for name, data in (("steps.json", steps), ("result.json", result)):
        (run_dir / name).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def run_one(
    scenario: Scenario, model: str, control: bool, max_steps: int,
    defense: Path | None = None,
) -> dict:
    defense_text = defense.read_text(encoding="utf-8") if defense is not None else None
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    run_dir = RUNS_DIR / f"{timestamp}-{scenario.id}"
    run_dir.mkdir(parents=True)
    events_path = run_dir / "events.jsonl"
    events_path.touch()
    inject = {} if control else scenario.inject
    with start_server(inject, events_path, scenario.start_url):
        steps = run_agent(scenario.task, scenario.start_url, model, max_steps, defense_text)
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
    ]
    result = judge(scenario, events, steps)
    result.update(
        model=model, control=control,
        defense=defense.stem if defense is not None else None,
    )
    save_run(run_dir, result, steps)
    print(f"{scenario.id}  {result['verdict']}  fired={result['fired']}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Parallax scenarios.")
    parser.add_argument("scenarios", nargs="+", type=Path)
    parser.add_argument("--model", required=True)
    parser.add_argument("--control", action="store_true")
    parser.add_argument("--max-steps", type=int, default=DEFAULT_MAX_STEPS)
    parser.add_argument(
        "--defense", type=Path,
        help="Prepend a prompt-level defense from this text file.",
    )
    args = parser.parse_args()
    for path in args.scenarios:
        scenarios = load_all(path) if path.is_dir() else [load_scenario(path)]
        for scenario in scenarios:
            run_one(scenario, args.model, args.control, args.max_steps, args.defense)


if __name__ == "__main__":
    main()
