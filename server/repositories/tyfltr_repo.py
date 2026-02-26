from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_tyfltr() -> list[dict]:
    sql = """
        SELECT
            tzengl   AS pk,
            tzspan   AS span,
            tzfren   AS fren,
            tzgerm   AS germ,

            tzrgid   AS added_by,
            tzrgdt   AS added_at,

            tzchid   AS changed_by,
            tzchdt   AS ch_dt,
            COALESCE(tzchno, 0) AS changed_no,

            tzgmbr   AS gmbr,
            tzposi   AS posi,
            tzdpfg   AS dp_fg,
            tzdsfg   AS ds_fg,
            tzptfg   AS pt_fg,
            tzptct   AS pt_ct,
            tzptid   AS pt_id,
            tzptdt   AS pt_dt,
            tzsrce   AS source,
            tzusrm   AS user_remark,
            tzitrm   AS item_remark

        FROM barcodesap.tyfltr
        WHERE tzdlfg <> '1'
        ORDER BY tzrgdt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_tyfltr_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            tzengl   AS pk,
            tzspan   AS span,
            tzfren   AS fren,
            tzgerm   AS germ,

            tzrgid   AS added_by,
            tzrgdt   AS added_at,

            tzchid   AS changed_by,
            tzchdt   AS ch_dt,
            COALESCE(tzchno, 0) AS changed_no,

            tzgmbr   AS gmbr,
            tzposi   AS posi,
            tzdpfg   AS dp_fg,
            tzdsfg   AS ds_fg,
            tzptfg   AS pt_fg,
            tzptct   AS pt_ct,
            tzptid   AS pt_id,
            tzptdt   AS pt_dt,
            tzsrce   AS source,
            tzusrm   AS user_remark,
            tzitrm   AS item_remark

        FROM barcodesap.tyfltr
        WHERE tzengl = %s
          AND tzdlfg <> '1'
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql, (pk,))
        cols = [desc[0] for desc in cur.description]
        row = cur.fetchone()
        return dict(zip(cols, row)) if row else None
    finally:
        conn.close()


# ── Create ────────────────────────────────────────────────────────────────────

def create_tyfltr(
    engl: str,
    span: str,
    fren: str,
    germ: str,
    gmbr: str | None = None,
    posi: str | None = None,
    user: str = "Admin",
) -> str:

    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO barcodesap.tyfltr (
                tzengl,
                tzspan, tzfren, tzgerm,
                tzgmbr, tzposi,
                tzrgid, tzrgdt,
                tzdlfg,
                tzchno
            )
            VALUES (
                %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                '0',
                0
            )
            RETURNING tzengl
            """,
            (
                engl,
                span, fren, germ,
                gmbr, posi,
                user, now,
            ),
        )
        pk = cur.fetchone()[0]
        conn.commit()
        return pk
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Update (Fixed Optimistic Locking) ─────────────────────────────────────────

def update_tyfltr(
    pk: str,
    span: str,
    fren: str,
    germ: str,
    old_changed_no: int,
    gmbr: str | None = None,
    posi: str | None = None,
    user: str = "Admin",
):

    existing = fetch_tyfltr_by_pk(pk)
    if existing is None:
        raise Exception(f"Record '{pk}' not found.")

    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.tyfltr
            SET
                tzspan = %s,
                tzfren = %s,
                tzgerm = %s,
                tzgmbr = %s,
                tzposi = %s,
                tzdpfg = %s,
                tzdsfg = %s,
                tzptfg = %s,
                tzptct = %s,
                tzptid = %s,
                tzptdt = %s,
                tzsrce = %s,
                tzusrm = %s,
                tzitrm = %s,
                tzchid = %s,
                tzchdt = %s,
                tzchno = COALESCE(tzchno, 0) + 1
            WHERE tzengl = %s
              AND COALESCE(tzchno, 0) = %s
            """,
            (
                span, fren, germ,
                gmbr, posi,
                existing["dp_fg"],
                existing["ds_fg"],
                existing["pt_fg"],
                existing["pt_ct"],
                existing["pt_id"],
                existing["pt_dt"],
                existing["source"],
                existing["user_remark"],
                existing["item_remark"],
                user, now,
                pk,
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception("Record was modified by another user.")

        conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Soft Delete (NULL-safe) ───────────────────────────────────────────────────

def soft_delete_tyfltr(pk: str, user: str = "Admin"):
    now = datetime.now()
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE barcodesap.tyfltr
            SET
                tzdlfg = '1',
                tzchid = %s,
                tzchdt = %s,
                tzchno = COALESCE(tzchno, 0) + 1
            WHERE tzengl = %s
            """,
            (user, now, pk),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()