from server.db import get_connection


def fetch_fields(conn_name: str, table_name: str):
    """
    Fetch real columns directly from PostgreSQL information_schema.
    """

    sql = """
        SELECT
            column_name AS field_name,
            column_name AS field_desc
        FROM information_schema.columns
        WHERE table_schema = 'barcodesap'
          AND table_name = %s
        ORDER BY ordinal_position
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (table_name,))

        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

        result = [dict(zip(cols, row)) for row in rows]

        print("FIELDS RETURNED FROM REPO:", result)

        return result

    except Exception as e:
        print("FIELD FETCH ERROR:", e)
        return []

    finally:
        conn.close()