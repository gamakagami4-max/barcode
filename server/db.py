"""
server/db.py
------------
Database manager supporting:
- PostgreSQL (psycopg)
- SQLite (sqlite3)
"""

import psycopg
import sqlite3
from contextlib import contextmanager
from server.config import POSTGRES_CONFIG, SQLITE_CONFIG


class DatabaseManager:
    def __init__(self):
        self.pg_conn = None
        self.sqlite_conn = None

    # ======================================================
    # CONNECTIONS
    # ======================================================

    def connect_postgres(self):
        if not self.pg_conn:
            self.pg_conn = psycopg.connect(**POSTGRES_CONFIG)
        return self.pg_conn

    def connect_sqlite(self):
        if not self.sqlite_conn:
            self.sqlite_conn = sqlite3.connect(SQLITE_CONFIG["path"])
        return self.sqlite_conn

    # ======================================================
    # CONTEXT MANAGERS
    # ======================================================

    @contextmanager
    def postgres_cursor(self):
        conn = self.connect_postgres()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    @contextmanager
    def sqlite_cursor(self):
        conn = self.connect_sqlite()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    # ======================================================
    # GENERIC HELPERS
    # ======================================================

    def fetch_all_pg(self, query, params=None):
        with self.postgres_cursor() as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_pg(self, query, params=None):
        with self.postgres_cursor() as cursor:
            cursor.execute(query, params)

    def fetch_all_sqlite(self, query, params=None):
        with self.sqlite_cursor() as cursor:
            cursor.execute(query, params or ())
            return cursor.fetchall()

    def execute_sqlite(self, query, params=None):
        with self.sqlite_cursor() as cursor:
            cursor.execute(query, params or ())

    # ======================================================
    # CLEANUP
    # ======================================================

    def close_all(self):
        if self.pg_conn:
            self.pg_conn.close()
            self.pg_conn = None

        if self.sqlite_conn:
            self.sqlite_conn.close()
            self.sqlite_conn = None
