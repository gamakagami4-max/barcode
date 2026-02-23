# server/repositories/mmsdgr_repo.py

from datetime import datetime
from server.db import get_connection


# ── DDL (run once) ────────────────────────────────────────────────────────────
#
# CREATE TABLE IF NOT EXISTS barcode.mmsdgf (
#     masgdfiy  SERIAL       PRIMARY KEY,
#     masgdriy  INT          NOT NULL REFERENCES barcode.mmsdgr(masgdriy),
#     matbnmiy  INT          NOT NULL REFERENCES barcode.mmtbnm(motbnmiy),
#     margid    VARCHAR(50)  NOT NULL DEFAULT '',
#     margdt    TIMESTAMP    NOT NULL DEFAULT NOW(),
#     madlfg    CHAR(1)      NOT NULL DEFAULT '0'
# );
# CREATE INDEX IF NOT EXISTS idx_mmsdgf_sgdriy ON barcode.mmsdgf(masgdriy);
#
# ─────────────────────────────────────────────────────────────────────────────


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_sdgr() -> list[dict]:
    """
    Fetch all active source-group records.
    Each row includes a 'fields' key: a list of field-name strings
    pulled from the mmsdgf → mmtbnm join.
    """
    sql = """
        SELECT
            s.masgdriy   AS pk,
            c.mnname     AS conn_name,
            t.moname     AS table_name,
            COALESCE(s.maqlsv, '') AS query,
            s.maengn     AS engine,
            s.margid     AS added_by,
            s.margdt     AS added_at,
            s.machid     AS changed_by,
            s.machdt     AS changed_at,
            s.machno     AS changed_no,
            -- aggregate selected field names as a pipe-separated string
            -- (pipe used to avoid conflicts with commas in field names)
            COALESCE(
                STRING_AGG(ft.moname, '|' ORDER BY ft.moname),
                ''
            ) AS fields_agg
        FROM barcode.mmsdgr  s
        JOIN barcode.mmconc  c  ON c.mnconciy  = s.maconciy
        LEFT JOIN barcode.mmtbnm  t  ON t.motbnmiy  = s.matbnmiy
        -- join to child fields table, then to tbnm for field names
        LEFT JOIN barcode.mmsdgf  f  ON f.masgdriy = s.masgdriy
                                     AND f.madlfg <> '1'
        LEFT JOIN barcode.mmtbnm  ft ON ft.motbnmiy = f.matbnmiy
                                     AND ft.modlfg  <> '1'
        WHERE s.madlfg <> '1'
        GROUP BY
            s.masgdriy, c.mnname, t.moname,
            s.maqlsv,   s.maengn,
            s.margid,   s.margdt,
            s.machid,   s.machdt,
            s.machno
        ORDER BY s.margdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        rows = []
        for raw in cur.fetchall():
            row = dict(zip(cols, raw))
            # split the pipe-separated aggregation into a proper list
            agg = row.pop("fields_agg", "") or ""
            row["fields"] = [f for f in agg.split("|") if f] if agg else []
            rows.append(row)
        return rows
    finally:
        conn.close()


def fetch_sdgr_by_id(sdgr_id: int) -> dict | None:
    """
    Fetch a single source-group record by PK, including its selected fields list.
    """
    sql = """
        SELECT
            s.masgdriy   AS pk,
            c.mnname     AS conn_name,
            t.moname     AS table_name,
            COALESCE(s.maqlsv, '') AS query,
            s.maengn     AS engine,
            s.margid     AS added_by,
            s.margdt     AS added_at,
            s.machid     AS changed_by,
            s.machdt     AS changed_at,
            s.machno     AS changed_no,
            COALESCE(
                STRING_AGG(ft.moname, '|' ORDER BY ft.moname),
                ''
            ) AS fields_agg
        FROM barcode.mmsdgr  s
        JOIN barcode.mmconc  c  ON c.mnconciy  = s.maconciy
        LEFT JOIN barcode.mmtbnm  t  ON t.motbnmiy  = s.matbnmiy
        LEFT JOIN barcode.mmsdgf  f  ON f.masgdriy = s.masgdriy
                                     AND f.madlfg <> '1'
        LEFT JOIN barcode.mmtbnm  ft ON ft.motbnmiy = f.matbnmiy
                                     AND ft.modlfg  <> '1'
        WHERE s.masgdriy = %s
          AND s.madlfg <> '1'
        GROUP BY
            s.masgdriy, c.mnname, t.moname,
            s.maqlsv,   s.maengn,
            s.margid,   s.margdt,
            s.machid,   s.machdt,
            s.machno
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (sdgr_id,))
        raw = cur.fetchone()
        if raw is None:
            return None
        cols = [desc[0] for desc in cur.description]
        row  = dict(zip(cols, raw))
        agg  = row.pop("fields_agg", "") or ""
        row["fields"] = [f for f in agg.split("|") if f] if agg else []
        return row
    finally:
        conn.close()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_field_ids(cur, conciy: int, field_names: list[str]) -> list[int]:
    """
    Given a connection ID and a list of field-name strings, return the
    corresponding motbnmiy PKs from mmtbnm.

    Only names WITHOUT a dot are treated as fields (same convention as
    _split_tables_and_fields in the UI layer).  Unknown names are silently
    skipped — the caller should validate upstream if strictness is needed.
    """
    if not field_names:
        return []

    # Filter to field-style names (no dot), deduplicate, preserve order
    seen: set[str] = set()
    pure_fields: list[str] = []
    for name in field_names:
        if "." not in name and name not in seen:
            seen.add(name)
            pure_fields.append(name)

    if not pure_fields:
        return []

    cur.execute(
        """
        SELECT motbnmiy, moname
        FROM barcode.mmtbnm
        WHERE moconciy = %s
          AND moname   = ANY(%s)
          AND modlfg  <> '1'
        """,
        (conciy, pure_fields),
    )
    name_to_id = {row[1]: row[0] for row in cur.fetchall()}
    # Return IDs in the same order as the input list (skipping unknowns)
    return [name_to_id[n] for n in pure_fields if n in name_to_id]


