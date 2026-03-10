"""Mixin for SYSTEM type logic in TextPropertyEditor."""


_DATETIME_OPTIONS = [
    "dd MMM yy", "dd MMM yyyy", "dd MMM yyyy HH:mm",
    "dd MMM yyyy HH:mm AM/PM", "dd-MMM-yy", "dd-MMM-yyyy",
    "dd-MMM-yyyy HH:mm", "dd-MMM-yyyy HH:mm AM/PM",
    "dd-MMM-yyyy HH:mm:ss", "HH:mm", "HH:mm AM/PM",
    "HH:mm:ss", "HH:mm:ss AM/PM", "MMM yyyy", "MMMM yyyy",
]

_LOT_NO_OPTIONS = [
    "FILTECHNO", "FLEETGUARD", "FLEETGUARD2", "FLEETRITE", "FUSO",
    "LUBERFINER", "MULTIFITTING", "MULTIFITTING2", "OEM",
    "PREMIUM GUARD", "PTC", "SAKURA", "SANKO", "YANMAR",
]

_OTHERS_OPTIONS = ["MADE IN", "NAMA"]


class SystemMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item and the following widgets:
      system_value_combo, system_extra_combo.
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_system(self, enabled: bool):
        self.system_value_combo.setEnabled(enabled)
        if enabled:
            sv = self.system_value_combo.currentText()
            self.system_extra_combo.setEnabled(sv in ("DATETIME", "LOT NO", "OTHERS"))
        else:
            self.system_value_combo.setCurrentIndex(-1)
            self.system_extra_combo.setCurrentIndex(-1)
            self.system_value_combo.setEnabled(False)
            self.system_extra_combo.setEnabled(False)

    # ── combo change handlers ─────────────────────────────────────────────────

    def _on_system_value_changed(self, val: str):
        setattr(self.item, "design_system_value", val)
        self._update_system_extra_options(val)

    def _update_system_extra_options(self, system_val: str):
        if system_val == "DATETIME":
            options = _DATETIME_OPTIONS
        elif system_val == "LOT NO":
            options = _LOT_NO_OPTIONS
        elif system_val == "OTHERS":
            options = _OTHERS_OPTIONS
        else:
            options = [""]

        has_extra = system_val in ("DATETIME", "LOT NO", "OTHERS")
        self.system_extra_combo.setEnabled(has_extra)
        self.system_extra_combo._items   = options
        self.system_extra_combo._current = options[0]
        self.system_extra_combo._label.setText(options[0])

        # Restore persisted extra value if it matches
        sv = getattr(self.item, "design_system_extra", "")
        if sv and sv in options:
            self.system_extra_combo.setCurrentText(sv)

    # ── restore on load ───────────────────────────────────────────────────────

    def restore_system_values(self, stored_value: str, stored_extra: str):
        """Called during editor init to restore persisted SYSTEM fields."""
        if getattr(self.item, "design_type", "") != "SYSTEM":
            self.system_extra_combo.setCurrentIndex(-1)
            self.system_extra_combo.setEnabled(False)
            return

        if stored_value in ("USER ID", "DATETIME", "LOT NO", "OTHERS"):
            self.system_value_combo.setCurrentText(stored_value)
            self._update_system_extra_options(stored_value)
            if stored_extra and stored_extra in self.system_extra_combo._items:
                self.system_extra_combo.setCurrentText(stored_extra)
        else:
            self.system_extra_combo.setEnabled(False)
            self.system_extra_combo.setCurrentIndex(-1)

    def clear_system_fields(self):
        """Clear SYSTEM selections when switching away."""
        setattr(self.item, "design_system_value", "")
        setattr(self.item, "design_system_extra", "")

        self.system_value_combo._current = ""
        self.system_value_combo._label.setText("")
        self.system_value_combo.setCurrentIndex(-1)

        self.system_extra_combo._items   = [""]
        self.system_extra_combo._current = ""
        self.system_extra_combo._label.setText("")
        self.system_extra_combo.setCurrentIndex(-1)
        self.system_extra_combo.setEnabled(False)