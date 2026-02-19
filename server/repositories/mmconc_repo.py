from ..db import get_connection
from datetime import datetime


def create_source_data(conn_name, table_name, query, user="Admin"):
    conn = get_connection()
    cur = conn.cursor()
    now = datetime.now()

    # Insert connection
    cur.execute("""
        INSERT INTO barcode.mmconc (
            mnname, mnrgid, mnrgdt,
            mnchid, mnchdt,
            mncsdt, mncsid
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING mnconciy
    """, (
        conn_name, user, now,
        user, now,
        now, user
    ))

    connection_id = cur.fetchone()[0]

    # Insert table
    cur.execute("""
        INSERT INTO barcode.mmtbnm (
            moname, moconciy,
            morgid, morgdt,
            mochid, mochdt,
            mocsdt, mocsid,
            mousrm
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (
        table_name,
        connection_id,
        user, now,
        user, now,
        now, user,
        query
    ))

    conn.commit()
    cur.close()
    conn.close()
