"""Property editors for Line, Rectangle, and Barcode scene items."""

from PySide6.QtWidgets import QWidget, QFormLayout, QLabel, QSizePolicy
from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QFont, QBrush

from components.barcode_editor.utils import COLORS, make_spin, make_chevron_combo, MODERN_INPUT_STYLE
from components.barcode_editor.scene_items import BarcodeItem

LABEL_W = 70


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


class BarcodePropertyEditor(QWidget):
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

        self.design_combo = make_chevron_combo(["CODE128", "MINIMAL", "EAN13", "CODE39", "QR MOCK"])
        self.design_combo.setCurrentText(self.item.design)
        self.design_combo.currentTextChanged.connect(self.update_design)
        layout.addRow(_lbl("DESIGN :"), self.design_combo)

        self.width_spin  = make_spin(20, 1000, self.item.container_width)
        self.height_spin = make_spin(20, 1000, self.item.container_height)
        self.width_spin.valueChanged.connect(self.update_size)
        self.height_spin.valueChanged.connect(self.update_size)
        layout.addRow(_lbl("WIDTH :"),  self.width_spin)
        layout.addRow(_lbl("HEIGHT :"), self.height_spin)

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

    def update_design(self, new_design: str):
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsTextItem
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
            sq = QGraphicsRectItem(40, 15, 50, 50)
            sq.setBrush(QBrush(Qt.black))
            sq.setPen(Qt.NoPen)
            self.item.addToGroup(sq)
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

        lbl_item = QGraphicsTextItem("*12345678*")
        lbl_item.setFont(QFont("Courier", 9, QFont.Bold))
        lbl_item.setPos(35, 58)
        self.item.addToGroup(lbl_item)

        self.item.setPos(old_scene_pos)
        self.update_callback()

    def update_size(self):
        self.item.container_width  = self.width_spin.value()
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

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        self.update_callback()