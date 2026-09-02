"""Fake adapters and a demo app, so the shell runs and tests without a database.

The numbers mirror the design canvas (a triage-pg project named chi311) so a
snapshot of the demo is a snapshot of the design.

Run it: ``python -m lynkeus.demo``.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any

from textual.app import ComposeResult
from textual.widgets import Static

from lynkeus.app import ShellApp
from lynkeus.models import (
    Action,
    ActionSource,
    ColumnInfo,
    Gauge,
    Health,
    IndexInfo,
    PendingItem,
    QueryResult,
    Run,
    RunDetail,
    RunEvent,
    RunState,
    Stage,
    Status,
    TableDetail,
    TableInfo,
)
from lynkeus.screens import ShellScreen
from lynkeus.widgets import Panel

NOW = datetime(2026, 9, 2, 10, 11, 0)


def _ago(**kwargs: float) -> datetime:
    return NOW - timedelta(**kwargs)


RUNS = [
    Run(
        "0f3a9c21",
        "chi311_v3",
        RunState.RUNNING,
        _ago(minutes=41),
        None,
        "12/20 matrices",
    ),
    Run(
        "9c21e7b4",
        "chi311_v3",
        RunState.SUCCEEDED,
        _ago(hours=2, minutes=30),
        _ago(hours=2),
    ),
    Run(
        "77be1a0d",
        "chi311_v2",
        RunState.FAILED,
        _ago(days=1, hours=3),
        _ago(days=1, hours=2),
        "OOM",
    ),
    Run(
        "41d02c9e",
        "chi311_v2",
        RunState.SUCCEEDED,
        _ago(days=2),
        _ago(days=1, hours=20),
    ),
    Run(
        "3be1d5f6",
        "chi311_v1",
        RunState.SUCCEEDED,
        _ago(days=5),
        _ago(days=4, hours=22),
    ),
    Run("c0d94a17", "donors_base", RunState.QUEUED, None, None),
    Run(
        "e8127b3c",
        "donors_base",
        RunState.SUCCEEDED,
        _ago(days=6),
        _ago(days=5, hours=21),
    ),
]

EVENTS = [
    RunEvent(
        _ago(minutes=1, seconds=2),
        "mark_built",
        "matrix",
        "as_of=2019-01-01 train 3.2s",
    ),
    RunEvent(_ago(seconds=56), "begin_artifact", "matrix", "as_of=2019-04-01 train"),
    RunEvent(_ago(seconds=53), "mark_built", "matrix", "as_of=2019-04-01 train 2.9s"),
    RunEvent(_ago(seconds=49), "begin_artifact", "matrix", "as_of=2019-04-01 test"),
    RunEvent(_ago(seconds=47), "mark_built", "matrix", "as_of=2019-04-01 test 1.8s"),
    RunEvent(_ago(seconds=45), "begin_artifact", "matrix", "as_of=2019-07-01 train"),
    RunEvent(
        _ago(seconds=19), "cache_hit", "matrix", "as_of=2018-10-01 shared with run 9c21"
    ),
    RunEvent(_ago(seconds=0), "begin_artifact", "matrix", "as_of=2019-07-01 test"),
]

LEADERBOARD = QueryResult(
    ["model_group_id", "model_type", "metric", "parameter", "value", "as_of_date"],
    [
        [17, "RandomForest", "precision", "100_abs", 0.412, "2019-07-01"],
        [23, "LightGBM", "precision", "100_abs", 0.398, "2019-07-01"],
        [17, "RandomForest", "precision", "100_abs", 0.391, "2019-04-01"],
        [31, "LightGBM", "precision", "100_abs", 0.377, "2019-07-01"],
        [23, "LightGBM", "precision", "100_abs", 0.362, "2019-04-01"],
        [9, "LogisticRegression", "precision", "100_abs", 0.301, "2019-07-01"],
        [17, "RandomForest", "precision", "500_abs", 0.288, "2019-07-01"],
        [4, "BaselineRank", "precision", "100_abs", 0.184, "2019-07-01"],
    ],
    84.0,
)

TABLES = [
    TableInfo("triage", "artifacts", "table", 1_812),
    TableInfo("triage", "evaluations", "table", 4_800),
    TableInfo("triage", "experiments", "table", 4),
    TableInfo("triage", "leaderboard", "matview", 4_800),
    TableInfo("triage", "model_groups", "table", 36),
    TableInfo("triage", "models", "table", 240),
    TableInfo("triage", "predictions", "table", 268_860),
    TableInfo("triage", "run_progress", "view", None),
    TableInfo("triage", "runs", "table", 37),
    TableInfo("public", "inspections", "table", 187_178),
    TableInfo("public", "facilities", "table", 41_204),
]

SAVED_QUERIES = {
    "leaderboard": "select model_group_id, model_type, metric, parameter,\n       round(value::numeric, 3) as value, as_of_date\nfrom   triage.leaderboard\nwhere  metric = 'precision'\norder by value desc\nlimit 20;",
    "run_progress": "select * from triage.run_progress order by run_id, kind;",
    "run_summary": "select run_id, status, started_at, finished_at from triage.run_summary\norder by started_at desc limit 20;",
}


class DemoStatus:
    """A status that looks like a live triage-pg project."""

    def status(self) -> Status:
        """Fixed numbers."""
        return Status(
            project="triage-pg",
            database=Health(True, "pg 16"),
            last_runs=RUNS[:5],
            pending=[
                PendingItem("leaderboard", "stale since run 0f3a", "refresh", "warn"),
                PendingItem("runs", "1 started > 6 h ago", "77be", "error"),
                PendingItem("gc", "14 collectable artifacts · 2.1 GB", "", "info"),
                PendingItem("sources", "nothing pending", "", "ok"),
            ],
            extra={"size": "4.1 GB · 22 tables · 9 views", "schema": "0020 (head)"},
            gauges=[
                Gauge("predictions", 268_860),
                Gauge("evaluations", 4_800),
                Gauge("models", 240),
                Gauge("runs", 37),
            ],
            series={"runs per day": [1, 2, 3, 5, 2, 6, 7, 5, 3, 6, 8, 5, 2, 3]},
        )


class DemoRuns:
    """Seven runs and a short event stream."""

    mode = "demo events"

    def list(self, limit: int = 50) -> list[Run]:
        """The design's list."""
        return RUNS[:limit]

    def show(self, run_id: str) -> RunDetail:
        """Stages as in the design for the running one; done for the others."""
        run = next((r for r in RUNS if r.run_id == run_id), RUNS[0])
        if run.state is RunState.RUNNING:
            stages = [
                Stage("cohort", 12, 12, "12 as-of dates · 3.1s"),
                Stage("labels", 12, 12, "12 as-of dates · 8.4s"),
                Stage("matrices", 12, 20, "ETA 6m"),
                Stage("models", 0, 48, "waiting"),
                Stage("predictions", 0, 0, "waiting"),
                Stage("evaluations", 0, 0, "waiting"),
            ]
        else:
            stages = [
                Stage("cohort", 12, 12),
                Stage("labels", 12, 12),
                Stage("matrices", 20, 20),
                Stage("models", 48, 48),
                Stage("predictions", 48, 48),
                Stage("evaluations", 48, 48),
            ]
        return RunDetail(
            run,
            stages,
            {
                "profile": "local",
                "git": "8c1e2d7",
                "splits": "2018-01 to 2019-07 · 12 as-of dates",
                "url": "http://127.0.0.1:8000/runs/" + run.run_id,
            },
        )

    def events(self, run_id: str) -> Iterator[RunEvent | None]:
        """The design's log, then the stream ends."""
        yield from EVENTS

    def cancel(self, run_id: str) -> None:
        """Pretend."""
        return


