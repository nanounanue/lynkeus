"""Building an ``ActionsAdapter`` from a justfile and a CLI, without a third copy.

Every consumer so far discovered the same three things: ``just --dump`` is the
only way to read recipes with their comments, a recipe or verb that needs an
argument must say so or ``enter`` on it only prints usage, and the subprocess
has to be started with colour off and line buffering on or the output pane
lags a stage behind. triage-pg and acervo each wrote that twice, near enough
identically that the diff was whitespace and a destructive-name rule; meio-sim
would have been the third. Drift starts at copy two.

A project supplies what is genuinely its own — which of its actions are
destructive, and which CLI to enumerate — and inherits the parsing::

    class MeioActions(SubprocessActions):
        prefix = "meio-platform"
        destructive = frozenset({"just db-reset"})

        def list(self) -> list[Action]:
            return just_actions(self.cwd, self.is_destructive) + typer_actions(
                cli_app, self.prefix, self.is_destructive
            )

``argparse_actions`` is the same for a project whose CLI is argparse, and
neither importer costs a runtime dependency: typer and argparse are imported
inside the function that needs them, so a consumer that uses one never pays
for the other.
"""

from __future__ import annotations

import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lynkeus.models import Action, ActionSource
from lynkeus.text import clip

#: Words that make an action destructive wherever they appear in its name or
#: description, so a recipe added next month is covered without anyone
#: remembering this list exists. acervo learned the need the hard way: on
#: 2026-08-24 a `migrate-roundtrip` recipe ran `alembic downgrade base` against
#: the live database and destroyed 2,302 documents.
DESTRUCTIVE_WORDS = re.compile(
    r"\b(drop|downgrade|destroy|truncate|delete|rebuild|purge|reset|clean|prune)\b",
    re.IGNORECASE,
)

_RECIPE = re.compile(r"^(?P<name>[A-Za-z0-9_-]+)(?P<params>[^:#]*):(?P<deps>.*)$")

#: A predicate over ``(name, description)`` deciding whether the shell confirms
#: before starting an action.
Destructive = Callable[[str, str], bool]


def destructive_by_words(name: str, description: str) -> bool:
    """Default rule: the name or description contains a destructive word."""
    return bool(DESTRUCTIVE_WORDS.search(f"{name} {description}"))


def recipe_args(params: str) -> str:
    """The just parameters a recipe cannot run without, as a usage hint.

    ``just`` takes ``NAME`` as required, ``NAME="x"`` as defaulted, ``*NAME``
    as zero-or-more and ``+NAME`` as one-or-more; ``$NAME`` exports it. Only
    the first and last forms stop a bare ``just recipe`` from running, so only
    those are prompted for — ``just test *ARGS`` still runs the whole suite on
    ``enter``.
    """
    required: list[str] = []
    for param in params.split():
        if "=" in param or param.startswith("*"):
            continue
        bare = param.lstrip("+$")
        if bare:
            required.append(f"{bare}..." if param.startswith("+") else bare)
    return " ".join(required)


def parse_just_dump(text: str, destructive: Destructive | None = None) -> list[Action]:
    """``just --dump`` into actions; the preceding comment is the description."""
    is_destructive = destructive or destructive_by_words
    actions: list[Action] = []
    comment = ""
    for line in text.splitlines():
        if line.startswith("#"):
            comment = line.lstrip("#").strip()
            continue
        if not line or line[0].isspace():
            continue
        match = _RECIPE.match(line)
        if match is None:
            comment = ""
            continue
        name = match.group("name")
        if name == "default":
            comment = ""
            continue
        full = f"just {name}"
        description = comment or full
        actions.append(
            Action(
                full,
                description,
                ActionSource.JUST,
                is_destructive(full, description),
                args=recipe_args(match.group("params")),
            )
        )
        comment = ""
    return actions


