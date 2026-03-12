class BatchNoMixin:
    """
    Mixin for BATCH_NO type logic in TextPropertyEditor.
    Allows selecting another label item as the batch source.
    """

    def _apply_batch_no_fields(self):
        """Populate combo with other label items."""
        if not getattr(self, "item", None):
            return

        self.result_combo.blockSignals(True)
        self.result_combo.clear()

        # collect labels from scene
        scene = getattr(self.item, "scene", lambda: None)()
        if not scene:
            return

        labels = []
        for it in scene.items():
            if it is self.item:
                continue

            name = getattr(it, "design_name", None)
            if name:
                labels.append(name)

        labels.sort()

        for name in labels:
            self.result_combo.addItem(name)

        # restore saved value
        val = getattr(self.item, "design_result", "")
        if val and val in labels:
            idx = self.result_combo.findText(val)
            if idx >= 0:
                self.result_combo.setCurrentIndex(idx)

        self.result_combo.setEnabled(True)
        self.result_combo.blockSignals(False)

    def _clear_batch_no_fields(self):
        """Clear fields when leaving BATCH_NO."""
        self.result_combo.blockSignals(True)
        self.result_combo.clear()
        self.result_combo.setEnabled(False)
        self.result_combo.blockSignals(False)