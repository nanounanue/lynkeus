"""The shell chrome: header, tab bar, key bars, footer, panels, confirm dialog.

Every colour is a theme variable (``$primary``, ``$text-muted`` …) so the two
Flexoki themes in ``lynkeus.theme`` are the only place a colour is chosen.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any

from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Static

from lynkeus.models import Health

Keys = Sequence[tuple[str, str]]


def colour(app: App[Any], name: str) -> str:
    """Resolve a theme variable (``primary``, ``text-muted`` …) to its colour."""
    return app.get_css_variables().get(name, "")


def styled(app: App[Any], text: str, name: str) -> Text:
    """A Rich ``Text`` coloured with the theme variable ``name``."""
    return Text(text, style=colour(app, name))


def keys_markup(keys: Keys) -> str:
    """Render ``(key, label)`` pairs as boxed keys with dim labels."""
    return "  ".join(
        f"[$foreground on $panel] {key} [/] [$text-muted]{label}[/]"
        for key, label in keys
    )


class ShellHeader(Static):
    """Project name and subtitle on the left; health dot and clock on the right."""

    DEFAULT_CSS = """
    ShellHeader { height: 1; background: $panel; color: $foreground; padding: 0 1; }
    """

    def __init__(self, project: str, subtitle: str = "") -> None:
        super().__init__("", id="shell-header")
        self.project = project
        self.subtitle = subtitle
        self.health = Health(connected=False, detail="")
        self.clock = "--:--"

    def set_health(self, health: Health) -> None:
        """Update the health dot and re-render."""
        self.health = health
        self.render_now()

    def set_clock(self, now: datetime) -> None:
        """Update the clock and re-render."""
        self.clock = now.strftime("%H:%M")
        self.render_now()

    def render_now(self) -> None:
        """Compose the header line from its parts."""
        dot = (
            "[$success]●[/] pg ok" if self.health.connected else "[$error]●[/] pg down"
        )
        detail = f" [$text-muted]{self.health.detail}[/]" if self.health.detail else ""
        left = f"[b]{self.project}[/b]  [$text-muted]{self.subtitle}[/]"
        right = f"{dot}{detail}  [$text-muted]{self.clock}[/]"
        width = max(0, self.size.width - 2)
        gap = max(1, width - _cell_len(left) - _cell_len(right))
        self.update(left + " " * gap + right)

    def on_resize(self) -> None:
        """Keep the right-hand side flush on resize."""
        self.render_now()


def _cell_len(markup: str) -> int:
    from textual.content import Content

    return Content.from_markup(markup).cell_length


class TabBar(Static):
    """Numbered tabs: the standard five, a divider, then the project's own."""

    DEFAULT_CSS = """
    TabBar { height: 1; background: $surface; color: $text-muted; padding: 0 1; }
    """

    class Selected(Message):
        """A tab was clicked."""

        def __init__(self, slug: str) -> None:
            super().__init__()
            self.slug = slug

    def __init__(
        self, tabs: Sequence[tuple[str, str, str]], divider_after: int
    ) -> None:
        """``tabs`` are ``(key, slug, title)``; a divider follows ``divider_after``."""
        super().__init__("", id="shell-tabs")
        self.tabs = list(tabs)
        self.divider_after = divider_after
        self.active = self.tabs[0][1] if self.tabs else ""

    def set_active(self, slug: str) -> None:
        """Highlight ``slug`` and re-render."""
        self.active = slug
        self.render_now()

    def render_now(self) -> None:
        """Compose the tab strip."""
        parts: list[str] = []
        for index, (key, slug, title) in enumerate(self.tabs):
            if index == self.divider_after:
                parts.append("[$border]│[/]")
            label = f"[$primary]{key}[/] {title}"
            if slug == self.active:
                label = f"[$foreground on $panel]{label}[/]"
            parts.append(f"[@click=app.tab_slug('{slug}')]{label}[/]")
        self.update("  ".join(parts))

    def on_mount(self) -> None:
        """First render."""
        self.render_now()


