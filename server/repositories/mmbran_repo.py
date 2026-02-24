# server/repositories/mmbran_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mmbran() -> list[dict]:
    sql = """
        SELECT
            mbnobr   AS pk,
            mbnama   AS name,
            mbflag   AS flag,
            mbcase   AS case_,
            mbadby   AS ad_by,
            mbaddt   AS ad_dt,
            mbchby   AS ch_by,
            mbchdt   AS ch_dt,
            mbchno   AS changed_no,
            mbrgid   AS added_by,
            mbrgdt   AS added_at,
            mbchid   AS changed_by,
            mbdpfg   AS dp_fg,
            mbdsfg   AS ds_fg,
            mbptfg   AS pt_fg,
            mbptct   AS pt_ct,
            mbptid   AS pt_id,
            mbptdt   AS pt_dt,
            mbsrce   AS source,
            mbusrm   AS user_remark,
            mbitrm   AS item_remark
        FROM barcodesap.mmbran
        WHERE mbdlfg <> 1
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


def fetch_mmbran_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            mbnobr   AS pk,
            mbnama   AS name,
            mbflag   AS flag,
            mbcase   AS case_,
            mbadby   AS ad_by,
            mbaddt   AS ad_dt,
            mbchby   AS ch_by,
            mbchdt   AS ch_dt,
            mbchno   AS changed_no,
            mbrgid   AS added_by,
            mbrgdt   AS added_at,
            mbchid   AS changed_by,
            mbdpfg   AS dp_fg,
            mbdsfg   AS ds_fg,
            mbptfg   AS pt_fg,
            mbptct   AS pt_ct,
            mbptid   AS pt_id,
            mbptdt   AS pt_dt,
            mbsrce   AS source,
            mbusrm   AS user_remark,
            mbitrm   AS item_remark
        FROM barcodesap.mmbran
        WHERE mbnobr = %s
          AND mbdlfg <> 1
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

def create_mmbran(
    nobr: str,
    name: str,
    flag: str | None = None,
    case_: str | None = None,
    user: str = "Admin",
) -> str:
    """
    Insert a new mmbran row.
    PK is mbnobr (varchar 10), supplied by the caller.
    mbadby / mbaddt are required NOT NULL — set to user/now on create.
    mbchby / mbchdt / mbchno start as NULL/0 until a real edit occurs.
    Flags, remarks, and other SAP-managed columns are left as DB defaults.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.mmbran (
                mbnobr,
                mbnama,
                mbflag,
                mbcase,
                mbadby, mbaddt,
                mbchno,
                mbdlfg,
                mbrgid, mbrgdt
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s, %s,
                0,
                0,
                %s, %s
            )
            RETURNING mbnobr
            """,
            (
                nobr,
                name,
                flag,
                case_,
                user, now,
                user, now,
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

def update_mmbran(
    pk: str,
    name: str,
    flag: str | None,
    case_: str | None,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update the editable fields on an existing mmbran row.
    All other columns (flags, remarks, print tracking, source) are
    preserved as-is — fetched from the DB and written back unchanged.
    Uses optimistic locking on mbchno.
    Note: mbnobr (PK) is intentionally not updatable.
    """
    # ── Fetch current row to preserve untouched fields ────────────────
    existing = fetch_mmbran_by_pk(pk)
    if existing is None:
        raise Exception(f"Record '{pk}' not found.")

    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mmbran
            SET
                mbnama = %s,
                mbflag = %s,
                mbcase = %s,
                mbdpfg = %s,
                mbdsfg = %s,
                mbptfg = %s,
                mbptct = %s,
                mbptid = %s,
                mbptdt = %s,
                mbsrce = %s,
                mbusrm = %s,
                mbitrm = %s,
                mbchby = %s,
                mbchdt = %s,
                mbchid = %s,
                mbchno = %s
            WHERE mbnobr = %s
              AND mbchno  = %s
            """,
            (
                name,
                flag,
                case_,
                # preserved fields
                existing["dp_fg"],
                existing["ds_fg"],
                existing["pt_fg"],
                existing["pt_ct"],
                existing["pt_id"],
                existing["pt_dt"],
                existing["source"],
                existing["user_remark"],
                existing["item_remark"],
                # audit
                user, now, user,
                old_changed_no + 1,
                # WHERE
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

def soft_delete_mmbran(pk: str, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mmbran
            SET
                mbdlfg = 1,
                mbchby = %s,
                mbchdt = %s,
                mbchid = %s,
                mbchno = mbchno + 1
            WHERE mbnobr = %s
            """,
            (user, now, user, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()