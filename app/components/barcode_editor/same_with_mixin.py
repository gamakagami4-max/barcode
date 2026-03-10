"""Mixin for SAME WITH type logic in TextPropertyEditor."""

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QGraphicsTextItem

from components.barcode_editor.utils import MODERN_INPUT_STYLE, _LINE_DISABLED
from components.barcode_editor.scene_items import SelectableTextItem


class SameWithRegistry:
    """Tracks which components are linked via SAME WITH relationships."""
    _links: dict = {}

    @classmethod
    def register(cls, target_item, source_item):
        cls._links[target_item] = source_item

    @classmethod
    def unregister(cls, target_item):
        cls._links.pop(target_item, None)

    @classmethod
    def get_source(cls, target_item):
        return cls._links.get(target_item)

    @classmethod
    def get_targets(cls, source_item):
        return [t for t, s in cls._links.items() if s == source_item]

    @classmethod
    def is_source(cls, item):
        return item in cls._links.values()

    @classmethod
    def clear(cls):
        cls._links.clear()


class SameWithMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item, self.update_callback, self.same_with_combo,
    and all other combo/spin widgets to be present (set up by the editor).
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_same_with(self, enabled: bool):
        """Called by _on_type_changed; enables/disables SAME WITH mode."""
        if enabled:
            self._lock_all_fields(True)
            self.same_with_combo.setEnabled(True)
            source_name = self.same_with_combo.currentText()
            if source_name and source_name not in ("", "(no other components)"):
                self._apply_same_with_link(source_name)
        else:
            self._clear_same_with()

    # ── combo change handler ──────────────────────────────────────────────────

    def _on_same_with_changed(self, value):
        if self.type_combo.currentText() == "SAME WITH":
            if value and value not in ("", "(no other components)"):
                self._apply_same_with_link(value)
            else:
                SameWithRegistry.unregister(self.item)
                self.item.design_same_with = ""
                self._lock_all_fields(True)
                self.same_with_combo.setEnabled(True)
            return
        self.item.design_same_with = value

    # ── core logic ────────────────────────────────────────────────────────────

    def _apply_same_with_link(self, source_name: str):
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
        if getattr(source_item, "design_type", "") == "SAME WITH":
            return

        SameWithRegistry.register(self.item, source_item)
        self.item.setPlainText(source_item.toPlainText())
        self.item.setFont(QFont(source_item.font().family(), source_item.font().pointSize()))
        self.item.setDefaultTextColor(source_item.defaultTextColor())
        self.item.design_inverse = getattr(source_item, "design_inverse", False)
        self.item.design_visible = getattr(source_item, "design_visible", True)
        self.item.design_same_with = source_name
        self._refresh_ui_from_item()
        self._lock_all_fields(True)
        self.update_callback()

    def _clear_same_with(self):
        SameWithRegistry.unregister(self.item)
        self.item.design_same_with = ""
        self._lock_all_fields(False)

    # ── sync helpers ─────────────────────────────────────────────────────────

    def _sync_same_with_targets(self):
        for target in SameWithRegistry.get_targets(self.item):
            if not target.scene():
                continue
            target.setPlainText(self.item.toPlainText())
            target.setFont(QFont(self.item.font().family(), self.item.font().pointSize()))
            target.setDefaultTextColor(self.item.defaultTextColor())
            target.design_inverse = getattr(self.item, "design_inverse", False)
            target.design_visible = getattr(self.item, "design_visible", True)
        self.update_callback()

    # ── field locking ─────────────────────────────────────────────────────────

    def _lock_all_fields(self, locked: bool):
        DISABLED_STYLE_FULL = """
            QComboBox, QSpinBox, QLineEdit {
                background-color: #F8FAFC; border: 1px solid #E2E8F0;
                border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
                background: transparent; border: none;
            }
        """
        for w in (self.text_input, self.caption_input, self.format_edit):
            w.setEnabled(not locked)
            w.setStyleSheet(MODERN_INPUT_STYLE if not locked else _LINE_DISABLED)

        for w in (self.size_spin, self.top_spin, self.left_spin,
                  self.wrap_width_spin, self.column_spin):
            w.setEnabled(not locked)
            w.setStyleSheet(MODERN_INPUT_STYLE if not locked else DISABLED_STYLE_FULL)

        for w in (self.align_combo, self.font_combo, self.angle_combo,
                  self.inverse_combo, self.editor_combo, self.wrap_combo,
                  self.data_type_combo, self.group_combo, self.table_combo,
                  self.field_edit, self.result_combo, self.link_combo,
                  self.merge_combo, self.timbangan_combo, self.weight_combo,
                  self.um_combo, self.visible_combo, self.save_field_combo,
                  self.mandatory_combo, self.batch_no_combo, self.wh_combo):
            w.setEnabled(not locked)

        self.table_extra.setEnabled(not locked)
        self.table_extra.setStyleSheet(MODERN_INPUT_STYLE if not locked else _LINE_DISABLED)
        self.trim_box.setEnabled(not locked)

        if locked:
            self.same_with_combo.setEnabled(True)

    # ── UI refresh from item state ────────────────────────────────────────────

    def _refresh_ui_from_item(self):
        self.text_input.blockSignals(True)
        self.size_spin.blockSignals(True)
        self.text_input.setText(self.item.toPlainText())
        self.size_spin.setValue(int(self.item.font().pointSize()))
        self.top_spin.setValue(int(self.item.pos().y()))
        self.left_spin.setValue(int(self.item.pos().x()))
        angle_map_inv = {0: "0", 270: "90", 180: "180", 90: "270"}
        self.angle_combo.setCurrentText(angle_map_inv.get(int(self.item.rotation()), "0"))
        self.inverse_combo.setCurrentText("YES" if getattr(self.item, "design_inverse", False) else "NO")
        self.visible_combo.setCurrentText("TRUE" if getattr(self.item, "design_visible", True) else "FALSE")
        self.text_input.blockSignals(False)
        self.size_spin.blockSignals(False)

    def clear_same_with_fields(self):
        """Clear SAME WITH link and reset the combo when switching away."""
        SameWithRegistry.unregister(self.item)
        self.item.design_same_with = ""

        self.same_with_combo._items   = [""]
        self.same_with_combo._current = ""
        self.same_with_combo._label.setText("")
        self.same_with_combo.setCurrentIndex(-1)