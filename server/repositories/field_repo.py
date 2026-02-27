from server.db import get_connection


def fetch_fields(connection_name: str, table_name: str) -> list[dict]:
    print("=== FETCH FIELDS DEBUG ===")
    print("Connection name:", repr(connection_name))
    print("Table name:", repr(table_name))

    sql = """
        SELECT
            a.attnum AS pk,                 -- column position (or use your own id if needed)
            a.attname AS name,              -- column name
            pgd.description AS comment      -- column comment
        FROM pg_catalog.pg_attribute a
        JOIN pg_catalog.pg_class c
            ON a.attrelid = c.oid
        JOIN pg_catalog.pg_namespace n
            ON c.relnamespace = n.oid
        LEFT JOIN pg_catalog.pg_description pgd
            ON pgd.objoid = c.oid
           AND pgd.objsubid = a.attnum
        WHERE c.relname = %s
          AND n.nspname = 'barcodesap'          -- change schema if needed
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (table_name,))

        rows = cur.fetchall()
        print("Rows returned from DB:", rows)

        cols = [desc[0] for desc in cur.description]
        result = [dict(zip(cols, row)) for row in rows]

        print("Final result:")
        for r in result:
            print(
                f"Column: {r['name']} | "
                f"Comment: {r.get('comment')}"
            )

        print("==========================")

        return result

    except Exception as e:
        print("FETCH FIELDS ERROR:", e)
        return []

    finally:
        conn.close()