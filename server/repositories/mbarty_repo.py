"""Repository for barcodesap.mbarty (barcode type master)."""


def fetch_all_mbarty() -> list[dict]:
    """
    Return all rows from barcodesap.mbarty as a list of dicts.
    Each dict has: pk (BRCODE), name (BRBART), is_2d (BR2DFG).
    Ordered by BRBART.
    """
    try:
        from db import get_connection  # ← same import you use everywhere else
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT BRCODE, BRBART, BR2DFG
            FROM barcodesap.mbarty
            ORDER BY BRBART
        """)
        rows = cursor.fetchall()
        cursor.close()
        return [
            {"pk": row[0], "name": row[1], "is_2d": bool(row[2])}
            for row in rows
        ]
    except Exception as e:
        import traceback
        print(f"[fetch_all_mbarty] {e}")
        traceback.print_exc()
        return []