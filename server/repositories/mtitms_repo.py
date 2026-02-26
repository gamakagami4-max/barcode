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
            mmumcd   AS uom,
            mmbupc   AS upc,
            mmrgid   AS added_by,
            mmrgdt   AS added_at,
            mmchid   AS changed_by,
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
            mmumcd   AS uom,
            mmbupc   AS upc,
            mmrgid   AS added_by,
            mmrgdt   AS added_at,
            mmchid   AS changed_by,
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
    user: str = "Admin",
) -> str:
    """
    Insert a new mtitms row.
    Satisfies all NOT NULL constraints explicitly.
    """
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
                mmtbfg,
                mmrgid,
                mmrgdt,
                mmadby,
                mmaddt,
                mmchid,
                mmchdt,
                mmchno,
                mmdlfg
            )
            VALUES (
                %s,  -- mmitno
                %s,  -- mmitds
                %s,  -- mmisap
                %s,  -- mmtyp1
                %s,  -- mmtbfg (required)
                %s,  -- mmrgid
                %s,  -- mmrgdt
                %s,  -- mmadby
                %s,  -- mmaddt
                %s,  -- mmchid
                %s,  -- mmchdt
                0,   -- mmchno
                '0'  -- mmdlfg
            )
            RETURNING mmitno
            """,
            (
                item_no,
                description,
                sap_code,
                type1,
                "0",     # mmtbfg default flag
                user,
                now,
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
    sap_code: str | None,
    type1: str | None,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update selected business fields only.
    Uses optimistic locking on mmchno.
    PK (mmitno) is not updatable.
    """
    existing = fetch_mtitms_by_pk(pk)
    if existing is None:
        raise Exception(f"Record '{pk}' not found.")

    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mtitms
            SET
                mmitds = %s,
                mmisap = %s,
                mmtyp1 = %s,
                mmchid = %s,
                mmchdt = %s,
                mmchno = %s
            WHERE mmitno = %s
              AND mmchno = %s
            """,
            (
                description,
                sap_code,
                type1,
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
                mmchid = %s,
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