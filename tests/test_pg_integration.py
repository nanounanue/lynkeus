"""The SQL in ``PgSource``, run against a real PostgreSQL.

``test_pg.py`` covers credential resolution with fake environments. These
cover the part four consumers actually depend on: the catalogue queries
behind the Data screen, the read-only guarantee behind Query, and LISTEN
behind the Runs progress log.
"""

from __future__ import annotations

import threading
import time

import psycopg
import pytest
from psycopg import sql

from lynkeus import PgSource

pytestmark = pytest.mark.integration


def test_health_reports_the_server_version(pg_dsn: str) -> None:
    health = PgSource(pg_dsn).health()

    assert health.connected is True
    assert health.detail.startswith("pg ")


def test_health_does_not_raise_when_the_server_is_absent() -> None:
    health = PgSource("postgresql://nobody@127.0.0.1:1/nothing").health()

    assert health.connected is False
    assert health.detail


def test_query_returns_columns_rows_and_timing(pg_dsn: str, sample_schema: str) -> None:
    result = PgSource(pg_dsn).query(
        f'select id, title from "{sample_schema}".episodes order by id'
    )

    assert result.error == ""
    assert result.columns == ["id", "title"]
    assert result.rows == [[1, "one"], [2, "two"], [3, "three"]]
    assert result.elapsed_ms > 0


def test_query_takes_parameters(pg_dsn: str, sample_schema: str) -> None:
    result = PgSource(pg_dsn).query(
        f'select title from "{sample_schema}".episodes where minutes > %s', (40,)
    )

    assert result.rows == [["two"], ["three"]]


def test_query_reports_an_error_instead_of_raising(pg_dsn: str) -> None:
    result = PgSource(pg_dsn).query("select * from no_such_table_at_all")

    assert result.rows == []
    assert "no_such_table_at_all" in result.error


def test_the_shell_cannot_write(pg_dsn: str, sample_schema: str) -> None:
    """A write is refused by the transaction, not by trusting the caller."""
    result = PgSource(pg_dsn).query(f'delete from "{sample_schema}".episodes')

    assert "read-only" in result.error.lower()
    assert PgSource(pg_dsn).query(
        f'select count(*) from "{sample_schema}".episodes'
    ).rows == [[3]]


def test_explain_returns_a_plan(pg_dsn: str, sample_schema: str) -> None:
    result = PgSource(pg_dsn).explain(f'select * from "{sample_schema}".episodes')

    assert result.error == ""
    assert any(
        "Seq Scan" in str(row[0]) or "Scan" in str(row[0]) for row in result.rows
    )


def test_rows_passes_parameters(pg_dsn: str, sample_schema: str) -> None:
    rows = PgSource(pg_dsn).rows(
        f'select title from "{sample_schema}".episodes where id = %(id)s', {"id": 2}
    )

    assert rows == [{"title": "two"}]


def test_tables_finds_each_kind_and_hides_the_catalogue(
    pg_dsn: str, sample_schema: str
) -> None:
    tables = PgSource(pg_dsn).tables()
    mine = {t.name: t for t in tables if t.schema == sample_schema}

    assert mine["episodes"].kind == "table"
    assert mine["long_episodes"].kind == "view"
    assert mine["episode_count"].kind == "matview"
    assert mine["episodes"].rows_estimate == 3
    assert not [t for t in tables if t.schema in ("pg_catalog", "information_schema")]


def test_table_detail_reads_columns_indexes_and_a_sample(
    pg_dsn: str, sample_schema: str
) -> None:
    detail = PgSource(pg_dsn).table_detail(sample_schema, "episodes", sample=2)

    columns = {c.name: c for c in detail.columns}
    assert [c.name for c in detail.columns] == ["id", "title", "minutes", "tags"]
    assert columns["id"].type == "bigint"
    assert columns["title"].nullable is False
    assert columns["minutes"].nullable is True
    assert columns["title"].note == "what the episode is called"

    assert {i.name for i in detail.indexes} == {"episodes_pkey", "episodes_minutes"}
    assert all(i.size for i in detail.indexes)

    assert detail.sample is not None
    assert detail.sample.columns == ["id", "title", "minutes", "tags"]
    assert len(detail.sample.rows) == 2

    assert detail.info.schema == sample_schema
    assert detail.info.kind == "table"

    # The facts are presentation-ready strings, keyed for a reader.
    assert set(detail.facts) == {
        "size",
        "live rows",
        "dead rows",
        "last vacuum",
        "last analyze",
    }
    assert "table" in detail.facts["size"]
    assert detail.facts["live rows"] == "3"
    assert detail.facts["last analyze"] != "never"


def test_table_detail_quotes_an_awkward_name(pg_dsn: str, sample_schema: str) -> None:
    """Identifiers are composed, never interpolated, so odd names still work."""
    with psycopg.connect(pg_dsn, autocommit=True) as conn:
        conn.execute(
            sql.SQL("create table {} (x int)").format(
                sql.Identifier(sample_schema, "odd name")
            )
        )

    detail = PgSource(pg_dsn).table_detail(sample_schema, "odd name")

    assert [c.name for c in detail.columns] == ["x"]


def test_listen_yields_a_payload(pg_dsn: str) -> None:
    source = PgSource(pg_dsn)
    received: list[str | None] = []

    def wait() -> None:
        for payload in source.listen("lynkeus_test_channel"):
            received.append(payload)
            return

    listener = threading.Thread(target=wait, daemon=True)
    listener.start()
    deadline = time.time() + 10
    while listener.is_alive() and time.time() < deadline:
        with psycopg.connect(pg_dsn, autocommit=True) as conn:
            conn.execute("select pg_notify('lynkeus_test_channel', 'run-42')")
        listener.join(timeout=0.5)

    assert received == ["run-42"]


def test_listen_with_a_timeout_yields_a_heartbeat(pg_dsn: str) -> None:
    """The Runs screen needs a chance to stop while nothing is happening."""
    stream = PgSource(pg_dsn).listen("lynkeus_quiet_channel", timeout=0.2)
    try:
        assert next(stream) is None
    finally:
        stream.close()
