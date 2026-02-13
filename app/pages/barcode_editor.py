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

# Shared modern combo style — removes native arrow entirely; chevron injected via qtawesome label
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

# Shared input style — SpinBox native arrows hidden (ChevronSpinBox paints them manually)
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
    """
    QSpinBox that paints qtawesome chevron-up / chevron-down icons
    directly into the up/down button regions — reliable cross-platform rendering.
    """
    _BTN_W = 20  # must match stylesheet width above

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

        # Up chevron — vertically centred in top half
        painter.drawPixmap(cx, (h // 2 - icon_h) // 2, self._px_up)
        # Down chevron — vertically centred in bottom half
        painter.drawPixmap(cx, h // 2 + (h // 2 - icon_h) // 2, self._px_down)
        painter.end()


def make_spin(min_val: int = 0, max_val: int = 5000, value: int = 0) -> ChevronSpinBox:
    """Convenience factory: ChevronSpinBox with consistent range + style."""
    spin = ChevronSpinBox()
    spin.setRange(min_val, max_val)
    spin.setValue(value)
    spin.setStyleSheet(MODERN_INPUT_STYLE)
    return spin


def make_chevron_combo(items: list[str], style: str = MODERN_INPUT_STYLE) -> QComboBox:
    """
    Factory that returns a QComboBox with a qtawesome chevron-down icon
    anchored to the far-right inside the widget, matching StandardSearchBar.
    """
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

    # critical fix for groups
    rect = item.sceneBoundingRect()

    width = rect.width()
    height = rect.height()

    x = max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - width))
    y = max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - height))

    return QPointF(x, y)


