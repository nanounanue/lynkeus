"""lynkeus: a shared Textual TUI shell for PostgreSQL-backed data projects.

The package owns the shell (screens, theme, key bindings, Postgres source and
test helpers). A project plugs in three adapters and its own screens. See
``lynkeus.adapters`` for the contract, ``lynkeus.models`` for the data every
screen renders, ``lynkeus.app.ShellApp`` for the shell and
``lynkeus.commands`` for the headless functions behind ``--json``.
"""

from __future__ import annotations

from lynkeus.adapters import ActionsAdapter, DataSource, RunsAdapter, StatusAdapter
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
    Series,
    Stage,
    Status,
    TableDetail,
    TableInfo,
)
from lynkeus.pg import MissingCredentials, PgSource
from lynkeus.theme import FLEXOKI_DARK, FLEXOKI_LIGHT

__version__ = "0.2.1"

__all__ = [
    "FLEXOKI_DARK",
    "FLEXOKI_LIGHT",
    "Action",
    "ActionSource",
    "ActionsAdapter",
    "ColumnInfo",
    "DataSource",
    "Gauge",
    "Health",
    "IndexInfo",
    "MissingCredentials",
    "PendingItem",
    "PgSource",
    "QueryResult",
    "Run",
    "RunDetail",
    "RunEvent",
    "RunState",
    "RunsAdapter",
    "Series",
    "Stage",
    "Status",
    "StatusAdapter",
    "TableDetail",
    "TableInfo",
    "__version__",
]


def __getattr__(name: str):  # noqa: ANN202 — lazy: Textual import is slow
    if name in {"ShellApp", "ShellScreen"}:
        from lynkeus.app import ShellApp
        from lynkeus.screens import ShellScreen

        return {"ShellApp": ShellApp, "ShellScreen": ShellScreen}[name]
    raise AttributeError(name)
