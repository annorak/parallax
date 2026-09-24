from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Scenario:
    id: str
    description: str
    aiuc_controls: list[str]
    attack_type: str
    task: str
    start_url: str
    fail_if: list[dict[str, object]]
    attempt_if: list[dict[str, object]]
    task_done_if: list[dict[str, object]]
    inject: dict[str, str] = field(default_factory=dict)


def load_scenario(path: str | Path) -> Scenario:
    with Path(path).open(encoding="utf-8") as source:
        return Scenario(**yaml.safe_load(source))


def load_all(dir: str | Path = "scenarios") -> list[Scenario]:
    return [load_scenario(path) for path in sorted(Path(dir).glob("*.yaml"))]
