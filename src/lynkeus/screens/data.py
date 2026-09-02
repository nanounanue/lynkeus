"""Data: every schema and relation in a tree; the selected one in detail.

Reads only ``DataSource``: the catalog, sizes, columns, indexes and a few
sample rows. ``4`` from here opens the Query screen on the selected table.
"""

from __future__ import annotations

from collections import defaultdict

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import Input, Static, Tree

from lynkeus.models import TableDetail, TableInfo
from lynkeus.screens import ShellScreen
from lynkeus.text import clip, count
from lynkeus.widgets import Panel, colour


class DataScreen(ShellScreen):
    """The third tab."""

    SLUG = "data"
    TITLE = "Data"
    KEYS = (("enter", "more rows"), ("y", "copy columns"), ("4", "query this table"))
    PRIMARY = "#data-tree"

    BINDINGS = [
        Binding("enter", "more_rows", "more rows", show=False),
        Binding("y", "copy", "copy columns", show=False),
        Binding("escape", "focus_tree", "back", show=False),
    ]

    DEFAULT_CSS = """
    DataScreen Horizontal { height: 1fr; }
    DataScreen #data-left { width: 42; }
    DataScreen #data-left Tree { height: 1fr; background: transparent; }
    DataScreen #data-left Input {
        height: 1; border: none; padding: 0; background: $surface;
    }
    DataScreen #data-right { width: 1fr; padding: 0 0 0 1; }
    DataScreen #data-detail { height: auto; }
    """

    def __init__(self, source, **kwargs) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.source = source
        self.tables: list[TableInfo] = []
        self.filter_text = ""
        self.selected: TableInfo | None = None
        self.detail: TableDetail | None = None
        self.sample_rows = 3

    def compose(self) -> ComposeResult:
        """Tree on the left, detail on the right."""
        with Horizontal():
            with Panel("schemas", id="data-left", classes="-fill"):
                tree: Tree[TableInfo] = Tree("schemas", id="data-tree")
                tree.show_root = False
                tree.guide_depth = 3
                yield tree
                yield Input(placeholder="/ filter", classes="filter", id="data-filter")
            with Panel("table", id="data-right", classes="-fill"), VerticalScroll():
                yield Static("[$text-muted]select a table[/]", id="data-detail")
        yield self.keys_bar()

    # ------------------------------------------------------------------ data
    def refresh_data(self) -> None:
        """Reload the catalog."""
        self.load(self.source.tables, self.show_tables, group="tables")

    def show_tables(self, tables: list[TableInfo]) -> None:
        """Rebuild the tree."""
        self.tables = tables
        tree = self.query_one("#data-tree", Tree)
        tree.clear()
        by_schema: dict[str, list[TableInfo]] = defaultdict(list)
        for info in tables:
            if (
                self.filter_text
                and self.filter_text.lower() not in f"{info.schema}.{info.name}".lower()
            ):
                continue
            by_schema[info.schema].append(info)
        muted = colour(self.app, "text-muted")
        for schema, infos in by_schema.items():
            label = Text(f"{schema}  ")
            label.append(f"{len(infos)} relations", style=muted)
            node = tree.root.add(
                label, expand=len(infos) <= 25 or bool(self.filter_text)
            )
            for info in infos:
                leaf = Text(f"{clip(info.name, 22):<22} ")
                leaf.append(f"{count(info.rows_estimate):>9}", style=muted)
                if info.kind != "table":
                    leaf.append(f" {info.kind}", style=muted)
                node.add_leaf(leaf, data=info)
        if self.selected is not None:
            self.load_detail(self.selected)

    def load_detail(self, info: TableInfo) -> None:
        """Fetch the selected relation."""
        rows = self.sample_rows
        self.load(
            lambda: self.source.table_detail(info.schema, info.name, rows),
            self.show_detail,
            group="detail",
        )

    def show_detail(self, detail: TableDetail) -> None:
        """Render facts, columns, indexes and sample rows."""
        self.detail = detail
        info = detail.info
        panel = self.query_one("#data-right", Panel)
        panel.set_title(f"{info.schema}.{info.name}")
        lines = [
            f"[b]{info.schema}.{info.name}[/b]  "
            f"[$text-muted]{info.kind} · ~{count(info.rows_estimate)} rows[/]"
        ]
        for key, value in detail.facts.items():
            lines.append(f"[$text-muted]{key:<12}[/] {value}")
        lines.append("")
        lines.append("[$primary]columns[/]")
        for column in detail.columns:
            nullable = "" if column.nullable else " [$text-muted]not null[/]"
            note = f"  [$text-muted]{column.note}[/]" if column.note else ""
            lines.append(
                f"  {column.name:<28} [$secondary]{column.type}[/]{nullable}{note}"
            )
        if detail.indexes:
            lines.append("")
            lines.append("[$primary]indexes[/]")
            for index in detail.indexes:
                using = (
                    index.definition.split(" USING ", 1)[-1]
                    if " USING " in index.definition
                    else index.definition
                )
                lines.append(
                    f"  {index.name:<28} [$text-muted]{clip(using, 48)}[/]"
                    f"  {index.size}"
                )
        if detail.sample and detail.sample.columns:
            sample = detail.sample
            lines.append("")
            lines.append(
                f"[$primary]sample[/] [$text-muted]· {len(sample.rows)} rows"
                f" · {sample.elapsed_ms:.0f} ms[/]"
            )
            widths = [max(len(c), 6) for c in sample.columns]
            header = "  ".join(
                clip(c, 18).ljust(min(w, 18))
                for c, w in zip(sample.columns, widths, strict=True)
            )
            lines.append(f"  [$text-muted]{header}[/]")
            for row in sample.rows:
                cells = []
                for value, width in zip(row, widths, strict=True):
                    text = "∅" if value is None else str(value)
                    cells.append(clip(text, 18).ljust(min(width, 18)))
                lines.append("  " + "  ".join(cells))
        self.query_one("#data-detail", Static).update("\n".join(lines))

    # --------------------------------------------------------------- actions
    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        """Selection follows the cursor."""
        info = event.node.data
        if isinstance(info, TableInfo) and info != self.selected:
            self.selected = info
            self.sample_rows = 3
            self.load_detail(info)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Enter on a relation shows more sample rows."""
        if isinstance(event.node.data, TableInfo):
            self.action_more_rows()

    def on_input_changed(self, event: Input.Changed) -> None:
        """Filter the tree."""
        self.filter_text = event.value
        self.show_tables(self.tables)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter returns focus to the tree."""
        self.action_focus_tree()

    def action_focus_tree(self) -> None:
        """Focus the tree."""
        self.query_one("#data-tree", Tree).focus()

    def action_more_rows(self) -> None:
        """Show 20 sample rows instead of 3."""
        if self.selected is None:
            return
        self.sample_rows = 20 if self.sample_rows < 20 else 3
        self.load_detail(self.selected)

    def action_copy(self) -> None:
        """Copy the column list as JSON."""
        if self.detail is not None:
            self.copy_json(self.detail.columns)

    def sql_for_selection(self) -> str | None:
        """A ``select *`` over the selected relation."""
        if self.selected is None:
            return None
        return f"select *\nfrom {self.selected.schema}.{self.selected.name}\nlimit 100;"

    def poll(self) -> None:
        """The catalog does not change under the user; polling does nothing."""
