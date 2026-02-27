from datetime import datetime
from server.db import get_connection

# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mmsdgr() -> list[dict]:
    sql = """
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
        WHERE madlfg <> '1'
        ORDER BY margdt DESC
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
    sql = """
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

def create_mmsdgr(
    maconciy: str,          # UPDATED: changed from int to str
    matbnmiy: str | None,   # UPDATED: changed from int to str
    maqlsv: str | None,
    maengn: str,
    user: str = "Admin",
) -> int:
    # DEBUG: confirmed this now receives strings like 'barcode db'
    # print(f"DEBUG: maconciy={maconciy}, type={type(maconciy)}") 

    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
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
            VALUES (
                %s, %s, %s, %s,
                %s, %s,
                0,
                '0',
                '1'
            )
            RETURNING masgdriy
            """,
            (
                maconciy,
                matbnmiy,
                maqlsv,
                maengn,
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

def update_mmsdgr(
    pk: int,
    maconciy: str,          # UPDATED: changed from int to str
    matbnmiy: str | None,   # UPDATED: changed from int to str
    maqlsv: str | None,
    maengn: str,
    old_changed_no: int,
    user: str = "Admin",
):
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()
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

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete ───────────────────────────────────────────────────────────────

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
                machno = machno + 1
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