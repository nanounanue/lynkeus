"""Status: database facts, last runs, a sparkline, pending work.

Everything on it comes from one ``StatusAdapter.status()`` call. Pending
work is whatever the adapter derived from queries; the screen never keeps a
flag of its own.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Static

from lynkeus.models import Status
from lynkeus.screens import ShellScreen
from lynkeus.text import GLYPHS, LEVEL_GLYPHS, STYLES, age, bar, count, spark
from lynkeus.widgets import Panel


class StatusScreen(ShellScreen):
    """The first tab."""

    SLUG = "status"
    TITLE = "Status"
    KEYS = (("enter", "open runs"), ("y", "copy as json"))

    BINDINGS = [
        Binding("enter", "open_runs", "open runs", show=False),
        Binding("y", "copy", "copy as json", show=False),
    ]

    DEFAULT_CSS = """
    StatusScreen Horizontal { height: 1fr; }
    StatusScreen #status-left { width: 1fr; }
    StatusScreen #status-right { width: 1fr; }
    StatusScreen Static { height: auto; }
    """

    def __init__(self, adapter, **kwargs) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.adapter = adapter
        self.status: Status | None = None

    def compose(self) -> ComposeResult:
        """Two columns of panels."""
        with Horizontal():
            with Vertical(id="status-left"):
                yield Panel("database", Static("", id="status-db"))
                yield Panel("last runs", Static("", id="status-runs"))
            with Vertical(id="status-right"):
                yield Panel(
                    "pending work · derived from queries",
                    Static("", id="status-pending"),
                )
        yield self.keys_bar()

    def refresh_data(self) -> None:
        """Ask the adapter for a fresh status."""
        self.load(self.adapter.status, self.show, group="status")

    def show(self, status: Status) -> None:
        """Render a status."""
        self.status = status
        self.query_one("#status-db", Static).update(self._database(status))
        self.query_one("#status-runs", Static).update(self._runs(status))
        self.query_one("#status-pending", Static).update(self._pending(status))
        self.app.set_health(status.database)  # type: ignore[attr-defined]

    def _database(self, status: Status) -> str:
        db = status.database
        dot = (
            "[$success]●[/] connected" if db.connected else "[$error]●[/] not connected"
        )
        lines = [f"[$text-muted]connection[/]   {dot} [$text-muted]{db.detail}[/]"]
        for key, value in status.extra.items():
            lines.append(f"[$text-muted]{key:<12}[/] {value}")
        if status.gauges:
            lines.append("")
            top = max((g.value for g in status.gauges), default=0) or 1
            for gauge in status.gauges:
                total = gauge.total if gauge.total is not None else top
                filled, rest = bar(gauge.value, total, width=14)
                amount = count(gauge.value)
                if gauge.total is not None:
                    amount += f" of {count(gauge.total)}"
                note = f" [$text-muted]{gauge.note}[/]" if gauge.note else ""
                lines.append(
                    f"[$text-muted]{gauge.name:<12}[/] [$primary]{filled}[/]"
                    f"[$border]{rest}[/] {amount}{note}"
                )
        return "\n".join(lines)

    def _runs(self, status: Status) -> str:
        now = self.now()
        lines = []
        for run in status.last_runs:
            glyph = f"[${STYLES[run.state]}]{GLYPHS[run.state]}[/]"
            detail = f" [$text-muted]{run.detail}[/]" if run.detail else ""
            when = age(run.finished_at or run.started_at, now)
            lines.append(f"{glyph} {run.name:<22}{detail}  [$text-muted]{when}[/]")
        if not lines:
            lines.append("[$text-muted]no runs yet[/]")
        for name, values in status.series.items():
            lines.append("")
            lines.append(f"[$text-muted]{name}[/]  [$primary]{spark(values, 40)}[/]")
        return "\n".join(lines)

    def _pending(self, status: Status) -> str:
        if not status.pending:
            return "[$success]✓[/] nothing pending"
        lines = []
        for item in status.pending:
            glyph, style = LEVEL_GLYPHS.get(item.level, LEVEL_GLYPHS["info"])
            due = f"  [$text-muted]{item.due}[/]" if item.due else ""
            lines.append(
                f"[${style}]{glyph}[/] {item.name:<22}"
                f" [$text-muted]{item.detail}[/]{due}"
            )
        return "\n".join(lines)

    def action_open_runs(self) -> None:
        """Jump to the Runs tab."""
        self.app.action_tab_slug("runs")  # type: ignore[attr-defined]

    def action_copy(self) -> None:
        """Copy the status as JSON."""
        if self.status is not None:
            self.copy_json(self.status)
