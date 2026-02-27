# server/repositories/mbarcd_repo.py

from datetime import datetime
from server.db import get_connection


# ── Read ──────────────────────────────────────────────────────────────────────

def fetch_all_mbarcd() -> list[dict]:
    sql = """
        SELECT
            mbbrcd   AS pk,
            mbbrnm   AS name,
            mbadby   AS added_by,
            mbaddt   AS added_at,
            mbchby   AS changed_by,
            mbchdt   AS changed_at,
            mbchno   AS changed_no,
            mbcono   AS company,
            mbheig   AS h_in,
            mbwidt   AS w_in,
            mbpixh   AS h_px,
            mbpixw   AS w_px,
            mbtype   AS type,
            mbconn   AS conn,
            mbsqlt   AS sql_text,
            mbfret   AS field_return,
            mbfixx   AS fix_x,
            mbrltn   AS rel_top,
            mbrlwt   AS rel_width,
            mbstnm   AS sticker_name,
            mbread   AS read_flag,
            mblook   AS lookup,
            mbpict1  AS picture1,
            mbpict2  AS picture2,
            mbsmple  AS sample,
            mbflag   AS flag,
            mbcolm   AS column,
            mbcont   AS cont,
            mbprnt   AS print,
            mbprfl   AS print_flag,
            mbdbfg   AS db_fg,
            mbdbiy   AS db_iy,
            mbadfg   AS ad_fg,
            mbadrl   AS ad_rl,
            mbadfr   AS ad_fr,
            mbprby   AS printed_by,
            mbprdt   AS printed_at,
            mbdpfg   AS dp_fg,
            mbhei3   AS h_in3,
            mbwid3   AS w_in3,
            mbpi3h   AS h_px3,
            mbpi3w   AS w_px3,
            mbstn3   AS sticker_name3,
            mbpic31  AS picture31,
            mbpic32  AS picture32
        FROM barcodesap.mbarcd
        ORDER BY mbaddt DESC
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        cols = [desc[0] for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()


def fetch_mbarcd_by_pk(pk: str) -> dict | None:
    sql = """
        SELECT
            mbbrcd   AS pk,
            mbbrnm   AS name,
            mbadby   AS added_by,
            mbaddt   AS added_at,
            mbchby   AS changed_by,
            mbchdt   AS changed_at,
            mbchno   AS changed_no,
            mbcono   AS company,
            mbheig   AS h_in,
            mbwidt   AS w_in,
            mbpixh   AS h_px,
            mbpixw   AS w_px,
            mbtype   AS type,
            mbconn   AS conn,
            mbsqlt   AS sql_text,
            mbfret   AS field_return,
            mbfixx   AS fix_x,
            mbrltn   AS rel_top,
            mbrlwt   AS rel_width,
            mbstnm   AS sticker_name,
            mbread   AS read_flag,
            mblook   AS lookup,
            mbpict1  AS picture1,
            mbpict2  AS picture2,
            mbsmple  AS sample,
            mbflag   AS flag,
            mbcolm   AS column,
            mbcont   AS cont,
            mbprnt   AS print,
            mbprfl   AS print_flag,
            mbdbfg   AS db_fg,
            mbdbiy   AS db_iy,
            mbadfg   AS ad_fg,
            mbadrl   AS ad_rl,
            mbadfr   AS ad_fr,
            mbprby   AS printed_by,
            mbprdt   AS printed_at,
            mbdpfg   AS dp_fg,
            mbhei3   AS h_in3,
            mbwid3   AS w_in3,
            mbpi3h   AS h_px3,
            mbpi3w   AS w_px3,
            mbstn3   AS sticker_name3,
            mbpic31  AS picture31,
            mbpic32  AS picture32
        FROM barcodesap.mbarcd
        WHERE mbbrcd = %s
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

