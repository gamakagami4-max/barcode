from server.db import get_connection


def fetch_fields(connection_name: str, table_name: str) -> list[dict]:
    print("=== FETCH FIELDS DEBUG ===")
    print("Connection name:", repr(connection_name))
    print("Table name:", repr(table_name))

    sql = """
        SELECT
            mflid AS pk,
            mtflnm AS name
        FROM barcodesap.mmfield
        WHERE mtconm = %s
          AND mttbnm = %s
        ORDER BY mtflnm
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (connection_name, table_name))

        rows = cur.fetchall()
        print("Rows returned from DB:", rows)

        cols = [desc[0] for desc in cur.description]
        result = [dict(zip(cols, row)) for row in rows]

        print("Final result:", result)
        print("==========================")

        return result

    except Exception as e:
        print("FETCH FIELDS ERROR:", e)
        return []

    finally:
        conn.close()