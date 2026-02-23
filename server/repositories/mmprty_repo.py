from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_prty():
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT
                mkprtyiy,
                mkingr,
                mkspan,
                mkprnc,
                mkjerm,
                mkrgid,
                mkrgdt,
                mkchid,
                mkchdt,
                mkchno,
                mkdpfg
            FROM barcode.mmprty
            WHERE mkdlfg = '0'
            ORDER BY mkprtyiy DESC
        """)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_prty(
    ingredient,
    spanish,
    pronunciation,
    german,
    user,
):
    """
    Insert a new mmprty row.
    mkchid / mkchdt / mkcsdt / mkcsid are omitted — nullable after ALTER TABLE,
    they should be NULL until a real edit occurs. mkchno starts at 0.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO barcode.mmprty (
                mkingr,
                mkspan,
                mkprnc,
                mkjerm,
                mkrgid,
                mkrgdt,
                mkchno,
                mkdlfg,
                mkdpfg
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0, '0', '1')
            RETURNING mkprtyiy
        """, (
            ingredient,
            spanish,
            pronunciation,
            german,
            user,
            now,
        ))
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update ────────────────────────────────────────────────────────────────────

def update_prty(
    prty_id,
    ingredient,
    spanish,
    pronunciation,
    german,
    user,
):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE barcode.mmprty
            SET
                mkingr = %s,
                mkspan = %s,
                mkprnc = %s,
                mkjerm = %s,
                mkchid = %s,
                mkchdt = %s,
                mkchno = mkchno + 1
            WHERE mkprtyiy = %s
              AND mkdlfg = '0'
        """, (
            ingredient,
            spanish,
            pronunciation,
            german,
            user,
            now,
            prty_id,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete ───────────────────────────────────────────────────────────────

def delete_prty(prty_id, user):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE barcode.mmprty
            SET
                mkdlfg = '1',
                mkchid = %s,
                mkchdt = %s,
                mkchno = mkchno + 1
            WHERE mkprtyiy = %s
              AND mkdlfg = '0'
        """, (user, now, prty_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()