"""One snapshot per screen, over the demo adapters (no database)."""

from __future__ import annotations

from dataclasses import replace

from textual.widgets import Input, RichLog, TextArea

from lynkeus.demo import demo_app
from lynkeus.models import Series, Status
from lynkeus.screens import (
    ActionsScreen,
    DataScreen,
    QueryScreen,
    RunsScreen,
    StatusScreen,
)
from lynkeus.testing import settle
from lynkeus.widgets import PromptScreen


def test_status_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app())


def test_runs_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["2"])


def test_data_screen(shell_snapshot) -> None:
    async def select_first_table(pilot) -> None:
        await pilot.press("down", "down")

    assert shell_snapshot(demo_app(), keys=["3"], before=select_first_table)


def test_query_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["4", "ctrl+r"])


def test_actions_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["5"])


def test_help_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["question_mark"])


def test_project_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["6"])


def test_light_theme(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["t"])


async def test_runs_selection_streams_events() -> None:
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("2")
        await settle(pilot)
        runs = app.screen_for("runs")
        assert isinstance(runs, RunsScreen)
        assert runs.selected == "0f3a9c21"
        log = runs.query_one("#run-log", RichLog)
        assert len(log.lines) == 8


async def test_data_to_query_carries_the_selection() -> None:
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("3")
        await settle(pilot)
        await pilot.press("down", "down")
        await settle(pilot)
        data = app.screen_for("data")
        assert isinstance(data, DataScreen)
        assert data.selected is not None
        await pilot.press("4")
        await settle(pilot)
        query = app.screen_for("query")
        assert isinstance(query, QueryScreen)
        editor = query.query_one("#query-editor", TextArea)
        assert f"from {data.selected.schema}.{data.selected.name}" in editor.text


async def test_action_runs_as_subprocess_and_reports_exit_code() -> None:
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("5")
        await settle(pilot)
        await pilot.press("enter")
        await settle(pilot, ticks=10)
        actions = app.screen_for("actions")
        assert isinstance(actions, ActionsScreen)
        assert actions.process is not None
        assert actions.process.wait() == 0
        await settle(pilot, ticks=5)
        state = actions.query_one("#actions-state")
        assert "exit 0" in str(state.render())


async def test_an_action_that_needs_arguments_prompts_for_them() -> None:
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("5", "down")
        await settle(pilot)
        actions = app.screen_for("actions")
        assert isinstance(actions, ActionsScreen)
        assert actions.selected is not None
        assert actions.selected.args == "CONFIG"

        await pilot.press("enter")
        await settle(pilot)
        prompt = app.screen
        assert isinstance(prompt, PromptScreen)
        assert actions.process is None  # nothing started before the answer

        prompt.query_one("#prompt", Input).value = "example/dirtyduck.yaml"
        await pilot.press("enter")
        await settle(pilot, ticks=10)
        assert actions.process is not None
        assert actions.process.wait() == 0
        await settle(pilot, ticks=5)
        log = actions.query_one("#actions-log", RichLog)
        assert "example/dirtyduck.yaml" in str(log.lines[0])


async def test_cancelling_the_prompt_starts_nothing() -> None:
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("5", "down", "enter")
        await settle(pilot)
        assert isinstance(app.screen, PromptScreen)

        await pilot.press("escape")
        await settle(pilot)
        actions = app.screen_for("actions")
        assert isinstance(actions, ActionsScreen)
        assert actions.process is None


async def test_a_quiet_sparkline_says_so_instead_of_drawing_a_flat_line() -> None:
    app = demo_app()
    status_screen = app.screen_for("status")
    assert isinstance(status_screen, StatusScreen)
    live = status_screen.adapter.status

    def quiet() -> Status:
        loud = live()
        return replace(
            loud, series=[Series("runs per day", [0.0] * 14, "none in 14 d")]
        )

    status_screen.adapter.status = quiet  # type: ignore[method-assign]
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        panel = str(status_screen.query_one("#status-runs").render())
        assert "none in 14 d" in panel
        assert "▁▁▁" not in panel


async def test_a_modal_dims_its_context_instead_of_replacing_it() -> None:
    """The app's `Screen` rule paints every screen opaque, modals included.

    A prompt that blanks the cockpit behind it loses the row the user was
    acting on, and a screenshot of one shows a dialog in a void.
    """
    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("5", "down", "enter")
        await settle(pilot)
        assert isinstance(app.screen, PromptScreen)
        assert app.screen.styles.background.a < 1.0, (
            "the modal is opaque, so the screen it was opened from is hidden"
        )
