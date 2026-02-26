# server/repositories/engine_repo.py

from server.db import get_connection


def fetch_all_engines():
    sql = """
        SELECT me_id AS pk,
               me_code AS code,
               me_name AS name
        FROM barcodesap.mengin
        ORDER BY me_name
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()