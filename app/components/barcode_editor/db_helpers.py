"""Database helper functions for the barcode editor (LOOKUP type)."""


def _fetch_connections() -> list[dict]:
    """Return list of {pk, name} for DB connections."""
    try:
        from server.db import get_connection

        conn = get_connection()
        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT mcconm
                FROM barcodesap.mconnc
                ORDER BY mcconm
                """
            )

            return [
                {
                    "pk": str(row[0]).strip(),
                    "name": str(row[0]).strip()
                }
                for row in cur.fetchall()
            ]

        finally:
            conn.close()

    except Exception as e:
        print(f"[_fetch_connections] {e}")
        return []


def _fetch_tables_for_connection(connection_name: str) -> list[dict]:
    """Return tables for a connection."""
    try:
        from server.db import get_connection

        conn = get_connection()
        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT DISTINCT mttbnm
                FROM barcodesap.mtable
                WHERE mtconm = %s
                ORDER BY mttbnm
                """,
                (connection_name,),
            )

            rows = cur.fetchall()

            return [
                {
                    "pk": str(row[0]).strip(),
                    "name": str(row[0]).strip()
                }
                for row in rows
            ]

        finally:
            conn.close()

    except Exception as e:
        print(f"[_fetch_tables_for_connection] {e}")
        return []


def _fetch_fields_for_table(table_name: str) -> list[str]:
    """Return field names for a table."""
    try:
        from server.db import get_connection

        conn = get_connection()
        try:
            cur = conn.cursor()

            cur.execute(
                """
                SELECT mtflnm
                FROM barcodesap.mmfield
                WHERE mttbnm = %s
                  AND madlfg <> '1'
                ORDER BY mtflnm
                """,
                (table_name,),
            )

            return [
                str(row[0]).strip()
                for row in cur.fetchall()
            ]

        finally:
            conn.close()

    except Exception as e:
        print(f"[_fetch_fields_for_table] {e}")
        return []