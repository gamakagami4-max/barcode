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
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()