from datetime import datetime
from server.db import get_connection


# ===============================
# FETCH ALL (Active Only)
# ===============================
def fetch_all_item():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            mlitemiy,
            mlcode,
            mlname,
            mlbrndiy,
            mlfltriy,
            mlprtyiy,
            mlstkriy,
            mlsgdriy,
            mlwhse,
            mlpnpr,
            mlinc1,
            mlinc2,
            mlinc3,
            mlinc4,
            mlinc5,
            mlinc6,
            mlinc7,
            mlinc8,
            mlqtyn,
            mlumit,
            mlrgid,
            mlrgdt,
            mlchid,
            mlchdt,
            mlchno,
            mldpfg
        FROM barcode.mmitem
        WHERE mldlfg = '0'
        ORDER BY mlitemiy DESC
    """)

    columns = [desc[0] for desc in cur.description]
    rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    cur.close()
    conn.close()
    return rows


# ===============================
# CREATE
# ===============================
def create_item(
    code,
    name,
    brand_id,
    filter_id,
    prty_id,
    stkr_id,
    sgdr_id,
    warehouse,
    pnpr,
    inc1,
    inc2,
    inc3,
    inc4,
    inc5,
    inc6,
    inc7,
    inc8,
    quantity,
    unit,
    user,
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        INSERT INTO barcode.mmitem (
            mlcode,
            mlname,
            mlbrndiy,
            mlfltriy,
            mlprtyiy,
            mlstkriy,
            mlsgdriy,
            mlwhse,
            mlpnpr,
            mlinc1,
            mlinc2,
            mlinc3,
            mlinc4,
            mlinc5,
            mlinc6,
            mlinc7,
            mlinc8,
            mlqtyn,
            mlumit,
            mlrgid,
            mlrgdt,
            mlchid,
            mlchdt,
            mlchno,
            mldlfg,
            mldpfg,
            mlcsdt,
            mlcsid
        )
        VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, 0, '0', '1', %s, %s
        )
        RETURNING mlitemiy
    """, (
        code,
        name,
        brand_id,
        filter_id,
        prty_id,
        stkr_id,
        sgdr_id,
        warehouse,
        pnpr,
        inc1,
        inc2,
        inc3,
        inc4,
        inc5,
        inc6,
        inc7,
        inc8,
        quantity,
        unit,
        user,
        now,
        user,
        now,
        now,
        user,
    ))

    pk = cur.fetchone()[0]

    conn.commit()
    cur.close()
    conn.close()

    return pk


# ===============================
# UPDATE
# ===============================
def update_item(
    item_id,
    code,
    name,
    brand_id,
    filter_id,
    prty_id,
    stkr_id,
    sgdr_id,
    warehouse,
    pnpr,
    inc1,
    inc2,
    inc3,
    inc4,
    inc5,
    inc6,
    inc7,
    inc8,
    quantity,
    unit,
    user,
):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE barcode.mmitem
        SET
            mlcode    = %s,
            mlname    = %s,
            mlbrndiy  = %s,
            mlfltriy  = %s,
            mlprtyiy  = %s,
            mlstkriy  = %s,
            mlsgdriy  = %s,
            mlwhse    = %s,
            mlpnpr    = %s,
            mlinc1    = %s,
            mlinc2    = %s,
            mlinc3    = %s,
            mlinc4    = %s,
            mlinc5    = %s,
            mlinc6    = %s,
            mlinc7    = %s,
            mlinc8    = %s,
            mlqtyn    = %s,
            mlumit    = %s,
            mlchid    = %s,
            mlchdt    = %s,
            mlchno    = mlchno + 1
        WHERE mlitemiy = %s
          AND mldlfg = '0'
    """, (
        code,
        name,
        brand_id,
        filter_id,
        prty_id,
        stkr_id,
        sgdr_id,
        warehouse,
        pnpr,
        inc1,
        inc2,
        inc3,
        inc4,
        inc5,
        inc6,
        inc7,
        inc8,
        quantity,
        unit,
        user,
        now,
        item_id,
    ))

    conn.commit()
    cur.close()
    conn.close()


# ===============================
# DELETE (Soft Delete)
# ===============================
def delete_item(item_id, user):
    conn = get_connection()
    cur = conn.cursor()

    now = datetime.now()

    cur.execute("""
        UPDATE barcode.mmitem
        SET
            mldlfg = '1',
            mlchid = %s,
            mlchdt = %s,
            mlchno = mlchno + 1
        WHERE mlitemiy = %s
          AND mldlfg = '0'
    """, (
        user,
        now,
        item_id,
    ))

    conn.commit()
    cur.close()
    conn.close()