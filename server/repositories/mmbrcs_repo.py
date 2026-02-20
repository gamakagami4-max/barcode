from datetime import datetime
from server.db import get_connection


# ---------------------------------------------------
# FETCH ALL (exclude soft-deleted)
# ---------------------------------------------------

def fetch_all_mmbrcs():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM barcode.mmbrcs
        WHERE mmdlfg = '0'
        ORDER BY mmbrcsiy ASC
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()

    return rows


# ---------------------------------------------------
# CREATE
# ---------------------------------------------------

def create_mmbrcs(
    code,
    type_case,
    user
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        INSERT INTO barcode.mmbrcs (
            mmcode,
            mmtyca,
            mmrgid,
            mmrgdt,
            mmchid,
            mmchdt,
            mmchno,
            mmcsdt,
            mmcsid
        )
        VALUES (%s,%s,%s,%s,%s,%s,0,%s,%s)
        RETURNING mmbrcsiy
    """, (
        code,
        type_case,
        user,
        now,
        user,
        now,
        now,
        user,
    ))

    new_id = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return new_id


# ---------------------------------------------------
# UPDATE
# ---------------------------------------------------

def update_mmbrcs(
    mmbrcs_id,
    code,
    type_case,
    user
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE barcode.mmbrcs
        SET
            mmcode = %s,
            mmtyca = %s,
            mmchid = %s,
            mmchdt = %s,
            mmchno = mmchno + 1
        WHERE mmbrcsiy = %s
    """, (
        code,
        type_case,
        user,
        now,
        mmbrcs_id,
    ))

    conn.commit()
    cur.close()
    conn.close()


# ---------------------------------------------------
# SOFT DELETE
# ---------------------------------------------------

def delete_mmbrcs(mmbrcs_id, user):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE barcode.mmbrcs
        SET
            mmdlfg = '1',
            mmchid = %s,
            mmchdt = %s,
            mmchno = mmchno + 1
        WHERE mmbrcsiy = %s
    """, (
        user,
        now,
        mmbrcs_id,
    ))

    conn.commit()
    cur.close()
    conn.close()
