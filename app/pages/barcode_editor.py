import sys
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsRectItem, 
    QGraphicsTextItem, QGraphicsItemGroup, QGraphicsLineItem, QListWidget, 
    QListWidgetItem, QComboBox, QLineEdit, QSpinBox, QFormLayout, 
    QApplication, QScrollArea, QStyledItemDelegate, QStyle
)
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, QSize, QEvent, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QFontMetrics
from components.barcode_design_modal import BarcodeDesignModal
from PySide6.QtWidgets import QDialog
import shiboken6

# Local Imports
from components.standard_button import StandardButton

COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "border": "#E2E8F0",
    "text_dark": "#1E293B",
    "text_mute": "#64748B",
    "white": "#FFFFFF",
    "prop_bg": "#F1F5F9",
    "canvas_bg": "#F1F5F9",
    "legacy_blue": "#1E3A8A" 
}

MODERN_COMBO_STYLE = """
    QComboBox {
        background-color: white;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        padding: 5px 28px 5px 8px;
        font-size: 11px;
        color: #334155;
    }
    QComboBox:focus {
        border: 1.5px solid #6366F1;
    }
    QComboBox::drop-down {
        border: 0px;
        background: transparent;
    }
    QComboBox::down-arrow {
        image: none;
        width: 0;
        height: 0;
    }
"""

MODERN_INPUT_STYLE = """
    QLineEdit, QSpinBox, QComboBox {
        background-color: white;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        padding: 5px;
        font-size: 11px;
        color: #334155;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
        border: 1.5px solid #6366F1;
    }
    QSpinBox::up-button, QSpinBox::down-button {
        subcontrol-origin: border;
        width: 20px;
        border: none;
        background: transparent;
    }
    QSpinBox::up-button {
        subcontrol-position: top right;
        border-left: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        border-top-right-radius: 4px;
    }
    QSpinBox::down-button {
        subcontrol-position: bottom right;
        border-left: 1px solid #CBD5E1;
        border-bottom-right-radius: 4px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {
        background: #F1F5F9;
    }
    QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {
        background: #E2E8F0;
    }
    QSpinBox::up-arrow, QSpinBox::down-arrow {
        width: 0px;
        height: 0px;
        image: none;
    }
    QComboBox::drop-down {
        border: 0px;
        background: transparent;
    }
    QComboBox::down-arrow {
        image: none;
        width: 0;
        height: 0;
    }
"""


class ChevronSpinBox(QSpinBox):
    _BTN_W = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._px_up   = qta.icon("fa5s.chevron-up",   color="#64748B").pixmap(7, 7)
        self._px_down = qta.icon("fa5s.chevron-down",  color="#64748B").pixmap(7, 7)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        h      = self.height()
        btn_w  = self._BTN_W
        x_left = self.width() - btn_w
        icon_w = self._px_up.width()
        icon_h = self._px_up.height()
        cx     = x_left + (btn_w - icon_w) // 2

        painter.drawPixmap(cx, (h // 2 - icon_h) // 2, self._px_up)
        painter.drawPixmap(cx, h // 2 + (h // 2 - icon_h) // 2, self._px_down)
        painter.end()


def make_spin(min_val: int = 0, max_val: int = 5000, value: int = 0) -> ChevronSpinBox:
    spin = ChevronSpinBox()
    spin.setRange(min_val, max_val)
    spin.setValue(value)
    spin.setStyleSheet(MODERN_INPUT_STYLE)
    return spin


def make_chevron_combo(items: list[str], style: str = MODERN_INPUT_STYLE) -> QComboBox:
    combo = QComboBox()
    combo.addItems(items)
    combo.setStyleSheet(style)
    combo.setCursor(Qt.PointingHandCursor)

    inner = QHBoxLayout(combo)
    inner.setContentsMargins(0, 0, 10, 0)
    inner.addStretch()

    chevron = QLabel()
    chevron.setPixmap(qta.icon("fa5s.chevron-down", color="#64748B").pixmap(10, 10))
    chevron.setAttribute(Qt.WA_TransparentForMouseEvents)
    chevron.setStyleSheet("background: transparent; border: none;")
    inner.addWidget(chevron)

    return combo


# --- Utilities ---

def keep_within_bounds(item, new_pos):
    scene_rect = item.scene().sceneRect()
    rect = item.sceneBoundingRect()
    width = rect.width()
    height = rect.height()
    x = max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - width))
    y = max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - height))
    return QPointF(x, y)


def setup_item_logic(item, on_move_callback):
    original_item_change = item.itemChange
    def patched_item_change(change, value):
        if change == QGraphicsItem.ItemPositionChange and item.scene():
            new_pos = keep_within_bounds(item, value)
            on_move_callback(new_pos)
            return new_pos
        return original_item_change(change, value)
    item.itemChange = patched_item_change

# --- Property Editors ---

class TextPropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase;"

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(label_style)
            return l

        # ── ALIGNMENT ────────────────────────────────────────────────
        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        layout.addRow(lbl("ALIGNMENT :"), self.align_combo)

        # ── FONT NAME ────────────────────────────────────────────────
        self.font_combo = make_chevron_combo(["STANDARD", "MONOSPACE", "SERIF"])
        layout.addRow(lbl("FONT NAME :"), self.font_combo)

        # ── FONT SIZE ────────────────────────────────────────────────
        self.size_spin = make_spin(1, 100, int(self.item.font().pointSize()))
        self.size_spin.valueChanged.connect(self.apply_font_changes)
        layout.addRow(lbl("FONT SIZE :"), self.size_spin)

        # ── TOP ──────────────────────────────────────────────────────
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(lbl("TOP :"), self.top_spin)

        # ── LEFT ─────────────────────────────────────────────────────
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(lbl("LEFT :"), self.left_spin)

        # ── ANGLE ────────────────────────────────────────────────────
        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}
        self.angle_combo.currentTextChanged.connect(
            lambda v: self.item.setRotation(angle_map.get(v, 0))
        )
        layout.addRow(lbl("ANGLE :"), self.angle_combo)

        # ── INVERSE ──────────────────────────────────────────────────
        self.inverse_combo = make_chevron_combo(["NO", "YES"])
        self.inverse_combo.currentTextChanged.connect(self._apply_inverse)
        layout.addRow(lbl("INVERSE :"), self.inverse_combo)

        # ── TYPE ─────────────────────────────────────────────────────
        self.type_combo = make_chevron_combo(["FIX", "VAR"])
        layout.addRow(lbl("TYPE :"), self.type_combo)

        # ── EDITOR ───────────────────────────────────────────────────
        self.editor_combo = make_chevron_combo(["INVISIBLE", "VISIBLE", "READONLY"])
        layout.addRow(lbl("EDITOR :"), self.editor_combo)

        # ── TEXT ─────────────────────────────────────────────────────
        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(lbl("TEXT :"), self.text_input)

        # ── CAPTION ──────────────────────────────────────────────────
        self.caption_input = QLineEdit("LABEL 1")
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        layout.addRow(lbl("CAPTION :"), self.caption_input)

        # ── WRAP TEXT + WIDTH (inline) ────────────────────────────────
        wrap_row = QWidget()
        wrap_row.setStyleSheet("background: transparent; border: none;")
        wrap_layout = QHBoxLayout(wrap_row)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(6)

        self.wrap_combo = make_chevron_combo(["NO", "YES"])
        wrap_layout.addWidget(self.wrap_combo, stretch=2)

        width_label = QLabel("WIDTH :")
        width_label.setStyleSheet(label_style)
        wrap_layout.addWidget(width_label)

        self.wrap_width_spin = make_spin(0, 5000, 1)
        wrap_layout.addWidget(self.wrap_width_spin, stretch=1)

        layout.addRow(lbl("WRAP TEXT :"), wrap_row)

        # ── GROUP ────────────────────────────────────────────────────
        self.group_combo = make_chevron_combo([""])
        layout.addRow(lbl("GROUP :"), self.group_combo)

        # ── TABLE (combo + extra text field inline) ───────────────────
        table_row = QWidget()
        table_row.setStyleSheet("background: transparent; border: none;")
        table_layout = QHBoxLayout(table_row)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(6)

        self.table_combo = make_chevron_combo([""])
        table_layout.addWidget(self.table_combo, stretch=2)

        self.table_extra = QLineEdit()
        self.table_extra.setStyleSheet(MODERN_INPUT_STYLE)
        table_layout.addWidget(self.table_extra, stretch=1)

        layout.addRow(lbl("TABLE :"), table_row)

        # ── FIELD (taller multiline-style input) ─────────────────────
        self.field_edit = QLineEdit()
        self.field_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.field_edit.setMinimumHeight(52)
        layout.addRow(lbl("FIELD :"), self.field_edit)

        # ── RESULT + TRIM checkbox (inline) ───────────────────────────
        result_row = QWidget()
        result_row.setStyleSheet("background: transparent; border: none;")
        result_layout = QHBoxLayout(result_row)
        result_layout.setContentsMargins(0, 0, 0, 0)
        result_layout.setSpacing(6)

        self.result_combo = make_chevron_combo([""])
        result_layout.addWidget(self.result_combo, stretch=2)

        self._trim_checked = False
        self.trim_box = QLabel()
        self.trim_box.setFixedSize(14, 14)
        self.trim_box.setCursor(Qt.PointingHandCursor)
        self._set_trim_style(False)
        self.trim_box.mousePressEvent = self._toggle_trim
        result_layout.addWidget(self.trim_box)

        trim_lbl = QLabel("TRIM")
        trim_lbl.setStyleSheet(label_style)
        result_layout.addWidget(trim_lbl)
        result_layout.addStretch()

        layout.addRow(lbl("RESULT :"), result_row)

        # ── FORMAT ───────────────────────────────────────────────────
        self.format_edit = QLineEdit()
        self.format_edit.setStyleSheet(MODERN_INPUT_STYLE)
        layout.addRow(lbl("FORMAT :"), self.format_edit)

        # ── VISIBLE ──────────────────────────────────────────────────
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)

        # ── SAVE FIELD ───────────────────────────────────────────────
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "SAVE"])
        layout.addRow(lbl("SAVE FIELD :"), self.save_field_combo)

        # ── COLUMN ───────────────────────────────────────────────────
        self.column_spin = make_spin(1, 999, 1)
        layout.addRow(lbl("COLUMN :"), self.column_spin)

        # ── MANDATORY ────────────────────────────────────────────────
        self.mandatory_combo = make_chevron_combo(["FALSE", "TRUE"])
        layout.addRow(lbl("MANDATORY :"), self.mandatory_combo)

    # ── Internal helpers ─────────────────────────────────────────────

    def _set_trim_style(self, checked: bool):
        if checked:
            self.trim_box.setText("✓")
            self.trim_box.setAlignment(Qt.AlignCenter)
            self.trim_box.setStyleSheet("""
                QLabel {
                    border: 1.5px solid #6366F1;
                    border-radius: 3px;
                    background: #6366F1;
                    color: white;
                    font-size: 9px;
                    font-weight: bold;
                }
            """)
        else:
            self.trim_box.setText("")
            self.trim_box.setStyleSheet("""
                QLabel {
                    border: 1.5px solid #CBD5E1;
                    border-radius: 3px;
                    background: white;
                }
            """)

    def _toggle_trim(self, event):
        self._trim_checked = not self._trim_checked
        self._set_trim_style(self._trim_checked)

    def _apply_inverse(self, value):
        if value == "YES":
            self.item.setDefaultTextColor(QColor("white"))
        else:
            self.item.setDefaultTextColor(QColor("black"))

    def apply_text_changes(self, text):
        self.item.setPlainText(text)
        self.update_callback()

    def apply_font_changes(self, size):
        font = self.item.font()
        font.setPointSize(size)
        self.item.setFont(font)
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)


class LinePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase;"

        def create_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(label_style)
            return lbl

        line = self.item.line()
        pen = self.item.pen()

        self.thickness_spin = make_spin(1, 100, int(pen.width()))
        self.thickness_spin.valueChanged.connect(self.update_thickness)
        layout.addRow(create_label("THICKNESS :"), self.thickness_spin)

        self.width_spin = make_spin(0, 5000, int(abs(line.dx())))
        self.width_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(create_label("WIDTH :"), self.width_spin)

        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(create_label("TOP :"), self.top_spin)

        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(create_label("LEFT :"), self.left_spin)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(create_label("VISIBLE :"), self.visible_combo)

    def update_geometry(self):
        self.item.setLine(0, 0, self.width_spin.value(), 0)
        self.update_callback()

    def update_thickness(self, value):
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


class RectanglePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase;"

        def create_label(text):
            lbl = QLabel(text)
            lbl.setStyleSheet(label_style)
            return lbl

        rect = self.item.rect()
        pen = self.item.pen()

        self.height_spin = make_spin(0, 5000, int(rect.height()))
        self.height_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(create_label("HEIGHT :"), self.height_spin)

        self.width_spin = make_spin(0, 5000, int(rect.width()))
        self.width_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(create_label("WIDTH :"), self.width_spin)

        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(create_label("TOP :"), self.top_spin)

        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(create_label("LEFT :"), self.left_spin)

        self.border_spin = make_spin(0, 20, int(pen.width()))
        self.border_spin.valueChanged.connect(self.update_border)
        layout.addRow(create_label("BORDER WIDTH :"), self.border_spin)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(create_label("VISIBLE :"), self.visible_combo)

        # ── COLUMN ───────────────────────────────────────────────────
        self.column_spin = make_spin(1, 999, 1)
        layout.addRow(create_label("COLUMN :"), self.column_spin)

    def update_geometry(self):
        self.item.setRect(0, 0, self.width_spin.value(), self.height_spin.value())
        self.update_callback()

    def update_border(self, width):
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


class BarcodePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item
        self.update_callback = update_callback

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        label_style = f"color:{COLORS['legacy_blue']}; font-size:9px; text-transform:uppercase;"

        def label(t):
            l = QLabel(t)
            l.setStyleSheet(label_style)
            return l

        self.design_combo = make_chevron_combo(["CODE128", "MINIMAL", "EAN13", "CODE39", "QR MOCK"])
        self.design_combo.setCurrentText(self.item.design)
        self.design_combo.currentTextChanged.connect(self.update_design)
        layout.addRow(label("DESIGN :"), self.design_combo)

        self.width_spin = make_spin(20, 1000, self.item.container_width)
        self.width_spin.valueChanged.connect(self.update_size)
        layout.addRow(label("WIDTH :"), self.width_spin)

        self.height_spin = make_spin(20, 1000, self.item.container_height)
        self.height_spin.valueChanged.connect(self.update_size)
        layout.addRow(label("HEIGHT :"), self.height_spin)

        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(label("TOP :"), self.top_spin)

        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(label("LEFT :"), self.left_spin)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(label("VISIBLE :"), self.visible_combo)

    def update_design(self, new_design):
        old_scene_pos = self.item.scenePos()

        for child in list(self.item.childItems()):
            self.item.removeFromGroup(child)
            if child.scene():
                child.scene().removeItem(child)
            child.setParentItem(None)
            del child

        self.item.setPos(0, 0)
        self.item.design = new_design
        self.item.bg = QGraphicsRectItem(0, 0, self.item.container_width, self.item.container_height)
        self.item.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine))
        self.item.bg.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.item.addToGroup(self.item.bg)

        if new_design == "MINIMAL":
            bar_pattern = [4, 2, 4, 2, 4, 2, 4]
        elif new_design == "EAN13":
            bar_pattern = [2, 2, 3, 2, 2, 4, 3, 2, 3, 2, 2]
        elif new_design == "CODE39":
            bar_pattern = [3, 1, 3, 1, 2, 1, 3, 1, 2, 1, 3]
        elif new_design == "QR MOCK":
            square = QGraphicsRectItem(40, 15, 50, 50)
            square.setBrush(QBrush(Qt.black))
            square.setPen(Qt.NoPen)
            self.item.addToGroup(square)
            bar_pattern = []
        else:
            bar_pattern = [3, 2, 3, 2, 2, 3, 2, 3, 3, 2, 2, 3, 2, 3, 2, 2, 3, 2, 3]

        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.item.addToGroup(bar)
            x_offset += width

        lbl = QGraphicsTextItem("*12345678*")
        lbl.setFont(QFont("Courier", 9, QFont.Bold))
        lbl.setPos(35, 58)
        self.item.addToGroup(lbl)

        self.item.setPos(old_scene_pos)
        self.update_callback()

    def update_size(self):
        self.item.container_width = self.width_spin.value()
        self.item.container_height = self.height_spin.value()
        self.item.bg.setRect(0, 0, self.item.container_width, self.item.container_height)
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)


# --- Custom Components ---

