from datetime import datetime
from server.db import get_connection


# ===============================
# FETCH ALL (Active Only)
# ===============================
def fetch_all_prty():
    conn = get_connection()
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
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()
    return rows

def create_prty(
    ingredient,
    spanish,
    pronunciation,
    german,
    user,
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        INSERT INTO barcode.mmprty (
            mkingr,
            mkspan,
            mkprnc,
            mkjerm,
            mkrgid,
            mkrgdt,
            mkchid,
            mkchdt,
            mkchno,
            mkdlfg,
            mkdpfg,
            mkcsdt,
            mkcsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, '0', '1', %s, %s)
        RETURNING mkprtyiy
    """, (
        ingredient,
        spanish,
        pronunciation,
        german,
        user,
        now,
        user,
        now,
        now,
        user
    ))

    pk = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return pk

def update_prty(
    prty_id,
    ingredient,
    spanish,
    pronunciation,
    german,
    user,
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

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
        prty_id
    ))

    conn.commit()
    cur.close()
    conn.close()

def delete_prty(prty_id, user):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE barcode.mmprty
        SET
            mkdlfg = '1',
            mkchid = %s,
            mkchdt = %s,
            mkchno = mkchno + 1
        WHERE mkprtyiy = %s
          AND mkdlfg = '0'
    """, (
        user,
        now,
        prty_id
    ))

    conn.commit()
    cur.close()
    conn.close()

