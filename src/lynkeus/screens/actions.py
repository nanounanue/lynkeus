"""Actions: the palette of ``just`` recipes and CLI verbs, and the running one.

The shell never runs project code in-process: ``ActionsAdapter.run`` starts a
subprocess, this screen streams its stdout and turns the exit code into the
final state. Destructive actions are confirmed first, and an action that
declares ``args`` is prompted for them — running ``triage run`` with none
would only print its usage and exit 2.
"""

from __future__ import annotations

import shlex
import subprocess
from datetime import datetime

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.widgets import DataTable, Input, RichLog, Static

from lynkeus.models import Action
from lynkeus.screens import ShellScreen
from lynkeus.text import clip, elapsed
from lynkeus.widgets import ConfirmScreen, Panel, PromptScreen, colour


class ActionsScreen(ShellScreen):
    """The fifth tab."""

    SLUG = "actions"
    TITLE = "Actions"
    PRIMARY = "#actions-table"
    KEYS = (("enter", "run"), ("k", "kill"), ("y", "copy command"))

    BINDINGS = [
        Binding("enter", "run_selected", "run", show=False),
        Binding("k", "kill", "kill", show=False),
        Binding("y", "copy", "copy command", show=False),
        Binding("escape", "focus_list", "back", show=False),
    ]

    DEFAULT_CSS = """
    ActionsScreen Horizontal { height: 1fr; }
    ActionsScreen #actions-left { width: 70; }
    ActionsScreen #actions-left Input {
        height: 1; border: none; padding: 0; background: $surface;
    }
    ActionsScreen #actions-left DataTable { height: 1fr; }
    ActionsScreen #actions-count { height: 1; color: $text-muted; }
    ActionsScreen #actions-right { width: 1fr; padding: 0 0 0 1; }
    ActionsScreen RichLog { height: 1fr; background: transparent; }
    ActionsScreen #actions-state { height: 1; color: $text-muted; }
    """

    def __init__(self, adapter, **kwargs) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.adapter = adapter
        self.actions: list[Action] = []
        self.filter_text = ""
        self.selected: Action | None = None
        self.process: subprocess.Popen[str] | None = None
        self.running: Action | None = None
        self.started_at: datetime | None = None

    def compose(self) -> ComposeResult:
        """Palette on the left, the running action on the right."""
        with Horizontal():
            with Panel("actions", id="actions-left", classes="-fill"):
                yield Input(
                    placeholder="› filter", classes="filter", id="actions-filter"
                )
                table = DataTable(
                    cursor_type="row", zebra_stripes=False, id="actions-table"
                )
                table.add_columns("action", "description", "source")
                yield table
                yield Static("", id="actions-count")
            with Panel("running", id="actions-right", classes="-fill"):
                yield RichLog(markup=False, wrap=True, id="actions-log")
                yield Static(
                    "[$text-muted]stdout streams here · "
                    "exit code becomes the run status[/]",
                    id="actions-state",
                )
        yield self.keys_bar()

    # ------------------------------------------------------------------ data
    def refresh_data(self) -> None:
        """Reload the palette."""
        self.load(self.adapter.list, self.show_actions, group="actions")

    def poll(self) -> None:
        """The palette is static; only the elapsed clock ticks."""
        self._tick()

    def show_actions(self, actions: list[Action]) -> None:
        """Render the palette."""
        self.actions = actions
        table = self.query_one("#actions-table", DataTable)
        table.clear()
        shown = 0
        for index, action in enumerate(actions):
            if (
                self.filter_text
                and self.filter_text.lower()
                not in f"{action.name} {action.description}".lower()
            ):
                continue
            name = Text(clip(action.name, 22))
            if action.destructive:
                name.stylize(colour(self.app, "error"))
            text = action.description
            if action.args:
                text = f"{action.args} · {text}" if text else action.args
            description = Text(clip(text, 30), style=colour(self.app, "text-muted"))
            source = Text(action.source.value, style=colour(self.app, "secondary"))
            table.add_row(name, description, source, key=str(index))
            shown += 1
        self.query_one("#actions-count", Static).update(
            f"{shown} actions · from justfile and cli"
        )

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Selection follows the cursor."""
        if event.row_key is not None and event.row_key.value is not None:
            self.selected = self.actions[int(event.row_key.value)]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a row runs it (the table consumes the key itself)."""
        if event.row_key is not None and event.row_key.value is not None:
            self.selected = self.actions[int(event.row_key.value)]
        self.action_run_selected()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the palette."""
        self.filter_text = event.value
        self.show_actions(self.actions)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter moves to the list."""
        self.action_focus_list()

    def action_focus_list(self) -> None:
        """Focus the palette."""
        self.query_one("#actions-table", DataTable).focus()

    # ------------------------------------------------------------------- run
    def action_run_selected(self) -> None:
        """Run the highlighted action, confirming a destructive one."""
        action = self.selected
        if action is None:
            return
        if self.process is not None and self.process.poll() is None:
            self.app.notify("an action is still running — k kills it", timeout=3)
            return
        if action.destructive:
            self.app.push_screen(
                ConfirmScreen(
                    f"Run {action.name}?", "marked destructive by the project"
                ),
                lambda yes: self.ask_args(action) if yes else None,
            )
        else:
            self.ask_args(action)

    def ask_args(self, action: Action) -> None:
        """Prompt for the arguments the action needs, then start it.

        An empty answer, like escape, cancels: an action that declares
        ``args`` cannot run without them, so there is nothing to start.
        """
        if not action.args:
            self.start(action)
            return
        self.app.push_screen(
            PromptScreen(f"{action.name} {action.args}", action.args),
            lambda text: self.start_with(action, text),
        )

    def start_with(self, action: Action, text: str | None) -> None:
        """Split the prompt's answer the way a shell would, then start."""
        if not text:
            self.app.notify(f"{action.name} needs {action.args}", timeout=3)
            return
        try:
            args = shlex.split(text)
        except ValueError as exc:  # unbalanced quote — shown, not swallowed
            self.report_error("arguments", exc)
            return
        self.start(action, args)

    def start(self, action: Action, args: list[str] | None = None) -> None:
        """Start ``action`` and stream its output."""
        log = self.query_one("#actions-log", RichLog)
        log.clear()
        try:
            process = self.adapter.run(action.name, args or [])
        except Exception as exc:  # noqa: BLE001 — shown, not hidden
            self.report_error("run", exc)
            return
        self.process = process
        self.running = action
        self.started_at = self.now()
        self.query_one("#actions-right", Panel).set_title(
            f"running · {action.name} · pid {process.pid}"
        )
        self.query_one("#actions-state", Static).update("[$primary]●[/] running")
        self.run_worker(
            lambda: self._stream(process, action),
            thread=True,
            exclusive=True,
            group="stream",
            exit_on_error=False,
        )

    def _stream(self, process: subprocess.Popen[str], action: Action) -> None:
        app = self.app
        stdout = process.stdout
        if stdout is not None:
            for line in stdout:
                app.call_from_thread(self.append_line, line.rstrip("\n"))
        code = process.wait()
        app.call_from_thread(self.finished, action, code)

    def append_line(self, line: str) -> None:
        """One line of stdout."""
        self.query_one("#actions-log", RichLog).write(line)

    def finished(self, action: Action, code: int) -> None:
        """Turn the exit code into the final state."""
        took = elapsed(self.started_at, self.now())
        if code == 0:
            state = f"[$success]✓[/] {action.name} · exit 0 · {took}"
        else:
            state = f"[$error]✗[/] {action.name} · exit {code} · {took}"
        self.query_one("#actions-state", Static).update(state)
        self.query_one("#actions-right", Panel).set_title(f"finished · {action.name}")

    def _tick(self) -> None:
        if self.process is not None and self.process.poll() is None and self.running:
            self.query_one("#actions-right", Panel).set_title(
                f"running · {self.running.name}"
                f" · {elapsed(self.started_at, self.now())}"
                f" · pid {self.process.pid}"
            )

    def action_kill(self) -> None:
        """Terminate the running subprocess."""
        if self.process is None or self.process.poll() is not None:
            self.app.notify("nothing running", timeout=2)
            return
        self.process.terminate()
        self.app.notify("terminate sent", timeout=2)

    def action_copy(self) -> None:
        """Copy the selected action's command line."""
        if self.selected is not None:
            command = self.selected.name
            if self.selected.args:
                command = f"{command} {self.selected.args}"
            self.app.copy_to_clipboard(command)
            self.app.notify("copied command", timeout=2)
