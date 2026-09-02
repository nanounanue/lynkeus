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


def test_from_env_needs_host_and_database_together() -> None:
    with pytest.raises(MissingCredentials):
        PgSource.from_env(env={"PGDATABASE": "x"})
