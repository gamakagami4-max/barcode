# server/repositories/table_repo.py

from server.db import get_connection


def fetch_tables_by_connection(conn_name: str):
    sql = """
        SELECT DISTINCT mttbnm AS name
        FROM barcodesap.mtable
        WHERE mtconm = %s
        ORDER BY mttbnm
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (conn_name,))
        rows = cur.fetchall()

        return [
            {
                "pk": row[0],      # 👈 use table name as PK
                "name": row[0]
            }
            for row in rows
        ]

    finally:
        conn.close()