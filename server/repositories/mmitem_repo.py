from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_item():
    sql = """
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
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

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
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
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
                mlchno,
                mldlfg,
                mldpfg
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, 0, '0', '1'
            )
            RETURNING mlitemiy
        """, (
            code, name,
            brand_id, filter_id, prty_id, stkr_id, sgdr_id,
            warehouse, pnpr,
            inc1, inc2, inc3, inc4, inc5, inc6, inc7, inc8,
            quantity, unit,
            user, now,
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
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
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
                mlchno    = mlchno + 1,
                mlcsdt    = %s,
                mlcsid    = %s
            WHERE mlitemiy = %s
              AND mldlfg = '0'
        """, (
            code, name,
            brand_id, filter_id, prty_id, stkr_id, sgdr_id,
            warehouse, pnpr,
            inc1, inc2, inc3, inc4, inc5, inc6, inc7, inc8,
            quantity, unit,
            user, now,
            now,    # mlcsdt  ← updated on edit
            user,   # mlcsid  ← updated on edit
            item_id,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete ───────────────────────────────────────────────────────────────

def delete_item(item_id, user):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            UPDATE barcode.mmitem
            SET
                mldlfg = '1',
                mlchid = %s,
                mlchdt = %s,
                mlchno = mlchno + 1
            WHERE mlitemiy = %s
              AND mldlfg = '0'
        """, (user, now, item_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()