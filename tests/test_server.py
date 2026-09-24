import json
from datetime import datetime, timedelta

import pytest

from parallax import server


@pytest.fixture
def trap(tmp_path, monkeypatch):
    traps = tmp_path / "traps"
    traps.mkdir()
    snippet = '<span hidden>Test trap: {{ literal_text }}</span>'
    (traps / "hidden_text.html").write_text(snippet, encoding="utf-8")
    monkeypatch.setattr(server, "TRAPS_DIR", traps)
    return snippet


@pytest.mark.parametrize(
    "page",
    sorted(server.ASSETS_DIR.rglob("*.html")),
    ids=lambda page: page.name,
)
def test_clean_pages(page, trap, tmp_path):
    events = tmp_path / "events.jsonl"
    app = server.create_app({}, str(events))

    response = app.test_client().get(f"/{page.relative_to(server.ASSETS_DIR)}")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert response.get_data(as_text=True) == page.read_text(encoding="utf-8").replace(
        "{{ INJECTION_SLOT }}", ""
    )
    assert trap not in response.get_data(as_text=True)
    assert not events.exists()


@pytest.mark.parametrize(
    "request_path",
    ["/helpdesk/ticket.html", "/helpdesk/./ticket.html", "/helpdesk//ticket.html"],
)
def test_injection_is_specific_to_page_and_app(request_path, trap, tmp_path):
    page = "helpdesk/ticket.html"
    attacked_events = tmp_path / "attacked.jsonl"
    control_events = tmp_path / "control.jsonl"
    attacked = server.create_app({page: "hidden_text.html"}, str(attacked_events))
    control = server.create_app({}, str(control_events))

    response = attacked.test_client().get(request_path)
    source = (server.ASSETS_DIR / page).read_text(encoding="utf-8")
    assert response.status_code == 200
    assert response.get_data(as_text=True) == source.replace("{{ INJECTION_SLOT }}", trap)
    for app, path in [(control, f"/{page}"), (attacked, "/webmail/inbox.html")]:
        response = app.test_client().get(path)
        assert response.status_code == 200
        assert trap not in response.get_data(as_text=True)

    attacked.test_client().post("/webmail/send", data={"body": "attacked"})
    control.test_client().post("/helpdesk/reply", data={"body": "control"})
    assert [json.loads(line)["form"] for line in attacked_events.read_text().splitlines()] == [
        {"body": "attacked"}
    ]
    assert [json.loads(line)["form"] for line in control_events.read_text().splitlines()] == [
        {"body": "control"}
    ]


def test_stylesheet_is_served_unchanged(tmp_path):
    app = server.create_app({}, str(tmp_path / "events.jsonl"))

    response = app.test_client().get("/shared/style.css")

    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert response.data == (server.ASSETS_DIR / "shared/style.css").read_bytes()


@pytest.mark.parametrize(
    "path", ["/webmail/send", "/helpdesk/reply", "/webmail/delete", "/new/action", "/"]
)
def test_posts_append_events(path, tmp_path):
    events = tmp_path / "run" / "events.jsonl"
    app = server.create_app({}, str(events))
    client = app.test_client()
    forms = [
        {"to": "recipient@example.test", "subject": "", "body": "Hello, Maya!\nCafé"},
        {"body": "Second action"},
    ]

    for index, form in enumerate(forms, start=1):
        response = client.post(path, data=form)
        assert response.status_code == 200
        assert response.get_data(as_text=True) == "OK"
        lines = events.read_text(encoding="utf-8").splitlines()
        assert len(lines) == index
        event = json.loads(lines[-1])
        assert set(event) == {"ts", "method", "path", "form"}
        assert event["method"] == "POST"
        assert event["path"] == path
        assert [json.loads(line)["form"] for line in lines] == forms[:index]
        assert datetime.fromisoformat(event["ts"]).utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "path",
    [
        "/../parallax/__init__.py",
        "/%2e%2e/parallax/__init__.py",
        "/helpdesk/../../parallax/__init__.py",
        "/helpdesk/../helpdesk/ticket.html",
        "/parallax/__init__.py",
        "/static/style.css",
        "/missing.html",
        "/helpdesk/",
    ],
)
def test_get_refuses_traversal_and_non_assets(path, tmp_path):
    events = tmp_path / "events.jsonl"
    app = server.create_app({}, str(events))

    response = app.test_client().get(path)

    assert response.status_code == 404
    assert not events.exists()


def test_get_refuses_symlink_escape(tmp_path, monkeypatch):
    assets = tmp_path / "scenario-assets"
    assets.mkdir()
    outside = tmp_path / "outside.html"
    outside.write_text("Outside the asset directory", encoding="utf-8")
    (assets / "escape.html").symlink_to(outside)
    monkeypatch.setattr(server, "ASSETS_DIR", assets)
    app = server.create_app({}, str(tmp_path / "events.jsonl"))

    response = app.test_client().get("/escape.html")

    assert response.status_code == 404
    assert outside.read_text(encoding="utf-8") not in response.get_data(as_text=True)


def test_failed_event_write_does_not_report_success(tmp_path):
    events = tmp_path / "events.jsonl"
    app = server.create_app({}, str(events))
    events.mkdir()

    response = app.test_client().post("/webmail/send", data={"body": "Hello"})

    assert response.status_code == 500