def create_mbarcd(
    pk: str,
    name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    company: str | None = None,
    type_: str | None = None,
    sticker_name: str | None = None,
    flag: int = 0,
    cont: int = 0,
    print_: int = 0,
    print_flag: int = 0,
    db_fg: int = 0,
    ad_fg: int = 0,
    dp_fg: int = 0,
    user: str = "Admin",
) -> str:
    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO barcodesap.mbarcd (
                mbbrcd,
                mbbrnm,
                mbadby,
                mbaddt,
                mbchby,
                mbchdt,
                mbchno,
                mbcono,
                mbheig,
                mbwidt,
                mbpixh,
                mbpixw,
                mbtype,
                mbstnm,
                mbflag,
                mbcont,
                mbprnt,
                mbprfl,
                mbdbfg,
                mbadfg,
                mbdpfg
            )
            VALUES (
                %s,  -- pk / barcode id
                %s,  -- name
                %s,  -- added by
                %s,  -- added at
                %s,  -- changed by
                %s,  -- changed at
                0,   -- changed no
                %s,  -- company
                %s,  -- height inch
                %s,  -- width inch
                %s,  -- height px
                %s,  -- width px
                %s,  -- type
                %s,  -- sticker name (FK)
                %s,  -- flag
                %s,  -- cont
                %s,  -- print
                %s,  -- print flag
                %s,  -- db fg
                %s,  -- ad fg
                %s   -- dp fg
            )
            RETURNING mbbrcd
            """,
            (
                pk,
                name,
                user,
                now,
                user,
                now,
                company,
                h_in,
                w_in,
                h_px,
                w_px,
                type_,
                sticker_name,
                flag,
                cont,
                print_,
                print_flag,
                db_fg,
                ad_fg,
                dp_fg,
            ),
        )

        created_pk = cur.fetchone()[0]
        conn.commit()
        return created_pk

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


# ── Update (Optimistic Locking) ───────────────────────────────────────────────

def update_mbarcd(
    old_pk: str,
    new_pk: str,
    name: str,
    h_in: float,
    w_in: float,
    h_px: int,
    w_px: int,
    old_changed_no: int,
    company: str | None = None,
    type_: str | None = None,
    sticker_name: str | None = None,
    user: str = "Admin",
):
    existing = fetch_mbarcd_by_pk(old_pk)
    if existing is None:
        raise Exception(f"Record '{old_pk}' not found.")

    now = datetime.now()
    conn = get_connection()

    try:
        cur = conn.cursor()

        print("UPDATE_MBARCD PARAMS:")
        print({
            "old_pk": old_pk,
            "new_pk": new_pk,
            "name": name,
            "h_in": h_in,
            "w_in": w_in,
            "h_px": h_px,
            "w_px": w_px,
            "old_changed_no": old_changed_no,
        })

        cur.execute(
            """
            UPDATE barcodesap.mbarcd
            SET
                mbbrcd  = %s,
                mbbrnm  = %s,
                mbcono  = %s,
                mbheig  = %s,
                mbwidt  = %s,
                mbpixh  = %s,
                mbpixw  = %s,
                mbtype  = %s,
                mbconn  = %s,
                mbsqlt  = %s,
                mbfret  = %s,
                mbfixx  = %s,
                mbrltn  = %s,
                mbrlwt  = %s,
                mbstnm  = %s,
                mbread  = %s,
                mblook  = %s,
                mbpict1 = %s,
                mbpict2 = %s,
                mbflag  = %s,
                mbcolm  = %s,
                mbcont  = %s,
                mbprnt  = %s,
                mbprfl  = %s,
                mbdbfg  = %s,
                mbdbiy  = %s,
                mbadfg  = %s,
                mbadrl  = %s,
                mbadfr  = %s,
                mbdpfg  = %s,
                mbhei3  = %s,
                mbwid3  = %s,
                mbpi3h  = %s,
                mbpi3w  = %s,
                mbstn3  = %s,
                mbpic31 = %s,
                mbpic32 = %s,
                mbchby  = %s,
                mbchdt  = %s,
                mbchno  = %s
            WHERE mbbrcd = %s
              AND mbchno = %s
            """,
            (
                new_pk,
                name,
                company,
                h_in,
                w_in,
                h_px,
                w_px,
                type_,
                existing["conn"],
                existing["sql_text"],
                existing["field_return"],
                existing["fix_x"],
                existing["rel_top"],
                existing["rel_width"],
                sticker_name,
                existing["read_flag"],
                existing["lookup"],
                existing["picture1"],
                existing["picture2"],
                existing["flag"],
                existing["column"],
                existing["cont"],
                existing["print"],
                existing["print_flag"],
                existing["db_fg"],
                existing["db_iy"],
                existing["ad_fg"],
                existing["ad_rl"],
                existing["ad_fr"],
                existing["dp_fg"],
                existing["h_in3"],
                existing["w_in3"],
                existing["h_px3"],
                existing["w_px3"],
                existing["sticker_name3"],
                existing["picture31"],
                existing["picture32"],
                user,
                now,
                old_changed_no + 1,
                old_pk,
                old_changed_no,
            ),
        )

        if cur.rowcount == 0:
            raise Exception("Record was modified by another user.")

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("UPDATE_MBARCD ERROR:")
        print(e)
        raise

    finally:
        conn.close()


# ── Delete ────────────────────────────────────────────────────────────────────

def delete_mbarcd(pk: str, user: str = "Admin"):
    conn = get_connection()

    try:
        cur = conn.cursor()

        cur.execute(
            """
            DELETE FROM barcodesap.mbarcd
            WHERE mbbrcd = %s
            """,
            (pk,),
        )

        conn.commit()

    except Exception as e:
        conn.rollback()
        print("DELETE_MBARCD ERROR:")
        print(e)
        raise

    finally:
        conn.close()