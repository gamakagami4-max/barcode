"""Mixin for LINK type logic in TextPropertyEditor."""

from components.barcode_editor.utils import _LINE_DISABLED
from components.barcode_editor.scene_items import SelectableTextItem


class LinkMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item and the following widgets:
      link_combo, group_combo, table_combo, table_extra, field_edit, result_combo.
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_link(self, enabled: bool):
        self.link_combo.setEnabled(enabled)
        if enabled:
            stored_link = getattr(self.item, "design_link", "")
            if stored_link and stored_link not in ("", "—"):
                self._apply_link_fields(stored_link)
            else:
                self._clear_link_fields()
        else:
            self.item.design_link = ""

    # ── combo change handler ──────────────────────────────────────────────────

    def _on_link_changed(self, value: str):
        if value and value not in ("", "—"):
            self.item.design_link = value
            self._apply_link_fields(value)
        else:
            self.item.design_link = ""
            self._clear_link_fields()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _set_combo_value(self, combo, val: str):
        """Set value on a chevron combo, InlineChecklistWidget, or MultiSelectCombo safely."""
        from components.barcode_editor.text_property_editor import InlineChecklistWidget
        from components.barcode_editor.merge_konversi_mixin import MultiSelectCombo
        if isinstance(combo, (InlineChecklistWidget, MultiSelectCombo)):
            combo.set_selected(val)
        else:
            combo._current = val
            combo._label.setText(val)

    def _clear_combo_value(self, combo):
        """Clear value on a chevron combo, InlineChecklistWidget, or MultiSelectCombo safely."""
        from components.barcode_editor.text_property_editor import InlineChecklistWidget
        from components.barcode_editor.merge_konversi_mixin import MultiSelectCombo
        if isinstance(combo, (InlineChecklistWidget, MultiSelectCombo)):
            combo.clear_selection()
        else:
            combo._current = ""
            combo._label.setText("")

    # ── core logic ────────────────────────────────────────────────────────────

    def _apply_link_fields(self, source_name: str):
        """Copy GROUP/TABLE/QUERY/FIELD/RESULT from the linked LOOKUP source."""
        scene = self.item.scene()
        if not scene:
            return

        source_item = next(
            (si for si in scene.items()
             if si is not self.item
             and isinstance(si, SelectableTextItem)
             and getattr(si, "component_name", "") == source_name),
            None,
        )
        if not source_item:
            return

        self.item.design_group  = getattr(source_item, "design_group",  "")
        self.item.design_table  = getattr(source_item, "design_table",  "")
        self.item.design_query  = getattr(source_item, "design_query",  "")
        self.item.design_field  = getattr(source_item, "design_field",  "")
        self.item.design_result = getattr(source_item, "design_result", "")

        for combo, attr in (
            (self.group_combo,  "design_group"),
            (self.table_combo,  "design_table"),
            (self.field_edit,   "design_field"),
            (self.result_combo, "design_result"),
        ):
            val = getattr(self.item, attr, "")
            combo.setEnabled(False)
            self._set_combo_value(combo, val)

        self.table_extra.setEnabled(False)
        self.table_extra.setText(self.item.design_query)
        self.table_extra.setStyleSheet(_LINE_DISABLED)

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