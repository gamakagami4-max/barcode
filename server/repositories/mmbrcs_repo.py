from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mmbrcs():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT *
            FROM barcode.mmbrcs
            WHERE mmdlfg = '0'
            ORDER BY mmbrcsiy ASC
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_mmbrcs(code, type_case, user):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO barcode.mmbrcs (
                mmcode,
                mmtyca,
                mmrgid,
                mmrgdt,
                mmchno
            )
            VALUES (%s, %s, %s, %s, 0)
            RETURNING mmbrcsiy
        """, (code, type_case, user, now))
        new_id = cur.fetchone()[0]
        conn.commit()
        return new_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update ────────────────────────────────────────────────────────────────────

def update_mmbrcs(mmbrcs_id, code, type_case, user):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE barcode.mmbrcs
            SET
                mmcode = %s,
                mmtyca = %s,
                mmchid = %s,
                mmchdt = %s,
                mmchno = mmchno + 1
            WHERE mmbrcsiy = %s
        """, (code, type_case, user, now, mmbrcs_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete ───────────────────────────────────────────────────────────────

def delete_mmbrcs(mmbrcs_id, user):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE barcode.mmbrcs
            SET
                mmdlfg = '1',
                mmchid = %s,
                mmchdt = %s,
                mmchno = mmchno + 1
            WHERE mmbrcsiy = %s
        """, (user, now, mmbrcs_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()