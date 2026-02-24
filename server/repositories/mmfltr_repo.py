# server/repositories/mmfltr_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_fltr() -> list[dict]:
    sql = """
        SELECT
            mcfltriy AS pk,
            mcname   AS name,
            mcdesc   AS description,
            mcdpfg   AS display_flag,
            mcdsfg   AS disable_flag,
            mcptfg   AS protect_flag,
            mcptct   AS protect_count,
            mcusrm   AS user_remark,
            mcitrm   AS internal_remark,
            mcrgid   AS added_by,
            mcrgdt   AS added_at,
            mcchid   AS changed_by,
            mcchdt   AS changed_at,
            mcchno   AS changed_no
        FROM barcode.mmfltr
        WHERE mcdlfg <> '1'
        ORDER BY mcrgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        results = []
        for row in cur.fetchall():
            record = dict(zip(cols, row))
            record["changed_no"] = record.get("changed_no") or 0
            results.append(record)

        return results
    finally:
        conn.close()


def fetch_column_comments(table: str = "mmfltr", schema: str = "barcode") -> dict[str, str | None]:
    """
    Returns a dict mapping physical column name → its COMMENT ON COLUMN text.
    Columns with no comment set will map to None.
    """
    sql = """
        SELECT
            col.column_name,
            pgd.description AS comment
        FROM information_schema.columns col
        LEFT JOIN pg_catalog.pg_description pgd
            ON pgd.objoid = (
                SELECT cls.oid
                FROM pg_catalog.pg_class cls
                JOIN pg_catalog.pg_namespace nsp ON nsp.oid = cls.relnamespace
                WHERE cls.relname  = col.table_name
                  AND nsp.nspname  = col.table_schema
            )
            AND pgd.objsubid = col.ordinal_position
        WHERE col.table_schema = %s
          AND col.table_name   = %s
        ORDER BY col.ordinal_position
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (schema, table))
        return {row[0]: row[1] for row in cur.fetchall()}
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_fltr(
    name: str,
    description: str | None,
    user: str = "Admin",
) -> int:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Guard: reuse if name already exists and not deleted
        cur.execute(
            """
            SELECT mcfltriy FROM barcode.mmfltr
            WHERE mcname = %s AND mcdlfg <> '1'
            LIMIT 1
            """,
            (name,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO barcode.mmfltr (
                mcname,
                mcdesc,
                mcrgid,
                mcrgdt,
                mcchno
            )
            VALUES (%s, %s, %s, %s, %s)
            RETURNING mcfltriy
            """,
            (
                name,
                description,
                user,
                now,
                0,      # mcchno
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

def update_fltr(
    pk: int,
    name: str,
    description: str | None,
    display_flag: str,
    disable_flag: str,
    protect_flag: str,
    old_changed_no: int,
    user: str = "Admin",
):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmfltr SET
                mcname  = %s,
                mcdesc  = %s,
                mcdpfg  = %s,
                mcdsfg  = %s,
                mcptfg  = %s,
                mcchid  = %s,
                mcchdt  = %s,
                mcchno  = %s,
                mccsdt  = %s,
                mccsid  = %s
            WHERE mcfltriy = %s
            """,
            (
                name, description,
                display_flag, disable_flag, protect_flag,
                user, now, old_changed_no + 1,
                now,    # mccsdt  ← updated on edit
                user,   # mccsid  ← updated on edit
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

def soft_delete_fltr(pk: int, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmfltr SET
                mcdlfg = '1',
                mcchid = %s,
                mcchdt = %s
            WHERE mcfltriy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()