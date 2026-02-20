# test_seed_connections.py
#
# Run this once to seed mmengn, mmconc, and mmtbnm with test data.
# Usage:
#   python test_seed_connections.py
#   python test_seed_connections.py --clean   ← wipes seeded rows first

import argparse
import sys
from datetime import datetime

# ── adjust this import to match your project structure ───────────────────────
from server.db import get_connection


# ── Seed definitions ──────────────────────────────────────────────────────────
#
# Structure:
#   ENGINE_CODE → list of {conn_name, tables: [str]}
#
SEED_DATA = {
    "postgresql": [
        {
            "conn_name": "WarehouseDB",
            "tables": [
                "inventory",
                "stock_movements",
                "suppliers",
            ],
        },
        {
            "conn_name": "SalesDB",
            "tables": [
                "orders",
                "order_items",
                "customers",
                "products",
            ],
        },
        {
            "conn_name": "BarcodeCoreDB",
            "tables": [
                "barcode.mmitem",
                "barcode.mmbrnd",
                "barcode.mmfltr",
                "barcode.mmprty",
            ],
        },
    ],
    "sqlite": [
        {
            "conn_name": "LocalCache",
            "tables": [
                "cached_items",
                "cached_barcodes",
            ],
        },
        {
            "conn_name": "OfflineSync",
            "tables": [
                "sync_queue",
                "sync_log",
                "pending_prints",
            ],
        },
    ],
}

USER = "seed_script"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _now():
    return datetime.now()


def _get_engine_id(cur, engine_code: str) -> int:
    cur.execute(
        "SELECT mpengniy FROM barcode.mmengn WHERE mpcode = %s AND mpdlfg <> '1'",
        (engine_code,),
    )
    row = cur.fetchone()
    if not row:
        raise ValueError(
            f"Engine '{engine_code}' not found in barcode.mmengn.\n"
            "Make sure you've run the mmengn CREATE + INSERT statements first."
        )
    return row[0]


def _get_or_create_connection(cur, conn_name: str, engine_id: int) -> tuple[int, bool]:
    """Returns (mnconciy, created: bool)."""
    cur.execute(
        """
        SELECT mnconciy FROM barcode.mmconc
        WHERE mnname = %s AND mnengniy = %s AND mndlfg <> '1'
        LIMIT 1
        """,
        (conn_name, engine_id),
    )
    row = cur.fetchone()
    if row:
        return row[0], False

    now = _now()
    cur.execute(
        """
        INSERT INTO barcode.mmconc (
            mnname, mnengniy,
            mnrgid, mnrgdt,
            mnchid, mnchdt,
            mncsdt, mncsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING mnconciy
        """,
        (conn_name, engine_id, USER, now, USER, now, now, USER),
    )
    return cur.fetchone()[0], True


def _get_or_create_table(cur, table_name: str, conciy: int) -> tuple[int, bool]:
    """Returns (motbnmiy, created: bool)."""
    cur.execute(
        """
        SELECT motbnmiy FROM barcode.mmtbnm
        WHERE moname = %s AND moconciy = %s AND modlfg <> '1'
        LIMIT 1
        """,
        (table_name, conciy),
    )
    row = cur.fetchone()
    if row:
        return row[0], False

    now = _now()
    cur.execute(
        """
        INSERT INTO barcode.mmtbnm (
            moname, moconciy,
            morgid, morgdt,
            mochid, mochdt,
            mocsdt, mocsid
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING motbnmiy
        """,
        (table_name, conciy, USER, now, USER, now, now, USER),
    )
    return cur.fetchone()[0], True


# ── Seed ──────────────────────────────────────────────────────────────────────

def seed():
    conn = get_connection()
    try:
        cur = conn.cursor()
        total_conns  = 0
        total_tables = 0

        for engine_code, connections in SEED_DATA.items():
            print(f"\n── Engine: {engine_code} ──")
            engine_id = _get_engine_id(cur, engine_code)

            for entry in connections:
                conn_name = entry["conn_name"]
                conciy, conn_created = _get_or_create_connection(cur, conn_name, engine_id)
                status = "CREATED" if conn_created else "exists"
                print(f"  [{status}] Connection: {conn_name!r} (id={conciy})")
                if conn_created:
                    total_conns += 1

                for table_name in entry["tables"]:
                    tbnmiy, tbl_created = _get_or_create_table(cur, table_name, conciy)
                    status = "CREATED" if tbl_created else "exists"
                    print(f"             [{status}] Table: {table_name!r} (id={tbnmiy})")
                    if tbl_created:
                        total_tables += 1

        conn.commit()
        print(f"\n✅ Seed complete — {total_conns} connection(s), {total_tables} table(s) created.")
    except Exception as exc:
        conn.rollback()
        print(f"\n❌ Seed failed: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


# ── Clean ─────────────────────────────────────────────────────────────────────

def clean():
    """
    Soft-delete all mmtbnm and mmconc rows that were created by this script.
    Does NOT touch mmengn.
    """
    conn = get_connection()
    now  = _now()
    try:
        cur = conn.cursor()

        # Soft-delete table rows first (FK child)
        cur.execute(
            """
            UPDATE barcode.mmtbnm SET modlfg = '1', mochid = %s, mochdt = %s
            WHERE morgid = %s AND modlfg <> '1'
            """,
            (USER, now, USER),
        )
        tbls = cur.rowcount

        # Soft-delete connection rows (FK parent)
        cur.execute(
            """
            UPDATE barcode.mmconc SET mndlfg = '1', mnchid = %s, mnchdt = %s
            WHERE mnrgid = %s AND mndlfg <> '1'
            """,
            (USER, now, USER),
        )
        conns = cur.rowcount

        conn.commit()
        print(f"🗑️  Cleaned — {conns} connection(s), {tbls} table(s) soft-deleted.")
    except Exception as exc:
        conn.rollback()
        print(f"❌ Clean failed: {exc}", file=sys.stderr)
        raise
    finally:
        conn.close()


# ── Verify ────────────────────────────────────────────────────────────────────

def verify():
    """Print a readable summary of what's currently in the DB."""
    sql = """
        SELECT e.mpcode, c.mnname, t.moname, t.motbnmiy
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
        if not rows:
            print("(no active connections / tables found)")
            return

        current_eng  = None
        current_conn = None
        for engine_code, conn_name, table_name, tbnmiy in rows:
            if engine_code != current_eng:
                print(f"\n── Engine: {engine_code} ──")
                current_eng  = engine_code
                current_conn = None
            if conn_name != current_conn:
                print(f"  Connection: {conn_name!r}")
                current_conn = conn_name
            print(f"    • {table_name!r} (id={tbnmiy})")
    finally:
        conn.close()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed / clean test connections and table names.")
    parser.add_argument("--clean",  action="store_true", help="Soft-delete all seeded rows")
    parser.add_argument("--verify", action="store_true", help="Print current DB state and exit")
    args = parser.parse_args()

    if args.verify:
        print("\n── Current DB state ──")
        verify()
    elif args.clean:
        clean()
        print()
        verify()
    else:
        seed()
        print()
        verify()