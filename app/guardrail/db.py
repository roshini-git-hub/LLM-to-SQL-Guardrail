"""Database access through a small connection pool.

Connections are opened once and reused (opening a PostgreSQL connection is slow because of
authentication and backend start-up). Every pooled connection is forced to be read-only and
to have a statement timeout, regardless of how the database role is configured.
"""
import os
import threading
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
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
    """Looks like a normal psycopg2 connection, but close() returns it to the pool."""

    def __init__(self, conn, owner):
        self._conn = conn
        self._owner = owner

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        if self._conn is None:
            return
        try:
            if not self._conn.closed:
                self._conn.rollback()
        finally:
            self._owner.putconn(self._conn, close=bool(self._conn.closed))
            self._conn = None


def get_connection() -> PooledConnection:
    p = _get_pool()
    for _ in range(3):
        conn = p.getconn()
        if not conn.closed:
            return PooledConnection(conn, p)
        p.putconn(conn, close=True)  # dead connection (e.g. server restarted), try another
    raise psycopg2.OperationalError("Could not get a live database connection")


@contextmanager
def connection():
    """Use as: with connection() as conn: ...  The connection always goes back to the pool."""
    conn = get_connection()
    try:
        yield conn
    finally:
        conn.close()
