import json
from datetime import UTC, datetime
from pathlib import Path

from flask import Flask, abort, request, send_file

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "scenario-assets"
TRAPS_DIR = PROJECT_ROOT / "traps"


def _resolve_file(directory: Path, name: str) -> Path:
    path = (directory / name).resolve()
    if ".." in Path(name).parts or not path.is_relative_to(directory) or not path.is_file():
        abort(404)
    return path


def _fill_injection_slot(page: Path, trap_name: str | None) -> str:
    snippet = ""
    if trap_name is not None:
        snippet = _resolve_file(TRAPS_DIR, trap_name).read_text(encoding="utf-8")
    return page.read_text(encoding="utf-8").replace("{{ INJECTION_SLOT }}", snippet)


def create_app(inject: dict[str, str], events_path: str) -> Flask:
    app = Flask(__name__, static_folder=None)
    app.config.update(INJECT=inject, EVENTS_PATH=Path(events_path))
    app.config["EVENTS_PATH"].parent.mkdir(parents=True, exist_ok=True)

    @app.get("/<path:path>")
    def get_asset(path: str):
        page = _resolve_file(ASSETS_DIR, path)
        if page.suffix == ".html":
            return _fill_injection_slot(page, app.config["INJECT"].get(Path(path).as_posix()))
        return send_file(page)

    @app.post("/", defaults={"path": ""})
    @app.post("/<path:path>")
    def record_action(path: str):
        event = {
            "ts": datetime.now(UTC).isoformat(),
            "method": request.method,
            "path": f"/{path}",
            "form": request.form.to_dict(),
        }
        with app.config["EVENTS_PATH"].open("a", encoding="utf-8") as events:
            events.write(json.dumps(event) + "\n")
        return "OK", 200

    return app
