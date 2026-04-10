"""TextPropertyEditor — orchestrates all type-specific mixins."""

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QSizePolicy, QHBoxLayout,
    QFrame, QScrollArea, QVBoxLayout, QPushButton, QTextEdit,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QTextCursor, QTextBlockFormat

from components.barcode_editor.utils import (
    COLORS, MODERN_INPUT_STYLE, _LINE_DISABLED,
    make_spin, make_chevron_combo,
)
from components.barcode_editor.same_with_mixin import SameWithMixin, SameWithRegistry
from components.barcode_editor.lookup_mixin import LookupMixin
from components.barcode_editor.link_mixin import LinkMixin
from components.barcode_editor.system_mixin import SystemMixin
from components.barcode_editor.merge_konversi_mixin import (
    MergeKonversiMixin, MultiSelectCombo, MergeInputWidget,
)

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


# Map Qt rotation angle -> display label
_QT_ANGLE_TO_DISPLAY = {0: "0", 270: "90", 180: "180", 90: "270"}


# ── Inline checklist widget (used for LOOKUP FIELD only) ──────────────────────

class InlineChecklistWidget(QWidget):
    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._selected: set[str] = set()
        self._rows: dict[str, tuple] = {}   # name -> (row_widget, box_label, text_label)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(2)

        # ── Top bar: ALL / NONE buttons + up/down arrows ──────────────────────
        top_bar = QWidget()
        top_bar.setStyleSheet("background:transparent;")
        top_lay = QHBoxLayout(top_bar)
        top_lay.setContentsMargins(0, 0, 0, 0)
        top_lay.setSpacing(4)

        _sa_style = (
            "QPushButton{background:#EEF2FF;border:1px solid #C7D2FE;color:#6366F1;"
            "font-size:8px;font-weight:600;border-radius:3px;padding:1px 6px;"
            "min-width:32px;}"
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

        # ── Checklist container ───────────────────────────────────────────────
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
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)  # allow horizontal scroll
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._scroll.setMinimumHeight(0)
        self._scroll.setMaximumHeight(160)
        self._scroll.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._scroll.setStyleSheet(
            "QScrollArea{background:transparent;border:none;}"
            "QScrollBar:vertical{"
            "  background:#F1F5F9;width:8px;border-radius:4px;margin:2px 2px 2px 0px;}"
            "QScrollBar::handle:vertical{"
            "  background:#94A3B8;border-radius:4px;min-height:24px;}"
            "QScrollBar::handle:vertical:hover{background:#6366F1;}"
            "QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical{height:0px;}"
            "QScrollBar:horizontal{"
            "  background:#F1F5F9;height:8px;border-radius:4px;margin:0px 0px 2px 0px;}"
            "QScrollBar::handle:horizontal{"
            "  background:#94A3B8;border-radius:4px;min-width:24px;}"
            "QScrollBar::handle:horizontal:hover{background:#6366F1;}"
            "QScrollBar::add-line:horizontal,QScrollBar::sub-line:horizontal{width:0px;}"
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

        # Disabled-state placeholder
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
        if hasattr(self, "_btn_all"):
            self._btn_all.setVisible(False)
            self._btn_none.setVisible(False)
            self._btn_up.setVisible(False)
            self._btn_dn.setVisible(False)

    def _apply_enabled_appearance(self):
        if hasattr(self, "_disabled_placeholder"):
            self._disabled_placeholder.setVisible(False)
        self._container.setVisible(True)
        self._container.setStyleSheet(
            "QFrame#checklistContainer { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:6px; }"
        )
        if hasattr(self, "_btn_all"):
            self._btn_all.setVisible(True)
            self._btn_none.setVisible(True)
            self._btn_up.setVisible(True)
            self._btn_dn.setVisible(True)
            self._btn_all.setEnabled(True)
            self._btn_none.setEnabled(True)

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

    def set_items(self, items: list[str], preserve_selection: bool = False):
        # Store raw items as-is — no newline splitting, single line only
        prev_selected = set(self._selected) if preserve_selection else set()
        self._items = list(items)
        self._raw_items = list(items)
        self._selected = {s for s in prev_selected if s in self._items}
        self._rebuild_rows()

    def clear_selection(self):
        self._selected.clear()
        self._refresh_row_styles()
        self.selectionChanged.emit([])

    def set_selected(self, value):
        names = [v.strip() for v in value.split(",")] if isinstance(value, str) else list(value)
        matched = set()
        for n in names:
            if n in self._items:
                matched.add(n)
        self._selected = matched
        self._refresh_row_styles()

    def get_selected(self) -> list[str]:
        return [i for i in self._items if i in self._selected]

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
            row_w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            row_w.setFixedHeight(24)
            r_lay = QHBoxLayout(row_w)
            r_lay.setContentsMargins(2, 0, 2, 0)
            r_lay.setSpacing(6)

            box = QLabel()
            box.setFixedSize(13, 13)
            box.setAlignment(Qt.AlignCenter)
            box.setCursor(Qt.PointingHandCursor)

            txt = QLabel(name)
            txt.setWordWrap(False)                          # single line
            txt.setFixedHeight(20)
            txt.setStyleSheet(
                "color:#334155;font-size:11px;background:transparent;"
                "border:none;white-space:nowrap;"
            )
            txt.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            txt.setCursor(Qt.PointingHandCursor)

            r_lay.addWidget(box, 0, Qt.AlignVCenter)
            r_lay.addWidget(txt, 0, Qt.AlignVCenter)
            r_lay.addStretch()

            box.mousePressEvent = lambda _e, n=name: self._toggle_only(n) if self.isEnabled() else None
            row_w.mousePressEvent = lambda _e, n=name: self._focus_row(n) if self.isEnabled() else None
            txt.mousePressEvent   = lambda _e, n=name: self._focus_row(n) if self.isEnabled() else None

            self._rows_layout.addWidget(row_w)
            self._rows[name] = (row_w, box, txt)

        self._refresh_row_styles()

        # Fixed row height now so scroll calculation is simple
        ROW_H, SPACING, MARGINS, MAX_H = 24, 2, 8, 140
        n = len(self._items)
        content_h = MARGINS + n * ROW_H + max(0, n - 1) * SPACING
        self._scroll.setFixedHeight(min(content_h, MAX_H))

        # Let rows_widget expand to natural width so horizontal scroll works
        self._rows_widget.setMinimumWidth(0)

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
                txt.setStyleSheet(
                    "color:#334155;font-size:11px;background:transparent;"
                    "border:none;font-weight:600;white-space:nowrap;"
                )
                row_w.setStyleSheet("background:#E1E7EF;border-radius:4px;")
            else:
                txt.setStyleSheet(
                    "color:#334155;font-size:11px;background:transparent;"
                    "border:none;white-space:nowrap;"
                )
                row_w.setStyleSheet("background:transparent;")

# ── TextPropertyEditor ────────────────────────────────────────────────────────

class TextPropertyEditor(
    SameWithMixin,
    LookupMixin,
    LinkMixin,
    SystemMixin,
    MergeKonversiMixin,
    QWidget,
):
    def __init__(self, target_item, update_callback):
        QWidget.__init__(self)
        self.item = target_item
        self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.init_lookup_state()

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(8)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)

        # ── ANGLE ─────────────────────────────────────────────────────────────
        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        _angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}

        _current_qt_angle = int(round(self.item.rotation())) % 360
        _display_val = _QT_ANGLE_TO_DISPLAY.get(_current_qt_angle, "0")
        self.angle_combo.blockSignals(True)
        self.angle_combo._current = _display_val
        self.angle_combo._label.setText(_display_val)
        self.angle_combo.blockSignals(False)

        def _apply_angle(v):
            angle = _angle_map.get(v, 0)
            if not hasattr(self, "top_spin"):
                return
            saved_left = self.left_spin.value()
            saved_top  = self.top_spin.value()
            br = self.item.boundingRect()
            self.item.setTransformOriginPoint(br.center())
            self.item.setRotation(angle)
            aabb = self.item.mapToScene(br).boundingRect()
            off_x = aabb.left() - self.item.pos().x()
            off_y = aabb.top()  - self.item.pos().y()
            self.item.setPos(saved_left - off_x, saved_top - off_y)
            self.top_spin.blockSignals(True)
            self.left_spin.blockSignals(True)
            self.top_spin.setValue(saved_top)
            self.left_spin.setValue(saved_left)
            self.top_spin.blockSignals(False)
            self.left_spin.blockSignals(False)

        self.angle_combo.currentTextChanged.connect(_apply_angle)

        # ── ALIGNMENT ─────────────────────────────────────────────────────────
        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        stored_align = getattr(self.item, "design_alignment", None)
        if stored_align in ("LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"):
            self.align_combo._current = stored_align
            self.align_combo._label.setText(stored_align)
        else:
            doc = self.item.document()
            if doc.blockCount() > 0:
                block_align = doc.begin().blockFormat().alignment()
                if block_align == Qt.AlignCenter:
                    self.align_combo._current = "CENTER"
                    self.align_combo._label.setText("CENTER")
                elif block_align == Qt.AlignRight:
                    self.align_combo._current = "RIGHT JUSTIFY"
                    self.align_combo._label.setText("RIGHT JUSTIFY")
        layout.addRow(_lbl("ALIGNMENT :"), self.align_combo)

        # ── FONT ──────────────────────────────────────────────────────────────
        self.font_combo = make_chevron_combo([
            "STANDARD", "ARIAL", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
            "ARIAL BOLD", "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD",
            "FUTURA-CONDENSED-BOL", "FUTURA-NORMAL", "GLORIOLA STD BOLD",
            "GLORIOLA STD LIGHT", "HELVETICANEUE", "MONTSERRAT BOLD",
            "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD", "MYRIAD PRO",
            "NEO SANS", "NEO SANS BOLD", "OCR-B", "SWIS721", "TAHOMA",
            "UNIVERS CONDENSED",
        ])
        layout.addRow(_lbl("FONT NAME :"), self.font_combo)
        _stored_font = getattr(self.item, "design_font_name", "STANDARD")
        if _stored_font in self.font_combo._items:
            self.font_combo.blockSignals(True)
            self.font_combo._current = _stored_font
            self.font_combo._label.setText(_stored_font)
            self.font_combo.blockSignals(False)

        # ── SIZE / POSITION ───────────────────────────────────────────────────
        self.size_spin = make_spin(1, 100, int(self.item.font().pointSize()))

        self.item.document().setDocumentMargin(0)

        _br = self.item.boundingRect()
        self.item.setTransformOriginPoint(_br.center())
        _init_scene_rect = self.item.mapToScene(_br).boundingRect()
        self.top_spin  = make_spin(-5000, 5000, int(round(_init_scene_rect.top())))
        self.left_spin = make_spin(-5000, 5000, int(round(_init_scene_rect.left())))
        self.size_spin.valueChanged.connect(self.apply_font_changes)
        self.top_spin.valueChanged.connect(lambda v: self._move_to_visual(target_y=v))
        self.left_spin.valueChanged.connect(lambda v: self._move_to_visual(target_x=v))
        layout.addRow(_lbl("FONT SIZE :"), self.size_spin)
        layout.addRow(_lbl("TOP :"),       self.top_spin)
        layout.addRow(_lbl("LEFT :"),      self.left_spin)
        layout.addRow(_lbl("ANGLE :"),     self.angle_combo)

        # ── INVERSE ───────────────────────────────────────────────────────────
        self.inverse_combo = make_chevron_combo(["NO", "YES"])
        self.inverse_combo.setCurrentText(
            "YES" if getattr(self.item, "design_inverse", False) else "NO"
        )
        self.inverse_combo.currentTextChanged.connect(self._apply_inverse)
        layout.addRow(_lbl("INVERSE :"), self.inverse_combo)

        # ── TYPE ──────────────────────────────────────────────────────────────
        self.type_combo = make_chevron_combo([
            "FIX", "INPUT", "LOOKUP", "SAME WITH", "LINK", "SYSTEM",
            "BATCH NO", "MERGE", "TIMBANGAN", "DUPLIKASI", "RUNNING NO",
            "KONVERSI TIMBANGAN",
        ])
        self.type_combo.setCurrentText(getattr(self.item, "design_type", "FIX"))
        layout.addRow(_lbl("TYPE :"), self.type_combo)

        # ── EDITOR ────────────────────────────────────────────────────────────
        self.editor_combo = make_chevron_combo(["ENABLED", "DISABLED", "INVISIBLE"])
        layout.addRow(_lbl("EDITOR :"), self.editor_combo)

        # ── SYSTEM fields ─────────────────────────────────────────────────────
        self.system_value_combo = make_chevron_combo(["USER ID", "DATETIME", "LOT NO", "OTHERS"])
        self.system_extra_combo = make_chevron_combo([])
        self.system_extra_combo.setCurrentIndex(-1)
        layout.addRow(_lbl("SYSTEM VALUE :"), self.system_value_combo)
        layout.addRow(_lbl("EXTRA :"),        self.system_extra_combo)
        self.system_value_combo.currentTextChanged.connect(self._on_system_value_changed)
        self.system_extra_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_system_extra", v)
        )
        self.restore_system_values(
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
        self.same_with_combo = self._build_scene_name_combo(exclude_same_with=True)
        stored_same_with_id = getattr(self.item, "design_same_with", "")
        if stored_same_with_id:
            display_name = self.same_with_combo._id_map_inv.get(stored_same_with_id, "")
            if display_name and display_name in self.same_with_combo._items:
                self.same_with_combo.setCurrentText(display_name)
        self.same_with_combo.currentTextChanged.connect(self._on_same_with_changed)
        layout.addRow(_lbl("SAME WITH :"), self.same_with_combo)

        # ── LINK combo ────────────────────────────────────────────────────────
        self.link_combo = self._build_scene_name_combo(only_lookup=True)
        stored_link_id = getattr(self.item, "design_link", "")
        if stored_link_id:
            display_name = self.link_combo._id_map_inv.get(stored_link_id, "")
            if display_name and display_name in self.link_combo._items:
                self.link_combo.setCurrentText(display_name)
        self.link_combo.currentTextChanged.connect(self._on_link_changed)
        layout.addRow(_lbl("LINK TO :"), self.link_combo)

        # ── MERGE WITH  (MergeInputWidget — token field + ⋯ picker) ──────────
        self.merge_combo = self._build_merge_combo()
        layout.addRow(_lbl("MERGE WITH :"), self.merge_combo)

        # ── KONVERSI TIMBANGAN combos ─────────────────────────────────────────
        self.timbangan_combo = self._build_scene_name_combo()
        self.weight_combo    = self._build_scene_name_combo()
        self.um_combo        = self._build_scene_name_combo()
        for stored_attr, combo in (
            ("design_timbangan", self.timbangan_combo),
            ("design_weight",    self.weight_combo),
            ("design_um",        self.um_combo),
        ):
            sv = getattr(self.item, stored_attr, "")
            if sv and sv in combo._items:
                combo.setCurrentText(sv)
        self.timbangan_combo.currentTextChanged.connect(self._on_timbangan_changed)
        self.weight_combo.currentTextChanged.connect(self._on_weight_changed)
        self.um_combo.currentTextChanged.connect(self._on_um_changed)
        layout.addRow(_lbl("TIMBANGAN :"), self.timbangan_combo)
        layout.addRow(_lbl("WEIGHT :"),    self.weight_combo)
        layout.addRow(_lbl("U/M :"),       self.um_combo)

        # ── LOOKUP cascade ────────────────────────────────────────────────────
        self.group_combo  = make_chevron_combo([])
        self.table_combo  = make_chevron_combo([])
        self.table_extra  = QTextEdit()
        self.field_edit   = InlineChecklistWidget()
        self.result_combo = make_chevron_combo([])

        self.table_extra.setStyleSheet(
            "QTextEdit { background:#FFFFFF; border:1px solid #E2E8F0; border-radius:4px; "
            "padding:5px; font-size:11px; color:#1E293B; }"
            "QTextEdit:focus { border:1px solid #6366F1; }"
        )
        self.table_extra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.table_extra.setFixedHeight(80)
        self.table_extra.setAcceptRichText(False)

        for combo, ph in (
            (self.group_combo,  "— select connection —"),
            (self.table_combo,  "— select table —"),
            (self.result_combo, "— select result field —"),
        ):
            combo.setPlaceholderText(ph)
            combo.setCurrentIndex(-1)
            combo.setEnabled(False)
        self.field_edit.setEnabled(False)

        layout.addRow(_lbl("GROUP :"),  self.group_combo)
        layout.addRow(_lbl("TABLE :"),  self.table_combo)
        layout.addRow(_lbl("QUERY :"),  self.table_extra)
        layout.addRow(_lbl("FIELD :"),  self.field_edit)

        # RESULT + TRIM checkbox on the same row
        result_trim_row = QWidget()
        result_trim_row.setStyleSheet("background:transparent;border:none;")
        result_trim_layout = QVBoxLayout(result_trim_row)
        result_trim_layout.setContentsMargins(0, 0, 0, 0)
        result_trim_layout.setSpacing(6)

        self._trim_checked = False
        self.trim_box = QLabel()
        self.trim_box.setFixedSize(14, 14)
        self.trim_box.setCursor(Qt.PointingHandCursor)
        self._set_trim_style(False)
        self.trim_box.mousePressEvent = self._toggle_trim
        trim_lbl = QLabel("TRIM")
        trim_lbl.setStyleSheet(
            f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; "
            "background: transparent; border: none;"
        )
        result_trim_layout.addWidget(self.result_combo)

        trim_row = QWidget()
        trim_layout = QHBoxLayout(trim_row)
        trim_layout.setContentsMargins(0, 0, 0, 0)
        trim_layout.setSpacing(6)

        trim_layout.addWidget(self.trim_box)
        trim_layout.addWidget(trim_lbl)
        trim_layout.addStretch()

        result_trim_layout.addWidget(trim_row)
        layout.addRow(_lbl("RESULT :"), result_trim_row)

        self.build_connection_combo()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        self.field_edit.selectionChanged.connect(
            lambda names: setattr(self.item, "design_field", ",".join(names))
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

        self.restore_lookup_values(
            getattr(self.item, "design_group",  ""),
            getattr(self.item, "design_table",  ""),
            getattr(self.item, "design_field",  ""),
            getattr(self.item, "design_result", ""),
            getattr(self.item, "design_query",  ""),
        )

        # ── Text / display fields ─────────────────────────────────────────────
        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(_lbl("TEXT :"), self.text_input)

        self.caption_input = QLineEdit()
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.caption_input.setText(getattr(self.item, "design_caption", "") or "")
        self.caption_input.textChanged.connect(
            lambda v: setattr(self.item, "design_caption", v)
        )
        layout.addRow(_lbl("CAPTION :"), self.caption_input)

        self.wrap_combo      = make_chevron_combo(["NO", "YES"])
        self.wrap_width_spin = make_spin(0, 5000, 0)
        self.wrap_combo.setCurrentText(
            "YES" if getattr(self.item, "design_wrap_text", False) else "NO"
        )
        self.wrap_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_wrap_text", v == "YES")
        )
        _ww = getattr(self.item, "design_wrap_width", 1)
        try:
            self.wrap_width_spin.setValue(int(_ww) if _ww else 0)
        except (TypeError, ValueError):
            pass
        self.wrap_width_spin.valueChanged.connect(
            lambda v: setattr(self.item, "design_wrap_width", v)
        )
        layout.addRow(_lbl("WRAP TEXT :"),  self.wrap_combo)
        layout.addRow(_lbl("WRAP WIDTH :"), self.wrap_width_spin)

        self.format_edit = QLineEdit()
        self.format_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.format_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(_lbl("FORMAT :"), self.format_edit)

        # ── VISIBLE ───────────────────────────────────────────────────────────
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

        # ── TAMPIL ────────────────────────────────────────────────────────────────  ← ADD THIS BLOCK
        self.tampil_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_tampil = getattr(self.item, "design_tampil", True)
        self.tampil_combo.setCurrentText("TRUE" if current_tampil in (True, None) else "FALSE")
        self.tampil_combo.currentTextChanged.connect(self._apply_tampil)
        layout.addRow(_lbl("TAMPIL :"), self.tampil_combo)

        # ── Remaining fields ──────────────────────────────────────────────────
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "PRPMNO"] + [f"PRPM{i:02d}" for i in range(1, 31)])
        self.column_spin      = make_spin(1, 999, 1)
        self.mandatory_combo  = make_chevron_combo(["FALSE", "TRUE"])
        self.batch_no_combo   = make_chevron_combo([])
        self.batch_no_combo.setCurrentIndex(-1)
        self.wh_combo         = make_chevron_combo([])
        self.wh_combo.setCurrentIndex(-1)
        layout.addRow(_lbl("SAVE FIELD :"), self.save_field_combo)
        layout.addRow(_lbl("COLUMN :"),     self.column_spin)
        layout.addRow(_lbl("MANDATORY :"),  self.mandatory_combo)
        layout.addRow(_lbl("BATCH NO :"),   self.batch_no_combo)
        layout.addRow(_lbl("WH :"),         self.wh_combo)

        # ── Wire remaining signals ────────────────────────────────────────────
        self.align_combo.currentTextChanged.connect(self._apply_alignment)
        self.font_combo.currentTextChanged.connect(self._apply_font_family)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        self.editor_combo.setCurrentText(
            getattr(self.item, "design_editor", "ENABLED") or "ENABLED"
        )
        self.data_type_combo.setCurrentText(
            getattr(self.item, "design_data_type", "STRING") or "STRING"
        )
        _ml = getattr(self.item, "design_max_length", 1)
        try:
            self.max_length_spin.setValue(int(_ml))
        except (TypeError, ValueError):
            pass
        self.save_field_combo.setCurrentText(
            getattr(self.item, "design_save_field", "-- NOT SAVE --") or "-- NOT SAVE --"
        )
        _col = getattr(self.item, "design_column", 1)
        try:
            self.column_spin.setValue(int(_col))
        except (TypeError, ValueError):
            pass
        self.mandatory_combo.setCurrentText(
            getattr(self.item, "design_mandatory", "FALSE") or "FALSE"
        )
        self.format_edit.setText(getattr(self.item, "design_format", "") or "")
        _trim = getattr(self.item, "design_trim", False)
        self._trim_checked = bool(_trim)
        self._set_trim_style(self._trim_checked)

        self.editor_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_editor", v)
        )
        self.data_type_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_data_type", v)
        )
        self.max_length_spin.valueChanged.connect(
            lambda v: setattr(self.item, "design_max_length", v)
        )
        self.save_field_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_save_field", v)
        )
        self.column_spin.valueChanged.connect(
            lambda v: setattr(self.item, "design_column", v)
        )
        self.mandatory_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_mandatory", v)
        )
        self.format_edit.textChanged.connect(
            lambda v: setattr(self.item, "design_format", v)
        )

        self._on_type_changed(getattr(self.item, "design_type", "FIX"))

        stored_same_with_id = getattr(self.item, "design_same_with", "")
        if (stored_same_with_id
                and getattr(self.item, "design_type", "") == "SAME WITH"):
            self._apply_same_with_link(stored_same_with_id)

    # ── Helper: build the MERGE WITH token-input widget ───────────────────────

    def _build_merge_combo(self) -> MergeInputWidget:
        from components.barcode_editor.scene_items import SelectableTextItem
        names: list[str] = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, SelectableTextItem):
                        continue
                    name = getattr(si, "component_name", "") or "Text"
                    names.append(name)
        except Exception:
            pass

        combo = MergeInputWidget()
        combo.set_items(names)
        stored = getattr(self.item, "design_merge", "")
        if stored:
            combo.set_selected(stored)
        combo.templateChanged.connect(self._on_merge_changed)
        return combo

    # ── Helper: build a single-select name combo from scene items ─────────────

    def _build_scene_name_combo(self, exclude_same_with=False, only_lookup=False):
        from components.barcode_editor.scene_items import SelectableTextItem
        names = []
        ids = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, SelectableTextItem):
                        continue
                    if exclude_same_with and getattr(si, "design_same_with", "") == getattr(self.item, "component_name", ""):
                        continue
                    if only_lookup and getattr(si, "design_type", "") != "LOOKUP":
                        continue
                    ids.append(getattr(si, "component_id", ""))
                    names.append(getattr(si, "component_name", "") or "Text")
        except Exception:
            pass

        combo = make_chevron_combo(names)
        combo._id_map     = dict(zip(names, ids))
        combo._id_map_inv = dict(zip(ids, names))
        combo.setPlaceholderText("—")
        combo.setCurrentIndex(-1)
        return combo

    # ── _on_type_changed ──────────────────────────────────────────────────────

    def _on_type_changed(self, val: str):
        is_input     = val == "INPUT"
        is_lookup    = val == "LOOKUP"
        is_same_with = val == "SAME WITH"
        is_link      = val == "LINK"
        is_system    = val == "SYSTEM"
        is_batch_no  = val == "BATCH NO"
        is_merge     = val == "MERGE"
        is_konversi  = val == "KONVERSI TIMBANGAN"
        is_timbangan = val == "TIMBANGAN"

        setattr(self.item, "design_type", val)

        _prev = getattr(self, "_last_type", None)
        if _prev is not None:
            if _prev == "LOOKUP"    and not is_lookup:    self.clear_lookup_fields()
            if _prev == "SAME WITH" and not is_same_with: self.clear_same_with_fields()
            if _prev == "LINK"      and not is_link:      self.clear_link_fields()
            if _prev == "SYSTEM"    and not is_system:    self.clear_system_fields()
            if _prev == "BATCH NO"  and not is_batch_no:  self._clear_batch_no_fields()

        self._last_type = val

        self.enable_for_same_with(is_same_with)
        if is_same_with:
            # SAME WITH → editor forced to INVISIBLE, locked
            self.editor_combo.blockSignals(True)
            self.editor_combo.setCurrentText("INVISIBLE")
            self.editor_combo.blockSignals(False)
            self.editor_combo.setEnabled(False)
            setattr(self.item, "design_editor", "INVISIBLE")
            return

        # ── EDITOR field rules per type ───────────────────────────────────────
        if is_input:
            # INPUT → editor forced to ENABLED, locked
            self.editor_combo.blockSignals(True)
            self.editor_combo.setCurrentText("ENABLED")
            self.editor_combo.blockSignals(False)
            self.editor_combo.setEnabled(False)
            setattr(self.item, "design_editor", "ENABLED")
        elif is_timbangan:
            # TIMBANGAN → editor forced to DISABLED, locked
            self.editor_combo.blockSignals(True)
            self.editor_combo.setCurrentText("DISABLED")
            self.editor_combo.blockSignals(False)
            self.editor_combo.setEnabled(False)
            setattr(self.item, "design_editor", "DISABLED")
        elif is_merge or is_batch_no:
            # MERGE / BATCH NO → editor forced to INVISIBLE, locked
            self.editor_combo.blockSignals(True)
            self.editor_combo.setCurrentText("INVISIBLE")
            self.editor_combo.blockSignals(False)
            self.editor_combo.setEnabled(False)
            setattr(self.item, "design_editor", "INVISIBLE")
        else:
            # All other types (FIX, LOOKUP, LINK, SYSTEM, etc.) → freely editable
            self.editor_combo.setEnabled(True)

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

        self.enable_for_lookup(is_lookup)
        self.enable_for_link(is_link)
        self.enable_for_system(is_system)
        self.enable_for_merge(is_merge)
        self.enable_for_konversi(is_konversi)

        if is_batch_no:
            self._populate_batch_no_options()
        else:
            self.batch_no_combo.setEnabled(False)
            self.wh_combo.setEnabled(False)
            self.batch_no_combo.setCurrentIndex(-1)
            self.wh_combo.setCurrentIndex(-1)

        self.same_with_combo.setEnabled(is_same_with)

    def _populate_batch_no_options(self):
        from components.barcode_editor.scene_items import SelectableTextItem

        names = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, SelectableTextItem):
                        continue
                    name = getattr(si, "component_name", "") or "Text"
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

    # ── Standard property-apply methods ──────────────────────────────────────

    def _apply_alignment(self, value: str):
        align_map = {
            "LEFT JUSTIFY":  Qt.AlignLeft,
            "CENTER":        Qt.AlignCenter,
            "RIGHT JUSTIFY": Qt.AlignRight,
        }
        alignment = align_map.get(value, Qt.AlignLeft)
        if value == "LEFT JUSTIFY":
            self.item.setTextWidth(-1)
        else:
            w = self.item.boundingRect().width()
            self.item.setTextWidth(w if w > 0 else 200)
        doc = self.item.document()
        doc_cursor = QTextCursor(doc)
        doc_cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setAlignment(alignment)
        doc_cursor.mergeBlockFormat(fmt)
        self.item.design_alignment = value
        self.update_callback()

    def _apply_font_family(self, value: str):
        self.item.design_font_name = value
        font_map = {
            "STANDARD":             "Arial",
            "ARIAL":                "Arial",
            "ARIAL BLACK":          "Arial Black",
            "ARIAL BLACK (GT)":     "Arial Black",
            "ARIAL BLACK NEW":      "Arial Black",
            "ARIAL BOLD":           "Arial",
            "ARIAL NARROW BOLD":    "Arial Narrow",
            "EUROSTILE BOLD OLD":   "Eurostile",
            "FUTURA-CONDENSED-BOL": "Futura",
            "FUTURA-NORMAL":        "Futura",
            "GLORIOLA STD BOLD":    "Arial",
            "GLORIOLA STD LIGHT":   "Arial",
            "HELVETICANEUE":        "Helvetica Neue",
            "MONTSERRAT BOLD":      "Montserrat",
            "MONTSERRAT SBOLD-CAE": "Montserrat",
            "MONTSERRAT SEMI BOLD": "Montserrat",
            "MYRIAD PRO":           "Myriad Pro",
            "NEO SANS":             "Neo Sans",
            "NEO SANS BOLD":        "Neo Sans",
            "OCR-B":                "OCR B",
            "SWIS721":              "Swiss 721",
            "TAHOMA":               "Tahoma",
            "UNIVERS CONDENSED":    "Univers Condensed",
        }
        bold_fonts = {
            "ARIAL BOLD", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
            "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD", "FUTURA-CONDENSED-BOL",
            "GLORIOLA STD BOLD", "HELVETICANEUE", "MONTSERRAT BOLD",
            "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD", "NEO SANS BOLD",
        }
        font = self.item.font()
        font.setFamily(font_map.get(value, "Arial"))
        font.setBold(value in bold_fonts)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_inverse(self, value: str):
        self.item.design_inverse = (value == "YES")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_tampil(self, value: str):          # ← ADD THIS METHOD
        self.item.design_tampil = (value == "TRUE")
        self.update_callback()

    def _set_trim_style(self, checked: bool):
        if checked:
            self.trim_box.setText("✓")
            self.trim_box.setAlignment(Qt.AlignCenter)
            self.trim_box.setStyleSheet(
                "QLabel{border:1.5px solid #6366F1;border-radius:3px;"
                "background:#6366F1;color:white;font-size:9px;font-weight:bold;}"
            )
        else:
            self.trim_box.setText("")
            self.trim_box.setStyleSheet(
                "QLabel{border:1.5px solid #CBD5E1;border-radius:3px;background:white;}"
            )

    def _toggle_trim(self, event):
        self._trim_checked = not self._trim_checked
        self._set_trim_style(self._trim_checked)
        self.item.design_trim = self._trim_checked

    def apply_text_changes(self, text: str):
        self.item.setPlainText(text)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def apply_font_changes(self, size: int):
        font = self.item.font()
        font.setPointSize(size)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _move_visual_tl(self, want_x: int, want_y: int):
        self._move_to_visual(target_x=want_x, target_y=want_y)

    def _get_rotation_offset(self):
        scene_rect = self.item.mapToScene(self.item.boundingRect()).boundingRect()
        pos = self.item.pos()
        off_x = scene_rect.left() - pos.x()
        off_y = scene_rect.top() - pos.y()
        return off_x, off_y

    def _move_to_visual(self, target_x=None, target_y=None):
        off_x, off_y = self._get_rotation_offset()
        if target_x is not None:
            self.item.setX(target_x - off_x)
        if target_y is not None:
            self.item.setY(target_y - off_y)
        self.update_position_fields(self.item.pos())

    def update_position_fields(self, pos):
        scene_rect = self.item.mapToScene(self.item.boundingRect()).boundingRect()
        new_top  = int(round(scene_rect.top()))
        new_left = int(round(scene_rect.left()))

        if not self.top_spin.hasFocus():
            self.top_spin.blockSignals(True)
            self.top_spin.setValue(new_top)
            self.top_spin.blockSignals(False)

        if not self.left_spin.hasFocus():
            self.left_spin.blockSignals(True)
            self.left_spin.setValue(new_left)
            self.left_spin.blockSignals(False)