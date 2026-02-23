# test_seed_connections.py
#
# Reads REAL data from barcode.mmengn, barcode.mmconc, and barcode.mmtbnm.
# No fake data is inserted — this script only inspects and verifies what's
# already in the database.
#
# Usage:
#   python test_seed_connections.py              ← verify current DB state
#   python test_seed_connections.py --verify     ← same, explicit flag
#   python test_seed_connections.py --summary    ← compact count summary only
#   python test_seed_connections.py --check-fk   ← check mmsdgr + mmsdgf integrity

import argparse
import sys

from server.db import get_connection


# ── Verify ────────────────────────────────────────────────────────────────────

def verify(show_fields: bool = True):
    """
    Print a full readable tree of engines → connections → tables/fields
    that currently exist in the DB (active rows only).
    """
    sql = """
        SELECT
            e.mpcode     AS engine_code,
            e.mpengniy   AS engine_id,
            c.mnname     AS conn_name,
            c.mnconciy   AS conn_id,
            t.moname     AS entry_name,
            t.motbnmiy   AS entry_id
        FROM barcode.mmengn  e
        JOIN barcode.mmconc  c ON c.mnengniy = e.mpengniy AND c.mndlfg <> '1'
        JOIN barcode.mmtbnm  t ON t.moconciy  = c.mnconciy AND t.modlfg <> '1'
        WHERE e.mpdlfg <> '1'
        ORDER BY e.mpcode, c.mnname, t.moname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("(no active engines / connections / entries found)")
        return

    current_eng  = None
    current_conn = None
    table_count  = 0
    field_count  = 0

    for engine_code, engine_id, conn_name, conn_id, entry_name, entry_id in rows:
        if engine_code != current_eng:
            print(f"\n── Engine: {engine_code!r} (id={engine_id}) ──")
            current_eng  = engine_code
            current_conn = None

        if conn_name != current_conn:
            print(f"  Connection: {conn_name!r} (id={conn_id})")
            current_conn = conn_name

        is_table = "." in entry_name
        kind = "Table" if is_table else "Field"

        if is_table:
            table_count += 1
        else:
            field_count += 1

        if show_fields or is_table:
            print(f"    [{kind}] {entry_name!r} (id={entry_id})")

    print(f"\n── Totals: {table_count} table(s), {field_count} field(s) ──")


# ── Summary ───────────────────────────────────────────────────────────────────

def summary():
    """Print a compact count summary per engine → connection."""
    sql = """
        SELECT
            e.mpcode,
            c.mnname,
            COUNT(*) FILTER (WHERE t.moname LIKE '%.%') AS table_count,
            COUNT(*) FILTER (WHERE t.moname NOT LIKE '%.%') AS field_count
        FROM barcode.mmengn  e
        JOIN barcode.mmconc  c ON c.mnengniy = e.mpengniy AND c.mndlfg <> '1'
        JOIN barcode.mmtbnm  t ON t.moconciy  = c.mnconciy AND t.modlfg <> '1'
        WHERE e.mpdlfg <> '1'
        GROUP BY e.mpcode, c.mnname
        ORDER BY e.mpcode, c.mnname
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        print("(no active data found)")
        return

    print(f"\n{'ENGINE':<20} {'CONNECTION':<25} {'TABLES':>7} {'FIELDS':>7}")
    print("─" * 62)
    for engine_code, conn_name, tbl_cnt, fld_cnt in rows:
        print(f"{engine_code:<20} {conn_name:<25} {tbl_cnt:>7} {fld_cnt:>7}")
    print("─" * 62)
    total_tbls = sum(r[2] for r in rows)
    total_flds = sum(r[3] for r in rows)
    print(f"{'TOTAL':<46} {total_tbls:>7} {total_flds:>7}")


# ── FK integrity check ────────────────────────────────────────────────────────

