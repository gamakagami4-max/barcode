# server/repositories/mmtbnm_repo.py

from datetime import datetime
from server.db import get_connection


# ── Internal helper ───────────────────────────────────────────────────────────

def _resolve_or_create_connection(cur, conn_name: str, user: str, now: datetime) -> int:
    """
    Return the mnconciy for conn_name.
    If no active mmconc row exists yet, insert one and return its new PK.
    """
    cur.execute(
        """
        SELECT mnconciy FROM barcode.mmconc
        WHERE mnname = %s AND mndlfg <> '1'
        LIMIT 1
        """,
        (conn_name,),
    )
    row = cur.fetchone()
    if row:
        return row[0]

    cur.execute(
        """
        INSERT INTO barcode.mmconc (
            mnname,
            mnrgid, mnrgdt,
            mnchid, mnchdt,
            mncsdt, mncsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING mnconciy
        """,
        (conn_name, user, now, user, now, now, user),
    )
    return cur.fetchone()[0]


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_source_data() -> list[dict]:
    """
    Return all active mmtbnm rows joined with mmconc, newest first.
    Each dict has keys: pk, conn_name, table_name, query,
                        added_by, added_at, changed_by, changed_at, changed_no
    """
    sql = """
        SELECT
            t.motbnmiy   AS pk,
            c.mnname     AS conn_name,
            t.moname     AS table_name,
            COALESCE(t.mousrm, '') AS query,
            t.morgid     AS added_by,
            t.morgdt     AS added_at,
            t.mochid     AS changed_by,
            t.mochdt     AS changed_at,
            t.mochno     AS changed_no
        FROM barcode.mmtbnm  t
        JOIN barcode.mmconc  c ON c.mnconciy = t.moconciy
        WHERE t.modlfg <> '1'
        ORDER BY t.morgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_connection_table_map() -> dict[str, list[str]]:
    """
    Return {conn_name: [table_name, ...]} for populating the cascade combo.
    Only includes active rows from both tables.
    """
    sql = """
        SELECT DISTINCT c.mnname, t.moname
        FROM barcode.mmtbnm  t
        JOIN barcode.mmconc  c ON c.mnconciy = t.moconciy
        WHERE t.modlfg <> '1'
          AND c.mndlfg <> '1'
        ORDER BY c.mnname, t.moname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        mapping: dict[str, list[str]] = {}
        for conn_name, table_name in cur.fetchall():
            mapping.setdefault(conn_name, []).append(table_name)
        return mapping
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_source_data(conn_name: str, table_name: str, query: str, user: str = "Admin") -> int:
    """
    Insert a new mmtbnm row.
    Reuses an existing mmconc row for conn_name if one exists; creates one otherwise.
    Returns the new motbnmiy PK.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        conciy = _resolve_or_create_connection(cur, conn_name, user, now)

        cur.execute(
            """
            INSERT INTO barcode.mmtbnm (
                moname, moconciy,
                morgid, morgdt,
                mochid, mochdt,
                mocsdt, mocsid,
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


# ── Update ────────────────────────────────────────────────────────────────────

def update_source_data(pk: int, conn_name: str, table_name: str,
                       query: str, old_changed_no: int, user: str = "Admin"):
    """
    Update the mmtbnm row identified by pk.
    Resolves (or creates) the mmconc FK for conn_name.
    Increments mochno automatically.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        conciy = _resolve_or_create_connection(cur, conn_name, user, now)

        cur.execute(
            """
            UPDATE barcode.mmtbnm SET
                moname   = %s,
                moconciy = %s,
                mousrm   = %s,
                mochid   = %s,
                mochdt   = %s,
                mochno   = %s
            WHERE motbnmiy = %s
            """,
            (table_name, conciy, query, user, now, old_changed_no + 1, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_source_data(pk: int, user: str = "Admin"):
    """
    Soft-delete by setting modlfg = '1'.
    The row remains in the DB but is excluded from all reads.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmtbnm SET
                modlfg = '1',
                mochid = %s,
                mochdt = %s
            WHERE motbnmiy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()