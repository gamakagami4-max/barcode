# server/repositories/mmbrnd_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_brnd() -> list[dict]:
    sql = """
        SELECT
            mdbrndiy AS pk,
            mdcode   AS code,
            mdname   AS name,
            mdcase   AS case_name,
            mddpfg   AS display_flag,
            mddsfg   AS disable_flag,
            mdptfg   AS protect_flag,
            mdptct   AS protect_count,
            mdusrm   AS user_remark,
            mditrm   AS internal_remark,
            mdrgid   AS added_by,
            mdrgdt   AS added_at,
            mdchid   AS changed_by,
            mdchdt   AS changed_at,
            mdchno   AS changed_no
        FROM barcode.mmbrnd
        WHERE mddlfg <> '1'
        ORDER BY mdrgdt DESC
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_brnd(
    code: str,
    name: str,
    case_name: str | None,
    user: str = "Admin",
) -> int:
    """
    Insert new mmbrnd row and return its mdbrndiy PK.
    """
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()

        # Guard: prevent duplicate code
        cur.execute(
            """
            SELECT mdbrndiy
            FROM barcode.mmbrnd
            WHERE mdcode = %s
              AND mddlfg <> '1'
            LIMIT 1
            """,
            (code,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO barcode.mmbrnd (
                mdcode,
                mdname,
                mdcase,
                mdrgid,
                mdrgdt,
                mdchid,
                mdchdt,
                mdcsdt,
                mdcsid
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING mdbrndiy
            """,
            (
                code,
                name,
                case_name,
                user, now,
                user, now,
                now, user,
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

def update_brnd(
    pk: int,
    code: str,
    name: str,
    case_name: str | None,
    display_flag: str,
    disable_flag: str,
    protect_flag: str,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update mmbrnd row.
    Flags must be '0' or '1'.
    """
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmbrnd SET
                mdcode  = %s,
                mdname  = %s,
                mdcase  = %s,
                mddpfg  = %s,
                mddsfg  = %s,
                mdptfg  = %s,
                mdchid  = %s,
                mdchdt  = %s,
                mdchno  = %s
            WHERE mdbrndiy = %s
            """,
            (
                code,
                name,
                case_name,
                display_flag,
                disable_flag,
                protect_flag,
                user,
                now,
                old_changed_no + 1,
                pk,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_brnd(pk: int, user: str = "Admin"):
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmbrnd SET
                mddlfg = '1',
                mdchid = %s,
                mdchdt = %s
            WHERE mdbrndiy = %s
            """,
            (user, now, pk),
        )
        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
