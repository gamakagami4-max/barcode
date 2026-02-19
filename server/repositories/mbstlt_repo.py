# server/repositories/mbstlt_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_stlt() -> list[dict]:
    sql = """
        SELECT
            mestltiy  AS pk,
            mecode    AS code,
            mename    AS name,
            mestsz    AS size,
            medisp    AS disp,
            mergid    AS added_by,
            mergdt    AS added_at,
            mechid    AS changed_by,
            mechdt    AS changed_at,
            mechno    AS changed_no
        FROM barcode.mbstlt
        WHERE medlfg <> '1'
        ORDER BY mergdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_stlt(code: str, name: str, size: str, disp: bool, user: str = "Admin") -> int:
    """
    Insert a new mbstlt row and return its mestltiy PK.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Guard: reuse if code already exists
        cur.execute(
            """
            SELECT mestltiy FROM barcode.mbstlt
            WHERE mecode = %s AND medlfg <> '1'
            LIMIT 1
            """,
            (code,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO barcode.mbstlt (
                mecode, mename, mestsz, medisp,
                mergid, mergdt,
                mechid, mechdt,
                mecsdt, mecsid
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING mestltiy
            """,
            (code, name, size, disp, user, now, user, now, now, user),
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

def update_stlt(pk: int, code: str, name: str, size: str,
                disp: bool, old_changed_no: int, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mbstlt SET
                mecode  = %s,
                mename  = %s,
                mestsz  = %s,
                medisp  = %s,
                mechid  = %s,
                mechdt  = %s,
                mechno  = %s
            WHERE mestltiy = %s
            """,
            (code, name, size, disp, user, now, old_changed_no + 1, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_stlt(pk: int, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mbstlt SET
                medlfg = '1',
                mechid = %s,
                mechdt = %s
            WHERE mestltiy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()