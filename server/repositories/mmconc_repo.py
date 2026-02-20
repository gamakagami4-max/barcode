# server/repositories/mmconc_repo.py

from datetime import datetime
from server.db import get_connection


# ── Engine ────────────────────────────────────────────────────────────────────

def fetch_all_engines() -> list[dict]:
    """
    Return all active engines (sqlite, postgresql).
    Each dict has keys: pk, code, name
    """
    sql = """
        SELECT mpengniy AS pk, mpcode AS code, mpname AS name
        FROM barcode.mmengn
        WHERE mpdlfg <> '1'
        ORDER BY mpname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_engine_id_by_code(code: str) -> int | None:
    """
    Return mpengniy for a given engine code ('sqlite' or 'postgresql').
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT mpengniy FROM barcode.mmengn WHERE mpcode = %s AND mpdlfg <> '1'",
            (code,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    finally:
        conn.close()


# ── Connection ────────────────────────────────────────────────────────────────

def fetch_connections_by_engine(engine_id: int) -> list[dict]:
    """
    Return all active connections for a given engine.
    Each dict has keys: pk, name, engine_id
    """
    sql = """
        SELECT mnconciy AS pk, mnname AS name, mnengniy AS engine_id
        FROM barcode.mmconc
        WHERE mnengniy = %s AND mndlfg <> '1'
        ORDER BY mnname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (engine_id,))
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_engine_connection_map() -> dict[str, list[dict]]:
    """
    Return a map of engine_code → list of connections.
    Shape: { 'postgresql': [{'pk': 1, 'name': 'MyDB'}, ...], 'sqlite': [...] }
    Used for cascading dropdowns: select engine → show its connections.
    """
    sql = """
        SELECT e.mpcode AS engine_code, c.mnconciy AS pk, c.mnname AS conn_name
        FROM barcode.mmengn  e
        LEFT JOIN barcode.mmconc c
            ON c.mnengniy = e.mpengniy
            AND c.mndlfg <> '1'
        WHERE e.mpdlfg <> '1'
        ORDER BY e.mpcode, c.mnname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        mapping: dict[str, list[dict]] = {}
        for engine_code, pk, conn_name in cur.fetchall():
            if engine_code not in mapping:
                mapping[engine_code] = []
            if pk is not None:
                mapping[engine_code].append({"pk": pk, "name": conn_name})
        return mapping
    finally:
        conn.close()


def _resolve_or_create_connection(cur, conn_name: str, engine_id: int,
                                   user: str, now: datetime) -> int:
    """
    Internal helper: return mnconciy for conn_name under the given engine.
    Creates a new mmconc row if none exists.
    """
    cur.execute(
        """
        SELECT mnconciy FROM barcode.mmconc
        WHERE mnname = %s AND mnengniy = %s AND mndlfg <> '1'
        LIMIT 1
        """,
        (conn_name, engine_id),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO barcode.mmconc (
            mnname,   mnengniy,
            mnrgid,   mnrgdt,
            mnchid,   mnchdt,
            mncsdt,   mncsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING mnconciy
        """,
        (conn_name, engine_id, user, now, user, now, now, user),
    )
    return cur.fetchone()[0]


def create_connection_record(conn_name: str, engine_id: int,
                              user: str = "Admin") -> int:
    """
    Insert a new mmconc row under the given engine and return its mnconciy PK.
    Reuses an existing active connection with the same name + engine if found.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        pk = _resolve_or_create_connection(cur, conn_name, engine_id, user, now)
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_table_record(conn_name: str, engine_id: int,
                         table_name: str, query: str,
                         user: str = "Admin") -> int:
    """
    Insert a new mmtbnm row under the given connection + engine.
    Resolves or creates the parent mmconc row automatically.
    Returns the new motbnmiy PK.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        conciy = _resolve_or_create_connection(cur, conn_name, engine_id, user, now)

        cur.execute(
            """
            INSERT INTO barcode.mmtbnm (
                moname,   moconciy,
                morgid,   morgdt,
                mochid,   mochdt,
                mocsdt,   mocsid,
                mousrm
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING motbnmiy
            """,
            (table_name, conciy, user, now, user, now, now, user, query),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()