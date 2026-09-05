"""A source that is not PostgreSQL: the two places the shell said ``pg``.

Raised by the tanaland round, the first consumer on SQLite. Two strings in the
shell named the engine rather than reading it: the header's ``pg ok`` and the
Query screen's ``x explain analyze``. SQLite has no ``explain analyze`` — the
plan is what the planner intends and nothing is executed to get it — so the
second was not merely mislabelled but wrong about what the key does.

Both are now read off the source with a default, so ``PgSource`` and the five
consumers on it are untouched.
"""

from __future__ import annotations

from typing import Any

from lynkeus.demo import DemoSource, DemoStatus, demo_app
from lynkeus.models import Health, Status


class SqliteLikeSource(DemoSource):
    """A source that names its own engine and its own explain."""

    label = "sqlite"
    explain_label = "explain query plan"

    def health(self) -> Health:
        """Up, and says what it is."""
        return Health(True, "sqlite 3.50.4 · data/database.db · 432.0 kB · wal")


class SqliteLikeStatus(DemoStatus):
    """The Status the header takes its health dot from."""

    def status(self) -> Status:
        """The demo's status with the file's health in place of the server's."""
        from dataclasses import replace

        return replace(super().status(), database=SqliteLikeSource().health())


def sqlite_app(**overrides: Any):
    """The demo shell over a source that is not PostgreSQL."""
    settings: dict[str, Any] = {
        "source": SqliteLikeSource(),
        "status_adapter": SqliteLikeStatus(),
        "project": "tanaland",
        "subtitle": "facilitator",
    }
    settings.update(overrides)
    return demo_app(**settings)


def test_query_screen_over_a_sqlite_source(shell_snapshot) -> None:
    """The header says ``sqlite ok`` and ``x`` says ``explain query plan``.

    One picture covers both, because the header sits above every screen and
    the Query screen is where the explain key is shown.
    """
    assert shell_snapshot(sqlite_app(), keys=["4"])
