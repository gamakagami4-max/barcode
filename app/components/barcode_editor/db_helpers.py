"""Database helper functions for the barcode editor (LOOKUP type).

Data is sourced from mmsdgr (Master Source Data Group) records.

Key facts from the actual repos:
  - fetch_all_mmsdgr()  -> fields is a comma-separated STRING of field NAMES
                           (from string_agg(fld.mtflnm, ', '))
  - fetch_tables_by_connection(conn_name) -> uses connection NAME as PK (not int)
  - connection_id in mmsdgr is the connection NAME string (mcconm)
  - table_id in mmsdgr is the table NAME string (mttbnm)
"""


def _fetch_connections() -> list[dict]:
    """
    Return distinct connection names that appear in mmsdgr source data records.
    Each entry is {pk: conn_name, name: conn_name}.
    """
    try:
        from repositories.mmsdgr_repo import fetch_all_mmsdgr
        from repositories.mconnc_repo import fetch_connections_by_engine
        from repositories.mengin_repo import fetch_all_engines

        # Build full set of valid connection names and a id->name map
        engines = fetch_all_engines()
        valid_conn_names: set[str] = set()
        conn_id_to_name: dict = {}
        for engine in engines:
            conns = fetch_connections_by_engine(engine["pk"])
            for c in conns:
                valid_conn_names.add(c["name"])
                conn_id_to_name[c["pk"]]   = c["name"]
                conn_id_to_name[c["name"]] = c["name"]

        records = fetch_all_mmsdgr()
        seen: set[str] = set()
        result: list[dict] = []

        for r in records:
            cid = r.get("connection_id")
            name = conn_id_to_name.get(cid) or (str(cid).strip() if cid else "")
            if name and name in valid_conn_names and name not in seen:
                seen.add(name)
                result.append({"pk": name, "name": name})

        return sorted(result, key=lambda x: x["name"])

    except Exception as e:
        import traceback
        print(f"[_fetch_connections] {e}")
        traceback.print_exc()
        return []


def _fetch_tables_for_connection(connection_name: str) -> list[dict]:
    """
    Return distinct table names from mmsdgr records for the given connection.
    Each entry is {pk: table_name, name: table_name}.
    """
    try:
        from repositories.mmsdgr_repo import fetch_all_mmsdgr
        from repositories.mconnc_repo import fetch_connections_by_engine
        from repositories.mengin_repo import fetch_all_engines

        # Build conn_id -> conn_name map
        engines = fetch_all_engines()
        conn_id_to_name: dict = {}
        for engine in engines:
            conns = fetch_connections_by_engine(engine["pk"])
            for c in conns:
                conn_id_to_name[c["pk"]]   = c["name"]
                conn_id_to_name[c["name"]] = c["name"]

        records = fetch_all_mmsdgr()
        seen: set[str] = set()
        result: list[dict] = []

        for r in records:
            cid = r.get("connection_id")
            resolved = conn_id_to_name.get(cid) or (str(cid).strip() if cid else "")
            if resolved != connection_name:
                continue

            # table_id is the table name string (mttbnm used as PK)
            tname = str(r.get("table_id") or "").strip()
            if tname and tname not in seen:
                seen.add(tname)
                result.append({"pk": tname, "name": tname})

        return sorted(result, key=lambda x: x["name"])

    except Exception as e:
        import traceback
        print(f"[_fetch_tables_for_connection] {e}")
        traceback.print_exc()
        return []


def _fetch_fields_for_table(table_name: str) -> list[str]:
    """
    Return field names from mmsdgr records for the given table.

    fetch_all_mmsdgr() returns `fields` as a comma-separated string of field
    NAMES (via string_agg(fld.mtflnm, ', ')), so no ID resolution needed.
    """
    try:
        from repositories.mmsdgr_repo import fetch_all_mmsdgr

        records = fetch_all_mmsdgr()
        seen: set[str] = set()
        result: list[str] = []

        for r in records:
            tname = str(r.get("table_id") or "").strip()
            if tname != table_name:
                continue

            raw = r.get("fields") or ""
            if isinstance(raw, str):
                names = [f.strip() for f in raw.split(",") if f.strip()]
            elif isinstance(raw, (list, tuple)):
                names = [str(f).strip() for f in raw if f]
            else:
                names = []

            for name in names:
                if name and name not in seen:
                    seen.add(name)
                    result.append(name)

        return sorted(result)

    except Exception as e:
        import traceback
        print(f"[_fetch_fields_for_table] {e}")
        traceback.print_exc()
        return []