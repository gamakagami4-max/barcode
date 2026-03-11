"""Custom QGraphicsItem subclasses used on the barcode design canvas."""

import uuid

from PySide6.QtWidgets import QGraphicsTextItem, QGraphicsLineItem, QGraphicsRectItem, QGraphicsItemGroup, QStyle
from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont

from components.barcode_editor.utils import keep_within_bounds


class SelectableTextItem(QGraphicsTextItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_color = QColor("#000000")
        self.component_id = str(uuid.uuid4())  # stable unique ID, never changes

    def setDefaultTextColor(self, color: QColor):
        # Never let red bleed into _original_color
        if color != QColor("#EF4444"):
            self._original_color = QColor(color)
        super().setDefaultTextColor(color)

    def itemChange(self, change, value):
        if change == QGraphicsTextItem.ItemSelectedChange:
            if value:
                self._original_color = self.defaultTextColor()
                self.setDefaultTextColor(QColor("#EF4444"))
            else:
                self.setDefaultTextColor(self._original_color)
        return super().itemChange(change, value)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        if getattr(self, "design_inverse", False):
            painter.save()
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor("#000000")))
            painter.drawRect(self.boundingRect())
            painter.restore()
            original_color = self.defaultTextColor()
            if not self.isSelected():
                self.setDefaultTextColor(QColor("#FFFFFF"))
            super().paint(painter, option, widget)
            if not self.isSelected():
                self.setDefaultTextColor(original_color)
        else:
            super().paint(painter, option, widget)


class SelectableLineItem(QGraphicsLineItem):
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        if self.isSelected():
            original_pen = self.pen()
            red_pen = QPen(original_pen)
            red_pen.setColor(QColor("#EF4444"))
            self.setPen(red_pen)
            super().paint(painter, option, widget)
            self.setPen(original_pen)
        else:
            super().paint(painter, option, widget)


class SelectableRectItem(QGraphicsRectItem):
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        if self.isSelected():
            original_pen = self.pen()
            red_pen = QPen(original_pen)
            red_pen.setColor(QColor("#EF4444"))
            self.setPen(red_pen)
            super().paint(painter, option, widget)
            self.setPen(original_pen)
        else:
            super().paint(painter, option, widget)


class BarcodeItem(QGraphicsItemGroup):
    def __init__(self, move_callback, design="CODE128"):
        super().__init__()
        self.move_callback = move_callback
        self.component_name = "Barcode"
        self.setFlags(
            QGraphicsItemGroup.ItemIsMovable
            | QGraphicsItemGroup.ItemIsSelectable
            | QGraphicsItemGroup.ItemSendsGeometryChanges
        )
        self.container_width = 160
        self.container_height = 80
        self.design = design
        self.bg = QGraphicsRectItem(0, 0, self.container_width, self.container_height)
        self.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine))
        self.bg.setBrush(QBrush(QColor(255, 255, 255, 100)))
        self.addToGroup(self.bg)
        self._draw_bars(design)

    def _draw_bars(self, design: str):
        if design == "MINIMAL":
            bar_pattern = [4, 2, 4, 2, 4, 2, 4]
        elif design == "EAN13":
            bar_pattern = [2, 2, 3, 2, 2, 4, 3, 2, 3, 2, 2]
        elif design == "CODE39":
            bar_pattern = [3, 1, 3, 1, 2, 1, 3, 1, 2, 1, 3]
        elif design == "QR MOCK":
            sq = QGraphicsRectItem(40, 15, 50, 50)
            sq.setBrush(QBrush(Qt.black))
            sq.setPen(Qt.NoPen)
            self.addToGroup(sq)
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

        from PySide6.QtWidgets import QGraphicsTextItem
        lbl = QGraphicsTextItem("*12345678*")
        lbl.setFont(QFont("Courier", 9, QFont.Bold))
        lbl.setPos(35, 58)
        self.addToGroup(lbl)

    def boundingRect(self):
        return self.childrenBoundingRect().adjusted(-2, -2, 2, 2)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItemGroup.ItemPositionChange and self.scene():
            constrained_pos = keep_within_bounds(self, value)
            if self.move_callback:
                self.move_callback(constrained_pos)
            return constrained_pos
        return super().itemChange(change, value)