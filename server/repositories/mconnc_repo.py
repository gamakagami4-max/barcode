# server/repositories/connection_repo.py

from server.db import get_connection


def fetch_connections_by_engine(engine_id: int):
    sql = """
        SELECT mcconm AS name
        FROM barcodesap.mconnc
        WHERE mcengine = %s
        ORDER BY mcconm
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (engine_id,))
        rows = cur.fetchall()

        return [
            {
                "pk": row[0],      # 👈 use name as PK
                "name": row[0]
            }
            for row in rows
        ]

    finally:
        conn.close()