class BarcodeItem(QGraphicsItemGroup):
    def __init__(self, move_callback, design="CODE128"):
        super().__init__()
        self.move_callback = move_callback
        self.component_name = "Barcode"
        self.setFlags(
            QGraphicsItem.ItemIsMovable | 
            QGraphicsItem.ItemIsSelectable | 
            QGraphicsItem.ItemSendsGeometryChanges
        )
        
        self.container_width = 160
        self.container_height = 80
        self.design = design
        
        self.bg = QGraphicsRectItem(0, 0, self.container_width, self.container_height)
        self.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine))
        self.bg.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.addToGroup(self.bg)

        if design == "MINIMAL":
            bar_pattern = [4, 2, 4, 2, 4, 2, 4]
        elif design == "EAN13":
            bar_pattern = [2, 2, 3, 2, 2, 4, 3, 2, 3, 2, 2]
        elif design == "CODE39":
            bar_pattern = [3, 1, 3, 1, 2, 1, 3, 1, 2, 1, 3]
        elif design == "QR MOCK":
            square = QGraphicsRectItem(40, 15, 50, 50)
            square.setBrush(QBrush(Qt.black))
            square.setPen(Qt.NoPen)
            self.addToGroup(square)
            bar_pattern = []
        else:
            bar_pattern = [3, 2, 3, 2, 2, 3, 2, 3, 3, 2, 2, 3, 2, 3, 2, 2, 3, 2, 3]

        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.addToGroup(bar)
            x_offset += width

        label_item = QGraphicsTextItem("*12345678*")
        label_item.setFont(QFont("Courier", 9, QFont.Bold))
        label_item.setPos(35, 58)
        self.addToGroup(label_item)

    def boundingRect(self):
        return self.childrenBoundingRect().adjusted(-2, -2, 2, 2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            constrained_pos = keep_within_bounds(self, value)
            if self.move_callback:
                self.move_callback(constrained_pos)
            return constrained_pos
        return super().itemChange(change, value)


class GridGraphicsScene(QGraphicsScene):
    def __init__(self, rect, grid_size=20, color=QColor("#E2E8F0"), parent=None):
        super().__init__(rect, parent)
        self.grid_size = grid_size
        self.grid_color = color

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)

        scene_r = self.sceneRect()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRect(scene_r)

        painter.setPen(QPen(self.grid_color, 1))
        left = int(scene_r.left()) - (int(scene_r.left()) % self.grid_size)
        top  = int(scene_r.top())  - (int(scene_r.top())  % self.grid_size)

        x = left
        while x < scene_r.right():
            painter.drawLine(QPointF(x, scene_r.top()), QPointF(x, scene_r.bottom()))
            x += self.grid_size

        y = top
        while y < scene_r.bottom():
            painter.drawLine(QPointF(scene_r.left(), y), QPointF(scene_r.right(), y))
            y += self.grid_size

        painter.setPen(QPen(QColor("#94A3B8"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(scene_r)


# --- Component List Delegate ---

COMPONENT_META = {
    'text':      ('fa5s.font',       '#6366F1', '#FFFFFF', '#4338CA'),
    'barcode':   ('fa5s.barcode',    '#0EA5E9', '#FFFFFF', '#0369A1'),
    'line':      ('fa5s.minus',      '#10B981', '#FFFFFF', '#047857'),
    'rect':      ('fa5s.square',     '#F59E0B', '#FFFFFF', '#B45309'),
}

def _get_meta(name: str):
    key = name.lower()
    if key.startswith('text'):      return COMPONENT_META['text']
    if key.startswith('barcode'):   return COMPONENT_META['barcode']
    if key.startswith('line'):      return COMPONENT_META['line']
    if key.startswith('rect'):      return COMPONENT_META['rect']
    return ('fa5s.cube', '#64748B', '#FFFFFF', '#475569')


class ComponentItemDelegate(QStyledItemDelegate):
    ROW_H     = 38
    ACCENT_W  = 3
    CHIP_SIZE = 24
    PAD       = 8
    TRASH_SIZE = 18

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), self.ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        name      = index.data(Qt.DisplayRole) or ""
        icon_name, badge_bg, badge_fg, accent = _get_meta(name)

        selected = bool(option.state & QStyle.State_Selected)
        hovered  = bool(option.state & QStyle.State_MouseOver) and not selected

        r = option.rect.adjusted(4, 2, -4, -2)

        if selected:
            bg = QColor("#EEF2FF")
        elif hovered:
            bg = QColor("#F8FAFC")
        else:
            bg = QColor("#FFFFFF")

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(r, 6, 6)

        accent_rect = QRect(r.left(), r.top() + 6, self.ACCENT_W, r.height() - 12)
        painter.setBrush(QBrush(QColor(accent)))
        painter.drawRoundedRect(accent_rect, 2, 2)

        chip_x = r.left() + self.ACCENT_W + self.PAD
        chip_y = r.top() + (r.height() - self.CHIP_SIZE) // 2
        chip_r = QRect(chip_x, chip_y, self.CHIP_SIZE, self.CHIP_SIZE)

        chip_bg = QColor(badge_bg)
        chip_bg.setAlpha(40 if not selected else 60)
        painter.setBrush(QBrush(chip_bg))
        painter.drawRoundedRect(chip_r, 5, 5)

        px = qta.icon(icon_name, color=badge_bg).pixmap(13, 13)
        painter.drawPixmap(chip_x + (self.CHIP_SIZE - 13) // 2, chip_y + (self.CHIP_SIZE - 13) // 2, px)

        trash_x = r.right() - self.TRASH_SIZE - self.PAD
        trash_y = r.top() + (r.height() - self.TRASH_SIZE) // 2
        trash_r = QRect(trash_x, trash_y, self.TRASH_SIZE, self.TRASH_SIZE)

        index.model().setData(index, trash_r, Qt.UserRole + 1)

        if hovered or selected:
            trash_bg = QColor("#FEE2E2")
            painter.setBrush(QBrush(trash_bg))
            painter.drawRoundedRect(trash_r, 4, 4)

        trash_px = qta.icon("fa5s.trash-alt", color="#EF4444" if (hovered or selected) else "#CBD5E1").pixmap(11, 11)
        painter.drawPixmap(trash_x + (self.TRASH_SIZE - 11) // 2, trash_y + (self.TRASH_SIZE - 11) // 2, trash_px)

        text_x = chip_x + self.CHIP_SIZE + self.PAD
        text_w = trash_x - text_x - self.PAD

        display_type = name
        display_value = ''

        if ': ' in name:
            parts = name.split(': ', 1)
            display_type = parts[0].strip()
            display_value = parts[1].strip()

        type_font = QFont()
        type_font.setPointSize(9)
        type_font.setWeight(QFont.DemiBold)
        painter.setFont(type_font)
        painter.setPen(QColor('#1E293B') if selected else QColor('#334155'))

        if display_value:
            type_rect = QRect(text_x, r.top() + 3, text_w, r.height() // 2)
            type_fm = QFontMetrics(type_font)
            elided_type = type_fm.elidedText(display_type, Qt.ElideRight, text_w)
            painter.drawText(type_rect, Qt.AlignLeft | Qt.AlignBottom, elided_type)

            value_font = QFont()
            value_font.setPointSize(8)
            painter.setFont(value_font)
            painter.setPen(QColor('#94A3B8'))

            value_fm = QFontMetrics(value_font)
            elided_value = value_fm.elidedText(display_value, Qt.ElideRight, text_w)

            value_rect = QRect(text_x, r.top() + r.height() // 2, text_w, r.height() // 2 - 3)
            painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignTop, elided_value)
        else:
            type_fm = QFontMetrics(type_font)
            elided_type = type_fm.elidedText(display_type, Qt.ElideRight, text_w)
            painter.drawText(QRect(text_x, r.top(), text_w, r.height()), Qt.AlignLeft | Qt.AlignVCenter, elided_type)

        if selected:
            painter.setPen(QPen(QColor('#6366F1'), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, 6, 6)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            trash_rect = index.data(Qt.UserRole + 1)
            if trash_rect and trash_rect.contains(event.pos()):
                list_widget = self.parent()
                if hasattr(list_widget, 'delete_item_requested'):
                    list_widget.delete_item_requested.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


class DeleteSignalList(QListWidget):
    delete_item_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        p = self.parent()
        while p:
            if isinstance(p, BarcodeEditorPage):
                p.sync_z_order_from_list()
                p.update_component_list()
                break
            p = p.parent()


import json as _json

# --- Main Page ---

class BarcodeEditorPage(QWidget):
    # Emitted by Save button — carries the full serialised design payload
    design_saved = Signal(dict)

    def __init__(self):
        super().__init__()
        self._canvas_w = 600
        self._canvas_h = 400
        self._design_code = ""
        self._design_name = ""
        self.init_ui()

    # ------------------------------------------------------------------
    # Public API — called by BarcodeListPage
    # ------------------------------------------------------------------

    def reset_for_new(self, form_data: dict | None = None):
        """Clear the canvas and reset the editor for a brand-new design."""
        self.scene.clearSelection()
        for item in list(self.scene.items()):
            self.scene.removeItem(item)
        self.component_list.clear()
        self.comp_count_badge.setText("0")
        self.prop_name_input.setText("")
        self.prop_name_input.setEnabled(False)
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if form_data:
            w = int(form_data.get("w_px") or 600)
            h = int(form_data.get("h_px") or 400)
            self._design_code = form_data.get("pk", "")
            self._design_name = form_data.get("name", "")
        else:
            w, h = 600, 400
            self._design_code = ""
            self._design_name = ""

        self._canvas_w, self._canvas_h = w, h
        self.scene.setSceneRect(QRectF(0, 0, w, h))
        self._update_design_subtitle()

    def load_design(self, row_data: tuple, row_dict: dict | None):
        """Load an existing design from the DB record into the editor."""
        self.reset_for_new()

        if row_dict:
            w = row_dict.get("w_px") or self._canvas_w
            h = row_dict.get("h_px") or self._canvas_h
            try:
                w, h = int(w), int(h)
                self._canvas_w, self._canvas_h = w, h
                self.scene.setSceneRect(QRectF(0, 0, w, h))
            except (TypeError, ValueError):
                pass

            self._design_code = str(row_dict.get("pk", ""))
            self._design_name = str(row_dict.get("name", ""))

            usrm = row_dict.get("usrm") or row_dict.get("bsusrm") or ""
            if usrm:
                try:
                    self.deserialize_canvas(_json.loads(usrm))
                except Exception as e:
                    print(f"[load_design] Could not deserialize canvas: {e}")

            itrm = row_dict.get("itrm") or row_dict.get("bsitrm") or ""
            if itrm:
                try:
                    meta = _json.loads(itrm)
                    cw = int(meta.get("canvas_w", w))
                    ch = int(meta.get("canvas_h", h))
                    if cw != w or ch != h:
                        self._canvas_w, self._canvas_h = cw, ch
                        self.scene.setSceneRect(QRectF(0, 0, cw, ch))
                except Exception as e:
                    print(f"[load_design] Could not read itrm meta: {e}")
        else:
            self._design_code = str(row_data[0]) if row_data else ""
            self._design_name = str(row_data[1]) if row_data and len(row_data) > 1 else ""

        self._update_design_subtitle()

    # ------------------------------------------------------------------
    # Serialise / deserialise canvas
    # ------------------------------------------------------------------

    def serialize_canvas(self) -> list[dict]:
        elements = []
        for item in self.scene.items():
            if item.group():
                continue
            d = self._serialize_item(item)
            if d:
                elements.append(d)
        return elements

    def _serialize_item(self, item) -> dict | None:
        base = {
            "x":        round(item.pos().x(), 2),
            "y":        round(item.pos().y(), 2),
            "z":        item.zValue(),
            "visible":  item.isVisible(),
            "rotation": item.rotation(),
            "name":     getattr(item, "component_name", ""),
        }

        if isinstance(item, BarcodeItem):
            base.update({
                "type":             "barcode",
                "design":           item.design,
                "container_width":  item.container_width,
                "container_height": item.container_height,
            })
            return base

        if isinstance(item, QGraphicsTextItem):
            font = item.font()
            base.update({
                "type":        "text",
                "text":        item.toPlainText(),
                "font_size":   font.pointSize(),
                "font_family": font.family(),
                "bold":        font.bold(),
                "italic":      font.italic(),
            })
            return base

        if isinstance(item, QGraphicsLineItem):
            line = item.line()
            pen  = item.pen()
            base.update({
                "type":      "line",
                "x2":        round(line.x2(), 2),
                "y2":        round(line.y2(), 2),
                "thickness": pen.width(),
            })
            return base

        if isinstance(item, QGraphicsRectItem):
            rect = item.rect()
            pen  = item.pen()
            base.update({
                "type":         "rect",
                "width":        round(rect.width(),  2),
                "height":       round(rect.height(), 2),
                "border_width": pen.width(),
            })
            return base

        return None

    def deserialize_canvas(self, elements: list[dict]):
        flags = (
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

        for d in elements:
            kind = d.get("type")
            item = None

            if kind == "text":
                item = QGraphicsTextItem(d.get("text", ""))
                font = QFont(d.get("font_family", "Arial"), d.get("font_size", 10))
                font.setBold(d.get("bold", False))
                font.setItalic(d.get("italic", False))
                item.setFont(font)
                item.component_name = d.get("name", "Text")
                setup_item_logic(item, self.update_pos_label)
                item.setFlags(flags)

            elif kind == "line":
                item = QGraphicsLineItem(0, 0, d.get("x2", 100), d.get("y2", 0))
                pen = QPen(Qt.black, d.get("thickness", 2))
                item.setPen(pen)
                item.component_name = d.get("name", "Line")
                setup_item_logic(item, self.update_pos_label)
                item.setFlags(flags)

            elif kind == "rect":
                item = QGraphicsRectItem(0, 0, d.get("width", 100), d.get("height", 50))
                pen = QPen(Qt.black, d.get("border_width", 2))
                item.setPen(pen)
                item.component_name = d.get("name", "Rectangle")
                setup_item_logic(item, self.update_pos_label)
                item.setFlags(flags)

            elif kind == "barcode":
                item = BarcodeItem(
                    self.update_pos_label,
                    design=d.get("design", "CODE128"),
                )
                item.container_width  = d.get("container_width",  160)
                item.container_height = d.get("container_height", 80)
                item.component_name   = d.get("name", "Barcode")
                item.bg.setRect(0, 0, item.container_width, item.container_height)

            if item is None:
                continue

            item.setPos(d.get("x", 0), d.get("y", 0))
            item.setZValue(d.get("z", 0))
            item.setVisible(d.get("visible", True))
            item.setRotation(d.get("rotation", 0))
            self.scene.addItem(item)

            display_name = self.get_component_display_name(item)
            li = QListWidgetItem(display_name)
            li.graphics_item = item
            self.component_list.addItem(li)

        self.comp_count_badge.setText(str(self.component_list.count()))
        self.sync_z_order_from_list()

    def get_design_payload(self) -> dict:
        elements = self.serialize_canvas()
        canvas_meta = {
            "canvas_w": self._canvas_w,
            "canvas_h": self._canvas_h,
        }
        return {
            "usrm": _json.dumps(elements,    separators=(",", ":")),
            "itrm": _json.dumps(canvas_meta, separators=(",", ":")),
        }

    def _update_design_subtitle(self):
        code = getattr(self, "_design_code", "")
        name = getattr(self, "_design_name", "")
        if code or name:
            text = f"{code}  ·  {name}" if (code and name) else (code or name)
        else:
            text = "New Design"
        self._subtitle_lbl.setText(text)

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------
    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)

        # ── Header ────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        self.back_btn = StandardButton(
            "Back to List",
            icon_name="fa5s.arrow-left",
            variant="secondary"
        )
        self.back_btn.setToolTip("Return to Barcode Design list")
        header_layout.addWidget(self.back_btn)
        header_layout.addSpacing(16)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)

        title_lbl = QLabel("Barcode Editor")
        title_lbl.setStyleSheet(
            "font-size: 22px; font-weight: 700; color: #111827; background: transparent;"
        )
        title_col.addWidget(title_lbl)

        self._subtitle_lbl = QLabel("New Design")
        self._subtitle_lbl.setStyleSheet(
            "font-size: 11px; color: #6366F1; font-weight: 600; background: transparent;"
        )
        title_col.addWidget(self._subtitle_lbl)

        header_layout.addLayout(title_col)
        header_layout.addStretch()
        self.main_layout.addWidget(header)
        self.main_layout.addSpacing(12)

        # ── Toolbar ───────────────────────────────────────────────────
        self.btn_add_text = StandardButton("Text",    icon_name="fa5s.font",    variant="secondary")
        self.btn_add_rect = StandardButton("Rect",    icon_name="fa5s.square",  variant="secondary")
        self.btn_add_line = StandardButton("Line",    icon_name="fa5s.minus",   variant="secondary")
        self.btn_add_code = StandardButton("Barcode", icon_name="fa5s.barcode", variant="secondary")
        self.save_btn     = StandardButton("Save Design", icon_name="fa5s.save", variant="primary")

        editor_toolbar = QHBoxLayout()
        editor_toolbar.setSpacing(6)
        editor_toolbar.addWidget(self.btn_add_text)
        editor_toolbar.addWidget(self.btn_add_rect)
        editor_toolbar.addWidget(self.btn_add_line)
        editor_toolbar.addWidget(self.btn_add_code)
        editor_toolbar.addStretch()
        editor_toolbar.addWidget(self.save_btn)
        self.main_layout.addLayout(editor_toolbar)
        self.main_layout.addSpacing(18)

        # ── Workspace ─────────────────────────────────────────────────
        workspace_layout = QHBoxLayout()
        self.scene = GridGraphicsScene(
            QRectF(0, 0, self._canvas_w, self._canvas_h),
            grid_size=20,
            color=QColor("#E2E8F0"),
        )
        self.scene.setBackgroundBrush(QBrush(QColor(COLORS["canvas_bg"])))

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet(
            "background: #E8EDF3; border: 1px solid #CBD5E1; border-radius: 8px;"
        )
        self.view.setAlignment(Qt.AlignCenter)
        workspace_layout.addWidget(self.view, stretch=3)

        # ── Sidebar ───────────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setStyleSheet(
            f"QFrame {{ background: {COLORS['white']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
        )
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        comp_header = QWidget()
        comp_header.setStyleSheet("background: transparent; border: none;")
        comp_header_layout = QHBoxLayout(comp_header)
        comp_header_layout.setContentsMargins(2, 4, 2, 4)

        comp_icon = QLabel()
        comp_icon.setPixmap(qta.icon("fa5s.layer-group", color="#6366F1").pixmap(13, 13))
        comp_header_layout.addWidget(comp_icon)

        components_label = QLabel("COMPONENTS")
        components_label.setStyleSheet(
            "font-weight: 800; font-size: 9pt; color: #1E293B; letter-spacing: 1px;"
        )
        comp_header_layout.addWidget(components_label)
        comp_header_layout.addStretch()

        self.comp_count_badge = QLabel("0")
        self.comp_count_badge.setAlignment(Qt.AlignCenter)
        self.comp_count_badge.setFixedSize(20, 20)
        self.comp_count_badge.setStyleSheet(
            "background: #6366F1; color: white; border-radius: 10px; font-weight: 700;"
        )
        comp_header_layout.addWidget(self.comp_count_badge)
        sidebar_layout.addWidget(comp_header)

        self.component_list = DeleteSignalList()
        self.component_list.setSpacing(2)
        self.component_list.setMouseTracking(True)
        self.component_list.viewport().setMouseTracking(True)
        self.component_list.setSelectionMode(QListWidget.SingleSelection)
        self.component_list.setFocusPolicy(Qt.NoFocus)
        self.component_list.setStyleSheet("""
            QListWidget { border: none; background: transparent; outline: none; }
            QScrollBar:vertical { border: none; background: transparent; width: 8px; margin: 0px; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #94A3B8; }
            QScrollBar::handle:vertical:pressed { background: #6366F1; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)
        self.component_list.setItemDelegate(ComponentItemDelegate(self.component_list))
        self.component_list.delete_item_requested.connect(self.delete_component)
        self.component_list.itemClicked.connect(self.sync_selection_from_list)
        sidebar_layout.addWidget(self.component_list, stretch=2)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {COLORS['border']}; min-height: 1px;")
        sidebar_layout.addWidget(divider)

        prop_header = QWidget()
        prop_header.setStyleSheet("QWidget { background: #F8FAFC; border-radius: 6px; padding: 2px 0px; }")
        prop_header_layout = QHBoxLayout(prop_header)
        prop_header_layout.setContentsMargins(8, 6, 8, 6)
        prop_header_layout.setSpacing(4)

        prop_icon = QLabel()
        prop_icon.setPixmap(qta.icon("fa5s.sliders-h", color="#6366F1").pixmap(14, 14))
        prop_header_layout.addWidget(prop_icon)

        prop_static_label = QLabel("PROPERTIES")
        prop_static_label.setStyleSheet("""
            font-weight: 700; font-size: 9pt; color: #64748B;
            letter-spacing: 0.5px; background: transparent; padding: 0px;
        """)
        prop_header_layout.addWidget(prop_static_label)

        separator = QLabel("—")
        separator.setStyleSheet("color: #CBD5E1; font-weight: 400; background: transparent; padding: 0px 2px;")
        prop_header_layout.addWidget(separator)

        self.prop_name_input = QLineEdit("")
        self.prop_name_input.setPlaceholderText("select component")
        self.prop_name_input.setFixedHeight(24)
        self.prop_name_input.setStyleSheet("""
            QLineEdit {
                font-weight: 700; font-size: 9pt; color: #1E293B;
                letter-spacing: 0.3px; background: white;
                border: 1px solid #E2E8F0; border-radius: 4px; padding: 2px 8px;
            }
            QLineEdit:focus { border: 1.5px solid #6366F1; background: white; }
            QLineEdit:disabled { background: #F1F5F9; color: #94A3B8; border: 1px solid #E2E8F0; }
        """)
        self.prop_name_input.textChanged.connect(self.update_current_component_name)
        prop_header_layout.addWidget(self.prop_name_input, stretch=1)
        sidebar_layout.addWidget(prop_header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setStyleSheet(f"background: {COLORS['prop_bg']}; border-radius: 8px;")
        self.apply_modern_scrollbar(self.scroll_area)

        self.inspector_widget = QWidget()
        self.inspector_layout = QVBoxLayout(self.inspector_widget)
        self.inspector_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.inspector_widget)
        sidebar_layout.addWidget(self.scroll_area, stretch=3)

        workspace_layout.addWidget(self.sidebar, stretch=1)
        self.main_layout.addLayout(workspace_layout)

        # ── Wire buttons ──────────────────────────────────────────────
        self.btn_add_text.clicked.connect(lambda: self.add_element("text"))
        self.btn_add_rect.clicked.connect(lambda: self.add_element("rect"))
        self.btn_add_line.clicked.connect(lambda: self.add_element("line"))
        self.btn_add_code.clicked.connect(lambda: self.add_element("barcode"))
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def _on_save_clicked(self):
        payload = self.get_design_payload()
        payload["pk"]   = self._design_code
        payload["name"] = self._design_name
        self.design_saved.emit(payload)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def apply_modern_scrollbar(self, scroll_area):
        scroll_area.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 4px; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #6366F1; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
        """)

    def sync_z_order_from_list(self):
        count = self.component_list.count()
        for i in range(count):
            list_item = self.component_list.item(i)
            graphics_item = getattr(list_item, 'graphics_item', None)
            if graphics_item:
                graphics_item.setZValue(count - i)

    def delete_component(self, row):
        list_item = self.component_list.item(row)
        if not list_item:
            return

        graphics_item = getattr(list_item, 'graphics_item', None)
        self.scene.blockSignals(True)
        self.component_list.blockSignals(True)

        if graphics_item and graphics_item.scene() == self.scene:
            self.scene.removeItem(graphics_item)

        self.component_list.takeItem(row)
        self.scene.blockSignals(False)
        self.component_list.blockSignals(False)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.on_selection_changed()

    def get_component_display_name(self, item):
        component_name = getattr(item, 'component_name', '')

        if isinstance(item, BarcodeItem):
            comp_type  = "Barcode"
            comp_value = getattr(item, 'design', 'CODE128')
            if not component_name:
                component_name = "Barcode"
        elif isinstance(item, QGraphicsTextItem):
            comp_type  = "Text"
            text_val   = item.toPlainText()[:20]
            comp_value = text_val if text_val else "Empty"
            if not component_name:
                component_name = "Text"
        elif isinstance(item, QGraphicsLineItem):
            comp_type  = "Line"
            comp_value = f"{int(item.line().length())}px"
            if not component_name:
                component_name = "Line"
        elif isinstance(item, QGraphicsRectItem):
            comp_type  = "Rectangle"
            rect       = item.rect()
            comp_value = f"{int(rect.width())}x{int(rect.height())}"
            if not component_name:
                component_name = "Rectangle"
        else:
            comp_type  = "Item"
            comp_value = ""
            if not component_name:
                component_name = "Item"

        return f"{comp_type} - {component_name}: {comp_value}"

    def update_component_list(self):
        self.component_list.blockSignals(True)

        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            graphics_item = getattr(li, 'graphics_item', None)
            if graphics_item:
                li.setText(self.get_component_display_name(graphics_item))

        existing_items_in_list = []
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            gi = getattr(li, 'graphics_item', None)
            if gi:
                existing_items_in_list.append(gi)

        items_to_add = []
        for item in self.scene.items():
            if item.group() or item.scene() != self.scene:
                continue
            if item not in existing_items_in_list:
                name = self.get_component_display_name(item)
                li = QListWidgetItem(name)
                li.graphics_item = item
                self.component_list.insertItem(0, li)
                items_to_add.append(li)

        if items_to_add:
            self.component_list.scrollToTop()
            selected_scene_items = self.scene.selectedItems()
            if selected_scene_items:
                for i in range(self.component_list.count()):
                    list_item = self.component_list.item(i)
                    if getattr(list_item, 'graphics_item', None) == selected_scene_items[0]:
                        self.component_list.setCurrentItem(list_item)
                        break

        self.comp_count_badge.setText(str(self.component_list.count()))
        self.component_list.blockSignals(False)

    def update_current_component_name(self, name):
        selected_items = self.scene.selectedItems()
        if selected_items:
            selected_items[0].component_name = name if name else "Unnamed"
            self.update_component_list()

    def sync_selection_from_list(self, li):
        item = getattr(li, 'graphics_item', None)
        if item:
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            item.setSelected(True)
            self.scene.blockSignals(False)
            self.on_selection_changed()

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()

        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not selected_items:
            self.component_list.clearSelection()
            self.prop_name_input.setText("")
            self.prop_name_input.setPlaceholderText("select component")
            self.prop_name_input.setEnabled(False)
            return

        selected = selected_items[0]

        current_name = getattr(selected, 'component_name', '')
        self.prop_name_input.blockSignals(True)
        if current_name:
            self.prop_name_input.setText(current_name)
        else:
            if isinstance(selected, BarcodeItem):
                default_name = "Barcode"
            elif isinstance(selected, QGraphicsTextItem):
                default_name = "Text"
            elif isinstance(selected, QGraphicsLineItem):
                default_name = "Line"
            elif isinstance(selected, QGraphicsRectItem):
                default_name = "Rectangle"
            else:
                default_name = "Item"
            self.prop_name_input.setText(default_name)
        self.prop_name_input.setEnabled(True)
        self.prop_name_input.blockSignals(False)

        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == selected:
                self.component_list.setCurrentItem(li)
                break
        self.component_list.blockSignals(False)

        self.current_editor = None
        if isinstance(selected, QGraphicsTextItem):
            self.current_editor = TextPropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsLineItem):
            self.current_editor = LinePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsRectItem):
            self.current_editor = RectanglePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, BarcodeItem):
            self.current_editor = BarcodePropertyEditor(selected, self.update_component_list)

        if self.current_editor:
            self.inspector_layout.addWidget(self.current_editor)

    def add_element(self, kind):
        self.scene.clearSelection()
        flags = (
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

        if kind == "text":
            item = QGraphicsTextItem("LABEL_VAR")
            item.setFont(QFont("Arial", 10))
            item.component_name = "Text"
            setup_item_logic(item, self.update_pos_label)
        elif kind == "rect":
            item = QGraphicsRectItem(0, 0, 100, 50)
            item.setPen(QPen(Qt.black, 2))
            item.component_name = "Rectangle"
            setup_item_logic(item, self.update_pos_label)
        elif kind == "line":
            item = QGraphicsLineItem(0, 0, 100, 0)
            item.setPen(QPen(Qt.black, 2))
            item.component_name = "Line"
            setup_item_logic(item, self.update_pos_label)
        elif kind == "barcode":
            item = BarcodeItem(self.update_pos_label)

        if not isinstance(item, BarcodeItem):
            item.setFlags(flags)
        self.scene.addItem(item)

        name = self.get_component_display_name(item)
        li = QListWidgetItem(name)
        li.graphics_item = item
        self.component_list.insertItem(0, li)
        self.comp_count_badge.setText(str(self.component_list.count()))

        item.setSelected(True)
        item.setPos(50, 50)
        self.sync_z_order_from_list()

    def update_pos_label(self, pos):
        editor = getattr(self, "current_editor", None)
        if not editor:
            return
        if not shiboken6.isValid(editor):
            self.current_editor = None
            return
        if hasattr(editor, "update_position_fields"):
            editor.update_position_fields(pos)