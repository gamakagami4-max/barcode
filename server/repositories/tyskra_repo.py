# server/repositories/tyskra_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_tyskra() -> list[dict]:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                sktynm  AS type_name,
                sktyds  AS type_desc,
                skadby  AS added_by,
                skaddt  AS added_at,
                skchby  AS changed_by,
                skchdt  AS changed_at,
                skchno  AS changed_no,
                skdlfg  AS deleted_flag,
                skrgid  AS reg_id,
                skrgdt  AS reg_at,
                skchid  AS changed_id,
                skdpfg  AS dp_flag,
                skdsfg  AS ds_flag,
                skptfg  AS pt_flag,
                skptct  AS pt_count,
                skptid  AS pt_id,
                skptdt  AS pt_at,
                sksrce  AS source,
                skusrm  AS user_remark,
                skitrm  AS item_remark,
                skcsdt  AS cs_at,
                skcsid  AS cs_id,
                skcsno  AS cs_no,
                skunix  AS unix_id
            FROM barcodesap.tyskra
            WHERE skdlfg <> 1
            ORDER BY sktynm
            """
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_tyskra_by_pk(type_name: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                sktynm  AS type_name,
                sktyds  AS type_desc,
                skadby  AS added_by,
                skaddt  AS added_at,
                skchby  AS changed_by,
                skchdt  AS changed_at,
                skchno  AS changed_no,
                skdlfg  AS deleted_flag,
                skrgid  AS reg_id,
                skrgdt  AS reg_at,
                skchid  AS changed_id,
                skdpfg  AS dp_flag,
                skdsfg  AS ds_flag,
                skptfg  AS pt_flag,
                skptct  AS pt_count,
                skptid  AS pt_id,
                skptdt  AS pt_at,
                sksrce  AS source,
                skusrm  AS user_remark,
                skitrm  AS item_remark,
                skcsdt  AS cs_at,
                skcsid  AS cs_id,
                skcsno  AS cs_no,
                skunix  AS unix_id
            FROM barcodesap.tyskra
            WHERE sktynm = %s
              AND skdlfg <> 1
            """,
            (type_name,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_tyskra(
    type_name: str,
    type_desc: str | None = None,
    user: str = "Admin",
) -> str:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.tyskra (
                sktynm,
                sktyds,
                skadby,
                skaddt,
                skchno,
                skdlfg
            )
            VALUES (
                %s, %s,
                %s, %s,
                0, 0
            )
            RETURNING sktynm
            """,
            (
                type_name,
                type_desc,
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

# ── Update ────────────────────────────────────────────────────────────────────

def update_tyskra(
    type_name: str,
    old_changed_no: int,
    type_desc: str | None = None,
    user: str = "Admin",
) -> None:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.tyskra SET
                sktyds = %s,
                skchby = %s,
                skchdt = %s,
                skchno = %s
            WHERE sktynm = %s
              AND skdlfg <> 1
            """,
            (
                type_desc,
                user,
                now,
                old_changed_no + 1,
                type_name,
            ),
        )

        if cur.rowcount == 0:
            raise Exception(f"Record '{type_name}' not found or already deleted.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_tyskra(type_name: str, user: str = "Admin") -> None:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.tyskra SET
                skdlfg = 1,
                skchby = %s,
                skchdt = %s,
                skchid = %s
            WHERE sktynm = %s
            """,
            (user, now, user, type_name),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()