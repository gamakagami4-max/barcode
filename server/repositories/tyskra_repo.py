from datetime import datetime
from server.db import get_connection


# =========================
# CREATE
# =========================
def create_tyskra(
    type_name: str,
    type_desc: str | None = None,
    user: str = "Admin",
) -> None:
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
                skchby,
                skchdt,
                skchno,
                skdlfg
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                type_name,
                type_desc,
                user,
                now,
                user,
                now,
                1,
                0,
            ),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("CREATE_TYSKRA ERROR:", e)
        raise

    finally:
        conn.close()


# =========================
# UPDATE (ALLOW RENAME + LOCKING)
# =========================
def update_tyskra(
    old_type_name: str,
    new_type_name: str,
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
                sktynm = %s,
                sktyds = %s,
                skchby = %s,
                skchdt = %s,
                skchno = %s
            WHERE sktynm = %s
              AND skdlfg <> 1
              AND skchno = %s
            """,
            (
                new_type_name,
                type_desc,
                user,
                now,
                old_changed_no + 1,
                old_type_name,
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception(
                f"Record '{old_type_name}' was modified or does not exist."
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("UPDATE_TYSKRA ERROR:", e)
        raise

    finally:
        conn.close()


# =========================
# SOFT DELETE
# =========================
def soft_delete_tyskra(
    type_name: str,
    old_changed_no: int,
    user: str = "Admin",
) -> None:
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
                skchno = %s
            WHERE sktynm = %s
              AND skchno = %s
            """,
            (
                user,
                now,
                old_changed_no + 1,
                type_name,
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception(
                f"Record '{type_name}' was modified or does not exist."
            )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DELETE_TYSKRA ERROR:", e)
        raise

    finally:
        conn.close()


# =========================
# FETCH ALL
# =========================
def fetch_all_tyskra():
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            SELECT
                sktynm,
                sktyds,
                skadby,
                skaddt,
                skchby,
                skchdt,
                skchno
            FROM barcodesap.tyskra
            WHERE skdlfg <> 1
            ORDER BY sktynm
            """
        )

        rows = cur.fetchall()

        result = []
        for r in rows:
            result.append({
                "type_name": r[0],
                "type_desc": r[1],
                "added_by": r[2],
                "added_at": r[3],
                "changed_by": r[4],
                "changed_at": r[5],
                "changed_no": r[6],
            })

        return result

    finally:
        conn.close()