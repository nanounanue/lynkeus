"""Data every standard screen renders.

Each model renders three ways: as a Textual widget (in the shell), as a Rich
renderable on a plain terminal (``to_rich``), and as JSON for agents and
scripts (``to_json``). Keeping the model separate from the widget is what lets
one build serve a human at the keyboard and an agent reading ``--json``.
"""

from __future__ import annotations

import dataclasses
import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from rich.table import Table


def _jsonable(value: Any) -> Any:
    """Coerce dataclass fields into JSON-serialisable values."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


class _Json:
    """Mixin giving dataclasses a ``to_json`` that returns plain dicts."""

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict of this model."""
        names: dict[str, Any] = getattr(self, "__dataclass_fields__", {})
        return {name: _jsonable(getattr(self, name)) for name in names}


class RunState(enum.StrEnum):
    """Lifecycle of a run, whatever the project calls it in its own tables."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ARCHIVED = "archived"


class ActionSource(enum.StrEnum):
    """Where an action comes from; shown as a tag in the Actions palette."""

    JUST = "just"
    CLI = "cli"
    DAGSTER = "dagster"


@dataclass(frozen=True, slots=True)
class Health(_Json):
    """Database reachability as the Status screen header shows it."""

    connected: bool
    detail: str = ""


@dataclass(frozen=True, slots=True)
class PendingItem(_Json):
    """One line of pending work, derived from a query, never from a flag."""

    name: str
    detail: str = ""
    due: str = ""


@dataclass(frozen=True, slots=True)
class Run(_Json):
    """One row of the Runs list."""

    run_id: str
    name: str
    state: RunState
    started_at: datetime | None = None
    finished_at: datetime | None = None
    detail: str = ""

    def to_rich(self) -> Table:
        """Render this run as a one-row Rich table."""
        table = _runs_table()
        _add_run_row(table, self)
        return table


@dataclass(frozen=True, slots=True)
class Stage(_Json):
    """Progress of one stage inside a run (cohort, matrices, cells, ...)."""

    name: str
    done: int
    total: int
    note: str = ""


@dataclass(frozen=True, slots=True)
class RunDetail(_Json):
    """The selected run: its row plus per-stage progress."""

    run: Run
    stages: list[Stage] = field(default_factory=list)
    meta: dict[str, str] = field(default_factory=dict)

    def to_rich(self) -> Table:
        """Render the stages as a Rich table."""
        table = Table(title=f"run {self.run.run_id} · {self.run.name}")
        table.add_column("stage")
        table.add_column("progress", justify="right")
        table.add_column("note", style="dim")
        for stage in self.stages:
            table.add_row(stage.name, f"{stage.done}/{stage.total}", stage.note)
        return table


@dataclass(frozen=True, slots=True)
class RunEvent(_Json):
    """One line of the live progress log."""

    at: datetime
    kind: str
    subject: str
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Action(_Json):
    """One entry of the Actions palette."""

    name: str
    description: str
    source: ActionSource
    destructive: bool = False


@dataclass(frozen=True, slots=True)
class Status(_Json):
    """The Status screen: health, last runs, pending work, project extras."""

    project: str
    database: Health
    last_runs: list[Run] = field(default_factory=list)
    pending: list[PendingItem] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)

    def to_rich(self) -> Table:
        """Render the status as a Rich table for a plain terminal."""
        table = Table(title=self.project, show_header=False)
        table.add_column("key", style="dim")
        table.add_column("value")
        mark = "connected" if self.database.connected else "not connected"
        table.add_row("database", f"{mark} {self.database.detail}".strip())
        for run in self.last_runs:
            table.add_row(f"run {run.run_id}", f"{run.state} · {run.name}")
        for item in self.pending:
            table.add_row(item.name, f"{item.detail} {item.due}".strip())
        for key, value in self.extra.items():
            table.add_row(key, value)
        return table


def runs_to_rich(runs: list[Run]) -> Table:
    """Render a list of runs as one Rich table."""
    table = _runs_table()
    for run in runs:
        _add_run_row(table, run)
    return table


def _runs_table() -> Table:
    table = Table()
    table.add_column("run")
    table.add_column("name")
    table.add_column("state")
    table.add_column("started", style="dim")
    table.add_column("detail", style="dim")
    return table


def _add_run_row(table: Table, run: Run) -> None:
    started = run.started_at.strftime("%Y-%m-%d %H:%M") if run.started_at else ""
    table.add_row(run.run_id, run.name, run.state.value, started, run.detail)