def setup_item_logic(item, on_move_callback):
    """Patches itemChange to enforce boundaries and update position UI."""
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
    """Refined editor with clear input boxes and modern styling."""
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

        # Fields — all combos use the qtawesome chevron factory
        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        layout.addRow(create_label("ALIGNMENT :"), self.align_combo)

        self.font_combo = make_chevron_combo(["STANDARD", "MONOSPACE", "SERIF"])
        layout.addRow(create_label("FONT NAME :"), self.font_combo)

        self.size_spin = make_spin(1, 100, int(self.item.font().pointSize()))
        self.size_spin.valueChanged.connect(self.apply_font_changes)
        layout.addRow(create_label("FONT SIZE :"), self.size_spin)

        self.top_spin  = make_spin(0, 1000, int(self.item.pos().y()))
        self.left_spin = make_spin(0, 1000, int(self.item.pos().x()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(create_label("TOP :"), self.top_spin)
        layout.addRow(create_label("LEFT :"), self.left_spin)

        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}
        self.angle_combo.currentTextChanged.connect(
            lambda v: self.item.setRotation(angle_map.get(v, 0))
        )
        layout.addRow(create_label("ANGLE :"), self.angle_combo)

        self.type_combo = make_chevron_combo(["FIX", "VAR"])
        layout.addRow(create_label("TYPE :"), self.type_combo)

        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(create_label("TEXT :"), self.text_input)

        self.caption_input = QLineEdit("LABEL 1")
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        layout.addRow(create_label("CAPTION :"), self.caption_input)

        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(create_label("VISIBLE :"), self.visible_combo)

        self.mandatory_combo = make_chevron_combo(["FALSE", "TRUE"])
        layout.addRow(create_label("MANDATORY :"), self.mandatory_combo)

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

        # ✅ Thickness (pen width)
        self.thickness_spin = make_spin(1, 100, int(pen.width()))
        self.thickness_spin.valueChanged.connect(self.update_thickness)
        layout.addRow(create_label("THICKNESS :"), self.thickness_spin)

        # ✅ Line Length (X direction)
        self.width_spin = make_spin(0, 5000, int(abs(line.dx())))
        self.width_spin.valueChanged.connect(self.update_geometry)
        layout.addRow(create_label("WIDTH :"), self.width_spin)

        # Position
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
        layout.setContentsMargins(10,10,10,10)
        layout.setSpacing(10)

        label_style = f"color:{COLORS['legacy_blue']}; font-size:9px; text-transform:uppercase;"

        def label(t):
            l = QLabel(t)
            l.setStyleSheet(label_style)
            return l

        # DESIGN - NEW FIELD
        self.design_combo = make_chevron_combo(["CODE128", "MINIMAL", "EAN13", "CODE39", "QR MOCK"])
        self.design_combo.setCurrentText(self.item.design)
        self.design_combo.currentTextChanged.connect(self.update_design)
        layout.addRow(label("DESIGN :"), self.design_combo)

        # WIDTH
        self.width_spin = make_spin(20, 1000, self.item.container_width)
        self.width_spin.valueChanged.connect(self.update_size)
        layout.addRow(label("WIDTH :"), self.width_spin)

        # HEIGHT
        self.height_spin = make_spin(20, 1000, self.item.container_height)
        self.height_spin.valueChanged.connect(self.update_size)
        layout.addRow(label("HEIGHT :"), self.height_spin)

        # TOP
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(label("TOP :"), self.top_spin)

        # LEFT
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(label("LEFT :"), self.left_spin)

        # VISIBLE
        self.visible_combo = make_chevron_combo(["TRUE","FALSE"])
        self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v=="TRUE"))
        layout.addRow(label("VISIBLE :"), self.visible_combo)

    def update_design(self, new_design):
        print("\n--- DEBUG: update_design called ---")
        print(f"Requested design: {new_design}")
        print(f"Before rebuild: scenePos={self.item.scenePos()}, pos={self.item.pos()}, boundingRect={self.item.boundingRect()}")

        old_scene_pos = self.item.scenePos()

        # Clear children
        for child in self.item.childItems():
            self.item.removeFromGroup(child)
            if child.scene():
                child.scene().removeItem(child)

        self.item.design = new_design

        # Background
        self.item.bg = QGraphicsRectItem(0, 0, self.item.container_width, self.item.container_height)
        self.item.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine))
        self.item.bg.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.item.addToGroup(self.item.bg)

        # Pattern
        if new_design == "MINIMAL":
            bar_pattern = [4,2,4,2,4,2,4]
        elif new_design == "EAN13":
            bar_pattern = [2,2,3,2,2,4,3,2,3,2,2]
        elif new_design == "CODE39":
            bar_pattern = [3,1,3,1,2,1,3,1,2,1,3]
        elif new_design == "QR MOCK":
            square = QGraphicsRectItem(40,15,50,50)
            square.setBrush(QBrush(Qt.black))
            square.setPen(Qt.NoPen)
            self.item.addToGroup(square)
            bar_pattern = []
        else:
            bar_pattern = [3,2,3,2,2,3,2,3,3,2,2,3,2,3,2,2,3,2,3]

        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.item.addToGroup(bar)
            x_offset += width

        label = QGraphicsTextItem("*12345678*")
        label.setFont(QFont("Courier", 9, QFont.Bold))
        label.setPos(35, 58)
        self.item.addToGroup(label)

        # Normalize children so boundingRect starts at (0,0)
        new_rect = self.item.childrenBoundingRect()
        dx, dy = new_rect.topLeft().x(), new_rect.topLeft().y()
        if dx != 0 or dy != 0:
            for child in self.item.childItems():
                child.setPos(child.pos() - QPointF(dx, dy))

        # Restore scene position
        self.item.setPos(old_scene_pos)

        print(f"After rebuild: scenePos={self.item.scenePos()}, pos={self.item.pos()}, boundingRect={self.item.boundingRect()}")
        print("--- DEBUG END ---\n")

        self.update_callback()

    def update_size(self):
        self.item.container_width = self.width_spin.value()
        self.item.container_height = self.height_spin.value()

        self.item.bg.setRect(
            0,
            0,
            self.item.container_width,
            self.item.container_height
        )

        self.update_callback()

    def update_position_fields(self,pos):
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
        self.component_name = "Barcode"  # Default name
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

        # Choose pattern based on design
        if design == "MINIMAL":
            bar_pattern = [4,2,4,2,4,2,4]

        elif design == "EAN13":
            bar_pattern = [2,2,3,2,2,4,3,2,3,2,2]

        elif design == "CODE39":
            bar_pattern = [3,1,3,1,2,1,3,1,2,1,3]

        elif design == "QR MOCK":
            square = QGraphicsRectItem(40,15,50,50)
            square.setBrush(QBrush(Qt.black))
            square.setPen(Qt.NoPen)
            self.addToGroup(square)
            bar_pattern = []

        else:  # CODE128 default
            bar_pattern = [3,2,3,2,2,3,2,3,3,2,2,3,2,3,2,2,3,2,3]

        x_offset = 15

        for i,width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset,15,width,45)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.addToGroup(bar)
            x_offset += width

        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.addToGroup(bar)
            x_offset += width
        
        label = QGraphicsTextItem("*12345678*")
        label.setFont(QFont("Courier", 9, QFont.Bold))
        label.setPos(35, 58)
        self.addToGroup(label)

    def boundingRect(self):
        return self.childrenBoundingRect().adjusted(-2, -2, 2, 2)


    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            constrained_pos = keep_within_bounds(self, value)
            if self.move_callback: self.move_callback(constrained_pos)
            return constrained_pos
        return super().itemChange(change, value)

