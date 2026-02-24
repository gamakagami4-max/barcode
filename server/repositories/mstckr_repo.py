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
    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        print("CREATE_MSTCKR PARAMS:")
        print({
            "name": name,
            "h_in": h_in,
            "w_in": w_in,
            "h_px": h_px,
            "w_px": w_px,
            "user": user,
            "now": now,
        })

        cur.execute(
            """
            INSERT INTO barcodesap.mstckr (
                msstnm,
                msheig,
                mswidt,
                mspixh,
                mspixw,
                msrgid,
                msrgdt,
                mschno,
                msdlfg
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                '0'
            )
            RETURNING msstnm
            """,
            (
                name,
                h_in,
                w_in,
                h_px,
                w_px,
                user,
                now,
                0,
            ),
        )

        pk = cur.fetchone()[0]
        conn.commit()
        return pk

    except Exception as e:
        conn.rollback()
        print("CREATE_MSTCKR ERROR:")
        print(e)
        raise

    finally:
        conn.close()


# ── Update (Optimistic Locking) ───────────────────────────────────────────────

def update_mstckr(
    old_pk: str,
    new_name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    old_changed_no: int,
    user: str = "Admin",
):
    existing = fetch_mstckr_by_pk(old_pk)
    if existing is None:
        raise Exception(f"Record '{old_pk}' not found.")

    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        print("UPDATE_MSTCKR PARAMS:")
        print({
            "old_pk": old_pk,
            "new_name": new_name,
            "h_in": h_in,
            "w_in": w_in,
            "h_px": h_px,
            "w_px": w_px,
            "old_changed_no": old_changed_no,
        })

        cur.execute(
            """
            UPDATE barcodesap.mstckr
            SET
                msstnm = %s,
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
              AND mschno = %s
            """,
            (
                new_name,
                h_in,
                w_in,
                h_px,
                w_px,
                existing["dp_fg"],
                existing["ds_fg"],
                existing["pt_fg"],
                existing["pt_ct"],
                existing["pt_id"],
                existing["pt_dt"],
                existing["source"],
                existing["user_remark"],
                existing["item_remark"],
                user,
                now,
                old_changed_no + 1,
                old_pk,            # ← FIXED
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception("Record was modified by another user.")

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("UPDATE_MSTCKR ERROR:")
        print(e)
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

    except Exception as e:
        conn.rollback()
        print("SOFT_DELETE_MSTCKR ERROR:")
        print(e)
        raise

    finally:
        conn.close()