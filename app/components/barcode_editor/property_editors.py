"""Property editors for Line, Rectangle, and Barcode scene items."""

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QFont, QBrush

from components.barcode_editor.utils import (
    COLORS, MODERN_INPUT_STYLE, _LINE_DISABLED,
    make_spin, make_chevron_combo,
)
from components.barcode_editor.scene_items import BarcodeItem

LABEL_W = 70

_DISABLED_COMBO_STYLE = """
    QComboBox, QSpinBox {
        background-color: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
    }
    QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
        background: transparent; border: none;
    }
"""


def _lbl(text: str) -> QLabel:
    label_style = (
        f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; "
        "background: transparent; border: none;"
    )
    l = QLabel(text)
    l.setStyleSheet(label_style)
    l.setFixedWidth(LABEL_W)
    l.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
    return l


# ── LinePropertyEditor ────────────────────────────────────────────────────────

class LinePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)

        line = self.item.line()
        pen  = self.item.pen()

        self.thickness_spin = make_spin(1, 100, int(pen.width()))
        self.thickness_spin.valueChanged.connect(self.update_thickness)
        layout.addRow(_lbl("THICKNESS :"), self.thickness_spin)

        self.width_spin = make_spin(0, 5000, int(abs(line.dx())))
        self.width_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(_lbl("WIDTH :"), self.width_spin)

        self.top_spin  = make_spin(0, 5000, int(self.item.pos().y()))
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(_lbl("TOP :"),  self.top_spin)
        layout.addRow(_lbl("LEFT :"), self.left_spin)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

    def update_geometry(self):
        self.item.setLine(0, 0, self.width_spin.value(), 0)
        self.update_callback()

    def update_thickness(self, value: int):
        pen = self.item.pen()
        pen.setWidth(value)
        self.item.setPen(pen)
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        self.update_callback()


# ── RectanglePropertyEditor ───────────────────────────────────────────────────

class RectanglePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(10)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)

        rect = self.item.rect()
        pen  = self.item.pen()

        self.height_spin = make_spin(0, 5000, int(rect.height()))
        self.width_spin  = make_spin(0, 5000, int(rect.width()))
        self.height_spin.valueChanged.connect(self.update_geometry)
        self.width_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(_lbl("HEIGHT :"), self.height_spin)
        layout.addRow(_lbl("WIDTH :"),  self.width_spin)

        self.top_spin  = make_spin(0, 5000, int(self.item.pos().y()))
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(_lbl("TOP :"),  self.top_spin)
        layout.addRow(_lbl("LEFT :"), self.left_spin)

        self.border_spin = make_spin(0, 20, int(pen.width()))
        self.border_spin.valueChanged.connect(self.update_border)
        layout.addRow(_lbl("BORDER WIDTH :"), self.border_spin)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

        self.column_spin = make_spin(1, 999, 1)
        layout.addRow(_lbl("COLUMN :"), self.column_spin)

    def update_geometry(self):
        self.item.setRect(0, 0, self.width_spin.value(), self.height_spin.value())
        self.update_callback()

    def update_border(self, width: int):
        pen = self.item.pen()
        pen.setWidth(width)
        self.item.setPen(pen)
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        self.update_callback()


# ── BarcodePropertyEditor ─────────────────────────────────────────────────────

