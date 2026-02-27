from server.db import get_connection


def fetch_fields(connection_pk: int, table_name: str) -> list[dict]:
    """
    Fetch column metadata for a given table from a PostgreSQL connection.
    
    Args:
        connection_pk: The primary key of the connection (used to identify DB connection params)
        table_name: The table name to fetch columns from
    
    Returns:
        List of dicts with keys: pk, name, comment
    """
    print("=== FETCH FIELDS DEBUG ===")
    print("Connection PK:", repr(connection_pk))
    print("Table name:", repr(table_name))

    sql = """
        SELECT
            a.attnum AS pk,                 -- column position
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
          AND n.nspname = 'barcodesap'
          AND a.attnum > 0
          AND NOT a.attisdropped
        ORDER BY a.attnum
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (table_name,))

        rows = cur.fetchall()
        print("Rows returned from DB:", len(rows))

        cols = [desc[0] for desc in cur.description]
        result = [dict(zip(cols, row)) for row in rows]

        print("Final result: Found", len(result), "columns")
        for r in result:
            print(
                f"  - {r['name']:30} | Comment: {r.get('comment', 'N/A')}"
            )

        print("==========================")

        return result

    except Exception as e:
        print("FETCH FIELDS ERROR:", e)
        import traceback
        traceback.print_exc()
        return []

    finally:
        conn.close()


def fetch_field_names_by_ids(field_ids: list[int]) -> list[str]:
    """
    Fetch field names from the mmfield table by their IDs.
    Used when retrieving saved field selections from mmsdgf.
    
    Args:
        field_ids: List of field IDs (mflid values)
    
    Returns:
        List of field names (mtflnm values) in order of input IDs
    """
    if not field_ids:
        return []

    sql = """
        SELECT mtflnm
        FROM barcodesap.mmfield
        WHERE mflid = ANY(%s)
        ORDER BY mflid
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (field_ids,))
        names = [row[0] for row in cur.fetchall()]
        print(f"Fetched {len(names)} field names from {len(field_ids)} IDs")
        return names
    except Exception as e:
        print(f"Error fetching field names: {e}")
        import traceback
        traceback.print_exc()
        return []
    finally:
        conn.close()