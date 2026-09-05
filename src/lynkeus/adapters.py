"""The contract a project implements to get the six standard screens.

Three protocols plus a data source. Status and Runs are read-only queries over
what already exists in the project's database. Actions is the one place the
shell starts work, and it does so by running the project's own CLI or ``just``
recipe as a subprocess, never through a parallel code path. ``DataSource`` is
what the Data and Query screens read; ``lynkeus.pg.PgSource`` implements it
and a project needs nothing beyond credentials.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from typing import Any, Protocol

from lynkeus.models import (
    Action,
    Health,
    QueryResult,
    Run,
    RunDetail,
    RunEvent,
    Status,
    TableDetail,
    TableInfo,
)


class StatusAdapter(Protocol):
    """Feeds the Status screen and ``<proj> status --json``."""

    def status(self) -> Status:
        """Return the current status, derived from queries, never stored."""
        ...


class RunsAdapter(Protocol):
    """Feeds the Runs screen and ``<proj> runs ...``."""

    def list(self, limit: int = 50) -> list[Run]:
        """Return the most recent runs, newest first."""
        ...

    def show(self, run_id: str) -> RunDetail:
        """Return one run with its per-stage progress."""
        ...

    def events(self, run_id: str) -> Iterator[RunEvent | None]:
        """Yield progress events for a run until it finishes.

        Implementations use ``LISTEN`` where the project emits notifications
        and poll a progress view otherwise. The shell does not care which,
        but it must be able to stop the stream when the user selects another
        run: yield ``None`` at least every few seconds while waiting, and
        release the connection when the generator is closed.
        """
        ...

    def cancel(self, run_id: str) -> None:
        """Ask the project to stop a run. Optional; raise if unsupported."""
        ...


class ActionsAdapter(Protocol):
    """Feeds the Actions palette and ``<proj> actions ...``."""

    def list(self) -> list[Action]:
        """Return every action the palette may offer."""
        ...

    def run(self, name: str, args: list[str]) -> subprocess.Popen[str]:
        """Start an action as a subprocess with text-mode piped output.

        The shell streams ``stdout`` into its output pane and turns the exit
        code into the run's final state. Destructive actions are confirmed by
        the shell before this is called.
        """
        ...


class DataSource(Protocol):
    """What the Data and Query screens read. ``PgSource`` is the real one.

    A source may also carry two optional attributes the shell reads with
    defaults, so nothing that does not set them changes:

    ``label``
        The engine's name in the header's health dot — ``pg ok`` by default,
        ``sqlite ok`` for a project whose state is a file.
    ``explain_label``
        What the Query screen's ``x`` key does, in the source's own words.
        Defaults to ``explain analyze``; SQLite's is ``explain query plan``,
        which is a different thing rather than the same thing spelt
        differently — nothing is executed to obtain it.
    """

    def health(self) -> Health:
        """Reachability plus a short server description."""
        ...

    def query(self, statement: str, params: Any = None) -> QueryResult:
        """Run one read-only statement and return its rows."""
        ...

    def explain(self, statement: str) -> QueryResult:
        """The statement's query plan; ``explain_label`` says what that means."""
        ...

    def tables(self) -> list[TableInfo]:
        """Every user relation, with a row estimate."""
        ...

    def table_detail(self, schema: str, name: str, sample: int = 3) -> TableDetail:
        """Columns, indexes, sizes and a few rows of one relation."""
        ...
