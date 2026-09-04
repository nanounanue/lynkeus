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
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from rich.table import Table


def _jsonable(value: Any) -> Any:
    """Coerce dataclass fields into JSON-serialisable values."""
    if isinstance(value, enum.Enum):
        return value.value
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Decimal):
        return float(value)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _jsonable(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(v) for v in value]
    return value


def jsonable(value: Any) -> Any:
    """Public form of the coercion, for query rows and ad-hoc payloads."""
    return _jsonable(value)


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
    """One line of pending work, derived from a query, never from a flag.

    ``level`` is ``info`` · ``ok`` · ``warn`` · ``error`` and picks the glyph.
    """

    name: str
    detail: str = ""
    due: str = ""
    level: str = "info"


@dataclass(frozen=True, slots=True)
class Gauge(_Json):
    """A bar with a number: ``value`` of ``total`` (``total`` None = a count)."""

    name: str
    value: float
    total: float | None = None
    note: str = ""


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
    """The selected run: its row plus per-stage progress.

    ``meta`` is free-form key → value shown under the run header. The key
    ``url`` is special: the Runs screen's ``o`` key opens it in a browser.
    """

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
    """One entry of the Actions palette.

    ``args`` is the usage hint for arguments the action cannot run without
    (``"CONFIG"``, ``"MODEL_ID AS_OF_DATE"``). A non-empty hint makes the
    shell prompt for them before starting the subprocess; leave it empty for
    an action that runs bare, whatever optional flags it also accepts.
    """

    name: str
    description: str
    source: ActionSource
    destructive: bool = False
    args: str = ""


@dataclass(frozen=True, slots=True)
class Series(_Json):
    """One sparkline: the values, and what to say when there is nothing to draw.

    All-zero values draw as a flat line indistinguishable from a constant
    one — honest but mute. ``empty_note`` is the project's own wording for
    that case, in its own units: ``Series("runs per day", counts, "none in
    14 d")``. The screens print the note instead of the flat line.
    """

    name: str
    values: list[float] = field(default_factory=list)
    empty_note: str = ""

    @property
    def empty(self) -> bool:
        """True when there is nothing to draw: no values, or every one zero."""
        return not any(self.values)

    def summary(self) -> str:
        """One line for a plain terminal, which has no sparkline."""
        if self.empty:
            return self.empty_note or "none"
        return f"{len(self.values)} points · last {self.values[-1]:g}"


@dataclass(frozen=True, slots=True)
class Status(_Json):
    """The Status screen: health, last runs, pending work, project extras.

    ``extra`` are plain key → value lines in the database panel; ``gauges``
    draw as bars there (table sizes, budgets); ``series`` draw as sparklines
    (runs per day), in the order given.
    """

    project: str
    database: Health
    last_runs: list[Run] = field(default_factory=list)
    pending: list[PendingItem] = field(default_factory=list)
    extra: dict[str, str] = field(default_factory=dict)
    gauges: list[Gauge] = field(default_factory=list)
    series: list[Series] = field(default_factory=list)

    def to_rich(self) -> Table:
        """Render the status as a Rich table for a plain terminal."""
        table = Table(title=self.project, show_header=False)
        table.add_column("key", style="dim")
        table.add_column("value")
        mark = "connected" if self.database.connected else "not connected"
        table.add_row("database", f"{mark} {self.database.detail}".strip())
        for key, value in self.extra.items():
            table.add_row(key, value)
        for gauge in self.gauges:
            total = f" of {gauge.total:g}" if gauge.total is not None else ""
            table.add_row(gauge.name, f"{gauge.value:g}{total} {gauge.note}".strip())
        for series in self.series:
            table.add_row(series.name, series.summary())
        for run in self.last_runs:
            table.add_row(f"run {run.run_id}", f"{run.state} · {run.name}")
        for item in self.pending:
            table.add_row(item.name, f"{item.detail} {item.due}".strip())
        return table


@dataclass(frozen=True, slots=True)
class QueryResult(_Json):
    """Rows from one SQL statement, plus how long it took."""

    columns: list[str]
    rows: list[list[Any]]
    elapsed_ms: float = 0.0
    error: str = ""

    def to_rich(self) -> Table:
        """Render the rows as a Rich table."""
        table = Table(caption=f"{len(self.rows)} rows · {self.elapsed_ms:.0f} ms")
        for column in self.columns:
            table.add_column(column)
        for row in self.rows:
            table.add_row(*("" if v is None else str(v) for v in row))
        return table

    def records(self) -> list[dict[str, Any]]:
        """Rows as dicts, JSON-safe."""
        return [
            {c: _jsonable(v) for c, v in zip(self.columns, row, strict=True)}
            for row in self.rows
        ]


@dataclass(frozen=True, slots=True)
class TableInfo(_Json):
    """One relation in the Data screen tree (``kind``: table · view · matview)."""

    schema: str
    name: str
    kind: str
    rows_estimate: int | None = None


@dataclass(frozen=True, slots=True)
class ColumnInfo(_Json):
    """One column of a relation."""

    name: str
    type: str
    nullable: bool = True
    note: str = ""


@dataclass(frozen=True, slots=True)
class IndexInfo(_Json):
    """One index of a relation."""

    name: str
    definition: str
    size: str = ""


@dataclass(frozen=True, slots=True)
class TableDetail(_Json):
    """Everything the Data screen shows for the selected relation."""

    info: TableInfo
    columns: list[ColumnInfo] = field(default_factory=list)
    indexes: list[IndexInfo] = field(default_factory=list)
    facts: dict[str, str] = field(default_factory=dict)
    sample: QueryResult | None = None


def runs_to_rich(runs: list[Run]) -> Table:
    """Render a list of runs as one Rich table."""
    table = _runs_table()
    for run in runs:
        _add_run_row(table, run)
    return table


def actions_to_rich(actions: list[Action]) -> Table:
    """Render the actions palette as one Rich table."""
    table = Table()
    table.add_column("action")
    table.add_column("args", style="dim")
    table.add_column("description")
    table.add_column("source", style="dim")
    table.add_column("", style="red")
    for action in actions:
        table.add_row(
            action.name,
            action.args,
            action.description,
            action.source.value,
            "destructive" if action.destructive else "",
        )
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
