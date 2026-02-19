    # repositories/mmtbnm_repo.py
from ..db import get_connection
from datetime import datetime


def create_table_record(table_name, connection_id, user_id):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO barcode.mmtbnm (
            moname,
            moconciy,
            morgid, morgdt,
            mochid, mochdt,
            mocsdt, mocsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        table_name,
        connection_id,
        user_id,
        datetime.now(),
        user_id,
        datetime.now(),
        datetime.now(),
        user_id
    ))

    conn.commit()
    cur.close()
    conn.close()
