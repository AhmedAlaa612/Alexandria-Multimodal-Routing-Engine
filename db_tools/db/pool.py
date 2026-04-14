"""
Thread-safe connection pool for PostGIS.
"""
from __future__ import annotations

import atexit

from psycopg2 import pool as pg_pool

from db_tools.config import settings

_pool: pg_pool.ThreadedConnectionPool | None = None


def get_pool() -> pg_pool.ThreadedConnectionPool:
    """Lazy-init the connection pool on first call."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=settings.db_pool_min,
            maxconn=settings.db_pool_max,
            host=settings.db_host,
            port=settings.db_port,
            dbname=settings.db_name,
            user=settings.db_user,
            password=settings.db_password,
        )
        atexit.register(_close_pool)
        print(f"[db] Connection pool created ({settings.db_pool_min}-{settings.db_pool_max} conns)")
    return _pool


def _close_pool():
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        print("[db] Connection pool closed")


class PooledConnection:
    """Context manager that borrows/returns a connection from the pool."""

    def __init__(self):
        self._conn = None

    def __enter__(self):
        self._conn = get_pool().getconn()
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            if exc_type:
                self._conn.rollback()
            get_pool().putconn(self._conn)
            self._conn = None
        return False