class KeysBar(Static):
    """A row of boxed keys with labels; a screen's own keys sit above the footer."""

    DEFAULT_CSS = """
    KeysBar { height: 1; padding: 0 1; }
    """

    def __init__(self, keys: Keys, **kwargs: Any) -> None:
        super().__init__(keys_markup(keys), **kwargs)
        self.keys = list(keys)

    def set_keys(self, keys: Keys) -> None:
        """Replace the keys shown."""
        self.keys = list(keys)
        self.update(keys_markup(keys))


STANDARD_KEYS: Keys = (
    ("?", "help"),
    ("/", "filter"),
    ("^p", "palette"),
    ("r", "refresh"),
    ("t", "theme"),
    ("q", "quit"),
)


class ShellFooter(Horizontal):
    """The standard keys on the left, a status note on the right."""

    DEFAULT_CSS = """
    ShellFooter { height: 1; background: $surface; }
    ShellFooter > KeysBar { width: 1fr; }
    ShellFooter > #footer-note { width: auto; color: $text-muted; padding: 0 1; }
    """

    def __init__(self, note: str = "") -> None:
        super().__init__(id="shell-footer")
        self.note = note

    def compose(self) -> ComposeResult:
        """Keys then note."""
        yield KeysBar(STANDARD_KEYS)
        yield Static(self.note, id="footer-note")

    def set_note(self, note: str) -> None:
        """Replace the right-hand note."""
        self.note = note
        self.query_one("#footer-note", Static).update(note)


class Panel(Vertical):
    """A bordered box whose title floats on the top edge, as in the design."""

    DEFAULT_CSS = """
    Panel {
        border: round $border;
        border-title-color: $primary;
        border-title-align: left;
        padding: 0 1;
        height: auto;
    }
    Panel.-fill { height: 1fr; }
    """

    def __init__(self, title: str, *children: Any, **kwargs: Any) -> None:
        super().__init__(*children, **kwargs)
        self.border_title = title

    def set_title(self, title: str) -> None:
        """Replace the floating title."""
        self.border_title = title


class ConfirmScreen(ModalScreen[bool]):
    """``y`` confirms, ``n`` or escape cancels. Used before destructive actions."""

    DEFAULT_CSS = """
    ConfirmScreen { align: center middle; }
    ConfirmScreen > Panel { width: 60; height: auto; background: $surface; }
    ConfirmScreen Static { padding: 1 1; }
    """

    BINDINGS = [
        Binding("y", "answer(True)", "yes"),
        Binding("n", "answer(False)", "no"),
        Binding("escape", "answer(False)", "cancel", show=False),
    ]

    def __init__(self, question: str, detail: str = "") -> None:
        super().__init__()
        self.question = question
        self.detail = detail

    def compose(self) -> ComposeResult:
        """The question, its detail and the two keys."""
        body = f"[b]{self.question}[/b]"
        if self.detail:
            body += f"\n[$text-muted]{self.detail}[/]"
        yield Panel("confirm", Static(body), KeysBar((("y", "yes"), ("n", "no"))))

    def action_answer(self, value: bool) -> None:
        """Close with the answer."""
        self.dismiss(value)


class PromptScreen(ModalScreen[str | None]):
    """One-line text prompt; enter returns the text, escape returns ``None``."""

    DEFAULT_CSS = """
    PromptScreen { align: center middle; }
    PromptScreen > Panel { width: 60; height: auto; background: $surface; }
    """

    BINDINGS = [Binding("escape", "cancel", "cancel", show=False)]

    def __init__(self, title: str, placeholder: str = "") -> None:
        super().__init__()
        self.title_text = title
        self.placeholder = placeholder

    def compose(self) -> ComposeResult:
        """A single input inside a titled panel."""
        from textual.widgets import Input

        yield Panel(self.title_text, Input(placeholder=self.placeholder, id="prompt"))

    def on_mount(self) -> None:
        """Focus the input."""
        from textual.widgets import Input

        self.query_one("#prompt", Input).focus()

    def on_input_submitted(self, event: Any) -> None:
        """Return the typed value."""
        self.dismiss(str(event.value).strip() or None)

    def action_cancel(self) -> None:
        """Return nothing."""
        self.dismiss(None)
