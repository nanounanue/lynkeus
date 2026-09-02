"""The six standard screens and the base every screen, project ones too, extends.

A *screen* here is the body under the shell's header and tabs: a Textual
container the app swaps in a ``ContentSwitcher``. Each one declares a
``SLUG`` (its id and command-palette name), a ``TITLE`` for the tab, and the
``KEYS`` shown in its own key bar above the footer. Reads go through
``load``: the adapter call runs in a thread worker and the result lands on
the UI thread; an exception is logged, shown as a notification and never
swallowed.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any, TypeVar

from loguru import logger
from textual.containers import Vertical
from textual.widgets import Input

from lynkeus.widgets import Keys, KeysBar

T = TypeVar("T")


class ShellScreen(Vertical):
    """Base for standard and project screens."""

    SLUG = "screen"
    TITLE = "Screen"
    KEYS: Keys = ()
    PRIMARY = ""
    """CSS selector of the widget that takes focus when the tab opens."""
    can_focus = True

    DEFAULT_CSS = """
    ShellScreen { height: 1fr; padding: 0 1; }
    ShellScreen > KeysBar { dock: bottom; }
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(id=self.SLUG, **kwargs)

    # ----------------------------------------------------------------- hooks
    def refresh_data(self) -> None:
        """Reload from the adapters. Called on ``r``, on activation, on poll."""

    def poll(self) -> None:
        """Called every poll interval while the screen is active."""
        self.refresh_data()

    def activate(self) -> None:
        """Called when the screen becomes the visible one."""
        self.refresh_data()

    def sql_for_selection(self) -> str | None:
        """A query the Query screen can open for what is selected here."""
        return None

    def focus_filter(self) -> None:
        """Give focus to this screen's filter input, when it has one."""
        try:
            self.query_one("Input.filter", Input).focus()
        except Exception:  # noqa: BLE001 — no filter on this screen
            return

    def now(self) -> datetime:
        """The shell clock (frozen in tests)."""
        return self.app.now()  # type: ignore[attr-defined]

    # --------------------------------------------------------------- workers
    def load(
        self,
        fn: Callable[[], T],
        on_done: Callable[[T], None],
        *,
        group: str = "load",
        exclusive: bool = True,
    ) -> None:
        """Run ``fn`` in a thread; hand its result to ``on_done`` on the UI thread."""
        app = self.app

        def job() -> None:
            try:
                result = fn()
            except Exception as exc:
                logger.exception("{}: {} failed", self.SLUG, group)
                app.call_from_thread(self.report_error, group, exc)
                return
            try:
                app.call_from_thread(on_done, result)
            except Exception as exc:
                logger.exception("{}: rendering {} failed", self.SLUG, group)
                app.call_from_thread(self.report_error, group, exc)

        self.run_worker(
            job, thread=True, exclusive=exclusive, group=group, exit_on_error=False
        )

    def report_error(self, what: str, exc: BaseException) -> None:
        """Surface a failure without hiding it."""
        message = f"{what}: {exc}".strip().splitlines()[0]
        self.app.notify(message, title=self.TITLE, severity="error", timeout=8)

    def keys_bar(self) -> KeysBar:
        """This screen's key bar (compose it last)."""
        return KeysBar(self.KEYS, classes="screen-keys")

    def copy_json(self, payload: Any) -> None:
        """Copy ``payload`` as JSON to the clipboard and say so."""
        import json

        from lynkeus.models import jsonable

        self.app.copy_to_clipboard(json.dumps(jsonable(payload), indent=2))
        self.app.notify("copied as json", timeout=2)


def later(fn: Callable[..., Any], *args: Any) -> Callable[[], Any]:
    """``partial`` with a name that reads well at call sites."""
    return partial(fn, *args)


from lynkeus.screens.actions import ActionsScreen  # noqa: E402
from lynkeus.screens.data import DataScreen  # noqa: E402
from lynkeus.screens.help import HelpScreen  # noqa: E402
from lynkeus.screens.query import QueryScreen  # noqa: E402
from lynkeus.screens.runs import RunsScreen  # noqa: E402
from lynkeus.screens.status import StatusScreen  # noqa: E402

__all__ = [
    "ActionsScreen",
    "DataScreen",
    "HelpScreen",
    "QueryScreen",
    "RunsScreen",
    "ShellScreen",
    "StatusScreen",
    "later",
]
