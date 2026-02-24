# server/repositories/mmsdgr_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_sdgr() -> list[dict]:
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
            agg = row.pop("fields_agg", "") or ""
            row["fields"] = [f for f in agg.split("|") if f] if agg else []
            rows.append(row)
        return rows
    finally:
        conn.close()


def fetch_sdgr_by_id(sdgr_id: int) -> dict | None:
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
    if not field_names:
        return []

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
    return [name_to_id[n] for n in pure_fields if n in name_to_id]


def _insert_field_rows(cur, sdgr_pk: int, field_ids: list[int],
                       user: str, now: datetime) -> None:
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
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        # Insert parent row — machid/machdt/machno are intentionally omitted
        # so they default to NULL/0 on a fresh insert.  Only the add-audit
        # columns (margid, margdt) are populated here.
        cur.execute(
            """
            INSERT INTO barcode.mmsdgr (
                maconciy, matbnmiy,
                maqlsv,   maengn,
                margid,   margdt
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING masgdriy
            """,
            (conciy, tbnmiy, qlsv, engn, user, now),
        )
        pk = cur.fetchone()[0]

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
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

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

        if fields is not None:
            field_ids = _resolve_field_ids(cur, conciy, fields)
            _replace_field_rows(cur, pk, field_ids, user, now)

        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Delete (soft) ─────────────────────────────────────────────────────────────

def soft_delete_sdgr(pk: int, user: str = "Admin") -> None:
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            """
            UPDATE barcode.mmsdgf
            SET madlfg = '1'
            WHERE masgdriy = %s AND madlfg <> '1'
            """,
            (pk,),
        )

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

def fetch_table_columns(schema: str, table: str) -> list[dict]:
    sql = """
        SELECT
            col.column_name,
            col.data_type,
            col.is_nullable,
            col.column_default,
            col.ordinal_position,
            col_description(
                (col.table_schema || '.' || col.table_name)::regclass,
                col.ordinal_position
            ) AS comment
        FROM information_schema.columns col
        WHERE col.table_schema = %s
          AND col.table_name   = %s
        ORDER BY col.ordinal_position
    """

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (schema, table))

        results = []
        for row in cur.fetchall():
            results.append({
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "default": row[3],
                "position": row[4],
                "comment": row[5],   # 👈 HERE
            })

        return results
    finally:
        conn.close()