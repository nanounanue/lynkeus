"""Help: the keys, the tabs, what feeds each screen."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from lynkeus.screens import ShellScreen
from lynkeus.widgets import Panel

_TEXT = """\
[b]tabs[/b]      [$primary]1[/] Status   [$primary]2[/] Runs   [$primary]3[/] Data   [$primary]4[/] Query   [$primary]5[/] Actions   [$primary]6+[/] the project's own screens

[b]everywhere[/b]
  [$primary]?[/]   this help            [$primary]/[/]   filter the current list        [$primary]^p[/]  command palette
  [$primary]r[/]   refresh              [$primary]t[/]   toggle dark / light theme      [$primary]q[/]   quit

[b]Status[/b]    database facts, last runs, pending work — every line is a query, never a stored flag
[b]Runs[/b]      [$primary]l[/] focus log   [$primary]k[/] kill   [$primary]o[/] open in browser   [$primary]y[/] copy as json   [$primary]esc[/] back to the list
[b]Data[/b]      [$primary]enter[/] more sample rows   [$primary]y[/] copy columns   [$primary]4[/] open the table in Query
[b]Query[/b]     [$primary]^enter[/] / [$primary]^r[/] run   [$primary]x[/] {explain}   [$primary]y[/] copy json   [$primary]e[/] export csv   [$primary]s[/] save   [$primary]d[/] delete   [$primary]esc[/] leave the editor
[b]Actions[/b]   [$primary]enter[/] run   [$primary]k[/] kill   [$primary]y[/] copy command — a subprocess of the project's CLI, never a parallel code path

[$text-muted]Every read is a query inside a read-only transaction. Mutations only happen through Actions,
and the exit code of the subprocess is the run's state.[/]
"""


class HelpScreen(ShellScreen):
    """Reached with ``?``."""

    SLUG = "help"
    TITLE = "Help"
    KEYS = (("esc", "back"),)
    BINDINGS = [Binding("escape", "back", "back", show=False)]

    def __init__(self, extra: str = "", **kwargs) -> None:  # noqa: ANN001
        super().__init__(**kwargs)
        self.extra = extra

    def compose(self) -> ComposeResult:
        """The help text in one panel, with the source's own word for ``x``."""
        # The key bar reads ``explain_label`` off the source; the help has to
        # say the same thing, or a SQLite cockpit contradicts its own key bar.
        explain = str(
            getattr(
                getattr(self.app, "source", None), "explain_label", "explain analyze"
            )
        )
        text = _TEXT.format(explain=explain) + (
            f"\n[b]project[/b]\n{self.extra}\n" if self.extra else ""
        )
        with Panel("help", classes="-fill"), VerticalScroll():
            yield Static(text)
        yield self.keys_bar()

    def action_back(self) -> None:
        """Escape returns to the first tab."""
        self.app.action_tab_slug("status")  # type: ignore[attr-defined]

    def refresh_data(self) -> None:
        """Static."""

    def poll(self) -> None:
        """Static."""
