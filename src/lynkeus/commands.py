"""The headless half: what the screens show, printed for a terminal or as JSON.

Plain functions so typer and argparse projects wire them the same way. Each
takes the adapter it reads, prints through a Rich ``Console`` (a table, or
JSON when ``json_out`` is true) and returns the model it printed, so tests
and callers can use the data without parsing output.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any

from rich.console import Console

from lynkeus.adapters import ActionsAdapter, DataSource, RunsAdapter, StatusAdapter
from lynkeus.models import (
    Action,
    QueryResult,
    Run,
    RunDetail,
    RunEvent,
    Status,
    actions_to_rich,
    jsonable,
    runs_to_rich,
)


def _console(console: Console | None) -> Console:
    return console or Console()


def _emit_json(console: Console, payload: Any) -> None:
    console.print_json(json.dumps(jsonable(payload)))


def status(
    adapter: StatusAdapter, *, json_out: bool = False, console: Console | None = None
) -> Status:
    """Print (and return) the project status."""
    out = _console(console)
    result = adapter.status()
    if json_out:
        _emit_json(out, result.to_json())
    else:
        out.print(result.to_rich())
    return result


def runs_list(
    adapter: RunsAdapter,
    limit: int = 20,
    *,
    json_out: bool = False,
    console: Console | None = None,
) -> list[Run]:
    """Print (and return) the most recent runs."""
    out = _console(console)
    runs = adapter.list(limit)
    if json_out:
        _emit_json(out, [run.to_json() for run in runs])
    else:
        out.print(runs_to_rich(runs))
    return runs


def runs_show(
    adapter: RunsAdapter,
    run_id: str,
    *,
    json_out: bool = False,
    console: Console | None = None,
) -> RunDetail:
    """Print (and return) one run with its stages."""
    out = _console(console)
    detail = adapter.show(run_id)
    if json_out:
        _emit_json(out, detail.to_json())
    else:
        out.print(detail.to_rich())
        for key, value in detail.meta.items():
            out.print(f"[dim]{key}[/dim] {value}")
    return detail


def runs_tail(
    adapter: RunsAdapter,
    run_id: str,
    *,
    json_out: bool = False,
    console: Console | None = None,
    limit: int | None = None,
) -> list[RunEvent]:
    """Stream a run's events until the stream ends (or ``limit`` events)."""
    out = _console(console)
    seen: list[RunEvent] = []
    stream = adapter.events(run_id)
    try:
        for event in stream:
            if event is None:
                continue
            seen.append(event)
            if json_out:
                out.print(json.dumps(event.to_json()), soft_wrap=True, markup=False)
            else:
                out.print(
                    f"[dim]{event.at:%H:%M:%S}[/dim] {event.kind:<14} {event.subject}"
                    + (f" [dim]{event.detail}[/dim]" if event.detail else ""),
                )
            if limit is not None and len(seen) >= limit:
                break
    finally:
        close = getattr(stream, "close", None)
        if close is not None:
            close()
    return seen


def query(
    source: DataSource,
    sql_text: str,
    *,
    json_out: bool = False,
    console: Console | None = None,
) -> QueryResult:
    """Run one read-only statement and print its rows."""
    out = _console(console)
    result = source.query(sql_text)
    if result.error:
        out.print(f"[red]error[/red] {result.error}", markup=True)
        return result
    if json_out:
        _emit_json(out, result.records())
    else:
        out.print(result.to_rich())
    return result


def actions_list(
    adapter: ActionsAdapter, *, json_out: bool = False, console: Console | None = None
) -> list[Action]:
    """Print (and return) the actions palette."""
    out = _console(console)
    actions = adapter.list()
    if json_out:
        _emit_json(out, [action.to_json() for action in actions])
    else:
        out.print(actions_to_rich(actions))
    return actions


def actions_run(
    adapter: ActionsAdapter,
    name: str,
    args: Sequence[str] = (),
    *,
    console: Console | None = None,
) -> int:
    """Run one action, stream its stdout, return the exit code."""
    out = _console(console)
    process = adapter.run(name, list(args))
    if process.stdout is not None:
        for line in process.stdout:
            out.print(line.rstrip("\n"), markup=False, highlight=False)
    code = process.wait()
    if code != 0:
        out.print(f"[red]exit {code}[/red]", markup=True)
        sys.stdout.flush()
    return code
