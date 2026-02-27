from datetime import datetime
from server.db import get_connection


# ─────────────────────────────────────────────────────────────
# READ (WITH FIELDS)
# ─────────────────────────────────────────────────────────────

def fetch_all_mmsdgr() -> list[dict]:
    sql = """
        SELECT
            m.masgdriy AS pk,
            m.maconciy AS connection_id,
            m.matbnmiy AS table_id,
            m.maqlsv   AS sql_value,
            m.maengn   AS engine,
            m.margid   AS added_by,
            m.margdt   AS added_at,
            m.machid   AS changed_by,
            m.machdt   AS changed_at,
            m.machno   AS changed_no,
            COALESCE(string_agg(fld.mtflnm, ', '), '') AS fields
        FROM barcodesap.mmsdgr m
        LEFT JOIN barcodesap.mmsdgf f
            ON f.masgdriy = m.masgdriy
            AND f.madlfg <> '1'
        LEFT JOIN barcodesap.mmfield fld
            ON fld.mflid = f.mtflid
        WHERE m.madlfg <> '1'
        GROUP BY
            m.masgdriy,
            m.maconciy,
            m.matbnmiy,
            m.maqlsv,
            m.maengn,
            m.margid,
            m.margdt,
            m.machid,
            m.machdt,
            m.machno
        ORDER BY m.margdt DESC
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_mmsdgr_by_pk(pk: int) -> dict | None:
    sql_parent = """
        SELECT
            masgdriy AS pk,
            maconciy AS connection_id,
            matbnmiy AS table_id,
            maqlsv   AS sql_value,
            maengn   AS engine,
            margid   AS added_by,
            margdt   AS added_at,
            machid   AS changed_by,
            machdt   AS changed_at,
            machno   AS changed_no
        FROM barcodesap.mmsdgr
        WHERE masgdriy = %s
          AND madlfg <> '1'
    """

    sql_fields = """
        SELECT mtflid
        FROM barcodesap.mmsdgf
        WHERE masgdriy = %s
          AND madlfg <> '1'
        ORDER BY masgdfiy
    """

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(sql_parent, (pk,))
        row = cur.fetchone()
        if not row:
            return None

        cols = [desc[0] for desc in cur.description]
        result = dict(zip(cols, row))

        cur.execute(sql_fields, (pk,))
        result["fields"] = [r[0] for r in cur.fetchall()]  # field IDs

        return result
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# CREATE (WITH CHILD INSERT)
# ─────────────────────────────────────────────────────────────

def create_mmsdgr(
    maconciy: int,
    matbnmiy: int | None,
    maqlsv: str | None,
    maengn: str,
    fields: list[int] | None,
    user: str = "Admin",
) -> int:

    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        # Insert parent
        cur.execute(
            """
            INSERT INTO barcodesap.mmsdgr (
                maconciy,
                matbnmiy,
                maqlsv,
                maengn,
                margid,
                margdt,
                machno,
                madlfg,
                madpfg
            )
            VALUES (%s, %s, %s, %s, %s, %s, 0, '0', '1')
            RETURNING masgdriy
            """,
            (maconciy, matbnmiy, maqlsv, maengn, user, now),
        )

        pk = cur.fetchone()[0]

        # Insert selected fields (by ID)
        if fields:
            for field_id in fields:
                cur.execute(
                    """
                    INSERT INTO barcodesap.mmsdgf (
                        masgdriy,
                        mtflid,
                        margid,
                        margdt,
                        madlfg
                    )
                    VALUES (%s, %s, %s, %s, '0')
                    """,
                    (pk, field_id, user, now),
                )

        conn.commit()
        return pk

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────
# UPDATE (WITH CHILD RESET)
# ─────────────────────────────────────────────────────────────

def update_mmsdgr(
    pk: int,
    maconciy: int,
    matbnmiy: int | None,
    maqlsv: str | None,
    maengn: str,
    fields: list[int] | None,
    old_changed_no: int,
    user: str = "Admin",
):

    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        # Update parent with optimistic locking
        cur.execute(
            """
            UPDATE barcodesap.mmsdgr
            SET
                maconciy = %s,
                matbnmiy = %s,
                maqlsv   = %s,
                maengn   = %s,
                machid   = %s,
                machdt   = %s,
                machno   = %s
            WHERE masgdriy = %s
              AND machno = %s
            """,
            (
                maconciy,
                matbnmiy,
                maqlsv,
                maengn,
                user,
                now,
                old_changed_no + 1,
                pk,
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception("Record was modified by another user.")

        # Soft delete old child fields
        cur.execute(
            """
            UPDATE barcodesap.mmsdgf
            SET madlfg = '1'
            WHERE masgdriy = %s
            """,
            (pk,),
        )

        # Reinsert new field IDs
        if fields:
            for field_id in fields:
                cur.execute(
                    """
                    INSERT INTO barcodesap.mmsdgf (
                        masgdriy,
                        mtflid,
                        margid,
                        margdt,
                        madlfg
                    )
                    VALUES (%s, %s, %s, %s, '0')
                    """,
                    (pk, field_id, user, now),
                )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def soft_delete_mmsdgr(pk: int, user: str = "Admin"):
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mmsdgr
            SET
                madlfg = '1',
                machid = %s,
                machdt = %s,
                machno = COALESCE(machno, 0) + 1
            WHERE masgdriy = %s
            """,
            (user, now, pk),
        )
        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()