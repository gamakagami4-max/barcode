# server/repositories/mtable_repo.py

from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mtable() -> list[dict]:
    """
    Returns every mtable row.

    Shape per row:
        pk      str   mtconm
        tbnm    str   mttbnm
        flnm    str   mtflnm
        flds    str   mtflds
        flno    int   mtflno
        tbfg    int   mttbfg
        link    str   mtlink
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                mtconm  AS pk,
                mttbnm  AS tbnm,
                mtflnm  AS flnm,
                mtflds  AS flds,
                mtflno  AS flno,
                mttbfg  AS tbfg,
                mtlink  AS link
            FROM barcodesap.mtable
            ORDER BY mtconm, mttbnm
            """
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_tables_by_conn(conm: str) -> list[dict]:
    """Return all mtable rows for a given connection name."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                mtconm  AS pk,
                mttbnm  AS tbnm,
                mtflnm  AS flnm,
                mtflds  AS flds,
                mtflno  AS flno,
                mttbfg  AS tbfg,
                mtlink  AS link
            FROM barcodesap.mtable
            WHERE mtconm = %s
            ORDER BY mttbnm
            """,
            (conm,),
        )
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_table_names_by_conn(conm: str) -> list[str]:
    """Return just the table name list for a connection — useful for dropdowns."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT mttbnm FROM barcodesap.mtable WHERE mtconm = %s ORDER BY mttbnm",
            (conm,),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_mtable(
    conm: str,
    tbnm: str,
    flnm: str,
    flds: str | None = None,
    flno: int | None = None,
    tbfg: int = 0,
    link: str | None = None,
) -> str:
    """
    Insert a new mtable row.
    PK is mtconm (varchar 20) — same value as the parent connection name.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.mtable (
                mtconm, mttbnm, mtflnm,
                mtflds, mtflno, mttbfg, mtlink
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING mtconm
            """,
            (conm, tbnm, flnm, flds, flno, tbfg, link),
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

def update_mtable(
    conm: str,
    tbnm: str,
    flnm: str,
    flds: str | None = None,
    flno: int | None = None,
    tbfg: int = 0,
    link: str | None = None,
) -> None:
    """Update an existing mtable row identified by mtconm (the PK)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.mtable
            SET
                mttbnm = %s,
                mtflnm = %s,
                mtflds = %s,
                mtflno = %s,
                mttbfg = %s,
                mtlink = %s
            WHERE mtconm = %s
            """,
            (tbnm, flnm, flds, flno, tbfg, link, conm),
        )
        if cur.rowcount == 0:
            raise Exception(f"Table entry for connection '{conm}' not found.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_mtable(conm: str) -> None:
    """Hard delete an mtable row by its PK (mtconm)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM barcodesap.mtable WHERE mtconm = %s",
            (conm,),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Replace (atomic swap of all table rows for a connection) ──────────────────

def replace_mtables(conm: str, tables: list[dict]) -> None:
    """
    Atomically replace all mtable rows for a connection.
    Each dict in `tables` must have keys: tbnm, flnm, and optionally
    flds, flno, tbfg, link.

    Useful when the user edits the full table list in one go,
    mirroring the _replace_field_rows pattern in mmsdgr_repo.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM barcodesap.mtable WHERE mtconm = %s",
            (conm,),
        )
        for t in tables:
            cur.execute(
                """
                INSERT INTO barcodesap.mtable (
                    mtconm, mttbnm, mtflnm,
                    mtflds, mtflno, mttbfg, mtlink
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    conm,
                    t["tbnm"],
                    t["flnm"],
                    t.get("flds"),
                    t.get("flno"),
                    t.get("tbfg", 0),
                    t.get("link"),
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()