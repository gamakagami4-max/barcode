"""Mixin for LOOKUP type logic in TextPropertyEditor."""

from components.barcode_editor.utils import MODERN_INPUT_STYLE, _LINE_DISABLED
from components.barcode_editor.db_helpers import (
    _fetch_connections, _fetch_tables_for_connection, _fetch_fields_for_table,
    _parse_fields_from_query,
)


class LookupMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item and the following widgets:
      group_combo, table_combo, table_extra, field_edit, result_combo.
    Internal state: self._conn_map, self._table_map, self._field_list.
    """

    def init_lookup_state(self):
        """Call once from TextPropertyEditor.__init__ before building widgets."""
        self._conn_map:   dict      = {}
        self._table_map:  dict      = {}
        self._field_list: list[str] = []

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_lookup(self, enabled: bool):
        """Enable/disable the LOOKUP cascade depending on current type."""
        self.group_combo.setEnabled(enabled)

        if enabled:
            self.build_connection_combo()
            current_group = getattr(self.item, "design_group", "")
            if current_group and current_group not in self.group_combo._items:
                setattr(self.item, "design_group", "")
                setattr(self.item, "design_table", "")
                setattr(self.item, "design_field", "")
                setattr(self.item, "design_result", "")
                self.group_combo.setCurrentIndex(-1)
                self.table_combo._items = [""]
                self.table_combo._current = ""
                self.table_combo._label.setText("")
                self.table_combo.setCurrentIndex(-1)
                self.table_combo.setEnabled(False)
                self._clear_field_combos()
            elif current_group:
                self.group_combo.setCurrentText(current_group)
                from components.barcode_editor.db_helpers import _fetch_tables_for_connection
                tables = _fetch_tables_for_connection(self._conn_map[current_group])
                self._table_map = {t["name"]: t["pk"] for t in tables}
                current_table = getattr(self.item, "design_table", "")
                if current_table and current_table not in self._table_map:
                    setattr(self.item, "design_table", "")
                    setattr(self.item, "design_field", "")
                    setattr(self.item, "design_result", "")
                    self.table_combo._items = list(self._table_map.keys()) or [""]
                    self.table_combo._current = ""
                    self.table_combo._label.setText("")
                    self.table_combo.setCurrentIndex(-1)
                    self._clear_field_combos()

        if enabled:
            _original_open = self.group_combo._open

            def _live_open():
                self.build_connection_combo()
                current = getattr(self.item, "design_group", "")
                if current and current in self.group_combo._items:
                    self.group_combo.setCurrentText(current)
                elif current:
                    setattr(self.item, "design_group", "")
                    self.group_combo.setCurrentIndex(-1)
                    self.table_combo._items = [""]
                    self.table_combo._current = ""
                    self.table_combo._label.setText("")
                    self.table_combo.setCurrentIndex(-1)
                    self.table_combo.setEnabled(False)
                    self._clear_field_combos()
                _original_open()

            self.group_combo._open = _live_open

        if enabled:
            has_group = bool(self.group_combo.currentText())
            self.table_combo.setEnabled(has_group)
            has_table = bool(self.table_combo.currentText())
            self.field_edit.setEnabled(has_table)
            self.result_combo.setEnabled(has_table)
        else:
            for w in (self.table_combo, self.field_edit, self.result_combo):
                w.setEnabled(False)

        self.table_extra.setEnabled(enabled)
        _enabled_style = (
            "QTextEdit { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:4px; "
            "padding:5px; font-size:11px; color:#1E293B; }"
            "QTextEdit:focus { border:1px solid #6366F1; }"
        )
        _disabled_style = (
            "QTextEdit { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:4px; "
            "padding:5px; font-size:11px; color:#94A3B8; }"
        )
        self.table_extra.setStyleSheet(_enabled_style if enabled else _disabled_style)

    # ── cascade change handlers ───────────────────────────────────────────────

    def _on_group_changed(self, conn_name: str):
        conn_pk = self._conn_map.get(conn_name)
        if conn_pk is None:
            self.table_combo._items = [""]
            self.table_combo.setCurrentIndex(-1)
            self.table_combo.setEnabled(False)
            self._table_map = {}
            self._clear_field_combos()
            return

        tables = _fetch_tables_for_connection(conn_pk)
        self._table_map = {t["name"]: t["pk"] for t in tables}
        table_names = list(self._table_map.keys())

        self.table_combo._items   = table_names if table_names else [""]
        self.table_combo._current = ""
        self.table_combo._label.setText("")
        self.table_combo.setEnabled(bool(table_names))
        self.table_combo.setPlaceholderText("— select table —")
        self.table_combo.setCurrentIndex(-1)

        setattr(self.item, "design_group", conn_name)
        self._clear_field_combos()

        _original_open = self.table_combo._open

        def _live_table_open():
            tables = _fetch_tables_for_connection(conn_pk)
            self._table_map = {t["name"]: t["pk"] for t in tables}
            self.table_combo._items = list(self._table_map.keys()) or [""]
            if self.table_combo._dropdown:
                self.table_combo._dropdown._options = self.table_combo._items
                for btn in self.table_combo._dropdown._buttons:
                    btn.deleteLater()
                self.table_combo._dropdown._buttons = []
                self.table_combo._dropdown._build(self.table_combo.width())
            current_table = getattr(self.item, "design_table", "")
            if current_table and current_table not in self._table_map:
                setattr(self.item, "design_table", "")
                self.table_combo._current = ""
                self.table_combo._label.setText("")
                self.table_combo.setCurrentIndex(-1)
                self._clear_field_combos()
            _original_open()

        self.table_combo._open = _live_table_open

    def clear_lookup_fields(self):
        """Clear all LOOKUP field values on the item and reset the widgets."""
        for attr in ("design_group", "design_table", "design_query",
                     "design_field", "design_result"):
            setattr(self.item, attr, "")

        self.group_combo._items   = [""]
        self.group_combo._current = ""
        self.group_combo._label.setText("")
        self.group_combo.setCurrentIndex(-1)

        self.table_combo._items   = [""]
        self.table_combo._current = ""
        self.table_combo._label.setText("")
        self.table_combo.setCurrentIndex(-1)

        self.table_extra.setPlainText("")
        self._clear_field_combos()
        self._table_map = {}

        self.build_connection_combo()

    def _on_table_changed(self, table_name: str):
        setattr(self.item, "design_table", table_name)
        if not table_name:
            self._clear_field_combos()
            return

        display_fields: list[str] = []
        try:
            conn_name = self.group_combo.currentText() or getattr(self.item, "design_group", "")
            conn_pk   = self._conn_map.get(conn_name)

            if not self._table_map and conn_pk is not None:
                tables = _fetch_tables_for_connection(conn_pk)
                self._table_map = {t["name"]: t["pk"] for t in tables}

            table_pk = self._table_map.get(table_name)

            if conn_pk is not None and table_pk is not None:
                from repositories.mmsdgr_repo import fetch_all_mmsdgr, fetch_mmsdgr_by_pk
                from repositories.field_repo import fetch_field_names_by_ids, fetch_fields

                all_records = fetch_all_mmsdgr()
                matched = next(
                    (r for r in all_records
                     if r["connection_id"] == conn_pk and r.get("table_id") == table_pk),
                    None,
                )

                if matched:
                    detail     = fetch_mmsdgr_by_pk(matched["pk"])
                    raw_fields = detail.get("fields", []) if detail else []

                    if isinstance(raw_fields, str):
                        # Stored as comma-separated field names
                        field_names = [f.strip() for f in raw_fields.split(",") if f.strip()]
                        seen = set()
                        field_names = [f for f in field_names if not (f in seen or seen.add(f))]
                    else:
                        # Stored as list of integer IDs
                        field_ids = list(raw_fields)
                        if field_ids:
                            seen = set()
                            field_ids = [f for f in field_ids if not (f in seen or seen.add(f))]
                            field_names = fetch_field_names_by_ids(field_ids)
                            seen = set()
                            field_names = [f for f in field_names if not (f in seen or seen.add(f))]
                        else:
                            field_names = []

                    cols = fetch_fields(conn_pk, table_name)
                    comment_map = {
                        col["name"]: col.get("comment", "")
                        for col in cols if col.get("name")
                    }
                    for name in field_names:
                        comment = comment_map.get(name, "")
                        display_fields.append(f"{name} AS {comment}" if comment else name)

        except Exception as e:
            import traceback
            print(f"Error loading source group fields: {e}")
            traceback.print_exc()

        self._field_list = display_fields

        self.field_edit.set_items(display_fields)
        self.field_edit.setEnabled(bool(display_fields))

        self.result_combo._items   = display_fields if display_fields else [""]
        self.result_combo._current = ""
        self.result_combo._label.setText("")
        self.result_combo.setCurrentIndex(-1)
        self.result_combo.setEnabled(bool(display_fields))

    def _clear_field_combos(self):
        self._field_list = []

        self.field_edit.set_items([])
        self.field_edit.clear_selection()
        self.field_edit.setEnabled(False)

        self.result_combo._items   = [""]
        self.result_combo._current = ""
        self.result_combo._label.setText("")
        self.result_combo.setCurrentIndex(-1)
        self.result_combo.setEnabled(False)

    # ── populate combos from DB on init ──────────────────────────────────────

    def build_connection_combo(self):
        """Fetch connections from DB and populate group_combo. Returns conn_names."""
        connections = _fetch_connections()
        self._conn_map = {c["name"]: c["pk"] for c in connections}
        conn_names = list(self._conn_map.keys())
        self.group_combo._items   = conn_names if conn_names else [""]
        self.group_combo._current = ""
        self.group_combo._label.setText("")
        self.group_combo.setPlaceholderText("— select connection —")
        self.group_combo.setCurrentIndex(-1)
        return conn_names

    def restore_lookup_values(self, stored_group, stored_table, stored_field,
                      stored_result, stored_query):
        from PySide6.QtCore import QTimer

        if stored_group and stored_group in self._conn_map:
            self.group_combo.setCurrentText(stored_group)
            self._on_group_changed(stored_group)

            if stored_table:
                self.table_combo.setCurrentText(stored_table)
                self._on_table_changed(stored_table)

                if stored_field:
                    if isinstance(stored_field, str):
                        fields_to_restore = [f.strip() for f in stored_field.split(",") if f.strip()]
                    else:
                        fields_to_restore = list(stored_field)

                    setattr(self.item, "design_field", stored_field)

                    if not self._field_list:
                        self.field_edit.set_items(fields_to_restore)
                        self._field_list = fields_to_restore

                    # Delay set_selected by one event loop tick so the
                    # checklist widget finishes rendering before we check boxes
                    QTimer.singleShot(0, lambda f=fields_to_restore: self.field_edit.set_selected(f))

                if stored_result:
                    self.result_combo.setCurrentText(stored_result)
                    setattr(self.item, "design_result", stored_result)

        if stored_query:
            self.table_extra.setPlainText(stored_query)
            setattr(self.item, "design_query", stored_query)