"""Query: saved queries, an editor, a results table. Read-only by construction.

Statements run through ``DataSource.query`` inside a ``read only``
transaction that is rolled back. The project's saved queries come from the
app; the user's own are kept in ``<state_dir>/queries.json``.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import DataTable, ListItem, ListView, Static, TextArea

from lynkeus.models import QueryResult
from lynkeus.screens import ShellScreen
from lynkeus.text import clip
from lynkeus.widgets import KeysBar, Panel, PromptScreen

_MINE = "─ mine ─"


class QueryScreen(ShellScreen):
    """The fourth tab."""

    SLUG = "query"
    TITLE = "Query"
    PRIMARY = "#query-results"
    KEYS = (
        ("^enter", "run"),
        ("x", "explain analyze"),
        ("y", "copy json"),
        ("e", "export csv"),
    )

    BINDINGS = [
        Binding("ctrl+enter", "run", "run", show=False, priority=True),
        Binding("ctrl+r", "run", "run", show=False, priority=True),
        Binding("f5", "run", "run", show=False, priority=True),
        Binding("x", "explain", "explain analyze", show=False),
        Binding("y", "copy", "copy json", show=False),
        Binding("e", "export", "export csv", show=False),
        Binding("s", "save", "save", show=False),
        Binding("d", "delete", "delete", show=False),
        Binding("escape", "leave_editor", "results", show=False),
    ]

    DEFAULT_CSS = """
    QueryScreen Horizontal { height: 1fr; }
    QueryScreen #query-left { width: 30; }
    QueryScreen #query-left ListView { height: 1fr; background: transparent; }
    QueryScreen #query-left KeysBar { height: 1; padding: 0; }
    QueryScreen #query-right { width: 1fr; padding: 0 0 0 1; }
    QueryScreen TextArea { height: 9; border: round $border; }
    QueryScreen TextArea:focus { border: round $primary; }
    QueryScreen #query-status { height: 1; color: $text-muted; padding: 0 1; }
    QueryScreen #query-results { height: 1fr; }
    """

    def __init__(
        self,
        source,
        saved: dict[str, str] | None = None,
        state_dir: Path | None = None,
        **kwargs,
    ) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.source = source
        self.saved = dict(saved or {})
        self.state_dir = state_dir
        self.mine: dict[str, str] = self._load_mine()
        self.result: QueryResult | None = None

    def compose(self) -> ComposeResult:
        """Saved list on the left; editor, status and results on the right."""
        with Horizontal():
            with Panel("saved", id="query-left", classes="-fill"):
                yield ListView(id="query-saved")
                yield KeysBar((("s", "save"), ("d", "delete")))
            with Vertical(id="query-right"):
                editor = TextArea(id="query-editor", show_line_numbers=False)
                editor.border_title = "sql"
                yield editor
                yield Static("[$text-muted]results[/]", id="query-status")
                yield DataTable(
                    cursor_type="row", zebra_stripes=False, id="query-results"
                )
        yield self.keys_bar()

    def on_mount(self) -> None:
        """Fill the saved list once."""
        self.show_saved()
        first = next(iter(self.saved.values()), None)
        if first:
            self.query_one("#query-editor", TextArea).load_text(first)

    def refresh_data(self) -> None:
        """Nothing loads by itself; ``r`` re-runs the editor."""
        if self.query_one("#query-editor", TextArea).text.strip():
            self.action_run()

    def activate(self) -> None:
        """Do not run anything just for becoming visible."""

    def poll(self) -> None:
        """Queries never auto-run."""

    # ----------------------------------------------------------------- saved
    def _mine_path(self) -> Path | None:
        return self.state_dir / "queries.json" if self.state_dir else None

    def _load_mine(self) -> dict[str, str]:
        path = self._mine_path()
        if path is None or not path.exists():
            return {}
        return {str(k): str(v) for k, v in json.loads(path.read_text()).items()}

    def _store_mine(self) -> None:
        path = self._mine_path()
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.mine, indent=2))

    def show_saved(self) -> None:
        """Rebuild the saved list."""
        view = self.query_one("#query-saved", ListView)
        view.clear()
        for name in self.saved:
            view.append(ListItem(Static(name), name=f"saved:{name}"))
        if self.mine:
            view.append(
                ListItem(
                    Static(f"[$text-muted]{_MINE}[/]"), name="divider", disabled=True
                )
            )
            for name in self.mine:
                view.append(ListItem(Static(name), name=f"mine:{name}"))

    def prefill(self, sql_text: str, run: bool = True) -> None:
        """Put ``sql_text`` in the editor (another screen sent it) and run it."""
        self.query_one("#query-editor", TextArea).load_text(sql_text)
        if run:
            self.action_run()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Load a saved query into the editor and run it."""
        name = event.item.name or ""
        kind, _, key = name.partition(":")
        sql_text = self.saved.get(key) if kind == "saved" else self.mine.get(key)
        if sql_text:
            self.prefill(sql_text)

    # ------------------------------------------------------------------- run
    def action_run(self) -> None:
        """Run the editor's text."""
        sql_text = self.query_one("#query-editor", TextArea).text.strip()
        if not sql_text:
            return
        self.query_one("#query-status", Static).update("[$text-muted]running…[/]")
        self.load(lambda: self.source.query(sql_text), self.show_result, group="query")

    def action_explain(self) -> None:
        """Run ``explain analyze`` on the editor's text."""
        sql_text = self.query_one("#query-editor", TextArea).text.strip()
        if not sql_text:
            return
        self.load(
            lambda: self.source.explain(sql_text), self.show_result, group="query"
        )

    def show_result(self, result: QueryResult) -> None:
        """Render rows or the error."""
        self.result = result
        table = self.query_one("#query-results", DataTable)
        table.clear(columns=True)
        status = self.query_one("#query-status", Static)
        if result.error:
            status.update(f"[$error]✗[/] {clip(result.error, 100)}")
            return
        table.add_columns(*result.columns)
        for row in result.rows[:500]:
            table.add_row(*("∅" if v is None else clip(str(v), 40) for v in row))
        shown = min(len(result.rows), 500)
        more = f" (showing {shown})" if shown < len(result.rows) else ""
        status.update(
            f"[$text-muted]results ·[/] {len(result.rows)} rows{more}"
            f" [$text-muted]· {result.elapsed_ms:.0f} ms[/]"
        )

    # --------------------------------------------------------------- actions
    def action_leave_editor(self) -> None:
        """Escape from the editor to the results, so plain keys work again."""
        self.query_one("#query-results", DataTable).focus()

    def action_copy(self) -> None:
        """Copy the result rows as JSON."""
        if self.result is not None and not self.result.error:
            self.copy_json(self.result.records())

    def action_export(self) -> None:
        """Write the result as CSV under the state dir."""
        if self.result is None or self.result.error or self.state_dir is None:
            self.app.notify("nothing to export", timeout=3)
            return
        path = self.state_dir / "exports" / f"{datetime.now():%Y%m%d-%H%M%S}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(self.result.columns)
            writer.writerows(self.result.rows)
        self.app.notify(f"exported {path}", timeout=5)

    def action_save(self) -> None:
        """Save the editor's text under a name."""
        sql_text = self.query_one("#query-editor", TextArea).text.strip()
        if not sql_text:
            return

        def done(name: str | None) -> None:
            if not name:
                return
            self.mine[name] = sql_text
            self._store_mine()
            self.show_saved()

        self.app.push_screen(PromptScreen("save query as", "name"), done)

    def action_delete(self) -> None:
        """Delete the highlighted saved query of mine."""
        view = self.query_one("#query-saved", ListView)
        item = view.highlighted_child
        name = (item.name or "") if item else ""
        kind, _, key = name.partition(":")
        if kind != "mine" or key not in self.mine:
            self.app.notify("only your own queries can be deleted", timeout=3)
            return
        del self.mine[key]
        self._store_mine()
        self.show_saved()

    def focus_filter(self) -> None:
        """``/`` here focuses the editor."""
        self.query_one("#query-editor", TextArea).focus()
