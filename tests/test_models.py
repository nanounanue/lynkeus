from __future__ import annotations

import json
from datetime import datetime

from rich.console import Console
from rich.table import Table

from lynkeus import (
    Action,
    ActionSource,
    Health,
    Run,
    RunDetail,
    RunState,
    Series,
    Stage,
    Status,
)


def _status() -> Status:
    return Status(
        project="triage-pg",
        database=Health(connected=True, detail="pg 16"),
        last_runs=[
            Run("0f3a", "chi311_v3", RunState.RUNNING, datetime(2026, 9, 2, 9, 30))
        ],
    )


def test_status_to_json_is_serialisable_and_matches_readme() -> None:
    payload = _status().to_json()

    assert payload["database"] == {"connected": True, "detail": "pg 16"}
    assert payload["last_runs"][0]["state"] == "running"
    assert payload["last_runs"][0]["started_at"] == "2026-09-02T09:30:00"
    json.dumps(payload)


def test_status_to_rich_renders_a_table() -> None:
    table = _status().to_rich()
    console = Console(record=True, width=80)
    console.print(table)

    assert isinstance(table, Table)
    assert "connected pg 16" in console.export_text()


def test_run_detail_to_rich_lists_stages() -> None:
    detail = RunDetail(
        run=Run("0f3a", "chi311_v3", RunState.RUNNING),
        stages=[Stage("matrices", 12, 20, "ETA 6m")],
    )
    console = Console(record=True, width=80)
    console.print(detail.to_rich())

    assert "12/20" in console.export_text()


def test_action_to_json_uses_enum_values() -> None:
    action = Action("just validate-surface", "coverage check", ActionSource.JUST)

    assert action.to_json()["source"] == "just"
    assert action.to_json()["destructive"] is False


def test_action_args_default_to_none_needed() -> None:
    action = Action("just test", "the suite", ActionSource.JUST)

    assert action.args == ""
    assert action.to_json()["args"] == ""


def test_a_series_of_zeros_is_empty_and_says_so() -> None:
    quiet = Series("runs per day", [0.0] * 14, "none in 14 d")
    busy = Series("runs per day", [0, 0, 3], "none in 14 d")

    assert quiet.empty
    assert quiet.summary() == "none in 14 d"
    assert not busy.empty
    assert busy.summary() == "3 points · last 3"


def test_an_empty_series_falls_back_to_none() -> None:
    assert Series("runs per day", []).summary() == "none"


def test_status_to_rich_prints_the_empty_note_not_a_flat_line() -> None:
    status = Status(
        project="triage-pg",
        database=Health(connected=True, detail="pg 16"),
        series=[Series("runs per day", [0.0] * 14, "none in 14 d")],
    )
    console = Console(record=True, width=80)
    console.print(status.to_rich())

    assert "none in 14 d" in console.export_text()
