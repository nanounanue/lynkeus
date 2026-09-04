from __future__ import annotations

import pytest

from lynkeus import MissingCredentials, PgSource


def test_from_env_refuses_to_guess() -> None:
    with pytest.raises(MissingCredentials, match="direnv allow"):
        PgSource.from_env(env={})


def test_from_env_prefers_database_url() -> None:
    source = PgSource.from_env(env={"DATABASE_URL": "postgresql:///x"})

    assert source.dsn == "postgresql:///x"


def test_from_env_accepts_pg_variables() -> None:
    source = PgSource.from_env(env={"PGDATABASE": "x", "PGHOST": "h"})

    assert source.dsn == ""


def test_from_env_accepts_a_database_without_a_host() -> None:
    """A unix-socket server is an ordinary local setup, not a missing one.

    meio-sim's own connection rule says so and refuses to require ``PGHOST``;
    a shell stricter than the project it watches would refuse to start against
    a database the project connects to happily.
    """
    source = PgSource.from_env(env={"PGDATABASE": "x"})

    assert source.dsn == ""


def test_from_env_refuses_a_host_with_no_database() -> None:
    """``PGHOST`` alone still leaves libpq to pick the database by OS user."""
    with pytest.raises(MissingCredentials):
        PgSource.from_env(env={"PGHOST": "h"})