def _insert_field_rows(cur, sdgr_pk: int, field_ids: list[int],
                       user: str, now: datetime) -> None:
    """Insert one mmsdgf row per field ID."""
    for fid in field_ids:
        cur.execute(
            """
            INSERT INTO barcode.mmsdgf (masgdriy, matbnmiy, margid, margdt)
            VALUES (%s, %s, %s, %s)
            """,
            (sdgr_pk, fid, user, now),
        )


def _replace_field_rows(cur, sdgr_pk: int, field_ids: list[int],
                        user: str, now: datetime) -> None:
    """
    Soft-delete existing mmsdgf rows for this sdgr record, then
    insert fresh ones for the new field selection.
    """
    cur.execute(
        """
        UPDATE barcode.mmsdgf
        SET madlfg = '1'
        WHERE masgdriy = %s AND madlfg <> '1'
        """,
        (sdgr_pk,),
    )
    _insert_field_rows(cur, sdgr_pk, field_ids, user, now)


# ── Create ────────────────────────────────────────────────────────────────────

def create_sdgr(
    conciy: int,
    tbnmiy: int | None,
    qlsv: str,
    engn: str,
    fields: list[str] | None = None,
    user: str = "Admin",
) -> int:
    """
    Insert a new mmsdgr row and, if *fields* is provided, the corresponding
    mmsdgf child rows that record which fields were selected.

    Parameters
    ----------
    conciy  : FK to barcode.mmconc (connection)
    tbnmiy  : FK to barcode.mmtbnm (table name) — None in Query mode
    qlsv    : raw query / link-server string (empty string in Table mode)
    engn    : engine code string (e.g. 'postgresql')
    fields  : list of field-name strings to associate; resolved to mmtbnm IDs
    user    : audit user
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Insert the parent sdgr row
        cur.execute(
            """
            INSERT INTO barcode.mmsdgr (
                maconciy, matbnmiy,
                maqlsv,   maengn,
                margid,   margdt,
                machid,   machdt,
                macsdt,   macsid
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING masgdriy
            """,
            (conciy, tbnmiy, qlsv, engn, user, now, user, now, now, user),
        )
        pk = cur.fetchone()[0]

        # 2. Resolve and insert field rows (skip silently if none / query mode)
        if fields:
            field_ids = _resolve_field_ids(cur, conciy, fields)
            _insert_field_rows(cur, pk, field_ids, user, now)

        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update ────────────────────────────────────────────────────────────────────

def update_sdgr(
    pk: int,
    conciy: int,
    tbnmiy: int | None,
    qlsv: str,
    engn: str,
    old_changed_no: int,
    fields: list[str] | None = None,
    user: str = "Admin",
) -> None:
    """
    Update an existing mmsdgr row and replace its mmsdgf field associations.

    Parameters
    ----------
    pk             : PK of the mmsdgr row to update
    conciy         : FK to barcode.mmconc
    tbnmiy         : FK to barcode.mmtbnm (table) — None in Query mode
    qlsv           : query / link-server string
    engn           : engine code
    old_changed_no : current changed_no (will be incremented by 1)
    fields         : new list of selected field names (replaces old selection)
    user           : audit user
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # 1. Update the parent sdgr row
        cur.execute(
            """
            UPDATE barcode.mmsdgr SET
                maconciy = %s,
                matbnmiy = %s,
                maqlsv   = %s,
                maengn   = %s,
                machid   = %s,
                machdt   = %s,
                machno   = %s
            WHERE masgdriy = %s
              AND madlfg <> '1'
            """,
            (conciy, tbnmiy, qlsv, engn, user, now, old_changed_no + 1, pk),
        )

        # 2. Replace field associations
        if fields is not None:
            field_ids = _resolve_field_ids(cur, conciy, fields)
            _replace_field_rows(cur, pk, field_ids, user, now)
        else:
            # fields=None means "leave existing associations untouched"
            pass

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_sdgr(pk: int, user: str = "Admin") -> None:
    """
    Soft-delete an mmsdgr row AND its mmsdgf child rows in one transaction.
    """
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Soft-delete child field rows first
        cur.execute(
            """
            UPDATE barcode.mmsdgf
            SET madlfg = '1'
            WHERE masgdriy = %s AND madlfg <> '1'
            """,
            (pk,),
        )

        # Soft-delete the parent row
        cur.execute(
            """
            UPDATE barcode.mmsdgr SET
                madlfg = '1',
                machid = %s,
                machdt = %s
            WHERE masgdriy = %s
            """,
            (user, now, pk),
        )

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Column introspection ──────────────────────────────────────────────────────

def fetch_table_columns(schema: str, table_name: str) -> list[str]:
    """
    Returns column names from information_schema for the given schema.table.
    Strips any leading schema prefix from table_name (e.g. 'dbo.Orders' → 'Orders').
    """
    tbl = table_name.split(".")[-1]
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name   = %s
            ORDER BY ordinal_position
            """,
            (schema, tbl),
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()