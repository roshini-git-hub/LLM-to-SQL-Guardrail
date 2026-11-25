"""Database access through a small connection pool.

Connections are opened once and reused (opening a PostgreSQL connection is slow because of
authentication and backend start-up). Every pooled connection is forced to be read-only and
to have a statement timeout, regardless of how the database role is configured.
"""
import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool, sql
from dotenv import load_dotenv

load_dotenv()

_pool = None
_lock = threading.Lock()


def _connect_args() -> dict:
    timeout_ms = int(os.getenv("DB_STATEMENT_TIMEOUT_MS", "5000"))
    return dict(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        options=f"-c default_transaction_read_only=on -c statement_timeout={timeout_ms}",
    )


def _get_pool() -> pool.ThreadedConnectionPool:
    global _pool
    with _lock:
        if _pool is None:
            _pool = pool.ThreadedConnectionPool(
                int(os.getenv("DB_POOL_MIN", "1")),
                int(os.getenv("DB_POOL_MAX", "10")),
                **_connect_args(),
            )
        return _pool


def close_pool():
    global _pool
    with _lock:
        if _pool is not None:
            _pool.closeall()
            _pool = None


class PooledConnection:
    """Looks like a normal psycopg2 connection, but close() returns it to the pool.

    If a role is given the session runs as that role (SET ROLE), so PostgreSQL itself applies
    that role's GRANTs and row-level security to everything the connection does.
    """

    def __init__(self, conn, owner, role=None):
        self._conn = conn
        self._owner = owner
        self._role = role

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if self._conn is None:
            return
        conn = self._conn
        self._conn = None
        broken = bool(conn.closed)
        if not broken:
            try:
                conn.rollback()
                if self._role:
                    cur = conn.cursor()
                    cur.execute("RESET ROLE")
                    conn.commit()
            except Exception:
                broken = True  # never hand a connection with an unknown role back to the pool
        self._owner.putconn(conn, close=broken)


def get_connection(role: str = None) -> PooledConnection:
    p = _get_pool()
    for _ in range(3):
        conn = p.getconn()
        if conn.closed:
            p.putconn(conn, close=True)  # dead connection (e.g. server restarted), try another
            continue
        pooled = PooledConnection(conn, p, role)
        if role:
            try:
                cur = conn.cursor()
                cur.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                conn.commit()  # commit so a later rollback cannot silently undo the role
            except Exception:
                pooled.close()
                raise
        return pooled
    raise psycopg2.OperationalError("Could not get a live database connection")


@contextmanager
def connection(role: str = None):
    """Use as: with connection(role) as conn: ...  The connection always goes back to the pool."""
    conn = get_connection(role)
    try:
        yield conn
    finally:
        conn.close()


def new_connection():
    """A dedicated, non-pooled connection (used for LISTEN, which must stay open)."""
    return psycopg2.connect(**_connect_args())
