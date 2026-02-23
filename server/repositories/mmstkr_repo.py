# server/repositories/mmstkr_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mmstkr() -> list[dict]:
    sql = """
        SELECT
            mbstkriy AS pk,
            mbname   AS name,
            mbhinc   AS h_in,
            mbwinc   AS w_in,
            mbhpix   AS h_px,
            mbwpix   AS w_px,
            mbrgid   AS added_by,
            mbrgdt   AS added_at,
            mbchid   AS changed_by,
            mbchdt   AS changed_at,
            mbchno   AS changed_no
        FROM barcode.mmstkr
        WHERE mbdlfg <> '1'
        ORDER BY mbrgdt DESC
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

def create_mmstkr(
    name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    user: str = "Admin",
) -> int:
    """
    Insert a new mmstkr row.
    mbchid / mbchdt / mbcsdt / mbcsid are omitted — nullable after ALTER TABLE,
    they should be NULL until a real edit occurs. mbchno starts at 0.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcode.mmstkr (
                mbname,
                mbhinc, mbwinc,
                mbhpix, mbwpix,
                mbrgid, mbrgdt,
                mbchno
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING mbstkriy
            """,
            (name, h_in, w_in, h_px, w_px, user, now, 0),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update (Optimistic Locking) ───────────────────────────────────────────────

def update_mmstkr(
    pk: int,
    name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    old_changed_no: int,
    user: str = "Admin",
):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmstkr
            SET
                mbname = %s,
                mbhinc = %s,
                mbwinc = %s,
                mbhpix = %s,
                mbwpix = %s,
                mbchid = %s,
                mbchdt = %s,
                mbchno = %s
            WHERE mbstkriy = %s
              AND mbchno   = %s
            """,
            (
                name,
                h_in, w_in,
                h_px, w_px,
                user, now,
                old_changed_no + 1,
                pk,
                old_changed_no,
            ),
        )
        if cur.rowcount == 0:
            raise Exception("Record was modified by another user.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete ───────────────────────────────────────────────────────────────

def soft_delete_mmstkr(pk: int, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmstkr
            SET
                mbdlfg = '1',
                mbchid = %s,
                mbchdt = %s,
                mbchno = mbchno + 1
            WHERE mbstkriy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()