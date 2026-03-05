"""Database helper functions for the barcode editor (LOOKUP type)."""


def _fetch_connections() -> list[dict]:
    """Return list of {pk, name} for all active DB connections."""
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT mcconm, mcconm
                  FROM barcodesap.mconnc
                 ORDER BY mcconm
                """
            )
            return [{"pk": row[0], "name": str(row[1]).strip()} for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_connections] {e}")
        return []


def _fetch_tables_for_connection(connection_pk: int) -> list[dict]:
    """Return list of {pk, name} for tables belonging to connection_pk."""
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT matbnmiy, matbnm
                  FROM barcodesap.mmstbnm
                 WHERE maconciy = %s
                   AND madlfg <> '1'
                 ORDER BY matbnm
                """,
                (connection_pk,),
            )
            return [{"pk": row[0], "name": str(row[1]).strip()} for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_tables_for_connection] {e}")
        return []


def _fetch_fields_for_table(table_pk: int) -> list[str]:
    """Return list of field names for the given table PK."""
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT mflid, mtflnm
                  FROM barcodesap.mmfield
                 WHERE matbnmiy = %s
                   AND madlfg <> '1'
                 ORDER BY mtflnm
                """,
                (table_pk,),
            )
            return [str(row[1]).strip() for row in cur.fetchall()]
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_fields_for_table] {e}")
        return []