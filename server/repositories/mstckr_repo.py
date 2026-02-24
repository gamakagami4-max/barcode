# server/repositories/mstckr_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mstckr() -> list[dict]:
    sql = """
        SELECT
            msstnm   AS pk,
            msheig   AS h_in,
            mswidt   AS w_in,
            mspixh   AS h_px,
            mspixw   AS w_px,
            msdpfg   AS dp_fg,
            msdsfg   AS ds_fg,
            msptfg   AS pt_fg,
            msptct   AS pt_ct,
            msptid   AS pt_id,
            msptdt   AS pt_dt,
            mssrce   AS source,
            msusrm   AS user_remark,
            msitrm   AS item_remark,
            msrgid   AS added_by,
            msrgdt   AS added_at,
            mschid   AS changed_by,
            mschdt   AS changed_at,
            mschno   AS changed_no
        FROM barcodesap.mstckr
        WHERE msdlfg <> '1'
        ORDER BY msrgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_mstckr_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            msstnm   AS pk,
            msheig   AS h_in,
            mswidt   AS w_in,
            mspixh   AS h_px,
            mspixw   AS w_px,
            msdpfg   AS dp_fg,
            msdsfg   AS ds_fg,
            msptfg   AS pt_fg,
            msptct   AS pt_ct,
            msptid   AS pt_id,
            msptdt   AS pt_dt,
            mssrce   AS source,
            msusrm   AS user_remark,
            msitrm   AS item_remark,
            msrgid   AS added_by,
            msrgdt   AS added_at,
            mschid   AS changed_by,
            mschdt   AS changed_at,
            mschno   AS changed_no
        FROM barcodesap.mstckr
        WHERE msstnm = %s
          AND msdlfg <> '1'
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

def create_mstckr(
    name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    user: str = "Admin",
) -> str:
    """
    Insert a new mstckr row.
    Only the core dimension fields are set by the caller.
    Flags, remarks, and change tracking columns are left as DB defaults.
    mschid / mschdt / mschno are intentionally omitted — NULL until a real edit occurs.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.mstckr (
                msstnm,
                msheig, mswidt,
                mspixh, mspixw,
                msrgid, msrgdt,
                msdlfg
            )
            VALUES (
                %s,
                %s, %s,
                %s, %s,
                %s, %s,
                '0'
            )
            RETURNING msstnm
            """,
            (
                name,
                h_in, w_in,
                h_px, w_px,
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

def update_mstckr(
    pk: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update only the dimension fields on an existing mstckr row.
    All other columns (flags, remarks, print tracking, source) are
    preserved as-is — fetched from the DB and written back unchanged.
    Uses optimistic locking on mschno.
    Note: msstnm (PK) is intentionally not updatable.
    """
    # ── Fetch current row to preserve untouched fields ────────────────
    existing = fetch_mstckr_by_pk(pk)
    if existing is None:
        raise Exception(f"Record '{pk}' not found.")

    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mstckr
            SET
                msheig = %s,
                mswidt = %s,
                mspixh = %s,
                mspixw = %s,
                msdpfg = %s,
                msdsfg = %s,
                msptfg = %s,
                msptct = %s,
                msptid = %s,
                msptdt = %s,
                mssrce = %s,
                msusrm = %s,
                msitrm = %s,
                mschid = %s,
                mschdt = %s,
                mschno = %s
            WHERE msstnm = %s
              AND mschno  = %s
            """,
            (
                h_in, w_in,
                h_px, w_px,
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
                user, now,
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

def soft_delete_mstckr(pk: str, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mstckr
            SET
                msdlfg = '1',
                mschid = %s,
                mschdt = %s,
                mschno = mschno + 1
            WHERE msstnm = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()