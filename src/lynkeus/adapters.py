"""The contract a project implements to get the six standard screens.

Three protocols. Status and Runs are read-only queries over what already
exists in the project's database. Actions is the one place the shell starts
work, and it does so by running the project's own CLI or ``just`` recipe as a
subprocess, never through a parallel code path.
"""

from __future__ import annotations

import subprocess
from collections.abc import Iterator
from typing import Protocol

from lynkeus.models import Action, Run, RunDetail, RunEvent, Status


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

    def events(self, run_id: str) -> Iterator[RunEvent]:
        """Yield progress events for a run until it finishes.

        Implementations use ``LISTEN`` where the project emits notifications
        and poll a progress view otherwise. The shell does not care which.
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
