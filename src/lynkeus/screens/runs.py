"""Runs: the list on the left, the selected run's stages and live log on the right.

The list and the stage table are queries (``RunsAdapter.list`` / ``show``);
the log is the adapter's event stream, consumed in a thread worker that is
cancelled when another run is selected.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Iterator

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, Input, RichLog, Static
from textual.worker import get_current_worker

from lynkeus.models import Run, RunDetail, RunEvent, RunState
from lynkeus.screens import ShellScreen
from lynkeus.text import GLYPHS, STYLES, age, bar, clip, elapsed
from lynkeus.widgets import Panel, colour

_EVENT_STYLES = {
    "built": "success",
    "mark_built": "success",
    "completed": "success",
    "succeeded": "success",
    "building": "secondary",
    "begin_artifact": "secondary",
    "started": "secondary",
    "failed": "error",
    "cache_hit": "warning",
}


class RunsScreen(ShellScreen):
    """The second tab."""

    SLUG = "runs"
    TITLE = "Runs"
    KEYS = (("l", "log"), ("k", "kill"), ("o", "open"), ("y", "copy as json"))
    PRIMARY = "#runs-table"

    BINDINGS = [
        Binding("l", "focus_log", "log", show=False),
        Binding("k", "kill", "kill", show=False),
        Binding("o", "open", "open", show=False),
        Binding("y", "copy", "copy as json", show=False),
        Binding("escape", "focus_list", "back", show=False),
    ]

    DEFAULT_CSS = """
    RunsScreen Horizontal { height: 1fr; }
    RunsScreen #runs-left { width: 40; }
    RunsScreen #runs-left DataTable { height: 1fr; }
    RunsScreen #runs-left Input {
        height: 1; border: none; padding: 0; background: $surface;
    }
    RunsScreen #runs-count { height: 1; color: $text-muted; text-align: right; }
    RunsScreen #runs-right { width: 1fr; padding: 0 0 0 1; }
    RunsScreen #run-header {
        height: 2; padding: 0 1; text-wrap: nowrap; text-overflow: ellipsis;
    }
    RunsScreen #run-stages { height: auto; }
    RunsScreen #run-log { height: 1fr; }
    RunsScreen RichLog { height: 1fr; background: transparent; }
    """

    def __init__(self, adapter, **kwargs) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.adapter = adapter
        #: How many characters of a run id to show. Eight suits a hash or a
        #: uuid, which is what the first consumers had; a project whose ids
        #: are names (``example_01.customers``) sets ``id_width`` on its
        #: adapter, next to ``mode``, and the list and header follow.
        self.id_width: int = int(getattr(adapter, "id_width", 8))
        self.runs: list[Run] = []
        self.filter_text = ""
        self.selected: str | None = None
        self.detail: RunDetail | None = None
        self.mode = "progress"

    def _prefix(self, run_id: str) -> str:
        """The first ``id_width`` characters of a run id: a prefix, never clipped.

        A prefix is what the project's own ``runs show`` accepts, so eight
        characters of a hash must read as usable; ``clip`` would drop one and
        add an ellipsis, which says the opposite. A project whose ids are
        names sets ``id_width`` to fit them and gets the whole name.
        """
        return run_id[: self.id_width]

    def compose(self) -> ComposeResult:
        """List and filter on the left; header, stages, log on the right."""
        with Horizontal():
            with Panel("runs", id="runs-left", classes="-fill"):
                table = DataTable(
                    cursor_type="row", zebra_stripes=False, id="runs-table"
                )
                table.add_columns("", "run", "name", "age")
                yield table
                yield Input(placeholder="/ filter", classes="filter", id="runs-filter")
                yield Static("", id="runs-count")
            with Vertical(id="runs-right"):
                yield Static("", id="run-header")
                yield Panel("artifacts", Static("", id="run-stages"))
                yield Panel(
                    "progress",
                    RichLog(markup=False, wrap=False, id="run-log"),
                    id="run-log-panel",
                    classes="-fill",
                )
        yield self.keys_bar()

    # ------------------------------------------------------------------ data
    def refresh_data(self) -> None:
        """Reload the list; the selected run's detail follows."""
        self.load(lambda: self.adapter.list(50), self.show_runs, group="runs")

    def show_runs(self, runs: list[Run]) -> None:
        """Render the list, keeping the selection where possible."""
        self.runs = runs
        table = self.query_one("#runs-table", DataTable)
        table.clear()
        now = self.now()
        shown = 0
        for run in runs:
            if self.filter_text and not self._matches(run):
                continue
            glyph = Text(GLYPHS[run.state], style=colour(self.app, STYLES[run.state]))
            when = (
                "queued" if run.state is RunState.QUEUED else age(run.started_at, now)
            )
            table.add_row(
                glyph,
                self._prefix(run.run_id),
                clip(run.name, 13),
                when,
                key=run.run_id,
            )
            shown += 1
        self.query_one("#runs-count", Static).update(f"{shown} of {len(runs)}")
        if self.selected is None and shown:
            self.select(self._first_key(table))
        elif self.selected is not None:
            self.load_detail(self.selected)

    def _first_key(self, table: DataTable) -> str | None:
        for key in table.rows:
            return str(key.value)
        return None

    def _matches(self, run: Run) -> bool:
        needle = self.filter_text.lower()
        return (
            needle in f"{run.run_id} {run.name} {run.state.value} {run.detail}".lower()
        )

    def select(self, run_id: str | None) -> None:
        """Select a run: load its detail and start its event stream."""
        if run_id is None or run_id == self.selected:
            return
        self.selected = run_id
        self.query_one("#run-log", RichLog).clear()
        self.load_detail(run_id)
        self.run_worker(
            lambda: self._follow(run_id),
            thread=True,
            exclusive=True,
            group="events",
            exit_on_error=False,
        )

    def load_detail(self, run_id: str) -> None:
        """Fetch the stage table for ``run_id``."""
        self.load(lambda: self.adapter.show(run_id), self.show_detail, group="detail")

    def show_detail(self, detail: RunDetail) -> None:
        """Render header and stages."""
        if detail.run.run_id != self.selected:
            return
        self.detail = detail
        run = detail.run
        now = self.now()
        state = f"[${STYLES[run.state]}]{GLYPHS[run.state]} {run.state.value}[/]"
        if run.state is RunState.RUNNING:
            state += f" {elapsed(run.started_at, now)}"
        line1 = f"[b]run {self._prefix(run.run_id)}[/b]  {run.name}  {state}"
        meta = "  ".join(
            f"[$text-muted]{k}[/] {v}" for k, v in detail.meta.items() if k != "url"
        )
        # A run nobody timestamped (featurizer's materializations are tables,
        # not events) gets no "started" label: a label with nothing after it
        # reads as a bug, not as a fact about the project.
        parts = []
        if run.started_at is not None:
            parts.append(f"[$text-muted]started[/] {run.started_at:%H:%M}")
        if meta:
            parts.append(meta)
        line2 = "  ".join(parts)
        self.query_one("#run-header", Static).update(f"{line1}\n{line2}")
        lines = []
        for stage in detail.stages:
            if stage.total <= 0:
                progress = "[$text-disabled]—[/]"
            elif stage.done >= stage.total:
                progress = f"[$success]✓[/] {stage.done}/{stage.total}"
            else:
                filled, rest = bar(stage.done, stage.total, 24)
                progress = (
                    f"[$primary]{filled}[/][$border]{rest}[/]"
                    f" {stage.done}/{stage.total}"
                )
            note = f"  [$text-muted]{stage.note}[/]" if stage.note else ""
            lines.append(f"{stage.name:<12} {progress}{note}")
        self.query_one("#run-stages", Static).update(
            "\n".join(lines) or "[$text-muted]no stages[/]"
        )

    # ---------------------------------------------------------------- events
    def _follow(self, run_id: str) -> None:
        worker = get_current_worker()
        app = self.app
        app.call_from_thread(self._set_mode, getattr(self.adapter, "mode", "events"))
        stream: Iterator[RunEvent | None] = self.adapter.events(run_id)
        try:
            for event in stream:
                if worker.is_cancelled:
                    break
                if event is None:
                    continue
                app.call_from_thread(self.append_event, run_id, event)
        except Exception as exc:
            app.call_from_thread(self.report_error, "events", exc)
        finally:
            close = getattr(stream, "close", None)
            if close is not None:
                close()

    def _set_mode(self, mode: str) -> None:
        self.mode = mode
        self.query_one("#run-log-panel", Panel).set_title(f"progress · {mode}")

    def append_event(self, run_id: str, event: RunEvent) -> None:
        """Write one event line and refresh the stages."""
        if run_id != self.selected:
            return
        log = self.query_one("#run-log", RichLog)
        line = Text()
        line.append(
            event.at.strftime("%H:%M:%S") + "  ", style=colour(self.app, "text-muted")
        )
        line.append(
            f"{event.kind:<14}",
            style=colour(self.app, _EVENT_STYLES.get(event.kind, "foreground")),
        )
        line.append(f" {event.subject}")
        if event.detail:
            line.append(f"  {event.detail}", style=colour(self.app, "text-muted"))
        log.write(line)
        self.load_detail(run_id)

    # --------------------------------------------------------------- actions
    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Selection follows the cursor."""
        if event.row_key is not None and event.row_key.value is not None:
            self.select(str(event.row_key.value))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the list as the user types."""
        self.filter_text = event.value
        self.show_runs(self.runs)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter returns focus to the list."""
        self.action_focus_list()

    def action_focus_list(self) -> None:
        """Focus the runs table."""
        self.query_one("#runs-table", DataTable).focus()

    def action_focus_log(self) -> None:
        """Focus the log so it can scroll."""
        self.query_one("#run-log", RichLog).focus()

    def action_kill(self) -> None:
        """Ask the adapter to cancel the selected run, after confirming."""
        if self.selected is None:
            return
        from lynkeus.widgets import ConfirmScreen

        run_id = self.selected

        def done(yes: bool | None) -> None:
            if yes:
                try:
                    self.adapter.cancel(run_id)
                except Exception as exc:  # noqa: BLE001 — shown, not hidden
                    self.report_error("cancel", exc)
                else:
                    self.app.notify(
                        f"cancel requested for {self._prefix(run_id)}",
                        timeout=3,
                    )

        self.app.push_screen(ConfirmScreen(f"Kill run {self._prefix(run_id)}?"), done)

    def action_open(self) -> None:
        """Open the run's URL, when the adapter gave one."""
        url = self.detail.meta.get("url") if self.detail else None
        if not url:
            self.app.notify("this run has no url", timeout=3)
            return
        webbrowser.open(url)

    def action_copy(self) -> None:
        """Copy the selected run's detail as JSON."""
        if self.detail is not None:
            self.copy_json(self.detail)

    def sql_for_selection(self) -> str | None:
        """No table behind a run; the project screens know their views."""
        return None

    def poll(self) -> None:
        """Refresh the list each poll; the detail refreshes on events."""
        self.refresh_data()
