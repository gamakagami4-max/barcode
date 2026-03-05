"""Mixin for MERGE and KONVERSI TIMBANGAN type logic in TextPropertyEditor."""


class MergeKonversiMixin:
    """
    Mixin for TextPropertyEditor.
    Requires self.item and the following widgets:
      merge_combo, timbangan_combo, weight_combo, um_combo.
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_merge(self, enabled: bool):
        self.merge_combo.setEnabled(enabled)
        if not enabled:
            self.merge_combo.setCurrentIndex(-1)
            self.item.design_merge = ""

    def enable_for_konversi(self, enabled: bool):
        for combo in (self.timbangan_combo, self.weight_combo, self.um_combo):
            combo.setEnabled(enabled)
        if not enabled:
            for combo in (self.timbangan_combo, self.weight_combo, self.um_combo):
                combo.setCurrentIndex(-1)
            self.item.design_timbangan = ""
            self.item.design_weight    = ""
            self.item.design_um        = ""

    # ── combo change handlers ─────────────────────────────────────────────────

    def _on_merge_changed(self, value: str):
        self.item.design_merge = value if value not in ("", "—") else ""

    def _on_timbangan_changed(self, v: str):
        self.item.design_timbangan = v if v not in ("", "—") else ""

    def _on_weight_changed(self, v: str):
        self.item.design_weight = v if v not in ("", "—") else ""

    def _on_um_changed(self, v: str):
        self.item.design_um = v if v not in ("", "—") else ""