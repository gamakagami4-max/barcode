from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mtitms() -> list[dict]:
    sql = """
        SELECT
            mmitno   AS pk,
            mmitds   AS description,
            mmisap   AS sap_code,
            mmpono   AS po_no,
            mmbrad   AS brand,
            mmwho    AS warehouse,
            mmtyp1   AS type1,
            mmtyp2   AS type2,
            mmweig   AS weight,
            mmcont AS qty,
            mmumcd   AS uom,
            mmbupc   AS upc,
            mmrgid   AS added_by,
            mmrgdt   AS added_at,
            mmchby   AS changed_by,
            mmchdt   AS changed_at,
            mmchno   AS changed_no
        FROM barcodesap.mtitms
        WHERE mmdlfg <> '1'
        ORDER BY mmrgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_mtitms_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            mmitno   AS pk,
            mmitds   AS description,
            mmisap   AS sap_code,
            mmpono   AS po_no,
            mmbrad   AS brand,
            mmwho    AS warehouse,
            mmtyp1   AS type1,
            mmtyp2   AS type2,
            mmweig   AS weight,
            mmcont AS qty,
            mmumcd   AS uom,
            mmbupc   AS upc,
            mmrgid   AS added_by,
            mmrgdt   AS added_at,
            mmchby   AS changed_by,
            mmchdt   AS changed_at,
            mmchno   AS changed_no
        FROM barcodesap.mtitms
        WHERE mmitno = %s
          AND mmdlfg <> '1'
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (pk,))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_mtitms(
    item_no: str,
    description: str | None,
    sap_code: str | None,
    type1: str | None,
    warehouse: str | None,
    part_no: str | None,
    qty: int,
    uom: str,
    user: str = "Admin",
) -> str:

    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.mtitms (
                mmitno,
                mmitds,
                mmisap,
                mmtyp1,
                mmwho,
                mmpono,
                mmcont,
                mmumcd,
                mmtbfg,
                mmrgid,
                mmrgdt,
                mmadby,
                mmaddt,
                mmchno,
                mmdlfg
            )
            VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                '0',
                %s, %s,
                %s, %s,
                0,
                '0'
            )
            RETURNING mmitno
            """,
            (
                item_no,
                description,
                sap_code,
                type1,
                warehouse,
                part_no,
                qty,
                uom,
                user,
                now,
                user,
                now,
            ),
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

def update_mtitms(
    pk: str,
    description: str | None,
    type1: str | None,
    warehouse: str | None,
    part_no: str | None,
    qty: int,
    uom: str,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update editable business fields.
    Uses optimistic locking on mmchno.
    """
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mtitms
            SET
                mmitds = %s,
                mmtyp1 = %s,
                mmwho  = %s,
                mmpono = %s,
                mmcont = %s,
                mmumcd = %s,
                mmchby = %s,
                mmchdt = %s,
                mmchno = %s
            WHERE mmitno = %s
              AND mmchno = %s
            """,
            (
                description,
                type1,
                warehouse,
                part_no,
                qty,
                uom,
                user,
                now,
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

def soft_delete_mtitms(pk: str, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mtitms
            SET
                mmdlfg = '1',
                mmchby = %s,
                mmchdt = %s,
                mmchno = mmchno + 1
            WHERE mmitno = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()