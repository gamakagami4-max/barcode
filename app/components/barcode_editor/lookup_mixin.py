"""Mixin for LOOKUP type logic in TextPropertyEditor."""

from components.barcode_editor.utils import MODERN_INPUT_STYLE, _LINE_DISABLED
from components.barcode_editor.db_helpers import (
    _fetch_connections, _fetch_tables_for_connection, _fetch_fields_for_table,
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
            has_group = bool(self.group_combo.currentText())
            self.table_combo.setEnabled(has_group)
            has_table = bool(self.table_combo.currentText())
            self.field_edit.setEnabled(has_table)
            self.result_combo.setEnabled(has_table)
        else:
            for w in (self.table_combo, self.field_edit, self.result_combo):
                w.setEnabled(False)

        self.table_extra.setEnabled(enabled)
        self.table_extra.setStyleSheet(MODERN_INPUT_STYLE if enabled else _LINE_DISABLED)

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

        self.table_extra.setText("")
        self._clear_field_combos()
        self._table_map = {}

        # Re-populate connections so switching back to LOOKUP still works
        self.build_connection_combo()  # ← replaces clearing _conn_map
        
    def _on_table_changed(self, table_name: str):
        # Save selected table immediately
        setattr(self.item, "design_table", table_name)

        if not table_name:
            self._clear_field_combos()
            return

        fields = _fetch_fields_for_table(table_name)

        self._field_list = fields
        opts = fields if fields else [""]

        for combo in (self.field_edit, self.result_combo):
            combo._items = opts
            combo._current = ""
            combo._label.setText("")
            combo.setEnabled(bool(fields))
            combo.setCurrentIndex(-1)

    def _clear_field_combos(self):
        self._field_list = []
        for combo in (self.field_edit, self.result_combo):
            combo._items   = [""]
            combo._current = ""
            combo._label.setText("")
            combo.setEnabled(False)
            combo.setCurrentIndex(-1)

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
        """Restore persisted LOOKUP values when loading a saved design."""
        if stored_group and stored_group in self._conn_map:
            self.group_combo.setCurrentText(stored_group)
            self._on_group_changed(stored_group)   # force table load

            if stored_table:
                self.table_combo.setCurrentText(stored_table)
                self._on_table_changed(stored_table)  # force field load

                if stored_field:
                    self.field_edit.setCurrentText(stored_field)

                if stored_result:
                    self.result_combo.setCurrentText(stored_result)
        if stored_query:
            self.table_extra.setText(stored_query)