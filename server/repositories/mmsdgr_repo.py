# server/repositories/mmsdgr_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_sdgr() -> list[dict]:
    sql = """
        SELECT
            s.masgdriy   AS pk,
            c.mnname     AS conn_name,
            t.moname     AS table_name,
            COALESCE(s.maqlsv, '') AS query,
            s.maengn     AS engine,
            s.margid     AS added_by,
            s.margdt     AS added_at,
            s.machid     AS changed_by,
            s.machdt     AS changed_at,
            s.machno     AS changed_no
        FROM barcode.mmsdgr  s
        JOIN barcode.mmconc  c ON c.mnconciy = s.maconciy
        JOIN barcode.mmtbnm  t ON t.motbnmiy = s.matbnmiy
        WHERE s.madlfg <> '1'
        ORDER BY s.margdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_sdgr_by_id(sdgr_id: int) -> dict | None:
    sql = """
        SELECT
            s.masgdriy   AS pk,
            c.mnname     AS conn_name,
            t.moname     AS table_name,
            COALESCE(s.maqlsv, '') AS query,
            s.maengn     AS engine,
            s.margid     AS added_by,
            s.margdt     AS added_at,
            s.machid     AS changed_by,
            s.machdt     AS changed_at,
            s.machno     AS changed_no
        FROM barcode.mmsdgr  s
        JOIN barcode.mmconc  c ON c.mnconciy = s.maconciy
        JOIN barcode.mmtbnm  t ON t.motbnmiy = s.matbnmiy
        WHERE s.masgdriy = %s
          AND s.madlfg <> '1'
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (sdgr_id,))
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_sdgr(conciy: int, tbnmiy: int, qlsv: str, engn: str,
                user: str = "Admin") -> int:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcode.mmsdgr (
                maconciy, matbnmiy,
                maqlsv,   maengn,
                margid,   margdt,
                machid,   machdt,
                macsdt,   macsid
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING masgdriy
            """,
            (conciy, tbnmiy, qlsv, engn, user, now, user, now, now, user),
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

def update_sdgr(pk: int, conciy: int, tbnmiy: int,
                qlsv: str, engn: str, old_changed_no: int,
                user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmsdgr SET
                maconciy = %s,
                matbnmiy = %s,
                maqlsv   = %s,
                maengn   = %s,
                machid   = %s,
                machdt   = %s,
                machno   = %s
            WHERE masgdriy = %s
              AND madlfg <> '1'
            """,
            (conciy, tbnmiy, qlsv, engn, user, now, old_changed_no + 1, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_sdgr(pk: int, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmsdgr SET
                madlfg = '1',
                machid = %s,
                machdt = %s
            WHERE masgdriy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Column introspection ──────────────────────────────────────────────────────

def fetch_table_columns(schema: str, table_name: str) -> list[str]:
    """
    Returns column names from information_schema for the given schema.table.
    Strips any leading schema prefix from table_name (e.g. 'dbo.Orders' → 'Orders').
    """
    tbl = table_name.split(".")[-1]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
            ORDER BY ordinal_position
            """,
            (schema, tbl),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()