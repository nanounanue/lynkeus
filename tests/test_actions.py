"""The justfile and CLI parsing every consumer used to write for itself."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest
import typer

from lynkeus.actions import (
    SubprocessActions,
    argparse_actions,
    destructive_by_words,
    just_actions,
    parse_just_dump,
    recipe_args,
    typer_actions,
)
from lynkeus.models import ActionSource

DUMP = """\
# Start the disposable PostgreSQL
db-up:
    docker compose up -d

# Drop every table and load the fixtures again
db-reset confirm:
    ./reset.sh {{confirm}}

replay policy="b0" window="2025-01-01" extra="":
    uv run python scripts/run_replay.py

test *args:
    uv run pytest {{args}}

campaign +files:
    uv run python scripts/run_campaign.py {{files}}

default:
    just --list
"""


def test_a_recipes_comment_becomes_its_description() -> None:
    actions = {a.name: a for a in parse_just_dump(DUMP)}
    assert actions["just db-up"].description == "Start the disposable PostgreSQL"
    assert actions["just db-up"].source is ActionSource.JUST
    assert actions["just replay"].description == "just replay", "no comment, no prose"


def test_a_variable_is_not_a_recipe() -> None:
    """``pg_port := "55432"`` prints like a recipe in ``just --dump`` and is not one.

    Offering it would put an action in the palette that `just` itself refuses
    ("Justfile does not contain recipe"). featurizer's justfile has three.
    """
    dump = 'pg_port   := "55432"\nexport PGURL := "x"\nalias t := test\n\n' + DUMP
    names = {a.name for a in parse_just_dump(dump)}
    assert "just pg_port" not in names
    assert "just export" not in names
    assert "just alias" not in names
    assert "just db-up" in names


def test_default_is_not_an_action() -> None:
    """`just default` only prints the recipe list the shell already renders."""
    assert "just default" not in {a.name for a in parse_just_dump(DUMP)}


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ("confirm", "confirm"),
        ('policy="b0" window="2025-01-01"', ""),
        ("*args", ""),
        ("+files", "files..."),
        ("$FORCE", "FORCE"),
        ("file workers='1'", "file"),
    ],
)
def test_only_the_parameters_that_block_a_bare_run_are_prompted(
    params: str, expected: str
) -> None:
    """`just test *args` still runs the whole suite on enter; `just db-reset` cannot."""
    assert recipe_args(params) == expected


def test_a_destructive_word_anywhere_asks_first() -> None:
    actions = {a.name: a for a in parse_just_dump(DUMP)}
    assert actions["just db-reset"].destructive, "named `reset`"
    assert not actions["just replay"].destructive
    assert destructive_by_words("just migrate", "drop every table")
    assert not destructive_by_words("just build", "compile the package")


def test_a_project_can_name_what_the_words_miss() -> None:
    """`just down` stops the database and carries no destructive word."""

    def rule(name: str, description: str) -> bool:
        return name == "just replay" or destructive_by_words(name, description)

    actions = {a.name: a for a in parse_just_dump(DUMP, rule)}
    assert actions["just replay"].destructive
    assert actions["just db-reset"].destructive, "the words still apply"


def test_no_justfile_is_no_actions_rather_than_an_error(tmp_path: Path) -> None:
    assert just_actions(tmp_path) == []


def test_a_broken_justfile_is_reported_as_an_action(tmp_path: Path) -> None:
    """A palette silently missing half its recipes reads as a project with none."""
    (tmp_path / "justfile").write_text("this is not a justfile\n  ???\n")
    actions = just_actions(tmp_path)
    if not actions:  # `just` is not installed on this machine
        pytest.skip("just is not on PATH")
    assert len(actions) == 1
    assert actions[0].name == "just --dump"
    assert actions[0].description.startswith("failed:")


# --------------------------------------------------------------------- typer

cli = typer.Typer(name="demo")
group = typer.Typer()
cli.add_typer(group, name="runs")


@cli.command()
def validate(config: str) -> None:
    """Check a config without running it.

    The second line is not the description.
    """


@cli.command("db-init")
def db_init(force: bool = False) -> None:
    """Create the schema."""


@group.command("show")
def runs_show(run_id: str, limit: int = 20) -> None:
    """One run with its stages."""


def test_a_typer_verb_reports_its_required_arguments() -> None:
    actions = {a.name: a for a in typer_actions(cli, "demo")}
    assert actions["demo validate"].args == "CONFIG"
    assert actions["demo validate"].description == "Check a config without running it."
    assert actions["demo db-init"].args == "", "a defaulted option is not prompted for"
    assert actions["demo runs show"].args == "RUN_ID", "the group's name is in the verb"


def test_a_typer_command_keeps_the_name_it_was_registered_under() -> None:
    names = {a.name for a in typer_actions(cli, "demo")}
    assert "demo db-init" in names, "not `demo db_init`"


def test_a_sub_app_named_on_itself_is_mounted_under_that_name() -> None:
    """``add_typer(sub)`` with ``Typer(name="fleet")``: the name is on the sub-app.

    typer resolves it from there when it builds the click group; the palette
    read only the ``TyperInfo`` and printed a ``DefaultPlaceholder`` repr in
    the verb. tcs mounts both of its sub-apps this way.
    """
    app = typer.Typer(name="tcs")
    fleet = typer.Typer(name="fleet")
    app.add_typer(fleet)

    @fleet.command("info")
    def fleet_info(fleet_file: str) -> None:
        """Display detailed fleet information."""

    names = [a.name for a in typer_actions(app, "tcs")]
    assert names == ["tcs fleet info"]


def _app_with_hidden_verbs() -> typer.Typer:
    """One visible verb, and a hidden one of each kind ``--help`` leaves out.

    A command hides itself with ``command(hidden=True)``; a group hides every
    verb under it, whether ``add_typer``, the sub-app's callback or the sub-app
    itself says so. triage-pg's ``postmodel kinds --json`` is the first kind.
    """
    app = typer.Typer(name="demo")

    @app.command()
    def shown() -> None:
        """A verb the help lists."""

    @app.command(hidden=True)
    def internal() -> None:
        """Read by a front end, not typed by a person."""

    by_mount = typer.Typer()
    app.add_typer(by_mount, name="mounted", hidden=True)

    @by_mount.command("run")
    def mounted_run() -> None: ...

    by_callback = typer.Typer()
    app.add_typer(by_callback, name="called")

    @by_callback.callback(hidden=True)
    def called_callback() -> None: ...

    @by_callback.command("run")
    def called_run() -> None: ...

    by_itself = typer.Typer(name="itself", hidden=True)
    app.add_typer(by_itself)

    @by_itself.command("run")
    def itself_run() -> None: ...

    return app


def test_a_hidden_typer_verb_is_left_out_as_help_leaves_it_out() -> None:
    names = [a.name for a in typer_actions(_app_with_hidden_verbs(), "demo")]
    assert names == ["demo shown"]


def test_include_hidden_lists_the_hidden_verbs_too() -> None:
    app = _app_with_hidden_verbs()
    names = [a.name for a in typer_actions(app, "demo", include_hidden=True)]
    assert names == [
        "demo shown",
        "demo internal",
        "demo mounted run",
        "demo called run",
        "demo itself run",
    ]


# ------------------------------------------------------------------ argparse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="demo")
    subs = parser.add_subparsers(dest="command")
    scrape = subs.add_parser("scrape", help="Fetch new episodes.")
    scrape.add_argument("feed")
    subs.add_parser("status", help="What the corpus holds.")
    return parser


def test_an_argparse_verb_reports_its_required_arguments() -> None:
    actions = {a.name: a for a in argparse_actions(_parser(), "demo")}
    assert actions["demo scrape"].args == "FEED"
    assert actions["demo scrape"].description == "Fetch new episodes."
    assert actions["demo status"].args == ""


# ---------------------------------------------------------------- subprocess


class _Actions(SubprocessActions):
    prefix = "demo"
    module = "this_module_does_not_exist"

    def list(self):  # noqa: ANN201 — the palette is not what is under test
        return []


def test_a_missing_cli_names_itself_instead_of_raising_filenotfound() -> None:
    """`FileNotFoundError: 'demo'` says nothing about which sync was skipped."""
    actions = _Actions(cwd=Path.cwd())
    with pytest.raises(FileNotFoundError, match="demo is not on PATH"):
        actions.module = ""
        actions.run("demo validate", ["config.yaml"])


def test_a_recipe_runs_even_when_the_cli_is_missing() -> None:
    """The prefix rule must not touch `just`, which is a different program."""
    actions = _Actions(cwd=Path.cwd())
    process = actions.run("python -c 'print(1)'", [])
    assert process.wait() == 0
    assert process.stdout is not None
