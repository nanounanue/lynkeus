"""One snapshot per screen, over the demo adapters (no database)."""

from __future__ import annotations

from dataclasses import replace

from textual.screen import ModalScreen
from textual.widgets import DataTable, Input, RichLog, Static, TextArea

from lynkeus.demo import demo_app
from lynkeus.models import Run, RunState, Series, Status
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


def test_actions_prompt_over_the_palette(shell_snapshot) -> None:
    """The one snapshot that opens a modal.

    The other eight would have photographed the opaque prompt of v0.2.0 without
    noticing, since none of them opens one; this is the picture that shows the
    palette still readable underneath.
    """
    assert shell_snapshot(demo_app(), keys=["5", "down", "enter"])


def test_runs_named_by_a_project_with_nothing_to_stream(shell_snapshot) -> None:
    """A run that is a table, not a process: a name for an id, no start, no log.

    featurizer's materializations look like this. The id must not be cut to
    eight characters, the header must not print a bare ``started`` label, and
    an event stream that ends at once must leave the panel titled by ``mode``.
    """
    from lynkeus.models import RunDetail, Stage

    class TableRuns:
        mode = "nothing to stream"
        id_width = 20

        def list(self, limit: int = 50) -> list:
            return [
                Run(
                    "example_01.customers",
                    "customers",
                    RunState.SUCCEEDED,
                    detail="104 features / 1 group",
                ),
                Run(
                    "scratch.stores",
                    "stores",
                    RunState.FAILED,
                    detail="5 features / 2 groups · 1 missing",
                ),
            ]

        def show(self, run_id: str) -> RunDetail:
            run = next(r for r in self.list() if r.run_id == run_id)
            return RunDetail(
                run,
                [
                    Stage("group_000", 104, 104),
                    Stage("group_001", 0, 3, "table missing"),
                ],
                {"schema": "example_01", "stem": "customers", "keys": "as_of_date, id"},
            )

        def events(self, run_id: str):
            return iter(())

        def cancel(self, run_id: str) -> None:
            raise RuntimeError("a table, not a process")

    assert shell_snapshot(demo_app(runs_adapter=TableRuns()), keys=["2"])


def test_help_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["question_mark"])


def test_project_screen(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["6"])


def test_light_theme(shell_snapshot) -> None:
    assert shell_snapshot(demo_app(), keys=["t"])


async def test_a_hash_id_shows_its_prefix_not_an_ellipsis() -> None:
    """Eight characters of a uuid are a usable prefix; ``b7e2c4a…`` is not.

    Four of the five consumers key runs by a hash or a uuid at the default
    ``id_width``. Cutting the id through ``clip`` gave them seven characters
    and an ellipsis in the list, the header and the kill prompt, which reads
    as a truncated value rather than as the prefix every CLI prints. The demo's
    ids are exactly eight characters, so the shell's own snapshots never
    tripped on it.
    """
    from lynkeus.models import RunDetail

    class HashRuns:
        mode = "hash ids"

        def list(self, limit: int = 50) -> list:
            return [
                Run(
                    "b7e2c4a1-5d6f-4e8a-9b0c-1d2e3f4a5b6c",
                    "corridor-audition",
                    RunState.SUCCEEDED,
                )
            ]

        def show(self, run_id: str) -> RunDetail:
            return RunDetail(self.list()[0])

        def events(self, run_id: str):
            return iter(())

        def cancel(self, run_id: str) -> None:
            raise RuntimeError("not from here")

    app = demo_app(runs_adapter=HashRuns())
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        await pilot.press("2")
        await settle(pilot)
        runs = app.screen_for("runs")
        assert isinstance(runs, RunsScreen)
        cell = str(runs.query_one("#runs-table", DataTable).get_row_at(0)[1])
        assert cell == "b7e2c4a1"
        header = runs.query_one("#run-header", Static).content
        text = getattr(header, "plain", str(header))
        assert "run b7e2c4a1" in text
        assert "…" not in text


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


async def test_a_project_modal_dims_too() -> None:
    """The rule has to name `ModalScreen`, not the shell's own two modals.

    A project gets its screens from `project_screens` and may push a modal of
    its own — a review queue asking which ruling to file. Naming
    `ConfirmScreen, PromptScreen` would leave that one opaque, which is the
    same bug again in the first repo that writes one.
    """

    class ProjectModal(ModalScreen[None]):
        def compose(self):
            yield Static("file this ruling?")

    app = demo_app()
    async with app.run_test(size=(110, 34)) as pilot:
        await settle(pilot)
        app.push_screen(ProjectModal())
        await settle(pilot)
        assert app.screen.styles.background.a < 1.0, (
            "a project's own modal is opaque, so only the shell's two dim"
        )