def check_fk():
    """
    Verify mmsdgr and mmsdgf referential integrity:
    - Every active mmsdgr row should have a valid maconciy (mmconc)
    - Every active mmsdgr row with a matbnmiy should have a valid mmtbnm row
    - Every active mmsdgf row should have a valid masgdriy (mmsdgr) and matbnmiy (mmtbnm)
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        issues = 0

        # ── mmsdgr → mmconc ───────────────────────────────────────────────────
        cur.execute("""
            SELECT s.masgdriy, s.maconciy
            FROM barcode.mmsdgr s
            LEFT JOIN barcode.mmconc c ON c.mnconciy = s.maconciy AND c.mndlfg <> '1'
            WHERE s.madlfg <> '1'
              AND c.mnconciy IS NULL
        """)
        orphan_conc = cur.fetchall()
        if orphan_conc:
            print(f"⚠️  mmsdgr rows with missing/deleted mmconc ({len(orphan_conc)}):")
            for pk, conciy in orphan_conc:
                print(f"   masgdriy={pk}, maconciy={conciy}")
            issues += len(orphan_conc)
        else:
            print("✅ mmsdgr → mmconc: all OK")

        # ── mmsdgr → mmtbnm (table) ───────────────────────────────────────────
        cur.execute("""
            SELECT s.masgdriy, s.matbnmiy
            FROM barcode.mmsdgr s
            LEFT JOIN barcode.mmtbnm t ON t.motbnmiy = s.matbnmiy AND t.modlfg <> '1'
            WHERE s.madlfg <> '1'
              AND s.matbnmiy IS NOT NULL
              AND t.motbnmiy IS NULL
        """)
        orphan_tbnm = cur.fetchall()
        if orphan_tbnm:
            print(f"⚠️  mmsdgr rows with missing/deleted mmtbnm (table) ({len(orphan_tbnm)}):")
            for pk, tbnmiy in orphan_tbnm:
                print(f"   masgdriy={pk}, matbnmiy={tbnmiy}")
            issues += len(orphan_tbnm)
        else:
            print("✅ mmsdgr → mmtbnm (table): all OK")

        # ── mmsdgf → mmsdgr ───────────────────────────────────────────────────
        cur.execute("""
            SELECT f.masgdfiy, f.masgdriy
            FROM barcode.mmsdgf f
            LEFT JOIN barcode.mmsdgr s ON s.masgdriy = f.masgdriy AND s.madlfg <> '1'
            WHERE f.madlfg <> '1'
              AND s.masgdriy IS NULL
        """)
        orphan_sdgf_sgdr = cur.fetchall()
        if orphan_sdgf_sgdr:
            print(f"⚠️  mmsdgf rows with missing/deleted mmsdgr ({len(orphan_sdgf_sgdr)}):")
            for pk, sgdriy in orphan_sdgf_sgdr:
                print(f"   masgdfiy={pk}, masgdriy={sgdriy}")
            issues += len(orphan_sdgf_sgdr)
        else:
            print("✅ mmsdgf → mmsdgr: all OK")

        # ── mmsdgf → mmtbnm (field) ───────────────────────────────────────────
        cur.execute("""
            SELECT f.masgdfiy, f.matbnmiy
            FROM barcode.mmsdgf f
            LEFT JOIN barcode.mmtbnm t ON t.motbnmiy = f.matbnmiy AND t.modlfg <> '1'
            WHERE f.madlfg <> '1'
              AND t.motbnmiy IS NULL
        """)
        orphan_sdgf_tbnm = cur.fetchall()
        if orphan_sdgf_tbnm:
            print(f"⚠️  mmsdgf rows with missing/deleted mmtbnm (field) ({len(orphan_sdgf_tbnm)}):")
            for pk, tbnmiy in orphan_sdgf_tbnm:
                print(f"   masgdfiy={pk}, matbnmiy={tbnmiy}")
            issues += len(orphan_sdgf_tbnm)
        else:
            print("✅ mmsdgf → mmtbnm (field): all OK")

        # ── mmsdgr counts ─────────────────────────────────────────────────────
        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE madlfg <> '1') AS active,
                COUNT(*) FILTER (WHERE madlfg  = '1') AS deleted
            FROM barcode.mmsdgr
        """)
        active, deleted = cur.fetchone()
        print(f"\n📊 mmsdgr: {active} active row(s), {deleted} soft-deleted")

        cur.execute("""
            SELECT
                COUNT(*) FILTER (WHERE madlfg <> '1') AS active,
                COUNT(*) FILTER (WHERE madlfg  = '1') AS deleted
            FROM barcode.mmsdgf
        """)
        f_active, f_deleted = cur.fetchone()
        print(f"📊 mmsdgf: {f_active} active field link(s), {f_deleted} soft-deleted")

        if issues == 0:
            print("\n✅ All FK checks passed — data integrity looks good.")
        else:
            print(f"\n❌ {issues} integrity issue(s) found.")

    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Inspect real barcode DB connection/table data and check integrity."
    )
    parser.add_argument(
        "--verify",   action="store_true",
        help="Print full engine → connection → table/field tree (default)"
    )
    parser.add_argument(
        "--no-fields", action="store_true",
        help="When verifying, hide field entries and show tables only"
    )
    parser.add_argument(
        "--summary",  action="store_true",
        help="Print compact count table per engine/connection"
    )
    parser.add_argument(
        "--check-fk", action="store_true",
        help="Check mmsdgr and mmsdgf referential integrity"
    )
    args = parser.parse_args()

    if args.summary:
        summary()
    elif args.check_fk:
        print("\n── FK Integrity Check ──")
        check_fk()
    else:
        # Default: verify (full tree)
        print("\n── Current DB State ──")
        verify(show_fields=not args.no_fields)