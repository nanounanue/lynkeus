from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest

pytest_plugins = ["lynkeus.testing"]


def _test_dsn() -> str:
    """The disposable database, from the environment or the compose default."""
    dsn = os.environ.get("LYNKEUS_TEST_DSN", "")
    if dsn:
        return dsn
    port = os.environ.get("LYNKEUS_PG_PORT", "11401")
    return f"postgresql://lynkeus:lynkeus@127.0.0.1:{port}/lynkeus_test"


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    """Skip the integration tier unless the database is actually reachable."""
    psycopg = pytest.importorskip("psycopg")
    dsn = _test_dsn()
    try:
        with psycopg.connect(dsn, connect_timeout=3):
            pass
    except psycopg.Error as exc:  # pragma: no cover - depends on the machine
        pytest.skip(f"no PostgreSQL at {dsn.rsplit('@', 1)[-1]}: {exc}")
    return dsn


@pytest.fixture
def sample_schema(pg_dsn: str) -> Iterator[str]:
    """Build one schema holding a table, a view, a matview and an index.

    Every shape the Data screen has to render is present, so the catalogue
    queries in ``PgSource`` are exercised against a real server rather than
    trusted. The schema is named uniquely and dropped even when the test
    fails, so the tier never touches anything it did not create.
    """
    import psycopg
    from psycopg import sql

    name = f"lynkeus_t_{uuid.uuid4().hex[:8]}"
    schema = sql.Identifier(name)
    episodes = sql.Identifier(name, "episodes")
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("create schema {}").format(schema))
        try:
            conn.execute(
                sql.SQL(
                    "create table {} ("
                    " id bigint primary key,"
                    " title text not null,"
                    " minutes integer,"
                    " tags text[])"
                ).format(episodes)
            )
            # COMMENT ON is DDL: it takes no parameters, so the text is
            # composed as a literal rather than bound.
            conn.execute(
                sql.SQL("comment on column {}.title is {}").format(
                    episodes, sql.Literal("what the episode is called")
                )
            )
            conn.execute(
                sql.SQL(
                    "insert into {} values"
                    " (1, 'one', 30, '{{a}}'),"
                    " (2, 'two', 45, '{{b}}'),"
                    " (3, 'three', 60, null)"
                ).format(episodes)
            )
            conn.execute(
                sql.SQL("create index episodes_minutes on {} (minutes)").format(
                    episodes
                )
            )
            conn.execute(
                sql.SQL("create view {} as select * from {} where minutes > 40").format(
                    sql.Identifier(name, "long_episodes"), episodes
                )
            )
            conn.execute(
                sql.SQL(
                    "create materialized view {} as select count(*) as n from {}"
                ).format(sql.Identifier(name, "episode_count"), episodes)
            )
            conn.execute(sql.SQL("analyze {}").format(episodes))
            yield name
        finally:
            conn.execute(sql.SQL("drop schema {} cascade").format(schema))
