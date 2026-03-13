"""Property editors for Line, Rectangle, and Barcode scene items."""

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QSizePolicy, QHBoxLayout,
    QFrame, QScrollArea, QVBoxLayout, QPushButton, QTextEdit,
)
from PySide6.QtCore import Qt, Signal
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


# ── Inline checklist (reused from text_property_editor) ──────────────────────

class InlineChecklistWidget(QWidget):
    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._selected: set[str] = set()
        self._rows: dict[str, tuple] = {}
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        top_bar = QWidget()
        top_bar.setStyleSheet("background:transparent;")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(4)

        _sa_style = (
            "QPushButton{background:#EEF2FF;border:1px solid #C7D2FE;color:#6366F1;"
            "font-size:8px;font-weight:600;border-radius:3px;padding:1px 6px;min-width:32px;}"
            "QPushButton:hover{background:#C7D2FE;}"
            "QPushButton:disabled{background:#F1F5F9;color:#CBD5E1;border-color:#E2E8F0;}"
        )
        _arrow_style = (
            "QPushButton{background:transparent;border:none;color:#94A3B8;"
            "font-size:9px;padding:0px;min-width:14px;max-width:14px;}"
            "QPushButton:hover{color:#6366F1;}"
            "QPushButton:disabled{color:#E2E8F0;}"
        )

        self._btn_all = QPushButton("ALL")
        self._btn_all.setFixedHeight(16)
        self._btn_all.setStyleSheet(_sa_style)
        self._btn_all.setCursor(Qt.PointingHandCursor)
        self._btn_all.setFocusPolicy(Qt.NoFocus)
        self._btn_all.clicked.connect(self._select_all)

        self._btn_none = QPushButton("NONE")
        self._btn_none.setFixedHeight(16)
        self._btn_none.setStyleSheet(_sa_style)
        self._btn_none.setCursor(Qt.PointingHandCursor)
        self._btn_none.setFocusPolicy(Qt.NoFocus)
        self._btn_none.clicked.connect(self._select_none)

        self._btn_up = QPushButton("▲")
        self._btn_up.setFixedSize(14, 16)
        self._btn_up.setStyleSheet(_arrow_style)
        self._btn_up.setCursor(Qt.PointingHandCursor)
        self._btn_up.setFocusPolicy(Qt.NoFocus)
        self._btn_up.clicked.connect(lambda: self._move_focused(-1))

        self._btn_dn = QPushButton("▼")
        self._btn_dn.setFixedSize(14, 16)
        self._btn_dn.setStyleSheet(_arrow_style)
        self._btn_dn.setCursor(Qt.PointingHandCursor)
        self._btn_dn.setFocusPolicy(Qt.NoFocus)
        self._btn_dn.clicked.connect(lambda: self._move_focused(+1))

        top_lay.addWidget(self._btn_all)
        top_lay.addWidget(self._btn_none)
        top_lay.addStretch()
        top_lay.addWidget(self._btn_up)
        top_lay.addWidget(self._btn_dn)
        outer.addWidget(top_bar)

        self._container = QFrame()
        self._container.setObjectName("checklistContainer")
        self._container.setStyleSheet(
            "QFrame#checklistContainer { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:6px; }"
        )
        cl = QVBoxLayout(self._container)
        cl.setContentsMargins(0, 4, 0, 4)
        cl.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setMinimumHeight(0)
        self._scroll.setMaximumHeight(160)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{background:#F1F5F9;width:8px;border-radius:4px;margin:2px 2px 2px 0px;}"
            "QScrollBar::handle:vertical{background:#94A3B8;border-radius:4px;min-height:24px;}"
            "QScrollBar::handle:vertical:hover{background:#6366F1;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}"
        )
        self._rows_widget = QWidget()
        self._rows_widget.setStyleSheet("background:transparent;")
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setContentsMargins(6, 4, 6, 4)
        self._rows_layout.setSpacing(2)
        self._scroll.setWidget(self._rows_widget)
        cl.addWidget(self._scroll)
        outer.addWidget(self._container)

        self._focused_name: str | None = None

        self._disabled_placeholder = QFrame()
        self._disabled_placeholder.setFixedHeight(28)
        self._disabled_placeholder.setStyleSheet(
            "QFrame { background:#F8FAFC; border:1px solid #E2E8F0; border-radius:4px; }"
        )
        outer.addWidget(self._disabled_placeholder)
        self._apply_disabled_appearance()

    def _apply_disabled_appearance(self):
        self._container.setVisible(False)
        self._disabled_placeholder.setVisible(True)
        for btn in (self._btn_all, self._btn_none, self._btn_up, self._btn_dn):
            btn.setVisible(False)

    def _apply_enabled_appearance(self):
        self._disabled_placeholder.setVisible(False)
        self._container.setVisible(True)
        for btn in (self._btn_all, self._btn_none, self._btn_up, self._btn_dn):
            btn.setVisible(True)
            btn.setEnabled(True)

    def _select_all(self):
        self._selected = set(self._items)
        self._refresh_row_styles()
        self.selectionChanged.emit(self.get_selected())

    def _select_none(self):
        self._selected.clear()
        self._refresh_row_styles()
        self.selectionChanged.emit(self.get_selected())

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        if enabled:
            self._apply_enabled_appearance()
        else:
            self._apply_disabled_appearance()
        self._refresh_row_styles()

    def set_items(self, items: list[str]):
        def _fmt(s: str) -> str:
            if " AS " in s:
                parts = s.split(" AS ", 1)
                return f"{parts[0]}\nAS {parts[1]}"
            return s
        self._items = [_fmt(i) for i in items]
        self._raw_items = list(items)
        self._selected.clear()
        self._rebuild_rows()

    def clear_selection(self):
        self._selected.clear()
        self._refresh_row_styles()
        self.selectionChanged.emit([])

    def set_selected(self, value):
        names = [v.strip() for v in value.split(",")] if isinstance(value, str) else list(value)
        raw = getattr(self, "_raw_items", self._items)
        fmt_map = {r: f for r, f in zip(raw, self._items)}
        matched = set()
        for n in names:
            if n in self._items:
                matched.add(n)
            elif n in fmt_map:
                matched.add(fmt_map[n])
        self._selected = matched
        self._refresh_row_styles()

    def get_selected(self) -> list[str]:
        raw = getattr(self, "_raw_items", self._items)
        fmt_map = {f: r for r, f in zip(raw, self._items)}
        return [fmt_map.get(i, i) for i in self._items if i in self._selected]

    def _toggle(self, name: str):
        self._selected.discard(name) if name in self._selected else self._selected.add(name)
        self._refresh_row_styles()
        self.selectionChanged.emit(self.get_selected())

    def _rebuild_rows(self):
        for row_w, _, _ in self._rows.values():
            self._rows_layout.removeWidget(row_w)
            row_w.deleteLater()
        self._rows.clear()

        for name in self._items:
            row_w = QWidget()
            row_w.setStyleSheet("background:transparent;")
            row_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            r_lay = QHBoxLayout(row_w)
            r_lay.setContentsMargins(2, 2, 2, 2)
            r_lay.setSpacing(6)
            r_lay.setAlignment(Qt.AlignTop)

            box = QLabel()
            box.setFixedSize(13, 13)
            box.setAlignment(Qt.AlignCenter)
            box.setCursor(Qt.PointingHandCursor)

            txt = QLabel(name)
            txt.setWordWrap(True)
            txt.setStyleSheet("color:#334155;font-size:11px;background:transparent;border:none;")
            txt.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
            txt.setCursor(Qt.PointingHandCursor)

            r_lay.addWidget(box, 0, Qt.AlignTop)
            r_lay.addWidget(txt, 1)

            box.mousePressEvent = lambda _e, n=name: self._toggle_only(n) if self.isEnabled() else None
            row_w.mousePressEvent = lambda _e, n=name: self._focus_row(n) if self.isEnabled() else None
            txt.mousePressEvent   = lambda _e, n=name: self._focus_row(n) if self.isEnabled() else None

            self._rows_layout.addWidget(row_w)
            self._rows[name] = (row_w, box, txt)

        self._refresh_row_styles()
        ROW_H, SPACING, MARGINS, MAX_H = 28, 2, 6, 140
        n = len(self._items)
        content_h = MARGINS + n * ROW_H + max(0, n - 1) * SPACING
        self._scroll.setFixedHeight(min(content_h, MAX_H))

    def _toggle_only(self, name: str):
        self._focused_name = name
        self._toggle(name)

    def _focus_row(self, name: str):
        self._focused_name = name
        self._refresh_row_styles()

    def _move_focused(self, direction: int):
        name = self._focused_name
        if not name or name not in self._items:
            return
        idx = self._items.index(name)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(self._items):
            return
        self._items[idx], self._items[new_idx] = self._items[new_idx], self._items[idx]
        self._rebuild_rows()
        self.selectionChanged.emit(self.get_selected())

    def _refresh_row_styles(self):
        for name, (row_w, box, txt) in self._rows.items():
            is_checked = name in self._selected
            is_focused = name == self._focused_name
            if is_checked:
                box.setText("✓")
                box.setStyleSheet(
                    "QLabel{border:1.5px solid #6366F1;border-radius:3px;"
                    "background:#6366F1;color:white;font-size:8px;font-weight:bold;}"
                )
            else:
                box.setText("")
                box.setStyleSheet(
                    "QLabel{border:1.5px solid #CBD5E1;border-radius:3px;background:white;}"
                )
            if is_focused:
                txt.setStyleSheet("color:#334155;font-size:11px;background:transparent;border:none;font-weight:600;")
                row_w.setStyleSheet("background:#E1E7EF;border-radius:4px;")
            else:
                txt.setStyleSheet("color:#334155;font-size:11px;background:transparent;border:none;")
                row_w.setStyleSheet("background:transparent;")


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
        if hasattr(self.height_cm_spin, "setDecimals"):
            self.height_cm_spin.setDecimals(1)
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
        _aabb = self.item.mapToScene(self.item.boundingRect()).boundingRect()
        self.top_spin  = make_spin(-5000, 5000, int(round(_aabb.top())))
        self.left_spin = make_spin(-5000, 5000, int(round(_aabb.left())))
        self.top_spin.valueChanged.connect(lambda v: self._move_to_visual(target_y=v))
        self.left_spin.valueChanged.connect(lambda v: self._move_to_visual(target_x=v))
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
            saved_left = self.left_spin.value()
            saved_top  = self.top_spin.value()
            br = self.item.boundingRect()
            self.item.setTransformOriginPoint(br.center())
            self.item.setRotation(angle)
            self._move_to_visual(target_x=saved_left, target_y=saved_top, block=True)

        self.angle_combo.currentTextChanged.connect(_apply_angle)
        layout.addRow(_lbl("ANGLE :"), self.angle_combo)

        # ── BARCODE TYPE ──────────────────────────────────────────────────────
        self.barcode_type_combo = make_chevron_combo([
            "AZTEC (2D)", "CODE 11", "CODE 128", "CODE 128-A", "CODE 128-B",
            "CODE 128-C", "CODE 39", "CODE 93", "DATA MATRIX (2D)", "EAN 13",
            "EAN 8", "INTERLEAVED 2 OF 5", "QR (2D)", "UPC A",
        ])
        _saved_design = getattr(self.item, "design", "")
        if _saved_design:
            self.barcode_type_combo.blockSignals(True)
            self.barcode_type_combo._current = _saved_design
            self.barcode_type_combo._label.setText(_saved_design)
            self.barcode_type_combo.blockSignals(False)
        else:
            self.barcode_type_combo.setCurrentIndex(-1)
        self.barcode_type_combo.currentTextChanged.connect(self._update_barcode_type)
        layout.addRow(_lbl("BARCODE TYPE :"), self.barcode_type_combo)

        # ── MAGNIFICATION FACTOR ──────────────────────────────────────────────
        self.magnification_combo = make_chevron_combo(["1","2","3","4","5","6","7","8","9","10"])
        _mag = str(getattr(self.item, "design_magnification", "") or "")
        self.magnification_combo.blockSignals(True)
        self.magnification_combo._current = _mag
        self.magnification_combo._label.setText(_mag)
        self.magnification_combo.blockSignals(False)
        self.magnification_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_magnification", v)
        )
        layout.addRow(_lbl("MAGNIFICATION FACTOR :"), self.magnification_combo)

        # ── RATIO ─────────────────────────────────────────────────────────────
        self.ratio_combo = make_chevron_combo(["1","2","3","4","5"])
        _ratio = str(getattr(self.item, "design_ratio", "") or "")
        self.ratio_combo.blockSignals(True)
        self.ratio_combo._current = _ratio
        self.ratio_combo._label.setText(_ratio)
        self.ratio_combo.blockSignals(False)
        self.ratio_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_ratio", v)
        )
        layout.addRow(_lbl("RATIO :"), self.ratio_combo)

        # ── CHECK DIGIT ───────────────────────────────────────────────────────
        _VALID_CD = ("AUTO GENERATE", "MANUAL INPUT")
        self.check_digit_combo = make_chevron_combo(list(_VALID_CD))
        _cd = getattr(self.item, "design_check_digit", "") or ""
        self.check_digit_combo.blockSignals(True)
        self.check_digit_combo._current = _cd
        self.check_digit_combo._label.setText(_cd)
        self.check_digit_combo.blockSignals(False)
        self.check_digit_combo.currentTextChanged.connect(self._on_check_digit_changed)
        layout.addRow(_lbl("CHECK DIGIT :"), self.check_digit_combo)

        # ── INTERPRETATION ────────────────────────────────────────────────────
        self.interpretation_combo = make_chevron_combo(["NO INTERPRETATION", "BELOW BARCODE"])
        _interp = getattr(self.item, "design_interpretation", "") or ""
        self.interpretation_combo.blockSignals(True)
        self.interpretation_combo._current = _interp
        self.interpretation_combo._label.setText(_interp)
        self.interpretation_combo.blockSignals(False)
        self.interpretation_combo.currentTextChanged.connect(self._update_interpretation)
        _interp_lbl = _lbl("INTERPRET. :")
        layout.addRow(_interp_lbl, self.interpretation_combo)

        # ── TYPE ──────────────────────────────────────────────────────────────
        self.type_combo = make_chevron_combo([
            "FIX", "INPUT", "LOOKUP", "SAME WITH", "LINK", "SYSTEM",
            "BATCH NO", "MERGE", "TIMBANGAN", "DUPLIKASI", "RUNNING NO",
            "KONVERSI TIMBANGAN",
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

        # ── SYSTEM VALUE / EXTRA ──────────────────────────────────────────────
        self.system_value_combo = make_chevron_combo(["USER ID", "DATETIME", "LOT NO", "OTHERS"])
        self.system_extra_combo = make_chevron_combo([])
        self.system_extra_combo.setCurrentIndex(-1)
        layout.addRow(_lbl("SYSTEM VALUE :"), self.system_value_combo)
        layout.addRow(_lbl("EXTRA :"),        self.system_extra_combo)
        self.system_value_combo.currentTextChanged.connect(self._on_system_value_changed)
        self.system_extra_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_system_extra", v)
        )
        self._restore_system_values(
            getattr(self.item, "design_system_value", ""),
            getattr(self.item, "design_system_extra", ""),
        )

        # ── INPUT fields ──────────────────────────────────────────────────────
        self.data_type_combo = make_chevron_combo(["STRING", "INTEGER", "DECIMAL"])
        self.max_length_spin = make_spin(0, 9999, 1)
        self.max_length_spin.setSpecialValueText(" ")
        layout.addRow(_lbl("DATA TYPE :"),  self.data_type_combo)
        layout.addRow(_lbl("MAX LENGTH :"), self.max_length_spin)

        # ── SAME WITH combo ───────────────────────────────────────────────────
        self.same_with_combo = self._build_scene_name_combo()
        _sw = getattr(self.item, "design_same_with", "")
        if _sw and _sw in self.same_with_combo._items:
            self.same_with_combo.setCurrentText(_sw)
        self.same_with_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_same_with", v)
        )
        layout.addRow(_lbl("SAME WITH :"), self.same_with_combo)

        # ── LINK combo ────────────────────────────────────────────────────────
        self.link_combo = self._build_scene_name_combo()
        _lnk = getattr(self.item, "design_link", "")
        if _lnk and _lnk in self.link_combo._items:
            self.link_combo.setCurrentText(_lnk)
        self.link_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_link", v)
        )
        layout.addRow(_lbl("LINK TO :"), self.link_combo)

        # ── MERGE WITH (inline checklist) ─────────────────────────────────────
        self.merge_combo = self._build_merge_combo()
        layout.addRow(_lbl("MERGE WITH :"), self.merge_combo)

        # ── TIMBANGAN / WEIGHT / U/M combos ───────────────────────────────────
        self.timbangan_combo = self._build_scene_name_combo()
        self.weight_combo    = self._build_scene_name_combo()
        self.um_combo        = self._build_scene_name_combo()
        for _attr, _combo in (
            ("design_timbangan", self.timbangan_combo),
            ("design_weight",    self.weight_combo),
            ("design_um",        self.um_combo),
        ):
            _sv = getattr(self.item, _attr, "")
            if _sv and _sv in _combo._items:
                _combo.setCurrentText(_sv)
        self.timbangan_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_timbangan", v)
        )
        self.weight_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_weight", v)
        )
        self.um_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_um", v)
        )
        layout.addRow(_lbl("TIMBANGAN :"), self.timbangan_combo)
        layout.addRow(_lbl("WEIGHT :"),    self.weight_combo)
        layout.addRow(_lbl("U/M :"),       self.um_combo)

        # ── LOOKUP cascade ────────────────────────────────────────────────────
        self.group_combo  = make_chevron_combo([])
        self.table_combo  = make_chevron_combo([])
        self.table_extra  = QTextEdit()
        self.field_combo  = make_chevron_combo([])
        self.result_combo = make_chevron_combo([])

        self.table_extra.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:4px; "
            "padding:5px; font-size:11px; color:#1E293B; }"
            "QTextEdit:focus { border:1px solid #6366F1; }"
            "QTextEdit:disabled { background:#F8FAFC; color:#94A3B8; border-color:#E2E8F0; }"
        )
        self.table_extra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.table_extra.setFixedHeight(80)
        self.table_extra.setAcceptRichText(False)

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

        def _on_query_changed():
            v = self.table_extra.toPlainText()
            setattr(self.item, "design_query", v)
            table = getattr(self.item, "design_table", "") or ""
            if table:
                self._on_table_changed(table)

        self.table_extra.textChanged.connect(_on_query_changed)

        layout.addRow(_lbl("GROUP :"),  self.group_combo)
        layout.addRow(_lbl("TABLE :"),  self.table_combo)
        layout.addRow(_lbl("QUERY :"),  self.table_extra)
        layout.addRow(_lbl("FIELD :"),  self.field_combo)
        layout.addRow(_lbl("RESULT :"), self.result_combo)

        # ── TEXT ──────────────────────────────────────────────────────────────
        self.text_input = QLineEdit()
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.setText(getattr(self.item, "design_text", "") or "")
        self.text_input.textChanged.connect(lambda v: setattr(self.item, "design_text", v))
        layout.addRow(_lbl("TEXT :"), self.text_input)

        # ── CAPTION ───────────────────────────────────────────────────────────
        self.caption_input = QLineEdit()
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.caption_input.setText(getattr(self.item, "design_caption", "") or "")
        self.caption_input.textChanged.connect(lambda v: setattr(self.item, "design_caption", v))
        layout.addRow(_lbl("CAPTION :"), self.caption_input)

        # ── FORMAT ────────────────────────────────────────────────────────────
        self.format_input = QLineEdit()
        self.format_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.format_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.format_input.setText(getattr(self.item, "design_format", "") or "")
        self.format_input.textChanged.connect(lambda v: setattr(self.item, "design_format", v))
        layout.addRow(_lbl("FORMAT :"), self.format_input)

        # ── VISIBLE ───────────────────────────────────────────────────────────
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

        # ── SAVE FIELD / COLUMN / MANDATORY ──────────────────────────────────
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

        self.column_spin = make_spin(1, 999, 1)
        _col = getattr(self.item, "design_column", 1)
        try:
            self.column_spin.setValue(int(_col))
        except (TypeError, ValueError):
            pass
        self.column_spin.valueChanged.connect(lambda v: setattr(self.item, "design_column", v))
        layout.addRow(_lbl("COLUMN :"), self.column_spin)

        self.mandatory_combo = make_chevron_combo(["FALSE", "TRUE"])
        self.mandatory_combo.setCurrentText(
            getattr(self.item, "design_mandatory", "FALSE") or "FALSE"
        )
        self.mandatory_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_mandatory", v)
        )
        layout.addRow(_lbl("MANDATORY :"), self.mandatory_combo)

        # ── BATCH NO / WH combos ──────────────────────────────────────────────
        self.batch_no_combo = make_chevron_combo([])
        self.batch_no_combo.setCurrentIndex(-1)
        self.wh_combo = make_chevron_combo([])
        self.wh_combo.setCurrentIndex(-1)
        layout.addRow(_lbl("BATCH NO :"), self.batch_no_combo)
        layout.addRow(_lbl("WH :"),       self.wh_combo)

        # ── Populate LOOKUP combos then restore persisted values ──────────────
        self._build_connection_combo()
        self._restore_lookup_values(
            getattr(self.item, "design_group",  ""),
            getattr(self.item, "design_table",  ""),
            getattr(self.item, "design_field",  ""),
            getattr(self.item, "design_result", ""),
            getattr(self.item, "design_query",  ""),
        )

        # ── Restore INPUT fields ──────────────────────────────────────────────
        self.data_type_combo.setCurrentText(
            getattr(self.item, "design_data_type", "STRING") or "STRING"
        )
        _ml = getattr(self.item, "design_max_length", 1)
        try:
            self.max_length_spin.setValue(int(_ml))
        except (TypeError, ValueError):
            pass

        # ── Apply initial enable/disable state ────────────────────────────────
        self._on_type_changed(_type)

    # ── Visual position helpers ───────────────────────────────────────────────

    def _get_aabb_offset(self):
        aabb = self.item.mapToScene(self.item.boundingRect()).boundingRect()
        pos  = self.item.pos()
        return aabb.left() - pos.x(), aabb.top() - pos.y()

    def _move_to_visual(self, target_x=None, target_y=None, block=False):
        off_x, off_y = self._get_aabb_offset()
        if target_x is not None:
            self.item.setX(target_x - off_x)
        if target_y is not None:
            self.item.setY(target_y - off_y)
        if block:
            self.update_position_fields()

    # ── Scene name combo helpers ──────────────────────────────────────────────

    def _build_scene_name_combo(self):
        from components.barcode_editor.scene_items import SelectableTextItem, BarcodeItem as _BC
        names = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, (SelectableTextItem, _BC)):
                        continue
                    name = getattr(si, "component_name", "") or ""
                    if name:
                        names.append(name)
        except Exception:
            pass
        combo = make_chevron_combo(names)
        combo._items = names
        combo.setPlaceholderText("—")
        combo.setCurrentIndex(-1)
        return combo

    def _build_merge_combo(self) -> InlineChecklistWidget:
        from components.barcode_editor.scene_items import SelectableTextItem, BarcodeItem as _BC
        names: list[str] = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, (SelectableTextItem, _BC)):
                        continue
                    name = getattr(si, "component_name", "") or ""
                    if name:
                        names.append(name)
        except Exception:
            pass
        combo = InlineChecklistWidget()
        combo.set_items(names)
        stored = getattr(self.item, "design_merge", "")
        if stored:
            combo.set_selected(stored)
        combo.selectionChanged.connect(
            lambda names: setattr(self.item, "design_merge", ",".join(names))
        )
        return combo

    # ── SYSTEM VALUE helpers ──────────────────────────────────────────────────

    def _on_system_value_changed(self, val: str):
        setattr(self.item, "design_system_value", val)
        _extras = {
            "DATETIME": ["DD/MM/YYYY HH:MM:SS", "DD/MM/YYYY", "HH:MM:SS",
                         "YYYY-MM-DD HH:MM:SS", "YYYY-MM-DD"],
            "LOT NO":   ["LOT NO FORMAT 1", "LOT NO FORMAT 2"],
            "OTHERS":   ["CUSTOM"],
        }
        extras = _extras.get(val, [])
        self.system_extra_combo.blockSignals(True)
        self.system_extra_combo._items = extras
        self.system_extra_combo._current = extras[0] if extras else ""
        self.system_extra_combo._label.setText(extras[0] if extras else "")
        self.system_extra_combo.setEnabled(bool(extras))
        self.system_extra_combo.blockSignals(False)

    def _restore_system_values(self, stored_value: str, stored_extra: str):
        if stored_value:
            self.system_value_combo.blockSignals(True)
            self.system_value_combo._current = stored_value
            self.system_value_combo._label.setText(stored_value)
            self.system_value_combo.blockSignals(False)
            self._on_system_value_changed(stored_value)
        if stored_extra:
            self.system_extra_combo.blockSignals(True)
            self.system_extra_combo._current = stored_extra
            self.system_extra_combo._label.setText(stored_extra)
            self.system_extra_combo.blockSignals(False)

    # ── LOOKUP helpers ────────────────────────────────────────────────────────

    def _build_connection_combo(self):
        try:
            from components.barcode_editor.db_helpers import _fetch_connections
            connections = _fetch_connections()
            self._conn_map = {c["name"]: c["pk"] for c in connections}
            conn_names = list(self._conn_map.keys())
            self.group_combo._items   = conn_names if conn_names else []
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
                self.table_combo._items = []
                self.table_combo.setCurrentIndex(-1)
                self.table_combo.setEnabled(False)
                self._table_map = {}
                self._clear_field_combos()
                return
            tables = _fetch_tables_for_connection(conn_pk)
            self._table_map = {t["name"]: t["pk"] for t in tables}
            table_names = list(self._table_map.keys())
            self.table_combo._items   = table_names if table_names else []
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
            query = self.table_extra.toPlainText().strip() if hasattr(self, "table_extra") else ""
            if not table_name:
                self._clear_field_combos()
                return
            fields = _fetch_fields_for_table(table_name, query=query)
            for combo in (self.field_combo, self.result_combo):
                combo._items   = fields if fields else []
                combo._current = ""
                combo._label.setText("")
                combo.setCurrentIndex(-1)
                combo.setEnabled(bool(fields))
        except Exception:
            pass

    def _clear_field_combos(self):
        for combo in (self.field_combo, self.result_combo):
            combo._items   = []
            combo._current = ""
            combo._label.setText("")
            combo.setCurrentIndex(-1)
            combo.setEnabled(False)

    def _restore_lookup_values(self, stored_group, stored_table,
                               stored_field, stored_result, stored_query=""):
        if stored_query:
            self.table_extra.blockSignals(True)
            self.table_extra.setPlainText(stored_query)
            self.table_extra.blockSignals(False)
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

    # ── BATCH NO helpers ──────────────────────────────────────────────────────

    def _populate_batch_no_options(self):
        from components.barcode_editor.scene_items import SelectableTextItem, BarcodeItem as _BC
        names = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, (SelectableTextItem, _BC)):
                        continue
                    name = getattr(si, "component_name", "") or ""
                    if name:
                        names.append(name)
        except Exception:
            pass
        names = sorted(set(names))

        self.batch_no_combo.blockSignals(True)
        self.wh_combo.blockSignals(True)
        self.batch_no_combo._items = names
        self.batch_no_combo._current = ""
        self.batch_no_combo._label.setText("")
        self.wh_combo._items = names
        self.wh_combo._current = ""
        self.wh_combo._label.setText("")

        saved_batch = getattr(self.item, "design_batch_no", "")
        if saved_batch and saved_batch in names:
            self.batch_no_combo._current = saved_batch
            self.batch_no_combo._label.setText(saved_batch)

        saved_wh = getattr(self.item, "design_wh", "")
        if saved_wh and saved_wh in names:
            self.wh_combo._current = saved_wh
            self.wh_combo._label.setText(saved_wh)

        self.batch_no_combo.setEnabled(True)
        self.wh_combo.setEnabled(True)
        self.batch_no_combo.blockSignals(False)
        self.wh_combo.blockSignals(False)

        try:
            self.batch_no_combo.currentTextChanged.disconnect(self._save_batch_no)
        except Exception:
            pass
        try:
            self.wh_combo.currentTextChanged.disconnect(self._save_wh)
        except Exception:
            pass
        self.batch_no_combo.currentTextChanged.connect(self._save_batch_no)
        self.wh_combo.currentTextChanged.connect(self._save_wh)

    def _save_batch_no(self, val: str):
        if self.item:
            self.item.design_batch_no = val

    def _save_wh(self, val: str):
        if self.item:
            self.item.design_wh = val

    def _clear_batch_no_fields(self):
        self.batch_no_combo.blockSignals(True)
        self.wh_combo.blockSignals(True)
        self.batch_no_combo._items = []
        self.batch_no_combo._current = ""
        self.batch_no_combo._label.setText("")
        self.wh_combo._items = []
        self.wh_combo._current = ""
        self.wh_combo._label.setText("")
        self.batch_no_combo.setEnabled(False)
        self.wh_combo.setEnabled(False)
        self.batch_no_combo.blockSignals(False)
        self.wh_combo.blockSignals(False)
        try:
            self.batch_no_combo.currentTextChanged.disconnect(self._save_batch_no)
        except Exception:
            pass
        try:
            self.wh_combo.currentTextChanged.disconnect(self._save_wh)
        except Exception:
            pass

    # ── Check digit / interpretation ─────────────────────────────────────────

    def _on_check_digit_changed(self, val: str):
        setattr(self.item, "design_check_digit", val)

    def _update_interpretation(self, val: str):
        setattr(self.item, "design_interpretation", val)
        self.item._show_text = (val != "NO INTERPRETATION")
        self.item.update()
        self.update_callback()

    # ── TYPE orchestrator ─────────────────────────────────────────────────────

    def _on_type_changed(self, val: str):
        setattr(self.item, "design_type", val)

        _prev = getattr(self, "_last_type", None)
        if _prev is not None and _prev != val:
            if _prev == "BATCH NO":
                self._clear_batch_no_fields()

            if _prev == "SYSTEM":
                self.system_value_combo.blockSignals(True)
                self.system_extra_combo.blockSignals(True)
                self.system_value_combo._current = ""
                self.system_value_combo._label.setText("")
                self.system_extra_combo._current = ""
                self.system_extra_combo._label.setText("")
                self.system_extra_combo._items = []
                self.system_value_combo.blockSignals(False)
                self.system_extra_combo.blockSignals(False)
                self.item.design_system_value = ""
                self.item.design_system_extra = ""

            if _prev == "LOOKUP":
                self.group_combo.blockSignals(True)
                self.table_combo.blockSignals(True)
                self.table_extra.blockSignals(True)
                self.group_combo._current = ""
                self.group_combo._label.setText("")
                self.table_combo._current = ""
                self.table_combo._label.setText("")
                self.table_extra.setPlainText("")
                self._clear_field_combos()
                self.group_combo.blockSignals(False)
                self.table_combo.blockSignals(False)
                self.table_extra.blockSignals(False)
                self.item.design_group  = ""
                self.item.design_table  = ""
                self.item.design_field  = ""
                self.item.design_result = ""
                self.item.design_query  = ""

            if _prev == "SAME WITH":
                self.same_with_combo.blockSignals(True)
                self.same_with_combo._current = ""
                self.same_with_combo._label.setText("")
                self.same_with_combo.blockSignals(False)
                self.item.design_same_with = ""

            if _prev == "LINK":
                self.link_combo.blockSignals(True)
                self.link_combo._current = ""
                self.link_combo._label.setText("")
                self.link_combo.blockSignals(False)
                self.item.design_link = ""

            if _prev == "MERGE":
                self.merge_combo.clear_selection()
                self.item.design_merge = ""

            if _prev in ("TIMBANGAN", "KONVERSI TIMBANGAN"):
                for combo, attr in (
                    (self.timbangan_combo, "design_timbangan"),
                    (self.weight_combo,    "design_weight"),
                    (self.um_combo,        "design_um"),
                ):
                    combo.blockSignals(True)
                    combo._current = ""
                    combo._label.setText("")
                    combo.blockSignals(False)
                    setattr(self.item, attr, "")

            if _prev == "INPUT":
                self.data_type_combo.blockSignals(True)
                self.data_type_combo.setCurrentIndex(-1)
                self.data_type_combo.blockSignals(False)
                self.max_length_spin.setValue(0)
                self.max_length_spin.setStyleSheet(_DISABLED_COMBO_STYLE)
                self.item.design_data_type  = ""
                self.item.design_max_length = 0

        self._last_type = val

        is_input     = val == "INPUT"
        is_lookup    = val == "LOOKUP"
        is_same_with = val == "SAME WITH"
        is_link      = val == "LINK"
        is_system    = val == "SYSTEM"
        is_batch_no  = val == "BATCH NO"
        is_merge     = val == "MERGE"
        is_konversi  = val == "KONVERSI TIMBANGAN"
        is_timbangan = val == "TIMBANGAN"

        # ── INPUT ─────────────────────────────────────────────────────────────
        self.data_type_combo.setEnabled(is_input)
        self.max_length_spin.setEnabled(is_input)
        if is_input:
            self.data_type_combo.blockSignals(False)
            if self.data_type_combo.currentIndex() == -1:
                self.data_type_combo.setCurrentIndex(0)
            self.max_length_spin.setStyleSheet(MODERN_INPUT_STYLE)
            if self.max_length_spin.value() == 0:
                self.max_length_spin.setValue(1)
        else:
            self.data_type_combo.blockSignals(True)
            self.data_type_combo.setCurrentIndex(-1)
            self.data_type_combo.blockSignals(False)
            self.max_length_spin.setValue(0)
            self.max_length_spin.setStyleSheet(_DISABLED_COMBO_STYLE)

        # ── SAME WITH ─────────────────────────────────────────────────────────
        self.same_with_combo.setEnabled(is_same_with)
        if not is_same_with:
            self.same_with_combo.blockSignals(True)
            self.same_with_combo._current = ""
            self.same_with_combo._label.setText("")
            self.same_with_combo.blockSignals(False)

        # ── LINK ──────────────────────────────────────────────────────────────
        self.link_combo.setEnabled(is_link)
        if not is_link:
            self.link_combo.blockSignals(True)
            self.link_combo._current = ""
            self.link_combo._label.setText("")
            self.link_combo.blockSignals(False)

        # ── SYSTEM ────────────────────────────────────────────────────────────
        self.system_value_combo.setEnabled(is_system)
        self.system_extra_combo.setEnabled(
            is_system and bool(self.system_extra_combo._items
                               if hasattr(self.system_extra_combo, "_items") else [])
        )
        if not is_system:
            self.system_value_combo.blockSignals(True)
            self.system_extra_combo.blockSignals(True)
            self.system_value_combo._current = ""
            self.system_value_combo._label.setText("")
            self.system_extra_combo._current = ""
            self.system_extra_combo._label.setText("")
            self.system_extra_combo._items = []
            self.system_value_combo.blockSignals(False)
            self.system_extra_combo.blockSignals(False)

        # ── MERGE ─────────────────────────────────────────────────────────────
        self.merge_combo.setEnabled(is_merge)
        if not is_merge:
            self.merge_combo.clear_selection()

        # ── TIMBANGAN / KONVERSI ──────────────────────────────────────────────
        show_timbangan = is_timbangan or is_konversi
        for w in (self.timbangan_combo, self.weight_combo, self.um_combo):
            w.setEnabled(show_timbangan)
        if not show_timbangan:
            for combo in (self.timbangan_combo, self.weight_combo, self.um_combo):
                combo.blockSignals(True)
                combo._current = ""
                combo._label.setText("")
                combo.blockSignals(False)

        # ── LOOKUP cascade ────────────────────────────────────────────────────
        self.group_combo.setEnabled(is_lookup)
        self.table_extra.setEnabled(is_lookup)
        if is_lookup:
            has_group = bool(getattr(self.group_combo, "_current", ""))
            self.table_combo.setEnabled(has_group)
            has_table = bool(getattr(self.table_combo, "_current", ""))
            self.field_combo.setEnabled(has_table)
            self.result_combo.setEnabled(has_table)
        else:
            for w in (self.table_combo, self.field_combo, self.result_combo):
                w.setEnabled(False)

        # ── BATCH NO ──────────────────────────────────────────────────────────
        if is_batch_no:
            self._populate_batch_no_options()
        else:
            self.batch_no_combo.setEnabled(False)
            self.wh_combo.setEnabled(False)

    # ── Barcode type change ───────────────────────────────────────────────────

    def _update_barcode_type(self, new_design: str):
        _2D = {"AZTEC (2D)", "DATA MATRIX (2D)", "QR (2D)"}
        old_design = self.item.design
        self.item.design = new_design
        was_2d = old_design in _2D
        is_2d  = new_design in _2D
        if was_2d != is_2d:
            saved_left = self.left_spin.value()
            saved_top  = self.top_spin.value()
            if is_2d:
                self.item._linear_width  = self.item.container_width
                self.item._linear_height = self.item.container_height
            linear_w = getattr(self.item, "_linear_width",  95)
            linear_h = getattr(self.item, "_linear_height", 40)
            new_w, new_h = BarcodeItem.natural_size_for(
                new_design, linear_w=linear_w, linear_h=linear_h,
            )
            self.item.prepareGeometryChange()
            self.item.container_width  = new_w
            self.item.container_height = new_h
            self.item.setTransformOriginPoint(new_w / 2, new_h / 2)
            self._move_to_visual(target_x=saved_left, target_y=saved_top, block=True)
        self.item.update()
        self.update_callback()

    # ── Size / position ───────────────────────────────────────────────────────

    def update_size(self):
        if hasattr(self, "width_spin"):
            self.item.container_width = self.width_spin.value()
        if hasattr(self, "height_spin"):
            self.item.container_height = self.height_spin.value()
        self.item.setRect(self.item.container_width, self.item.container_height)
        self.update_callback()

    def update_position_fields(self, pos=None):
        aabb = self.item.mapToScene(self.item.boundingRect()).boundingRect()
        new_top  = int(round(aabb.top()))
        new_left = int(round(aabb.left()))
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(new_top)
        self.left_spin.setValue(new_left)
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        self.update_callback()