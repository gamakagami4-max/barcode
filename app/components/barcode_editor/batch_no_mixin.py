class BatchNoMixin:
    def _apply_batch_no_fields(self):
        if not getattr(self, "item", None):
            return

        self.result_combo.blockSignals(True)
        self.result_combo.clear()

        scene = getattr(self.item, "scene", lambda: None)()
        if not scene:
            self.result_combo.blockSignals(False)
            return

        labels = []
        for it in scene.items():
            if it is self.item:
                continue
            # ← was "design_name", your items use "component_name"
            name = getattr(it, "component_name", None)
            if name:
                labels.append(name)

        labels.sort()

        for name in labels:
            self.result_combo.addItem(name)

        val = getattr(self.item, "design_result", "")
        if val and val in labels:
            idx = self.result_combo.findText(val)
            if idx >= 0:
                self.result_combo.setCurrentIndex(idx)

        self.result_combo.setEnabled(True)
        self.result_combo.blockSignals(False)

        # ← connect save signal if not already connected
        try:
            self.result_combo.currentTextChanged.disconnect(self._save_batch_result)
        except RuntimeError:
            pass
        self.result_combo.currentTextChanged.connect(self._save_batch_result)

    def _save_batch_result(self, val: str):
        if self.item:
            self.item.design_result = val

    def _clear_batch_no_fields(self):
        self.result_combo.blockSignals(True)
        self.result_combo.clear()
        self.result_combo.setEnabled(False)
        self.result_combo.blockSignals(False)
        try:
            self.result_combo.currentTextChanged.disconnect(self._save_batch_result)
        except RuntimeError:
            pass