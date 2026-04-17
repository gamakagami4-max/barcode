"""Mixin for LINK type logic in TextPropertyEditor."""

from components.barcode_editor.utils import _LINE_DISABLED
from components.barcode_editor.scene_items import SelectableTextItem


class LinkMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item and the following widgets:
      link_combo, group_combo, table_combo, table_extra, field_edit, result_combo.

    Stores component_id in item.design_link (not component_name),
    so links survive component renames.
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_link(self, enabled: bool):
        self.link_combo.setEnabled(enabled)
        if enabled:
            stored_id = getattr(self.item, "design_link", "")
            if stored_id:
                # Restore display name in combo
                display_name = getattr(self.link_combo, "_id_map_inv", {}).get(stored_id, "")
                if display_name and display_name in self.link_combo._items:
                    self.link_combo.blockSignals(True)
                    self.link_combo.setCurrentText(display_name)
                    self.link_combo.blockSignals(False)
                self._apply_link_fields(stored_id)
                try:
                    self.result_combo.currentTextChanged.disconnect()
                except Exception:
                    pass
                self.result_combo.currentTextChanged.connect(self._on_link_result_changed)
            else:
                self._clear_link_fields()
        else:
            self.item.design_link = ""
            try:
                self.result_combo.currentTextChanged.disconnect()
            except Exception:
                pass
            self.result_combo.currentTextChanged.connect(
                lambda v: setattr(self.item, "design_result", v)
            )

    # ── combo change handler ──────────────────────────────────────────────────

    def _on_link_changed(self, value: str):
        if value and value not in ("", "—"):
            # Translate display name -> component_id
            source_id = getattr(self.link_combo, "_id_map", {}).get(value, "")
            if source_id:
                self.item.design_link = source_id  # store ID
                self._apply_link_fields(source_id)
            else:
                self.item.design_link = ""
                self._clear_link_fields()
        else:
            self.item.design_link = ""
            self._clear_link_fields()

    def _on_link_result_changed(self, value: str):
        """Called when user picks a new result column while in LINK mode."""
        self.item.design_result = value

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_combo_value(self, combo, val: str):
        """Set value on a chevron combo or InlineChecklistWidget safely."""
        from components.barcode_editor.text_property_editor import InlineChecklistWidget
        if isinstance(combo, InlineChecklistWidget):
            combo.set_selected(val)
        else:
            combo._current = val
            combo._label.setText(val)

    def _clear_combo_value(self, combo):
        """Clear value on a chevron combo or InlineChecklistWidget safely."""
        from components.barcode_editor.text_property_editor import InlineChecklistWidget
        if isinstance(combo, InlineChecklistWidget):
            combo.clear_selection()
        else:
            combo._current = ""
            combo._label.setText("")

    # ── core logic ────────────────────────────────────────────────────────────

    def _apply_link_fields(self, source_id: str):
        """Copy GROUP/TABLE/QUERY/FIELD/RESULT from the linked LOOKUP source (by ID)."""
        scene = self.item.scene()
        if not scene:
            return

        source_item = next(
            (si for si in scene.items()
            if si is not self.item
            and isinstance(si, SelectableTextItem)
            and getattr(si, "component_id", "") == source_id),
            None,
        )
        if not source_item:
            return

        # Skip re-applying if already linked to this source with same table (prevents wiping RESULT)
        current_link = getattr(self.item, "design_link", "")
        current_table = getattr(self.item, "design_table", "")
        source_table = getattr(source_item, "design_table", "")
        
        if current_link == source_id and current_table == source_table:
            # Just ensure controls are disabled correctly, don't wipe values
            for combo, attr in (
                (self.group_combo, "design_group"),
                (self.table_combo, "design_table"),
            ):
                combo.setEnabled(False)
                self._set_combo_value(combo, getattr(self.item, attr, ""))
            
            self.table_extra.setEnabled(False)
            self.table_extra.blockSignals(True)
            self.table_extra.setText(self.item.design_query)
            self.table_extra.blockSignals(False)
            self.table_extra.setStyleSheet(
                "QTextEdit { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:4px; "
                "padding:5px; font-size:11px; color:#94A3B8; }"
            )
            
            self.result_combo.setEnabled(True)
            try:
                self.result_combo.currentTextChanged.disconnect()
            except Exception:
                pass
            self.result_combo.currentTextChanged.connect(self._on_link_result_changed)
            self.field_edit.setEnabled(False)
            self.field_edit._apply_disabled_appearance()
            return

        # Preserve this item's own result BEFORE copying anything from source
        saved_result = getattr(self.item, "design_result", "")

        self.item.design_group = getattr(source_item, "design_group", "")
        self.item.design_table = source_table
        self.item.design_query = getattr(source_item, "design_query", "")
        self.item.design_field = getattr(source_item, "design_field", "")
        # Do NOT copy design_result from source — each LINK item picks its own result column

        # GROUP and TABLE — read-only, mirrored from source
        for combo, attr in (
            (self.group_combo, "design_group"),
            (self.table_combo, "design_table"),
        ):
            combo.setEnabled(False)
            self._set_combo_value(combo, getattr(self.item, attr, ""))

        # QUERY — read-only, mirrored from source
        self.table_extra.setEnabled(False)
        self.table_extra.blockSignals(True)
        self.table_extra.setText(self.item.design_query)
        self.table_extra.blockSignals(False)
        self.table_extra.setStyleSheet(
            "QTextEdit { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:4px; "
            "padding:5px; font-size:11px; color:#94A3B8; }"
        )

        # Populate result_combo items by replaying the table-load from LookupMixin
        table = getattr(self.item, "design_table", "")
        if table:
            self._on_table_changed(table)  # fills _items on field_edit and result_combo
            # _on_table_changed resets result to "" so restore it
            self.item.design_result = saved_result
            try:
                self.result_combo.currentTextChanged.disconnect()
            except Exception:
                pass
            self.result_combo.currentTextChanged.connect(self._on_link_result_changed)
            self.result_combo.blockSignals(True)
            self.result_combo.setEnabled(True)
            if saved_result and saved_result in getattr(self.result_combo, "_items", []):
                self.result_combo._current = saved_result
                self.result_combo._label.setText(saved_result)
            self.result_combo.blockSignals(False)
        else:
            try:
                self.result_combo.currentTextChanged.disconnect()
            except Exception:
                pass
            self.result_combo.currentTextChanged.connect(self._on_link_result_changed)
            self.result_combo.blockSignals(True)
            self.result_combo.setEnabled(True)
            val = getattr(self.item, "design_result", "")
            self._set_combo_value(self.result_combo, val)
            self.result_combo.blockSignals(False)

        # FIELD — always disabled for LINK type (value mirrored, not editable).
        # This must be the LAST operation so result_combo.setEnabled(True) above
        # cannot indirectly re-enable it through any Qt layout/paint cascade.
        self.field_edit.blockSignals(True)
        self._set_combo_value(self.field_edit, getattr(self.item, "design_field", ""))
        self.field_edit.blockSignals(False)
        self.field_edit.setEnabled(False)
        self.field_edit._apply_disabled_appearance()

    def _clear_link_fields(self):
        for attr in ("design_group", "design_table", "design_query",
                     "design_field", "design_result"):
            setattr(self.item, attr, "")

        for combo in (self.group_combo, self.table_combo,
                      self.field_edit, self.result_combo):
            combo.setEnabled(False)
            self._clear_combo_value(combo)

        self.table_extra.setEnabled(False)
        self.table_extra.clear()
        self.table_extra.setStyleSheet(_LINE_DISABLED)

    def clear_link_fields(self):
        """Clear LINK selection and reset all linked fields when switching away."""
        self.item.design_link = ""

        self.link_combo._current = ""
        self.link_combo._label.setText("")
        self.link_combo.setCurrentIndex(-1)

        self._clear_link_fields()