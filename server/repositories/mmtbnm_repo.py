# server/repositories/mmtbnm_repo.py

from datetime import datetime
from server.db import get_connection
from server.repositories.mmconc_repo import _resolve_or_create_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_source_data() -> list[dict]:
    """
    Return all active mmtbnm rows joined with mmconc + mmengn, newest first.
    """
    sql = """
        SELECT
            t.motbnmiy          AS pk,
            e.mpcode            AS engine_code,
            e.mpname            AS engine_name,
            c.mnconciy          AS conn_id,
            c.mnname            AS conn_name,
            t.moname            AS table_name,
            COALESCE(t.mousrm, '') AS query,
            t.morgid            AS added_by,
            t.morgdt            AS added_at,
            t.mochid            AS changed_by,
            t.mochdt            AS changed_at,
            t.mochno            AS changed_no
        FROM barcode.mmtbnm  t
        JOIN barcode.mmconc  c ON c.mnconciy  = t.moconciy
        JOIN barcode.mmengn  e ON e.mpengniy  = c.mnengniy
        WHERE t.modlfg <> '1'
        ORDER BY t.morgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_connection_table_map() -> dict[str, dict[str, list[str]]]:
    """
    Return a two-level map for cascading dropdowns:
      engine_code → conn_name → [table_names]

    Shape:
    {
      'postgresql': {
        'MyDB': ['orders', 'products'],
        'WarehouseDB': ['inventory']
      },
      'sqlite': {
        'LocalDB': ['items']
      }
    }
    """
    sql = """
        SELECT DISTINCT e.mpcode, c.mnname, t.moname
        FROM barcode.mmengn  e
        LEFT JOIN barcode.mmconc  c ON c.mnengniy = e.mpengniy AND c.mndlfg <> '1'
        LEFT JOIN barcode.mmtbnm  t ON t.moconciy  = c.mnconciy
        WHERE e.mpdlfg <> '1'
        ORDER BY e.mpcode, c.mnname, t.moname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        mapping: dict[str, dict[str, list[str]]] = {}
        for engine_code, conn_name, table_name in cur.fetchall():
            if engine_code not in mapping:
                mapping[engine_code] = {}
            if conn_name is not None:
                if conn_name not in mapping[engine_code]:
                    mapping[engine_code][conn_name] = []
                if table_name is not None:
                    mapping[engine_code][conn_name].append(table_name)
        return mapping
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_source_data(conn_name: str, engine_id: int,
                        table_name: str, query: str,
                        user: str = "Admin") -> int:
    """
    Insert a new mmtbnm row. engine_id is now required to scope the connection lookup.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        conciy = _resolve_or_create_connection(cur, conn_name, engine_id, user, now)

        cur.execute(
            """
            INSERT INTO barcode.mmtbnm (
                moname,   moconciy,
                morgid,   morgdt,
                mochid,   mochdt,
                mocsdt,   mocsid,
                mousrm
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING motbnmiy
            """,
            (table_name, conciy, user, now, user, now, now, user, query),
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

def update_source_data(pk: int, conn_name: str, engine_id: int,
                        table_name: str, query: str,
                        old_changed_no: int, user: str = "Admin"):
    """
    Update a mmtbnm row. engine_id required to correctly scope connection resolution.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        conciy = _resolve_or_create_connection(cur, conn_name, engine_id, user, now)

        cur.execute(
            """
            UPDATE barcode.mmtbnm SET
                moname   = %s,
                moconciy = %s,
                mousrm   = %s,
                mochid   = %s,
                mochdt   = %s,
                mochno   = %s
            WHERE motbnmiy = %s
            """,
            (table_name, conciy, query, user, now, old_changed_no + 1, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_source_data(pk: int, user: str = "Admin"):
    """Soft-delete by setting modlfg = '1'."""
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcode.mmtbnm SET
                modlfg = '1',
                mochid = %s,
                mochdt = %s
            WHERE motbnmiy = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── ID map ────────────────────────────────────────────────────────────────────

def fetch_tbnm_id_map() -> tuple[dict[str, int], dict[str, int]]:
    """
    Returns two maps for resolving name → FK ID:
      - tbnm_map:  "conn_name::table_name" → motbnmiy
      - conc_map:  "conn_name"             → mnconciy
    Now engine-scoped; keys include engine for safety:
      - tbnm_map:  "engine_code::conn_name::table_name" → motbnmiy
      - conc_map:  "engine_code::conn_name"             → mnconciy
    """
    sql = """
        SELECT e.mpcode, c.mnname, t.moname, t.motbnmiy, c.mnconciy
        FROM barcode.mmengn  e
        JOIN barcode.mmconc  c ON c.mnengniy = e.mpengniy AND c.mndlfg <> '1'
        JOIN barcode.mmtbnm  t ON t.moconciy  = c.mnconciy
        WHERE e.mpdlfg <> '1'
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        tbnm_map, conc_map = {}, {}
        for engine_code, conn_name, table_name, tbnmiy, conciy in cur.fetchall():
            tbnm_map[f"{engine_code}::{conn_name}::{table_name}"] = tbnmiy
            conc_map[f"{engine_code}::{conn_name}"] = conciy
        return tbnm_map, conc_map
    finally:
        conn.close()