"""``ShellApp``: header, tabs, the screens, footer, keys, theme, palette.

A project instantiates it with its three adapters, a data source and its
own screens; everything else is the shell's. Numbered keys switch tabs
(1–5 standard, 6+ project), ``?`` opens help, ``/`` focuses the current
filter, ``^p`` the command palette, ``r`` refreshes, ``t`` flips the theme,
``q`` quits.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from functools import partial
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.command import DiscoveryHit, Hit, Hits, Provider
from textual.widgets import ContentSwitcher

from lynkeus.adapters import ActionsAdapter, DataSource, RunsAdapter, StatusAdapter
from lynkeus.models import Action, Health
from lynkeus.screens import (
    ActionsScreen,
    DataScreen,
    HelpScreen,
    QueryScreen,
    RunsScreen,
    ShellScreen,
    StatusScreen,
)
from lynkeus.theme import FLEXOKI_DARK, FLEXOKI_LIGHT
from lynkeus.widgets import ShellFooter, ShellHeader, TabBar


class ShellCommands(Provider):
    """Command palette entries: tabs, refresh, theme, and every project action."""

    async def search(self, query: str) -> Hits:
        """Match the query against tab names, shell verbs and actions."""
        app = self.app
        assert isinstance(app, ShellApp)
        matcher = self.matcher(query)
        for key, slug, title in app.tabs:
            name = f"go to {title}"
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    partial(app.action_tab_slug, slug),
                    help=f"key {key}",
                )
        for name, callback in (
            ("refresh", app.action_refresh),
            ("toggle theme", app.action_toggle_theme),
        ):
            score = matcher.match(name)
            if score > 0:
                yield Hit(score, matcher.highlight(name), callback)
        for action in app.actions_cache:
            name = f"run {action.name}"
            score = matcher.match(name)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(name),
                    partial(app.start_action, action),
                    help=action.description,
                )

    async def discover(self) -> Hits:
        """With an empty query, list the tabs."""
        app = self.app
        assert isinstance(app, ShellApp)
        for key, slug, title in app.tabs:
            yield DiscoveryHit(
                f"go to {title}", partial(app.action_tab_slug, slug), help=f"key {key}"
            )


class ShellApp(App[None]):
    """The shared shell. See the module docstring for the keys."""

    TITLE = "lynkeus"
    COMMANDS = App.COMMANDS | {ShellCommands}
    BINDINGS = [
        Binding("question_mark", "tab_slug('help')", "help", show=False),
        Binding("slash", "focus_filter", "filter", show=False),
        Binding("r", "refresh", "refresh", show=False),
        Binding("t", "toggle_theme", "theme", show=False),
        Binding("q", "quit", "quit", show=False),
        *[Binding(str(n), f"tab({n})", f"tab {n}", show=False) for n in range(1, 10)],
    ]
    CSS = """
    Screen { layout: vertical; background: $background; color: $foreground; }
    /* ...but a modal must dim the screen it was opened from, not replace it:
       the rule above would otherwise paint it opaque, and the prompt for an
       action's arguments would hide the very row being acted on. This lives
       here, not in the widgets' DEFAULT_CSS, because App.CSS outranks it, and
       it names `ModalScreen` rather than this shell's own two, so a modal a
       project defines is dimmed by the same rule. */
    ModalScreen { background: $background 60%; }
    #shell-body { height: 1fr; }
    DataTable { background: transparent; }
    DataTable > .datatable--header { background: transparent; color: $text-muted; }
    DataTable > .datatable--cursor { background: $panel; color: $foreground; }
    Tree > .tree--cursor { background: $panel; color: $foreground; }
    Tree > .tree--guides { color: $border; }
    ListView > ListItem.--highlight { background: $panel; }
    Toast { background: $panel; }
    * {
        scrollbar-size: 1 1;
        scrollbar-background: $background;
        scrollbar-background-hover: $background;
        scrollbar-background-active: $background;
        scrollbar-color: $border;
        scrollbar-color-hover: $text-muted;
        scrollbar-color-active: $primary;
        scrollbar-corner-color: $background;
    }
    RichLog, DataTable { overflow-x: hidden; }
    Panel > Static, Panel > VerticalScroll > Static {
        text-wrap: nowrap; text-overflow: ellipsis;
    }
    """

    def __init__(
        self,
        *,
        project: str,
        status_adapter: StatusAdapter,
        runs_adapter: RunsAdapter,
        actions_adapter: ActionsAdapter,
        source: DataSource,
        subtitle: str = "",
        project_screens: Sequence[ShellScreen] = (),
        saved_queries: dict[str, str] | None = None,
        version: str = "",
        poll_seconds: float = 5.0,
        clock: Callable[[], datetime] | None = None,
        state_dir: Path | None = None,
        help_extra: str = "",
    ) -> None:
        super().__init__()
        self.project = project
        self.subtitle = subtitle
        self.status_adapter = status_adapter
        self.runs_adapter = runs_adapter
        self.actions_adapter = actions_adapter
        self.source = source
        self.project_screens = list(project_screens)
        self.saved_queries = dict(saved_queries or {})
        self.version = version
        self.poll_seconds = poll_seconds
        self.clock = clock
        self.state_dir = state_dir
        self.help_extra = help_extra
        self.actions_cache: list[Action] = []
        self.standard: list[ShellScreen] = [
            StatusScreen(status_adapter),
            RunsScreen(runs_adapter),
            DataScreen(source),
            QueryScreen(source, self.saved_queries, state_dir),
            ActionsScreen(actions_adapter),
        ]
        self.help_screen = HelpScreen(help_extra)
        self.tabs: list[tuple[str, str, str]] = [
            (str(i + 1), s.SLUG, s.TITLE) for i, s in enumerate(self.standard)
        ]
        self.tabs += [
            (str(6 + i), s.SLUG, s.TITLE) for i, s in enumerate(self.project_screens)
        ]
        self.tabs.append(("?", self.help_screen.SLUG, self.help_screen.TITLE))
        self.current_slug = self.standard[0].SLUG

    # --------------------------------------------------------------- compose
    def compose(self) -> ComposeResult:
        """Header, tabs, the switcher, footer."""
        yield ShellHeader(self.project, self.subtitle)
        yield TabBar(self.tabs, divider_after=len(self.standard))
        with ContentSwitcher(initial=self.current_slug, id="shell-body"):
            for screen in self.standard:
                yield screen
            for screen in self.project_screens:
                yield screen
            yield self.help_screen
        yield ShellFooter(self.footer_note())

    def footer_note(self) -> str:
        """The right-hand footer text."""
        poll = f"poll {self.poll_seconds:g}s" if self.poll_seconds > 0 else "no poll"
        return f"{poll} · {self.version}" if self.version else poll

    def on_mount(self) -> None:
        """Themes, clock, polling, first load."""
        self.register_theme(FLEXOKI_DARK)
        self.register_theme(FLEXOKI_LIGHT)
        self.theme = FLEXOKI_DARK.name
        self.query_one(ShellHeader).set_clock(self.now())
        if self.clock is None:
            self.set_interval(
                30, lambda: self.query_one(ShellHeader).set_clock(self.now())
            )
        if self.poll_seconds > 0:
            self.set_interval(self.poll_seconds, self._poll)
        self.load_actions()
        self.screen_for(self.current_slug).activate()
        self.focus_screen(self.current_slug)

    # ------------------------------------------------------------- plumbing
    def now(self) -> datetime:
        """The shell clock; a fixed one in tests."""
        return self.clock() if self.clock is not None else datetime.now()

    def set_health(self, health: Health) -> None:
        """Update the header's health dot."""
        self.query_one(ShellHeader).set_health(health)

    def screen_for(self, slug: str) -> ShellScreen:
        """The screen with ``slug``."""
        for screen in (*self.standard, *self.project_screens, self.help_screen):
            if slug == screen.SLUG:
                return screen
        raise KeyError(slug)

    @property
    def current(self) -> ShellScreen:
        """The visible screen."""
        return self.screen_for(self.current_slug)

    def focus_screen(self, slug: str) -> None:
        """Move focus into the screen's main widget, if it names one."""
        screen = self.screen_for(slug)
        if screen.PRIMARY:
            try:
                screen.query_one(screen.PRIMARY).focus()
                return
            except Exception:  # noqa: BLE001 — fall back to the container
                pass
        screen.focus()

    def load_actions(self) -> None:
        """Cache the action list for the palette."""

        def job() -> None:
            try:
                actions = self.actions_adapter.list()
            except Exception as exc:  # noqa: BLE001 — surfaced, not hidden
                self.call_from_thread(
                    self.notify, f"actions: {exc}", severity="error", timeout=8
                )
                return
            self.call_from_thread(setattr, self, "actions_cache", actions)

        self.run_worker(job, thread=True, group="palette", exit_on_error=False)

    def _poll(self) -> None:
        self.current.poll()

    def start_action(self, action: Action) -> None:
        """Palette entry point: open Actions on ``action`` and start it."""
        actions = self.standard[4]
        assert isinstance(actions, ActionsScreen)
        self.action_tab_slug(actions.SLUG)
        actions.selected = action
        actions.action_run_selected()

    def start_action_named(self, name: str) -> bool:
        """Start the action called ``name``, from the adapter's own list.

        For a project screen that knows a command but not the ``Action``
        describing it — acervo's Pending screen offers the verb that clears
        each row. Resolving through the palette's list rather than building an
        ``Action`` here is what keeps the destructive flag and the argument
        hint attached: a reconstructed action would run ``db downgrade``
        without the confirmation the real one carries.

        Returns False, and says so, when no such action exists.
        """
        for action in self.actions_cache:
            if action.name == name:
                self.start_action(action)
                return True
        self.notify(
            f"no action named {name!r} — the palette lists what there is",
            severity="warning",
            timeout=5,
        )
        return False

    # --------------------------------------------------------------- actions
    def action_tab(self, number: int) -> None:
        """Switch to the tab numbered ``number``."""
        for key, slug, _ in self.tabs:
            if key == str(number):
                self.action_tab_slug(slug)
                return

    def action_tab_slug(self, slug: str) -> None:
        """Switch to the tab with ``slug``; ``query`` inherits a selection."""
        try:
            target = self.screen_for(slug)
        except KeyError:
            return
        previous = self.current
        if slug == "query" and previous is not target:
            sql_text = previous.sql_for_selection()
            if sql_text and isinstance(target, QueryScreen):
                target.prefill(sql_text)
        self.current_slug = slug
        self.query_one(ContentSwitcher).current = slug
        self.query_one(TabBar).set_active(slug)
        target.activate()
        self.focus_screen(slug)

    def action_focus_filter(self) -> None:
        """``/``: focus the current screen's filter."""
        self.current.focus_filter()

    def action_refresh(self) -> None:
        """``r``: reload the current screen."""
        self.current.refresh_data()

    def action_toggle_theme(self) -> None:
        """``t``: dark ↔ light."""
        dark = self.theme == FLEXOKI_DARK.name
        self.theme = FLEXOKI_LIGHT.name if dark else FLEXOKI_DARK.name
        self.current.refresh_data()