class BarcodePropertyEditor(QWidget):

    _LOOKUP_TYPES = {"LOOKUP"}

    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self._conn_map:  dict = {}
        self._table_map: dict = {}

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(8)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)

        # ── HEIGHT (CM) ───────────────────────────────────────────────────────
        self.height_cm_spin = make_spin(0, 9999, 0)
        self.height_cm_spin.setDecimals(1) if hasattr(self.height_cm_spin, "setDecimals") else None
        _hcm = getattr(self.item, "design_height_cm", 1.0)
        try:
            self.height_cm_spin.setValue(float(_hcm))
        except Exception:
            pass
        self.height_cm_spin.valueChanged.connect(
            lambda v: setattr(self.item, "design_height_cm", v)
        )
        layout.addRow(_lbl("HEIGHT(CM) :"), self.height_cm_spin)

        # ── TOP / LEFT ────────────────────────────────────────────────────────
        self.top_spin  = make_spin(-5000, 5000, int(self.item.pos().y()))
        self.left_spin = make_spin(-5000, 5000, int(self.item.pos().x()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(_lbl("TOP :"),  self.top_spin)
        layout.addRow(_lbl("LEFT :"), self.left_spin)

        # ── ANGLE ─────────────────────────────────────────────────────────────
        _angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}
        _rev_angle  = {v: k for k, v in _angle_map.items()}
        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        _cur_angle = _rev_angle.get(int(round(self.item.rotation())) % 360, "0")
        self.angle_combo.blockSignals(True)
        self.angle_combo._current = _cur_angle
        self.angle_combo._label.setText(_cur_angle)
        self.angle_combo.blockSignals(False)

        def _apply_angle(v):
            angle = _angle_map.get(v, 0)
            saved_x = self.left_spin.value()
            saved_y = self.top_spin.value()
            br = self.item.boundingRect()
            self.item.setTransformOriginPoint(br.center())
            self.item.setRotation(angle)
            self.item.setPos(saved_x, saved_y)

        self.angle_combo.currentTextChanged.connect(_apply_angle)
        layout.addRow(_lbl("ANGLE :"), self.angle_combo)

        # ── BARCODE TYPE ──────────────────────────────────────────────────────
        self.barcode_type_combo = make_chevron_combo([
            "AZTEC (2D)",
            "CODE 11",
            "CODE 128",
            "CODE 128-A",
            "CODE 128-B",
            "CODE 128-C",
            "CODE 39",
            "CODE 93",
            "DATA MATRIX (2D)",
            "EAN 13",
            "EAN 8",
            "INTERLEAVED 2 OF 5",
            "QR (2D)",
            "UPC A",
        ])
        self.barcode_type_combo.setCurrentText(
            getattr(self.item, "design", "CODE128")
        )
        self.barcode_type_combo.currentTextChanged.connect(self._update_barcode_type)
        layout.addRow(_lbl("BARCODE TYPE :"), self.barcode_type_combo)

        # ── MAGNIFICATION FACTOR ──────────────────────────────────────────────
        self.magnification_combo = make_chevron_combo(["1", "2", "3", "4", "5"])
        _mag = str(getattr(self.item, "design_magnification", "1"))
        self.magnification_combo.blockSignals(True)
        self.magnification_combo._current = _mag
        self.magnification_combo._label.setText(_mag)
        self.magnification_combo.blockSignals(False)
        self.magnification_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_magnification", v)
        )
        layout.addRow(_lbl("MAGNIFICATION FACTOR :"), self.magnification_combo)

        # ── RATIO ─────────────────────────────────────────────────────────────
        self.ratio_combo = make_chevron_combo(["1", "2", "3", "4", "5"])
        _ratio = str(getattr(self.item, "design_ratio", "2"))
        self.ratio_combo.blockSignals(True)
        self.ratio_combo._current = _ratio
        self.ratio_combo._label.setText(_ratio)
        self.ratio_combo.blockSignals(False)
        self.ratio_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_ratio", v)
        )
        layout.addRow(_lbl("RATIO :"), self.ratio_combo)

        # ── CHECK DIGIT ───────────────────────────────────────────────────────
        self.check_digit_combo = make_chevron_combo([
            "-- NONE --", "MOD 10", "MOD 11", "MOD 43",
        ])
        _cd = getattr(self.item, "design_check_digit", "-- NONE --") or "-- NONE --"
        self.check_digit_combo.blockSignals(True)
        self.check_digit_combo._current = _cd
        self.check_digit_combo._label.setText(_cd)
        self.check_digit_combo.blockSignals(False)
        self.check_digit_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_check_digit", v)
        )
        layout.addRow(_lbl("CHECK DIGIT :"), self.check_digit_combo)

        # ── INTERPRETATION ────────────────────────────────────────────────────
        self.interpretation_combo = make_chevron_combo([
            "NO INTERPRETATION", "ABOVE BARCODE", "BELOW BARCODE",
        ])
        _interp = getattr(self.item, "design_interpretation", "NO INTERPRETATION") or "NO INTERPRETATION"
        self.interpretation_combo.blockSignals(True)
        self.interpretation_combo._current = _interp
        self.interpretation_combo._label.setText(_interp)
        self.interpretation_combo.blockSignals(False)
        self.interpretation_combo.currentTextChanged.connect(
            self._update_interpretation
        )
        layout.addRow(_lbl("INTERPRETATION :"), self.interpretation_combo)

        # ── TYPE ──────────────────────────────────────────────────────────────
        self.type_combo = make_chevron_combo([
            "FIX", "INPUT", "LOOKUP", "SYSTEM", "BATCH NO", "RUNNING NO",
        ])
        _type = getattr(self.item, "design_type", "FIX") or "FIX"
        self.type_combo.blockSignals(True)
        self.type_combo._current = _type
        self.type_combo._label.setText(_type)
        self.type_combo.blockSignals(False)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)
        layout.addRow(_lbl("TYPE :"), self.type_combo)

        # ── EDITOR ────────────────────────────────────────────────────────────
        self.editor_combo = make_chevron_combo(["ENABLED", "DISABLED", "INVISIBLE"])
        _editor = getattr(self.item, "design_editor", "INVISIBLE") or "INVISIBLE"
        self.editor_combo.blockSignals(True)
        self.editor_combo._current = _editor
        self.editor_combo._label.setText(_editor)
        self.editor_combo.blockSignals(False)
        self.editor_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_editor", v)
        )
        layout.addRow(_lbl("EDITOR :"), self.editor_combo)

        # ── TEXT ──────────────────────────────────────────────────────────────
        self.text_input = QLineEdit()
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.setText(getattr(self.item, "design_text", "") or "")
        self.text_input.textChanged.connect(
            lambda v: setattr(self.item, "design_text", v)
        )
        layout.addRow(_lbl("TEXT :"), self.text_input)

        # ── CAPTION ───────────────────────────────────────────────────────────
        self.caption_input = QLineEdit()
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.caption_input.setText(getattr(self.item, "design_caption", "") or "")
        self.caption_input.textChanged.connect(
            lambda v: setattr(self.item, "design_caption", v)
        )
        layout.addRow(_lbl("CAPTION :"), self.caption_input)

        # ── LOOKUP cascade: GROUP / TABLE / FIELD / RESULT ────────────────────
        self.group_combo  = make_chevron_combo([""])
        self.table_combo  = make_chevron_combo([""])
        self.field_combo  = make_chevron_combo([""])
        self.result_combo = make_chevron_combo([""])

        for combo, ph in (
            (self.group_combo,  "— select connection —"),
            (self.table_combo,  "— select table —"),
            (self.field_combo,  "— select field —"),
            (self.result_combo, "— select result field —"),
        ):
            combo.setPlaceholderText(ph)
            combo.setCurrentIndex(-1)
            combo.setEnabled(False)

        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        self.field_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_field", v)
        )
        self.result_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_result", v)
        )

        layout.addRow(_lbl("GROUP :"),  self.group_combo)
        layout.addRow(_lbl("TABLE :"),  self.table_combo)
        layout.addRow(_lbl("FIELD :"),  self.field_combo)
        layout.addRow(_lbl("RESULT :"), self.result_combo)

        # ── FORMAT ────────────────────────────────────────────────────────────
        self.format_input = QLineEdit()
        self.format_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.format_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.format_input.setText(getattr(self.item, "design_format", "") or "")
        self.format_input.textChanged.connect(
            lambda v: setattr(self.item, "design_format", v)
        )
        layout.addRow(_lbl("FORMAT :"), self.format_input)

        # ── VISIBLE ───────────────────────────────────────────────────────────
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

        # ── SAVE FIELD ────────────────────────────────────────────────────────
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "SAVE"])
        _sf = getattr(self.item, "design_save_field", "-- NOT SAVE --") or "-- NOT SAVE --"
        self.save_field_combo.blockSignals(True)
        self.save_field_combo._current = _sf
        self.save_field_combo._label.setText(_sf)
        self.save_field_combo.blockSignals(False)
        self.save_field_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_save_field", v)
        )
        layout.addRow(_lbl("SAVE FIELD :"), self.save_field_combo)

        # ── COLUMN ────────────────────────────────────────────────────────────
        self.column_spin = make_spin(1, 999, 1)
        _col = getattr(self.item, "design_column", 1)
        try:
            self.column_spin.setValue(int(_col))
        except (TypeError, ValueError):
            pass
        self.column_spin.valueChanged.connect(
            lambda v: setattr(self.item, "design_column", v)
        )
        layout.addRow(_lbl("COLUMN :"), self.column_spin)

        # ── Populate LOOKUP combos then restore persisted values ───────────────
        self._build_connection_combo()
        self._restore_lookup_values(
            getattr(self.item, "design_group",  ""),
            getattr(self.item, "design_table",  ""),
            getattr(self.item, "design_field",  ""),
            getattr(self.item, "design_result", ""),
        )

        # ── Apply initial enable/disable state ────────────────────────────────
        self._on_type_changed(_type)

    # ── LOOKUP helpers ────────────────────────────────────────────────────────

    def _build_connection_combo(self):
        try:
            from components.barcode_editor.db_helpers import _fetch_connections
            connections = _fetch_connections()
            self._conn_map = {c["name"]: c["pk"] for c in connections}
            conn_names = list(self._conn_map.keys())
            self.group_combo._items   = conn_names if conn_names else [""]
            self.group_combo._current = ""
            self.group_combo._label.setText("")
            self.group_combo.setPlaceholderText("— select connection —")
            self.group_combo.setCurrentIndex(-1)
        except Exception:
            pass

    def _on_group_changed(self, conn_name: str):
        try:
            from components.barcode_editor.db_helpers import _fetch_tables_for_connection
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
            self.table_combo.setCurrentIndex(-1)
            setattr(self.item, "design_group", conn_name)
            self._clear_field_combos()
        except Exception:
            pass

    def _on_table_changed(self, table_name: str):
        try:
            from components.barcode_editor.db_helpers import _fetch_fields_for_table
            setattr(self.item, "design_table", table_name)
            if not table_name:
                self._clear_field_combos()
                return
            fields = _fetch_fields_for_table(table_name)
            for combo in (self.field_combo, self.result_combo):
                combo._items   = fields if fields else [""]
                combo._current = ""
                combo._label.setText("")
                combo.setCurrentIndex(-1)
                combo.setEnabled(bool(fields))
        except Exception:
            pass

    def _clear_field_combos(self):
        for combo in (self.field_combo, self.result_combo):
            combo._items   = [""]
            combo._current = ""
            combo._label.setText("")
            combo.setCurrentIndex(-1)
            combo.setEnabled(False)

    def _restore_lookup_values(self, stored_group, stored_table,
                               stored_field, stored_result):
        if stored_group and stored_group in self._conn_map:
            self.group_combo.setCurrentText(stored_group)
            self._on_group_changed(stored_group)
            if stored_table:
                self.table_combo.setCurrentText(stored_table)
                self._on_table_changed(stored_table)
                if stored_field:
                    self.field_combo.setCurrentText(stored_field)
                if stored_result:
                    self.result_combo.setCurrentText(stored_result)

    # ── TYPE change ───────────────────────────────────────────────────────────

    def _on_type_changed(self, val: str):
        setattr(self.item, "design_type", val)
        is_lookup = val == "LOOKUP"

        self.group_combo.setEnabled(is_lookup)
        if is_lookup:
            has_group = bool(self.group_combo.currentText())
            self.table_combo.setEnabled(has_group)
            has_table = bool(self.table_combo.currentText())
            self.field_combo.setEnabled(has_table)
            self.result_combo.setEnabled(has_table)
        else:
            for w in (self.table_combo, self.field_combo, self.result_combo):
                w.setEnabled(False)

    # ── Barcode type change ───────────────────────────────────────────────────

    def _update_barcode_type(self, new_design: str):
        """Update the barcode design and trigger a repaint.

        BarcodeItem is now a plain QGraphicsItem that draws everything in
        paint() — there are no child items or group API calls needed.
        """
        self.item.design = new_design
        self.item.prepareGeometryChange()
        self.item.update()
        self.update_callback()

    # ── Interpretation change ─────────────────────────────────────────────────

    def _update_interpretation(self, val: str):
        """Sync interpretation to item and toggle the text line in the preview."""
        setattr(self.item, "design_interpretation", val)
        # Show interpretation text in preview when not "NO INTERPRETATION"
        self.item._show_text = (val != "NO INTERPRETATION")
        self.item.update()
        self.update_callback()

    # ── Size / position ───────────────────────────────────────────────────────

    def update_size(self):
        """Resize the barcode container and repaint."""
        if hasattr(self, "width_spin"):
            self.item.container_width = self.width_spin.value()
        if hasattr(self, "height_spin"):
            self.item.container_height = self.height_spin.value()
        self.item.setRect(self.item.container_width, self.item.container_height)
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        self.update_callback()