class DemoActions:
    """A palette from a justfile and a CLI."""

    def list(self) -> list[Action]:
        """Seven actions, one destructive."""
        return [
            Action("just test", "run the test suite · ~2 min", ActionSource.JUST),
            Action("just lint", "ruff check + format --check", ActionSource.JUST),
            Action(
                "triage analyze-config",
                "what a config will build, before it does",
                ActionSource.CLI,
            ),
            Action(
                "triage leaderboard",
                "the experiment leaderboard, headless",
                ActionSource.CLI,
            ),
            Action("just serve", "dashboard on :8000", ActionSource.JUST),
            Action(
                "triage gc",
                "destructive · collects unreferenced artifacts",
                ActionSource.CLI,
                True,
            ),
            Action("triage db upgrade", "alembic upgrade head", ActionSource.CLI),
        ]

    def run(self, name: str, args: list[str]) -> subprocess.Popen[str]:
        """Echo a few lines instead of doing anything."""
        script = 'for i in 1 2 3; do echo "$0 step $i"; done; echo done'
        return subprocess.Popen(
            ["sh", "-c", script, name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )


class DemoSource:
    """A catalog and one canned result set."""

    def health(self) -> Health:
        """Always up."""
        return Health(True, "pg 16")

    def query(self, sql: str, params: Any = None) -> QueryResult:
        """Any statement returns the leaderboard; an ``explain`` returns a plan."""
        if sql.lstrip().lower().startswith("explain"):
            return QueryResult(
                ["QUERY PLAN"],
                [
                    ["Limit  (cost=0.42..8.44 rows=20)"],
                    ["  ->  Index Scan on leaderboard"],
                ],
                3.0,
            )
        if "error" in sql.lower():
            return QueryResult([], [], 1.0, 'relation "nope" does not exist')
        return LEADERBOARD

    def explain(self, sql: str) -> QueryResult:
        """A plan."""
        return self.query("explain " + sql)

    def tables(self) -> list[TableInfo]:
        """The design's catalog."""
        return TABLES

    def table_detail(self, schema: str, name: str, sample: int = 3) -> TableDetail:
        """The same shape for every relation."""
        info = next(
            (t for t in TABLES if t.schema == schema and t.name == name), TABLES[0]
        )
        return TableDetail(
            info,
            columns=[
                ColumnInfo("model_id", "bigint", False, "→ triage.models"),
                ColumnInfo("entity_id", "bigint", False),
                ColumnInfo("as_of_date", "date", False),
                ColumnInfo("score", "double precision", True, "append-only, ADR-0006"),
                ColumnInfo("scored_at", "timestamptz", False, "partition key"),
            ],
            indexes=[
                IndexInfo(
                    "predictions_pkey",
                    "btree (model_id, entity_id, as_of_date, scored_at)",
                    "42 MB",
                ),
                IndexInfo("predictions_scored_at", "btree (scored_at)", "12 MB"),
            ],
            facts={
                "size": "2.9 GB · table 1.6 GB · indexes 1.3 GB",
                "live rows": "268,860",
                "last vacuum": "2026-09-02 08:10",
                "last analyze": "2026-09-02 08:10",
            },
            sample=QueryResult(
                ["model_id", "entity_id", "as_of_date", "score"],
                [
                    [17, 184201, "2019-07-01", 0.91],
                    [17, 184202, "2019-07-01", 0.88],
                    [17, 184203, "2019-07-01", 0.87],
                ][:sample],
                2.0,
            ),
        )


class DemoProjectScreen(ShellScreen):
    """A project screen, to exercise the 6+ tabs."""

    SLUG = "experiments"
    TITLE = "Experiments"
    KEYS = (("enter", "drill into runs"),)

    def compose(self) -> ComposeResult:
        """One panel."""
        yield Panel(
            "experiments",
            Static(
                "chi311_v3    [$text-muted]classification · early_warning[/]   3 runs   base rate 0.12\n"
                "chi311_v2    [$text-muted]classification · early_warning[/]   2 runs   base rate 0.12\n"
                "donors_base  [$text-muted]regression_ranking[/]              2 runs"
            ),
            classes="-fill",
        )
        yield self.keys_bar()

    def refresh_data(self) -> None:
        """Static."""


def demo_app(**overrides: Any) -> ShellApp:
    """The demo shell with a frozen clock and no polling (snapshot-stable)."""
    settings: dict[str, Any] = {
        "project": "triage-pg",
        "subtitle": "project chi311",
        "status_adapter": DemoStatus(),
        "runs_adapter": DemoRuns(),
        "actions_adapter": DemoActions(),
        "source": DemoSource(),
        "project_screens": [DemoProjectScreen()],
        "saved_queries": SAVED_QUERIES,
        "version": "v1.1.4",
        "poll_seconds": 0,
        "clock": lambda: NOW,
        "help_extra": "[$primary]6[/] Experiments — one row per prediction problem",
    }
    settings.update(overrides)
    return ShellApp(**settings)


def main(argv: list[str] | None = None) -> int:
    """Run the demo interactively (``--live`` keeps the clock and polling on)."""
    live = "--live" in (argv if argv is not None else sys.argv[1:])
    app = demo_app(clock=None, poll_seconds=5) if live else demo_app()
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
