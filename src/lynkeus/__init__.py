"""lynkeus: a shared Textual TUI shell for PostgreSQL-backed data projects.

The package owns the shell (screens, theme, key bindings, Postgres source and
test helpers). A project plugs in three adapters and its own screens. See
``lynkeus.adapters`` for the contract and ``lynkeus.models`` for the data every
screen renders.
"""

from __future__ import annotations

from lynkeus.adapters import ActionsAdapter, RunsAdapter, StatusAdapter
from lynkeus.models import (
    Action,
    ActionSource,
    Health,
    PendingItem,
    Run,
    RunDetail,
    RunEvent,
    RunState,
    Stage,
    Status,
)
from lynkeus.pg import MissingCredentials, PgSource
from lynkeus.theme import FLEXOKI_DARK, FLEXOKI_LIGHT

__version__ = "0.0.1"

__all__ = [
    "FLEXOKI_DARK",
    "FLEXOKI_LIGHT",
    "Action",
    "ActionSource",
    "ActionsAdapter",
    "Health",
    "MissingCredentials",
    "PendingItem",
    "PgSource",
    "Run",
    "RunDetail",
    "RunEvent",
    "RunState",
    "RunsAdapter",
    "Stage",
    "Status",
    "StatusAdapter",
    "__version__",
]