class GridGraphicsScene(QGraphicsScene):
    def __init__(self, rect, grid_size=20, color=QColor("#E2E8F0"), parent=None):
        super().__init__(rect, parent)
        self.grid_size = grid_size
        self.grid_color = color

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        painter.setPen(QPen(self.grid_color, 1))  # subtle thin line

        left = int(rect.left()) - (int(rect.left()) % self.grid_size)
        top = int(rect.top()) - (int(rect.top()) % self.grid_size)

        lines = []

        x = left
        while x < rect.right():
            lines.append((QPointF(x, rect.top()), QPointF(x, rect.bottom())))
            x += self.grid_size

        y = top
        while y < rect.bottom():
            lines.append((QPointF(rect.left(), y), QPointF(rect.right(), y)))
            y += self.grid_size

        for p1, p2 in lines:
            painter.drawLine(p1, p2)


# --- Component List Delegate ---

# Type metadata: (icon_name, badge_color, badge_text_color, label_color)
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

        # Use ONLY QStyle.State_Selected — never rely on hover highlight for selection
        selected = bool(option.state & QStyle.State_Selected)
        hovered  = bool(option.state & QStyle.State_MouseOver) and not selected

        r = option.rect.adjusted(4, 2, -4, -2)

        # Background
        if selected:
            bg = QColor("#EEF2FF")
        elif hovered:
            bg = QColor("#F8FAFC")
        else:
            bg = QColor("#FFFFFF")

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(r, 6, 6)

        # Left accent bar
        accent_rect = QRect(r.left(), r.top() + 6, self.ACCENT_W, r.height() - 12)
        painter.setBrush(QBrush(QColor(accent)))
        painter.drawRoundedRect(accent_rect, 2, 2)

        # Icon chip
        chip_x = r.left() + self.ACCENT_W + self.PAD
        chip_y = r.top() + (r.height() - self.CHIP_SIZE) // 2
        chip_r = QRect(chip_x, chip_y, self.CHIP_SIZE, self.CHIP_SIZE)

        chip_bg = QColor(badge_bg)
        chip_bg.setAlpha(40 if not selected else 60)
        painter.setBrush(QBrush(chip_bg))
        painter.drawRoundedRect(chip_r, 5, 5)

        px = qta.icon(icon_name, color=badge_bg).pixmap(13, 13)
        painter.drawPixmap(chip_x + (self.CHIP_SIZE - 13) // 2, chip_y + (self.CHIP_SIZE - 13) // 2, px)

        # Trash bin icon on the right
        trash_x = r.right() - self.TRASH_SIZE - self.PAD
        trash_y = r.top() + (r.height() - self.TRASH_SIZE) // 2
        trash_r = QRect(trash_x, trash_y, self.TRASH_SIZE, self.TRASH_SIZE)
        
        # Store trash rect for click detection
        index.model().setData(index, trash_r, Qt.UserRole + 1)
        
        # Trash icon with subtle background
        if hovered or selected:
            trash_bg = QColor("#FEE2E2")
            painter.setBrush(QBrush(trash_bg))
            painter.drawRoundedRect(trash_r, 4, 4)
        
        trash_px = qta.icon("fa5s.trash-alt", color="#EF4444" if (hovered or selected) else "#CBD5E1").pixmap(11, 11)
        painter.drawPixmap(trash_x + (self.TRASH_SIZE - 11) // 2, trash_y + (self.TRASH_SIZE - 11) // 2, trash_px)

        # Text area (adjusted to leave space for trash icon)
        text_x = chip_x + self.CHIP_SIZE + self.PAD
        text_w = trash_x - text_x - self.PAD

        # Parse the name format: "Type - VarName: Value"
        display_type = name
        display_value = ''
        
        if ': ' in name:
            # Split by ': ' to separate "Type - VarName" from "Value"
            parts = name.split(': ', 1)
            display_type = parts[0].strip()  # "Type - VarName"
            display_value = parts[1].strip()  # "Value"
        
        # Type and VarName are shown together on top line in bold
        type_font = QFont()
        type_font.setPointSize(9)
        type_font.setWeight(QFont.DemiBold)
        painter.setFont(type_font)
        painter.setPen(QColor('#1E293B') if selected else QColor('#334155'))

        if display_value:
            # Show "Type - VarName" on top
            type_rect = QRect(text_x, r.top() + 3, text_w, r.height() // 2)
            type_fm = QFontMetrics(type_font)
            elided_type = type_fm.elidedText(display_type, Qt.ElideRight, text_w)
            painter.drawText(type_rect, Qt.AlignLeft | Qt.AlignBottom, elided_type)

            # Show value below in gray
            value_font = QFont()
            value_font.setPointSize(8)
            painter.setFont(value_font)
            painter.setPen(QColor('#94A3B8'))
            
            value_fm = QFontMetrics(value_font)
            elided_value = value_fm.elidedText(display_value, Qt.ElideRight, text_w)
            
            value_rect = QRect(text_x, r.top() + r.height() // 2, text_w, r.height() // 2 - 3)
            painter.drawText(value_rect, Qt.AlignLeft | Qt.AlignTop, elided_value)
        else:
            # Only type, show it centered
            type_fm = QFontMetrics(type_font)
            elided_type = type_fm.elidedText(display_type, Qt.ElideRight, text_w)
            painter.drawText(QRect(text_x, r.top(), text_w, r.height()), Qt.AlignLeft | Qt.AlignVCenter, elided_type)

        # Selection border ring
        if selected:
            painter.setPen(QPen(QColor('#6366F1'), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, 6, 6)

        painter.restore()

    def editorEvent(self, event, model, option, index):
        """Handle click events on the trash icon"""
        if event.type() == QEvent.MouseButtonRelease:
            trash_rect = index.data(Qt.UserRole + 1)
            if trash_rect and trash_rect.contains(event.pos()):
                # Emit a custom signal or call parent's delete method
                # For now, we'll access the parent widget directly
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
        # Corrected: InternalMove handles the reordering logic automatically
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        # Look for the editor page in the parents to sync the Z-index after a move
        p = self.parent()
        while p:
            if isinstance(p, BarcodeEditorPage):
                p.sync_z_order_from_list()
                p.update_component_list()
                break
            p = p.parent()

# --- Main Page ---

class BarcodeEditorPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)

        # Title-only header
        header = QWidget()
        header.setStyleSheet("background: transparent; border: none;")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title_lbl = QLabel("Barcode Editor")
        title_lbl.setStyleSheet(
            "font-size: 24px; font-weight: 700; color: #111827; background: transparent;"
        )
        header_layout.addWidget(title_lbl)
        header_layout.addStretch()
        self.main_layout.addWidget(header)
        self.main_layout.addSpacing(12)

        # Toolbar row
        self.btn_add_text = StandardButton("Text", icon_name="fa5s.font", variant="secondary")
        self.btn_add_rect = StandardButton("Rect", icon_name="fa5s.square", variant="secondary")
        self.btn_add_line = StandardButton("Line", icon_name="fa5s.minus", variant="secondary")
        self.btn_add_code = StandardButton("Barcode", icon_name="fa5s.barcode", variant="secondary")
        self.save_btn = StandardButton("Save Design", icon_name="fa5s.save", variant="primary")

        editor_toolbar = QHBoxLayout()
        editor_toolbar.addWidget(self.btn_add_text)
        editor_toolbar.addWidget(self.btn_add_rect)
        editor_toolbar.addWidget(self.btn_add_line)
        editor_toolbar.addWidget(self.btn_add_code)
        editor_toolbar.addStretch()
        editor_toolbar.addWidget(self.save_btn)
        self.main_layout.addLayout(editor_toolbar)
        self.main_layout.addSpacing(18)

        # Workspace
        workspace_layout = QHBoxLayout()
        self.scene = GridGraphicsScene(QRectF(0, 0, 600, 400), grid_size=20, color=QColor("#E2E8F0"))
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background: white; border: 1px solid #CBD5E1; border-radius: 8px;")
        workspace_layout.addWidget(self.view, stretch=3)

        # Sidebar
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setStyleSheet(f"QFrame {{ background: {COLORS['white']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}")
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        # COMPONENTS section header
        comp_header = QWidget()
        comp_header.setStyleSheet("background: transparent; border: none;")
        comp_header_layout = QHBoxLayout(comp_header)
        comp_header_layout.setContentsMargins(2, 4, 2, 4)
        
        comp_icon = QLabel()
        comp_icon.setPixmap(qta.icon("fa5s.layer-group", color="#6366F1").pixmap(13, 13))
        comp_header_layout.addWidget(comp_icon)

        components_label = QLabel("COMPONENTS")
        components_label.setStyleSheet("font-weight: 800; font-size: 9pt; color: #1E293B; letter-spacing: 1px;")
        comp_header_layout.addWidget(components_label)
        comp_header_layout.addStretch()

        self.comp_count_badge = QLabel("0")
        self.comp_count_badge.setAlignment(Qt.AlignCenter)
        self.comp_count_badge.setFixedSize(20, 20)
        self.comp_count_badge.setStyleSheet("background: #6366F1; color: white; border-radius: 10px; font-weight: 700;")
        comp_header_layout.addWidget(self.comp_count_badge)
        sidebar_layout.addWidget(comp_header)
        
        # Component List Configuration
        self.component_list = DeleteSignalList()
        self.component_list.setSpacing(2)
        self.component_list.setMouseTracking(True)
        self.component_list.viewport().setMouseTracking(True)
        self.component_list.setSelectionMode(QListWidget.SingleSelection)
        self.component_list.setFocusPolicy(Qt.NoFocus)
        self.component_list.setStyleSheet("""
            QListWidget { 
                border: none; 
                background: transparent; 
                outline: none; 
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 8px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 4px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::handle:vertical:pressed {
                background: #6366F1;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.component_list.setItemDelegate(ComponentItemDelegate(self.component_list))
        
        # Signals
        self.component_list.delete_item_requested.connect(self.delete_component)
        self.component_list.itemClicked.connect(self.sync_selection_from_list)

        sidebar_layout.addWidget(self.component_list, stretch=2)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {COLORS['border']}; min-height: 1px;")
        sidebar_layout.addWidget(divider)

        # PROPERTIES section
        prop_header = QWidget()
        prop_header.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border-radius: 6px;
                padding: 2px 0px;
            }
        """)
        prop_header_layout = QHBoxLayout(prop_header)
        prop_header_layout.setContentsMargins(8, 6, 8, 6)
        prop_header_layout.setSpacing(4)
        
        prop_icon = QLabel()
        prop_icon.setPixmap(qta.icon("fa5s.sliders-h", color="#6366F1").pixmap(14, 14))
        prop_header_layout.addWidget(prop_icon)
        
        # Static "PROPERTIES - " label
        prop_static_label = QLabel("PROPERTIES")
        prop_static_label.setStyleSheet("""
            font-weight: 700; 
            font-size: 9pt; 
            color: #64748B; 
            letter-spacing: 0.5px;
            background: transparent;
            padding: 0px;
        """)
        prop_header_layout.addWidget(prop_static_label)
        
        # Separator
        separator = QLabel("—")
        separator.setStyleSheet("""
            color: #CBD5E1;
            font-weight: 400;
            background: transparent;
            padding: 0px 2px;
        """)
        prop_header_layout.addWidget(separator)
        
        # Editable name field (only the component name part)
        self.prop_name_input = QLineEdit("")
        self.prop_name_input.setPlaceholderText("select component")
        self.prop_name_input.setFixedHeight(24)
        self.prop_name_input.setStyleSheet("""
            QLineEdit {
                font-weight: 700; 
                font-size: 9pt; 
                color: #1E293B; 
                letter-spacing: 0.3px;
                background: white;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                padding: 2px 8px;
            }
            QLineEdit:focus {
                border: 1.5px solid #6366F1;
                background: white;
            }
            QLineEdit:disabled {
                background: #F1F5F9;
                color: #94A3B8;
                border: 1px solid #E2E8F0;
            }
        """)
        self.prop_name_input.textChanged.connect(self.update_current_component_name)
        prop_header_layout.addWidget(self.prop_name_input, stretch=1)
        
        sidebar_layout.addWidget(prop_header)

        # Scrollable Property Inspector
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

        # Scene Events
        self.btn_add_text.clicked.connect(lambda: self.add_element("text"))
        self.btn_add_rect.clicked.connect(lambda: self.add_element("rect"))
        self.btn_add_line.clicked.connect(lambda: self.add_element("line"))
        self.btn_add_code.clicked.connect(lambda: self.add_element("barcode"))
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def apply_modern_scrollbar(self, scroll_area):
        """Helper to style scrollbars consistently."""
        scroll_area.verticalScrollBar().setStyleSheet("""
            QScrollBar:vertical { border: none; background: transparent; width: 6px; margin: 4px; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #6366F1; }
            QScrollBar::add-line, QScrollBar::sub-line { height: 0px; }
        """)

    def sync_z_order_from_list(self):
        """Source of Truth: The list order. Top of list = Front of screen."""
        count = self.component_list.count()
        for i in range(count):
            list_item = self.component_list.item(i)
            graphics_item = getattr(list_item, 'graphics_item', None)
            if graphics_item:
                graphics_item.setZValue(count - i)

    def delete_component(self, row):
        list_item = self.component_list.item(row)
        if not list_item: return
        
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
        """Generate display name in format 'Type - VariableName' with value as subtitle"""
        # Get component type and variable name
        component_name = getattr(item, 'component_name', '')
        
        if isinstance(item, BarcodeItem):
            comp_type = "Barcode"
            comp_value = getattr(item, 'design', 'CODE128')
            if not component_name:
                component_name = "Barcode"
        elif isinstance(item, QGraphicsTextItem):
            comp_type = "Text"
            text_val = item.toPlainText()[:20]
            comp_value = text_val if text_val else "Empty"
            if not component_name:
                component_name = "Text"
        elif isinstance(item, QGraphicsLineItem):
            comp_type = "Line"
            comp_value = f"{int(item.line().length())}px"
            if not component_name:
                component_name = "Line"
        elif isinstance(item, QGraphicsRectItem):
            comp_type = "Rectangle"
            rect = item.rect()
            comp_value = f"{int(rect.width())}x{int(rect.height())}"
            if not component_name:
                component_name = "Rectangle"
        else:
            comp_type = "Item"
            comp_value = ""
            if not component_name:
                component_name = "Item"
        
        # Return formatted string: "Type - VarName: Value"
        return f"{comp_type} - {component_name}: {comp_value}"

    def update_component_list(self):
        """Syncs the list with the scene, ensuring new items appear at the top."""
        self.component_list.blockSignals(True)

        # 1. Update existing items' names
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            graphics_item = getattr(li, 'graphics_item', None)
            if graphics_item:
                new_name = self.get_component_display_name(graphics_item)
                li.setText(new_name)

        # 2. Map what is already in our QListWidget to avoid duplicates
        existing_items_in_list = []
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            graphics_item = getattr(li, 'graphics_item', None)
            if graphics_item:
                existing_items_in_list.append(graphics_item)

        # 3. Check the scene for items not yet in the list
        items_to_add = []
        for item in self.scene.items():
            # Skip internal items, background grids, or items already grouped
            if item.group() or item.scene() != self.scene:
                continue
            
            if item not in existing_items_in_list:
                name = self.get_component_display_name(item)
                
                # Create the UI item
                li = QListWidgetItem(name)
                li.graphics_item = item  # Store reference
                self.component_list.insertItem(0, li) # Always at the top
                items_to_add.append(li)

        # 4. If we added something, make sure it is visible and selected
        if items_to_add:
            self.component_list.scrollToTop()
            # If the scene has a selection, make sure the list matches
            selected_scene_items = self.scene.selectedItems()
            if selected_scene_items:
                for i in range(self.component_list.count()):
                    list_item = self.component_list.item(i)
                    if getattr(list_item, 'graphics_item', None) == selected_scene_items[0]:
                        self.component_list.setCurrentItem(list_item)
                        break

        # Update the badge count
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.component_list.blockSignals(False)

    def update_current_component_name(self, name):
        """Update the selected component's name when typing in the properties header"""
        selected_items = self.scene.selectedItems()
        if selected_items:
            selected_items[0].component_name = name if name else "Unnamed"
            # Update the component list to reflect the new name
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
        
        # Clear Inspector
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if not selected_items:
            self.component_list.clearSelection()
            self.prop_name_input.setText("")
            self.prop_name_input.setPlaceholderText("select component")
            self.prop_name_input.setEnabled(False)
            return

        selected = selected_items[0]
        
        # Update properties header with just the component name
        current_name = getattr(selected, 'component_name', '')
        self.prop_name_input.blockSignals(True)
        if current_name:
            self.prop_name_input.setText(current_name)
        else:
            # Get default name based on type
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
        
        # Sync List Selection
        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == selected:
                self.component_list.setCurrentItem(li)
                break
        self.component_list.blockSignals(False)

        # Load Property Editors
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
        flags = (QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        
        if kind == "text":
            item = QGraphicsTextItem("LABEL_VAR")
            item.setFont(QFont("Arial", 10))
            item.component_name = "Text"  # Set default name
            setup_item_logic(item, self.update_pos_label)
        elif kind == "rect":
            item = QGraphicsRectItem(0, 0, 100, 50)
            item.setPen(QPen(Qt.black, 2))
            item.component_name = "Rectangle"  # Set default name
            setup_item_logic(item, self.update_pos_label)
        elif kind == "line":
            item = QGraphicsLineItem(0, 0, 100, 0)
            item.setPen(QPen(Qt.black, 2))
            item.component_name = "Line"  # Set default name
            setup_item_logic(item, self.update_pos_label)
        elif kind == "barcode":
            item = BarcodeItem(self.update_pos_label)
            # BarcodeItem already has component_name in __init__

        if not isinstance(item, BarcodeItem): item.setFlags(flags)
        self.scene.addItem(item)

        # ---- Add directly to component list ----
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

        # 🔥 Check if Qt object still exists
        if not shiboken6.isValid(editor):
            self.current_editor = None
            return

        if hasattr(editor, "update_position_fields"):
            editor.update_position_fields(pos)