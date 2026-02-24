# server/repositories/mconnc_repo.py

from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mconnc() -> list[dict]:
    """
    Returns every connection row.

    Shape per row:
        pk          str   mcconm
        conn_str    str   mccost
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                mcconm  AS pk,
                mccost  AS conn_str
            FROM barcodesap.mconnc
            ORDER BY mcconm
            """
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_mconnc_by_pk(pk: str) -> dict | None:
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                mcconm  AS pk,
                mccost  AS conn_str
            FROM barcodesap.mconnc
            WHERE mcconm = %s
            """,
            (pk,),
        )
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


def fetch_mconnc_names() -> list[str]:
    """Return just the connection name list — useful for dropdown population."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT mcconm FROM barcodesap.mconnc ORDER BY mcconm")
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_mconnc(conm: str, cost: str) -> str:
    """
    Insert a new connection row.
    PK is mcconm (varchar 20), supplied by the caller.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.mconnc (mcconm, mccost)
            VALUES (%s, %s)
            RETURNING mcconm
            """,
            (conm, cost),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update ────────────────────────────────────────────────────────────────────

def update_mconnc(pk: str, cost: str) -> None:
    """Update the connection string for an existing connection."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mconnc
            SET mccost = %s
            WHERE mcconm = %s
            """,
            (cost, pk),
        )
        if cur.rowcount == 0:
            raise Exception(f"Connection '{pk}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_mconnc(pk: str) -> None:
    """
    Hard delete a connection and all its child mtable rows.
    Children are deleted first to respect the FK constraint.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM barcodesap.mtable WHERE mtconm = %s",
            (pk,),
        )
        cur.execute(
            "DELETE FROM barcodesap.mconnc WHERE mcconm = %s",
            (pk,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()