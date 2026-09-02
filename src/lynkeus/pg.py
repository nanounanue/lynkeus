"""PostgreSQL access for the shell: env guard, queries, LISTEN.

Credentials come from the ``PG*`` variables or ``DATABASE_URL`` that direnv
loads from the project's ``.envrc``. There is no default host, no prompt and
no fallback: a missing configuration is an explicit error.
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from psycopg import Connection, sql
from psycopg.rows import DictRow, dict_row


class MissingCredentials(RuntimeError):
    """Raised when neither ``PGDATABASE`` + ``PGHOST`` nor ``DATABASE_URL`` is set."""


@dataclass(frozen=True, slots=True)
class PgSource:
    """A connection recipe that psycopg resolves from the environment.

    ``dsn`` is ``DATABASE_URL`` when that is set, else an empty string so that
    psycopg reads the ``PG*`` variables on its own.
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
        """Run one query and return every row as a dict."""
        with self.connect() as conn, conn.cursor() as cur:
            cur.execute(query, params)  # type: ignore[arg-type]
            return list(cur.fetchall())

    def listen(self, channel: str) -> Iterator[str]:
        """Yield notification payloads from ``LISTEN channel`` until closed."""
        with self.connect(autocommit=True) as conn:
            conn.execute(sql.SQL("listen {}").format(sql.Identifier(channel)))
            for note in conn.notifies():
                yield note.payload
