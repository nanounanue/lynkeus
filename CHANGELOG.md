# Changelog

Consumers pin git tags, so every entry names the tag. Dates are the tag's
commit date. Breaking changes are marked; everything else is additive.

## [Unreleased]

Raised by the tcs round, the sixth consumer and the first after the freeze.

### Fixed

- `typer_actions` named a sub-app mounted with `app.add_typer(sub)` — where
  the name lives on `typer.Typer(name=...)` rather than on the `add_typer`
  call — by the `repr` of a `DefaultPlaceholder`. The mount name is now
  resolved the way typer resolves it, from the sub-app's own `info` when the
  `TyperInfo` carries none. A regression test covers it.

## [1.0.0] - 2026-09-05

The API freezes. No code changed since 0.3.2: this tag records that five
consumers have landed and the last two needed nothing from the contract.
What "frozen" covers is stated in the README's Status section. From here, new
fields, keyword arguments and adapter attributes are 1.x; a rename or a
removal is a 2.0.

Consumers at the freeze: triage-pg (typer; pins 0.2.1), acervo (argparse;
pins 0.2.1), meio-sim (typer, Dagster; pins 0.3.0), corredor (typer, Dagster;
pins 0.3.0), featurizer (argparse, `python_version >= '3.12'` marker; pins
0.3.2). All of them can move to 1.0.0 without changing a line.

## [0.3.2] - 2026-09-04

Raised by the featurizer round: a run that is a table, not a process.

### Added

- `RunsAdapter` may carry `id_width` (default 8), read by the Runs screen for
  the list, the header, the kill prompt and the cancel notice. A project whose
  run ids are names rather than hashes sets it wider. Documented beside the
  existing `mode` attribute.

### Changed

- A run with no `started_at` shows no `started` label. A label with nothing
  after it read as a bug, not as a fact about the project.
- An `events()` stream that ends at once leaves the log panel empty under the
  adapter's `mode` title.

## [0.3.1] - 2026-09-04

### Fixed

- `parse_just_dump` read a justfile variable assignment as a recipe. Raised by
  the featurizer round; a regression test covers it.

## [0.3.0] - 2026-09-03

Raised by the meio-sim round, the third consumer.

### Added

- `lynkeus.actions`: `parse_just_dump`, `recipe_args`, `just_actions`,
  `typer_actions`, `argparse_actions`, `destructive_by_words` and the
  `SubprocessActions` base class. The first two consumers had each written
  this; the diff between their copies was whitespace and a destructive-name
  rule. `typer_actions` also treats a bare `config: str` parameter as
  required, a rule neither copy had. typer and argparse are imported inside
  the functions that need them, so an argparse consumer inherits no typer.

### Changed

- The modal dimming rule matches `ModalScreen`, not the shell's own two
  modals by name, so a project's own modal is dimmed by the same rule.
- `PgSource.from_env()` accepts `PGDATABASE` without `PGHOST`; a unix-socket
  server is an ordinary local setup. What is still refused is no
  configuration at all.

## [0.2.1] - 2026-09-03

### Fixed

- A modal dimmed the screen it was opened from instead of replacing it.
  `ShellApp.CSS`'s `Screen { background }` rule matched `ModalScreen` and
  painted `ConfirmScreen` and `PromptScreen` opaque, which blanked the cockpit
  behind a confirm dialog. Raised by the acervo round, whose actions write.

## [0.2.0] - 2026-09-03

Raised by the acervo round, the second consumer.

### Changed (breaking)

- `Status.series` is a `list[Series]`, not a `dict[str, list[float]]`. A
  series carries `empty_note`, the wording for the case where there is nothing
  to draw, because a line of zeros and a flat constant line are the same
  picture.

### Added

- `Action.args`: a hint the Actions screen prompts for before starting a
  verb, since running such a verb bare only prints its usage and exits 2.
- An integration test tier against a disposable PostgreSQL (`just db-up`,
  `just test-all`) and CI with three jobs. `just check` is the same gate CI
  applies.

## [0.1.0] - 2026-09-02

Raised by the triage-pg round, the first consumer.

### Added

- `ShellApp`, the six standard screens (Status, Runs, Data, Query, Actions,
  Help), `lynkeus.commands` for the headless verbs, `lynkeus.testing` for
  Pilot-driven and snapshot tests, and `lynkeus.demo` against fake data.

### Changed

- `DataSource.query` and `explain` name their argument `statement`;
  basedpyright rejects a Protocol match on a parameter-name mismatch.
- The Data screen expands a schema by default when it has 25 relations or
  fewer, rather than by schema count, which had left every schema folded on
  a five-schema database.

## [0.0.1] - 2026-09-02

Scaffold: the adapter contract, the models, the Flexoki theme, `PgSource`
with its read-only transaction, and ADR-0001 on why the shell is a shared
package rather than a vendored copy.
