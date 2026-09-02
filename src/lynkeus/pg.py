"""PostgreSQL access for the shell: env guard, read-only queries, LISTEN.

Credentials come from the ``PG*`` variables or ``DATABASE_URL`` that direnv
loads from the project's ``.envrc``. There is no default host, no prompt and
no fallback: a missing configuration is an explicit error. Everything the
screens run goes through a ``read only`` transaction that is rolled back, so
the shell cannot write by accident.
"""

from __future__ import annotations

import os
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import psycopg
from psycopg import Connection, sql
from psycopg.rows import DictRow, dict_row

from lynkeus.models import (
    ColumnInfo,
    Health,
    IndexInfo,
    QueryResult,
    TableDetail,
    TableInfo,
)

_SYSTEM_SCHEMAS = ("pg_catalog", "information_schema", "pg_toast")

_TABLES_SQL = """
select n.nspname as schema, c.relname as name,
       case c.relkind when 'r' then 'table' when 'p' then 'table'
                      when 'v' then 'view' when 'm' then 'matview'
                      when 'f' then 'table' end as kind,
       case when c.reltuples < 0 then null else c.reltuples::bigint end as rows_estimate
from   pg_class c
join   pg_namespace n on n.oid = c.relnamespace
where  c.relkind in ('r', 'p', 'v', 'm', 'f')
  and  n.nspname not in ('pg_catalog', 'information_schema', 'pg_toast')
  and  left(n.nspname, 7) <> 'pg_temp'
order by n.nspname, c.relname
"""

_COLUMNS_SQL = """
select a.attname as name,
       format_type(a.atttypid, a.atttypmod) as type,
       not a.attnotnull as nullable,
       coalesce(col_description(a.attrelid, a.attnum), '') as note
from   pg_attribute a
where  a.attrelid = %(rel)s::regclass and a.attnum > 0 and not a.attisdropped
order by a.attnum
"""

_INDEXES_SQL = """
select i.indexname as name, i.indexdef as definition,
       pg_size_pretty(pg_relation_size((quote_ident(i.schemaname) || '.' ||
                                        quote_ident(i.indexname))::regclass)) as size
from   pg_indexes i
where  i.schemaname = %(schema)s and i.tablename = %(name)s
order by i.indexname
"""

_FACTS_SQL = """
select pg_size_pretty(pg_total_relation_size(%(rel)s::regclass)) as total_size,
       pg_size_pretty(pg_relation_size(%(rel)s::regclass))       as table_size,
       pg_size_pretty(pg_indexes_size(%(rel)s::regclass))        as indexes_size,
       s.n_live_tup, s.n_dead_tup,
       greatest(s.last_vacuum, s.last_autovacuum)   as last_vacuum,
       greatest(s.last_analyze, s.last_autoanalyze) as last_analyze
from   (select 1) as one
left join pg_stat_user_tables s
       on s.schemaname = %(schema)s and s.relname = %(name)s
"""


class MissingCredentials(RuntimeError):
    """Raised when neither ``PGDATABASE`` + ``PGHOST`` nor ``DATABASE_URL`` is set."""


