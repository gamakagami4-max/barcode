"""Custom QGraphicsItem subclasses used on the barcode design canvas."""

import uuid

from PySide6.QtWidgets import (
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsRectItem,
    QGraphicsItemGroup, QStyle, QGraphicsItem,
)
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QColor, QPen, QBrush, QFont, QPainter, QPainterPath

from components.barcode_editor.utils import keep_within_bounds


class SelectableTextItem(QGraphicsTextItem):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_color = QColor("#000000")
        self.component_id = str(uuid.uuid4())

    def setDefaultTextColor(self, color: QColor):
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


# ── Barcode rendering helpers ─────────────────────────────────────────────────

# Symbolic bar patterns: 1=narrow bar, 2=wide bar, 0=narrow space, 3=wide space
# Each pattern is (bar_widths, space_widths) alternating, starting with a bar.
# We just need a plausible-looking repeating pattern for the preview.

_LINEAR_PATTERN  = [1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 1,
                    1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1]
_EAN_PATTERN     = [1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1,
                    1, 1, 2, 1, 2, 1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1, 1]
_CODE39_PATTERN  = [2, 1, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 2, 1, 1,
                    1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1, 1, 1, 2, 1, 1, 2, 1]

_2D_DESIGNS  = {"AZTEC (2D)", "DATA MATRIX (2D)", "QR (2D)"}
_EAN_DESIGNS = {"EAN 13", "EAN 8", "UPC A"}
_C39_DESIGNS = {"CODE 39", "CODE 93", "CODE 11", "INTERLEAVED 2 OF 5"}


def _bar_pattern_for(design: str):
    if design in _EAN_DESIGNS:
        return _EAN_PATTERN
    if design in _C39_DESIGNS:
        return _CODE39_PATTERN
    return _LINEAR_PATTERN