def just_actions(
    cwd: Path, destructive: Destructive | None = None, timeout: float = 10.0
) -> list[Action]:
    """Every recipe of the justfile in ``cwd``, or nothing when there is none.

    A justfile that fails to parse comes back as a single action describing the
    failure rather than as a shorter list: a palette silently missing half its
    recipes reads as a project that has none.
    """
    just = shutil.which("just")
    if just is None or not (cwd / "justfile").exists():
        return []
    dump = subprocess.run(  # noqa: S603 — `just` off PATH, no shell
        [just, "--dump"],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if dump.returncode != 0:
        why = _first_line(dump.stderr) or "no output"
        return [Action("just --dump", f"failed: {clip(why, 70)}", ActionSource.JUST)]
    return parse_just_dump(dump.stdout, destructive)


def typer_actions(
    cli_app: Any, prefix: str, destructive: Destructive | None = None
) -> list[Action]:
    """Every verb of a ``typer.Typer`` app, introspected rather than imported.

    ``typer`` is not a dependency of this package — the argparse consumers must
    not inherit it — so the app arrives as ``Any`` and the one import happens
    here, where a project that calls this has typer by definition.
    """
    from typer.models import ArgumentInfo

    is_destructive = destructive or destructive_by_words

    def entry(name: str, command: Any) -> Action:
        doc = command.help or (command.callback.__doc__ if command.callback else "")
        description = clip(_first_line(doc), 80)
        return Action(
            name,
            description,
            ActionSource.CLI,
            is_destructive(name, description),
            args=_typer_args(command.callback, ArgumentInfo),
        )

    def verb(command: Any) -> str:
        if command.name:
            return str(command.name)
        return command.callback.__name__.replace("_", "-") if command.callback else "?"

    actions = [
        entry(f"{prefix} {verb(command)}", command)
        for command in cli_app.registered_commands
    ]
    for group in cli_app.registered_groups:
        if group.typer_instance is None:
            continue
        for command in group.typer_instance.registered_commands:
            actions.append(entry(f"{prefix} {group.name} {verb(command)}", command))
    return actions


def argparse_actions(
    parser: Any, prefix: str, destructive: Destructive | None = None
) -> list[Action]:
    """Every subcommand of an ``argparse`` parser, with its help as description.

    argparse offers no public way to enumerate subcommands with their help:
    ``add_subparsers`` returns an action whose ``choices`` maps names to
    subparsers and whose ``_choices_actions`` carries the help strings, in
    registration order. Both are private, and reading them is still better than
    a second hand-maintained list of verbs that drifts from the first.
    """
    import argparse

    is_destructive = destructive or destructive_by_words
    actions: list[Action] = []
    for action in parser._actions:  # noqa: SLF001 — see the docstring
        if not isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            continue
        for choice in action._choices_actions:  # noqa: SLF001
            name = f"{prefix} {choice.dest}"
            description = clip(_first_line(choice.help), 80)
            actions.append(
                Action(
                    name,
                    description,
                    ActionSource.CLI,
                    is_destructive(name, description),
                    args=_argparse_args(action.choices[choice.dest]),
                )
            )
    return actions


class SubprocessActions:
    """``ActionsAdapter.run``: the project's own command line, as a subprocess.

    The shell never runs project code in-process, so this is the one place work
    starts. ``prefix`` is the console script; when it is not on ``PATH`` — an
    editable install that was never ``uv sync``'d, a checkout run from source —
    ``module`` is used as ``python -m`` instead of failing with ``FileNotFound``.

    Subclasses implement :meth:`list`.
    """

    #: The console script the CLI verbs are named with (``"meio-platform"``).
    prefix: str = ""
    #: ``python -m`` fallback when ``prefix`` is not on ``PATH``.
    module: str = ""
    #: Action names that are always confirmed, whatever their wording.
    destructive: frozenset[str] = frozenset()

    def __init__(self, cwd: Path | None = None) -> None:
        self.cwd = cwd or Path.cwd()

    def is_destructive(self, name: str, description: str) -> bool:
        """Named outright, or carrying a destructive word."""
        return name in self.destructive or destructive_by_words(name, description)

    def list(self) -> list[Action]:  # pragma: no cover — subclasses implement it
        """Every action the palette may offer."""
        raise NotImplementedError

    def run(self, name: str, args: list[str]) -> subprocess.Popen[str]:
        """Start the recipe or verb; stdout and stderr merged, line buffered.

        ``NO_COLOR`` and ``TERM=dumb`` because the output pane renders text,
        not escape sequences, and ``PYTHONUNBUFFERED`` because a stage that
        buffers its stdout shows nothing until it exits — which looks exactly
        like a hung run.
        """
        argv = shlex.split(name) + list(args)
        names_the_cli = bool(argv) and bool(self.prefix) and argv[0] == self.prefix
        if names_the_cli and shutil.which(self.prefix) is None:
            if not self.module:
                raise FileNotFoundError(
                    f"{self.prefix} is not on PATH and no `module` fallback is "
                    f"set on {type(self).__name__} — run `uv sync`, or set "
                    "`module` to the CLI's importable path"
                )
            argv = [sys.executable, "-m", self.module, *argv[1:]]
        env = {**os.environ, "PYTHONUNBUFFERED": "1", "NO_COLOR": "1", "TERM": "dumb"}
        return subprocess.Popen(  # noqa: S603 — argv, no shell
            argv,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env,
        )


def _first_line(text: str | None) -> str:
    if not text:
        return ""
    lines = [line for line in text.strip().splitlines() if line.strip()]
    return lines[0].strip() if lines else ""


def _typer_args(callback: Any, argument_info: type) -> str:
    """The metavars of the arguments a typer verb cannot run without.

    typer prints a required argument in its usage line as the upper-cased
    parameter name (``triage predictlist MODEL_ID``); the palette shows the
    same string and the shell prompts for it. Options and defaulted arguments
    are left out — the verb runs without them.

    Both declaration styles count. ``config: str = typer.Argument(...)`` carries
    an ``ArgumentInfo``, but a bare ``config: str`` is just as positional and
    just as required, and meio-sim's CLI is written that way throughout: reading
    only the explicit form would offer ``meio-platform validate`` as a verb that
    runs bare and then exits 2 on its own usage — the bug ``args`` exists to fix.
    """
    import inspect

    if callback is None:
        return ""
    try:
        parameters = inspect.signature(callback).parameters
    except (TypeError, ValueError):  # pragma: no cover — a builtin as callback
        return ""
    names: list[str] = []
    for name, parameter in parameters.items():
        if parameter.kind in (parameter.VAR_POSITIONAL, parameter.VAR_KEYWORD):
            continue
        if _is_context(parameter):
            continue
        info = _argument_of(parameter, argument_info)
        if info is None:
            # A bare positional with no default: typer makes it required.
            if parameter.default is inspect.Parameter.empty and not _is_option(
                parameter
            ):
                names.append(name.upper())
            continue
        required = (
            info.default is ...
            if info is parameter.default
            else parameter.default is inspect.Parameter.empty
        )
        if required:
            names.append(str(info.metavar or name.upper()))
    return " ".join(names)


def _is_context(parameter: Any) -> bool:
    """``ctx: typer.Context`` is filled by typer, never by the user."""
    annotation = parameter.annotation
    return "Context" in getattr(annotation, "__name__", "") or "Context" in str(
        annotation
    )


def _is_option(parameter: Any) -> bool:
    """A parameter whose annotation carries a ``typer.Option`` is a flag."""
    from typer.models import OptionInfo

    if isinstance(parameter.default, OptionInfo):
        return True
    return any(
        isinstance(meta, OptionInfo)
        for meta in getattr(parameter.annotation, "__metadata__", ())
    )


def _argument_of(parameter: Any, argument_info: type) -> Any:
    """The ``typer.Argument`` of a parameter, in either declaration style."""
    if isinstance(parameter.default, argument_info):
        return parameter.default
    for meta in getattr(parameter.annotation, "__metadata__", ()):
        if isinstance(meta, argument_info):
            return meta
    return None


def _argparse_args(subparser: Any) -> str:
    """What an argparse verb cannot run without, as a usage hint."""
    import argparse

    hints: list[str] = []
    for action in getattr(subparser, "_actions", []):  # noqa: SLF001
        if isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
            hints.append("|".join(action.choices))
            continue
        if action.option_strings:
            if action.required:
                hints.append(f"{action.option_strings[-1]} {action.dest.upper()}")
            continue
        if action.nargs in ("?", "*") or action.default is not None:
            continue
        hints.append(action.dest.upper())
    return " ".join(hints)