@dataclass(frozen=True, slots=True)
class PgSource:
    """A connection recipe that psycopg resolves from the environment.

    ``dsn`` is ``DATABASE_URL`` when that is set, else an empty string so that
    psycopg reads the ``PG*`` variables on its own. A project that resolves
    its database some other way (a ``database.yaml``, a registry) passes the
    libpq conninfo it already has.
    """

    dsn: str = ""

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> PgSource:
        """Build a source from the environment, or raise ``MissingCredentials``.

        Args:
            env: Mapping to read instead of ``os.environ``; used in tests.

        Raises:
            MissingCredentials: when no usable configuration is present.
        """
        env = os.environ if env is None else env
        url = env.get("DATABASE_URL", "")
        if url:
            return cls(dsn=url)
        if env.get("PGDATABASE") and env.get("PGHOST"):
            return cls(dsn="")
        raise MissingCredentials(
            "No PostgreSQL configuration: set PGDATABASE and PGHOST (plus "
            "PGUSER/PGPASSWORD) or DATABASE_URL. In this workspace they come "
            "from the project's .envrc; run `direnv allow` in the project "
            "directory and retry."
        )

    def connect(self, *, autocommit: bool = False) -> Connection[DictRow]:
        """Open a connection with dict rows."""
        return Connection[DictRow].connect(
            self.dsn, autocommit=autocommit, row_factory=dict_row
        )

    def rows(
        self, query: str, params: Sequence[Any] | Mapping[str, Any] | None = None
    ) -> list[DictRow]:
        """Run one statement inside a read-only transaction; return dict rows."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute("set transaction read only")
            cur.execute(query, params)  # type: ignore[arg-type]
            rows = list(cur.fetchall()) if cur.description else []
            conn.rollback()
            return rows

    def health(self) -> Health:
        """Reachability plus the server version, without raising."""
        try:
            with self.connect() as conn:
                row = conn.execute("select current_setting('server_version') as v")
                version = str(row.fetchone()["v"]).split(".")[0]  # type: ignore[index]
        except psycopg.Error as exc:
            return Health(connected=False, detail=str(exc).strip().splitlines()[0])
        return Health(connected=True, detail=f"pg {version}")

    def query(self, statement: str, params: Any = None) -> QueryResult:
        """Run one read-only statement; errors come back in ``QueryResult.error``."""
        started = time.perf_counter()
        try:
            with self.connect() as conn, conn.cursor() as cur:
                cur.execute("set transaction read only")
                cur.execute(statement, params)  # type: ignore[arg-type]
                columns = [d.name for d in cur.description] if cur.description else []
                rows = [list(r.values()) for r in cur.fetchall()] if columns else []
                conn.rollback()
        except psycopg.Error as exc:
            elapsed = (time.perf_counter() - started) * 1000
            return QueryResult([], [], elapsed, str(exc).strip())
        return QueryResult(columns, rows, (time.perf_counter() - started) * 1000)

    def explain(self, statement: str) -> QueryResult:
        """``explain (analyze, buffers)`` of one statement, rolled back."""
        return self.query("explain (analyze, buffers) " + statement)

    def tables(self) -> list[TableInfo]:
        """Every user relation with its kind and a planner row estimate."""
        return [
            TableInfo(r["schema"], r["name"], r["kind"], r["rows_estimate"])
            for r in self.rows(_TABLES_SQL)
        ]

    def table_detail(self, schema: str, name: str, sample: int = 3) -> TableDetail:
        """Columns, indexes, size facts and a few rows of one relation."""
        rel = sql.Identifier(schema, name)
        with self.connect() as conn:
            conn.execute("set transaction read only")
            rel_text = rel.as_string(conn)
            params = {"rel": rel_text, "schema": schema, "name": name}
            columns = [
                ColumnInfo(r["name"], r["type"], r["nullable"], r["note"])
                for r in conn.execute(_COLUMNS_SQL, params).fetchall()
            ]
            indexes = [
                IndexInfo(r["name"], r["definition"], r["size"] or "")
                for r in conn.execute(_INDEXES_SQL, params).fetchall()
            ]
            facts_row = conn.execute(_FACTS_SQL, params).fetchone() or {}
            kind_row = conn.execute(
                "select relkind, case when reltuples < 0 then null"
                " else reltuples::bigint end as est from pg_class"
                " where oid = %(rel)s::regclass",
                params,
            ).fetchone()
            started = time.perf_counter()
            cur = conn.execute(
                sql.SQL("select * from {} limit {}").format(rel, sql.Literal(sample))
            )
            sample_cols = [d.name for d in cur.description] if cur.description else []
            sample_rows = [list(r.values()) for r in cur.fetchall()]
            elapsed = (time.perf_counter() - started) * 1000
            conn.rollback()
        kind = {"v": "view", "m": "matview"}.get(
            str(kind_row["relkind"]) if kind_row else "r", "table"
        )
        facts: dict[str, str] = {}
        if facts_row:
            facts["size"] = (
                f"{facts_row['total_size']} · table {facts_row['table_size']}"
                f" · indexes {facts_row['indexes_size']}"
            )
            if facts_row.get("n_live_tup") is not None:
                facts["live rows"] = f"{facts_row['n_live_tup']:,}"
                facts["dead rows"] = f"{facts_row['n_dead_tup']:,}"
            for key in ("last_vacuum", "last_analyze"):
                value = facts_row.get(key)
                facts[key.replace("_", " ")] = (
                    value.strftime("%Y-%m-%d %H:%M") if value else "never"
                )
        return TableDetail(
            info=TableInfo(schema, name, kind, kind_row["est"] if kind_row else None),
            columns=columns,
            indexes=indexes,
            facts=facts,
            sample=QueryResult(sample_cols, sample_rows, elapsed),
        )

    def listen(
        self, channel: str, timeout: float | None = None
    ) -> Iterator[str | None]:
        """Yield notification payloads from ``LISTEN channel`` until closed.

        With a ``timeout`` (seconds) the generator yields ``None`` whenever
        that long passes without a notification, so a caller can check
        whether it should stop and close the generator; closing releases the
        connection.
        """
        with self.connect(autocommit=True) as conn:
            conn.execute(sql.SQL("listen {}").format(sql.Identifier(channel)))
            while True:
                seen = False
                for note in conn.notifies(timeout=timeout):
                    seen = True
                    yield note.payload
                if timeout is None:
                    return
                if not seen:
                    yield None
