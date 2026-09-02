"""The headless functions print the same data the screens show."""

from __future__ import annotations

import json

from rich.console import Console

from lynkeus import commands
from lynkeus.demo import DemoActions, DemoRuns, DemoSource, DemoStatus


def _console() -> Console:
    return Console(record=True, width=120, force_terminal=False, color_system=None)


def test_status_json_is_parseable() -> None:
    console = _console()
    status = commands.status(DemoStatus(), json_out=True, console=console)
    payload = json.loads(console.export_text())

    assert payload["project"] == status.project == "triage-pg"
    assert payload["database"]["connected"] is True
    assert payload["gauges"][0]["name"] == "predictions"


def test_runs_list_and_show() -> None:
    console = _console()
    runs = commands.runs_list(DemoRuns(), 3, json_out=True, console=console)
    assert [r["run_id"] for r in json.loads(console.export_text())] == [
        r.run_id for r in runs
    ]

    console = _console()
    detail = commands.runs_show(DemoRuns(), runs[0].run_id, console=console)
    text = console.export_text()
    assert "matrices" in text and "12/20" in text
    assert detail.meta["profile"] == "local"


def test_runs_tail_stops_when_the_stream_ends() -> None:
    console = _console()
    events = commands.runs_tail(DemoRuns(), "0f3a9c21", json_out=True, console=console)
    lines = [json.loads(line) for line in console.export_text().splitlines() if line]

    assert len(events) == 8
    assert lines[0]["kind"] == "mark_built"


def test_query_json_records() -> None:
    console = _console()
    result = commands.query(DemoSource(), "select 1", json_out=True, console=console)
    records = json.loads(console.export_text())

    assert records[0]["model_type"] == "RandomForest"
    assert result.elapsed_ms == 84.0


def test_query_error_is_printed_not_raised() -> None:
    console = _console()
    result = commands.query(DemoSource(), "select * from error", console=console)

    assert result.error
    assert "does not exist" in console.export_text()


def test_actions_list_and_run() -> None:
    console = _console()
    actions = commands.actions_list(DemoActions(), json_out=True, console=console)
    assert any(a["destructive"] for a in json.loads(console.export_text()))

    console = _console()
    code = commands.actions_run(DemoActions(), actions[0].name, console=console)
    assert code == 0
    assert "step 3" in console.export_text()
