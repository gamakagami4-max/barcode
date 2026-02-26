from datetime import datetime
from server.db import get_connection
import psycopg2

# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_barsys() -> list[dict]:
    sql = """
        SELECT
            bscode   AS code,
            bsname   AS name,
            bsdesc   AS description,
            bsrgid   AS added_by,
            bsrgdt   AS added_at,
            bschid   AS changed_by,
            bschdt   AS changed_at,
            bschno   AS changed_no
        FROM barcodesap.barsys
        WHERE bsdlfg <> '1'
        ORDER BY bsrgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_barsys_by_pk(name: str, code: str) -> dict | None:
    sql = """
        SELECT
            bscode   AS code,
            bsname   AS name,
            bsdesc   AS description,
            bsrgid   AS added_by,
            bsrgdt   AS added_at,
            bschid   AS changed_by,
            bschdt   AS changed_at,
            bschno   AS changed_no
        FROM barcodesap.barsys
        WHERE bsname = %s
          AND bscode = %s
          AND bsdlfg <> '1'
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (name, code))
        row = cur.fetchone()
        if not row:
            return None
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_barsys(
    code: str,
    name: str,
    description: str | None,
    user: str = "Admin",
) -> tuple[str, str]:
    """
    Insert a new barsys record.
    Composite PK: (bsname, bscode)
    """
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO barcodesap.barsys (
                bscode,
                bsname,
                bsdesc,
                bsrgid,
                bsrgdt,
                bsaddt,
                bschdt,
                bschno,
                bsdlfg
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s,0,'0')
            RETURNING bsname, bscode
            """,
            (code, name, description, user, now, now, now),
        )

        pk = cur.fetchone()
        conn.commit()
        return pk

    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        raise Exception("System Code and Name already exist.")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update (Optimistic Locking) ───────────────────────────────────────────────

def update_barsys(
    name: str,
    code: str,
    description: str | None,
    old_changed_no: int,
    user: str = "Admin",
):
    """
    Update description only.
    Uses optimistic locking via bschno.
    PK (bsname, bscode) is NOT updatable.
    """
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE barcodesap.barsys
            SET
                bsdesc  = %s,
                bschid  = %s,
                bschdt  = %s,
                bschno  = %s
            WHERE bsname = %s
              AND bscode = %s
              AND bschno = %s
            """,
            (
                description,
                user,
                now,
                old_changed_no + 1,
                name,
                code,
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

def soft_delete_barsys(
    name: str,
    code: str,
    user: str = "Admin",
):
    now = datetime.now()

    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE barcodesap.barsys
            SET
                bsdlfg = '1',
                bschid = %s,
                bschdt = %s,
                bschno = bschno + 1
            WHERE bsname = %s
              AND bscode = %s
            """,
            (
                user,
                now,
                name,
                code,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()