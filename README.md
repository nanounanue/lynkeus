# lynkeus

A shared [Textual](https://textual.textualize.io/) shell for terminal cockpits
over PostgreSQL-backed data projects. It gives every project the same six
screens (Status, Runs, Data, Query, Actions, Help), the same keys, one theme
and a Postgres source that refuses to start without credentials. A project
supplies three small adapters and its own screens. The same data the screens
render is available as JSON from the project's CLI, so an agent reads what a
person watches.

## Why the name

Lynceus (Greek Λυγκεύς, Lynkeus) sailed on the Argo as its lookout. The poets
gave him the sharpest eyes of any mortal and said he could see through wood
and earth. This package is the lookout of a data project. It watches runs,
tables and pending work from the terminal and reports what it sees. It never
steers; steering stays with the project's own CLI, which the shell runs as a
subprocess when asked. The Greek transliteration is the package name because
the Latin spelling was already taken on PyPI. Argos and Panoptes were
considered and dropped, both taken, and Panoptes carries the panopticon along
with it.

## Status

Pre-alpha, version 0.0.1. This release holds the contract (adapters and
models), the theme and the Postgres source. The shell itself, with its six
screens and Pilot test helpers, is being written against its first consumer,
[triage-pg](https://github.com/ccd-ia/triage-pg). The API stays at 0.x until a
third project consumes it; 1.0 freezes it.

## Install

Not published on PyPI. Pin a git tag:

```bash
uv add "lynkeus @ git+https://github.com/nanounanue/lynkeus.git@v0.0.1"
```

Python 3.12 or newer. Runtime dependencies are Textual 6, Rich, psycopg 3 and
loguru.

## Usage

Build a status, then render it for a terminal and for an agent:

```python
from datetime import datetime

from rich.console import Console

from lynkeus import Health, Run, RunState, Status

status = Status(
    project="triage-pg",
    database=Health(connected=True, detail="pg 16"),
    last_runs=[Run("0f3a", "chi311_v3", RunState.RUNNING, datetime(2026, 9, 2, 9, 30))],
)

print(status.to_json()["database"])
Console().print(status.to_rich())
```

The first line prints `{'connected': True, 'detail': 'pg 16'}`; the second
draws a two-column table titled `triage-pg`.

A project plugs into the shell by implementing three protocols from
`lynkeus.adapters`:

| Protocol | Feeds | Reads |
|---|---|---|
| `StatusAdapter` | Status screen, `<proj> status --json` | health, last runs, pending work derived from queries |
| `RunsAdapter` | Runs screen, `<proj> runs list/show/tail` | the project's runs table, `LISTEN` or polling for progress |
| `ActionsAdapter` | Actions palette, `<proj> actions list/run` | `just --dump` plus the project's CLI commands, run as subprocesses |

The Data and Query screens need only `PgSource`, so they cost a project
nothing beyond credentials.

## API

- `lynkeus.adapters` — the three protocols above.
- `lynkeus.models` — `Status`, `Run`, `RunDetail`, `RunEvent`, `Stage`,
  `Action`, `PendingItem`, `Health`; each has `to_json()`, and the screen-level
  ones have `to_rich()`.
- `lynkeus.pg.PgSource` — `from_env()`, `rows(sql, params)`, `listen(channel)`.
  `from_env()` raises `MissingCredentials` instead of guessing a host.
- `lynkeus.theme` — `FLEXOKI_DARK` and `FLEXOKI_LIGHT`, Textual `Theme`
  objects built on the Flexoki palette.

## Configuration

Credentials are read from the environment only: `DATABASE_URL`, or
`PGDATABASE` and `PGHOST` with `PGUSER` and `PGPASSWORD`. In this workspace
direnv loads them from the project's `.envrc`. There is no default host and no
prompt.

## Development

```bash
just sync        # uv sync, all groups
just test        # uv run pytest
just lint        # uv run ruff check
just fmt         # uv run ruff format
just typecheck   # uv run basedpyright
just check       # lint, typecheck, test
```

## Non-goals

- Business logic. The shell reads adapters and runs the project's CLI; it
  decides nothing about cohorts, scenarios or corpora.
- Visualisation beyond sparklines and one plotext chart per screen. Maps,
  surfaces and networks open in the project's existing web console.
- A CLI framework. The command functions are plain callables so that typer and
  argparse projects wire them the same way.
- Authentication. A served shell sits behind a reverse proxy.

## Layout

```
src/lynkeus/
  adapters.py   the three protocols
  models.py     dataclasses with to_json and to_rich
  pg.py         PgSource and the credential guard
  theme.py      Flexoki dark and light
tests/
docs/adr/       decisions, starting with why this is a package
```

Decisions live in `docs/adr/`.
