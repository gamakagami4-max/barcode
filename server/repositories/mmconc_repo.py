# server/repositories/mmconc_repo.py

from datetime import datetime
from server.db import get_connection


def create_connection_record(conn_name: str, user: str = "Admin") -> int:
    """
    Insert a new active mmconc row and return its mnconciy PK.
    If an active connection with the same name already exists, return its PK instead.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Guard: reuse if already exists
        cur.execute(
            """
            SELECT mnconciy FROM barcode.mmconc
            WHERE mnname = %s AND mndlfg <> '1'
            LIMIT 1
            """,
            (conn_name,),
        )
        row = cur.fetchone()
        if row:
            return row[0]

        cur.execute(
            """
            INSERT INTO barcode.mmconc (
                mnname,
                mnrgid, mnrgdt,
                mnchid, mnchdt,
                mncsdt, mncsid
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING mnconciy
            """,
            (conn_name, user, now, user, now, now, user),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# server/repositories/mmconc_repo.py  (add this function)

def create_table_record(conn_name: str, table_name: str, query: str, user: str = "Admin") -> int:
    """
    Insert a new mmtbnm row under the given connection name.
    Reuses existing mmconc if found, creates one otherwise.
    Returns the new motbnmiy PK.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Resolve or create the parent connection
        cur.execute(
            """
            SELECT mnconciy FROM barcode.mmconc
            WHERE mnname = %s AND mndlfg <> '1'
            LIMIT 1
            """,
            (conn_name,),
        )
        row = cur.fetchone()
        if row:
            conciy = row[0]
        else:
            cur.execute(
                """
                INSERT INTO barcode.mmconc (
                    mnname, mnrgid, mnrgdt,
                    mnchid, mnchdt,
                    mncsdt, mncsid
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING mnconciy
                """,
                (conn_name, user, now, user, now, now, user),
            )
            conciy = cur.fetchone()[0]

        # Insert the table row
        cur.execute(
            """
            INSERT INTO barcode.mmtbnm (
                moname, moconciy,
                morgid, morgdt,
                mochid, mochdt,
                mocsdt, mocsid,
                mousrm
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING motbnmiy
            """,
            (table_name, conciy, user, now, user, now, now, user, query),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()