class BarcodeItem(QGraphicsItem):
    """
    A lightweight QGraphicsItem that draws a barcode preview scaled to fit
    its container_width × container_height bounding box exactly.

    For linear barcodes the bars always fill the full height (minus an
    optional interpretation text area at the bottom).  For 2-D codes a
    square pixel-matrix is drawn centred in the box.
    """

    def __init__(self, move_callback, design: str = "CODE128"):
        super().__init__()
        self.move_callback     = move_callback
        self.component_name    = "Barcode"
        self.design            = design
        self.container_width   = 95
        self.container_height  = 40
        self._show_text        = True   # show "*12345*" interpretation line

        # Store original linear dimensions so we can restore them when
        # switching back from a 2D barcode type.
        self._linear_width     = 95
        self._linear_height    = 40

        self.setTransformOriginPoint(
            self.container_width / 2,
            self.container_height / 2
        )

        self.setFlags(
            QGraphicsItem.ItemIsMovable
            | QGraphicsItem.ItemIsSelectable
            | QGraphicsItem.ItemSendsGeometryChanges
        )

    # ── geometry ──────────────────────────────────────────────────────────────

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.container_width, self.container_height)

    def setRect(self, w: float, h: float):
        """Resize the barcode container and trigger a repaint."""
        self.prepareGeometryChange()
        self.container_width  = w
        self.container_height = h
        self.setTransformOriginPoint(w / 2, h / 2)
        self.update()

    def visual_top_left(self) -> QPointF:
        """
        Returns the visual top-left corner in scene coordinates, accounting
        for rotation. Use this to read LEFT/TOP in the properties panel
        instead of pos().
        """
        return self.mapToScene(QPointF(0, 0))

    def set_visual_top_left(self, scene_pos: QPointF):
        """
        Moves the item so its visual top-left corner lands at scene_pos.
        Use this to write LEFT/TOP from the properties panel
        instead of setPos().
        """
        current_tl = self.mapToScene(QPointF(0, 0))
        delta = scene_pos - current_tl
        self.setPos(self.pos() + delta)

    @staticmethod
    def natural_size_for(design: str, linear_w: float = 95, linear_h: float = 40):
        """
        Return (width, height) that reflects the natural aspect ratio for
        the given barcode design.

        - 2D designs (AZTEC, QR, DataMatrix) → square, side = min(linear_w, linear_h)
        - Linear designs → restore the saved linear_w × linear_h dimensions
        """
        if design in _2D_DESIGNS:
            side = min(linear_w, linear_h)
            return side, side
        else:
            return linear_w, linear_h

    # ── painting ──────────────────────────────────────────────────────────────

    def paint(self, painter: QPainter, option, widget=None):
        option.state &= ~QStyle.State_Selected

        w = self.container_width
        h = self.container_height
        is_2d = self.design in _2D_DESIGNS

        painter.setRenderHint(QPainter.Antialiasing, False)

        # ── background ────────────────────────────────────────────────────────
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.white))
        painter.drawRect(QRectF(0, 0, w, h))

        # ── selection border ─────────────────────────────────────────────────
        if self.isSelected():
            painter.setPen(QPen(QColor("#EF4444"), 1, Qt.DashLine))
        else:
            painter.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(0, 0, w, h))

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))

        if is_2d:
            self._paint_2d(painter, w, h)
        else:
            self._paint_linear(painter, w, h)

    def _paint_linear(self, painter: QPainter, w: float, h: float):
        MARGIN_X  = w * 0.04          # 4% side margin
        MARGIN_T  = h * 0.05          # 5% top margin
        TEXT_H    = h * 0.18 if self._show_text else 0
        bar_area_w = w - 2 * MARGIN_X
        bar_area_h = h - MARGIN_T - TEXT_H - h * 0.03  # small bottom gap

        pattern = _bar_pattern_for(self.design)
        total_units = sum(pattern)
        unit = bar_area_w / total_units

        x = MARGIN_X
        for i, units in enumerate(pattern):
            bar_w = units * unit
            if i % 2 == 0:  # even indices = bars
                painter.drawRect(QRectF(x, MARGIN_T, bar_w, bar_area_h))
            x += bar_w

        # interpretation text
        if self._show_text:
            painter.setPen(Qt.black)
            font = QFont("Courier", max(5, int(h * 0.11)), QFont.Bold)
            painter.setFont(font)
            text_y = MARGIN_T + bar_area_h + h * 0.01
            painter.drawText(
                QRectF(MARGIN_X, text_y, bar_area_w, TEXT_H),
                Qt.AlignHCenter | Qt.AlignVCenter,
                "*12345*"
            )

    def _paint_2d(self, painter: QPainter, w: float, h: float):
        MARGIN = min(w, h) * 0.08
        size   = min(w - 2 * MARGIN, h - 2 * MARGIN)
        ox     = (w - size) / 2
        oy     = (h - size) / 2
        CELLS  = 11  # grid resolution for preview
        cell   = size / CELLS

        # Deterministic pixel pattern that looks like a QR/DataMatrix
        _PATTERN = [
            [1,1,1,1,1,1,1,0,1,0,1],
            [1,0,0,0,0,0,1,0,0,1,0],
            [1,0,1,1,1,0,1,0,1,0,1],
            [1,0,1,1,1,0,1,0,0,1,1],
            [1,0,1,1,1,0,1,0,1,0,0],
            [1,0,0,0,0,0,1,0,1,1,0],
            [1,1,1,1,1,1,1,0,1,0,1],
            [0,0,0,0,0,0,0,0,1,1,0],
            [1,0,1,0,1,1,1,1,0,1,0],
            [0,1,1,0,0,1,0,1,1,0,1],
            [1,0,0,1,1,0,1,0,0,1,1],
        ]
        for row, cols in enumerate(_PATTERN):
            for col, filled in enumerate(cols):
                if filled:
                    painter.drawRect(QRectF(
                        ox + col * cell, oy + row * cell,
                        cell - 0.5, cell - 0.5
                    ))

    # ── interaction ───────────────────────────────────────────────────────────

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            constrained = keep_within_bounds(self, value)
            if self.move_callback:
                self.move_callback(constrained)
            return constrained
        return super().itemChange(change, value)