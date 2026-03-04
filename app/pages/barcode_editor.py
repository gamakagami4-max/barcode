import sys
import os
import json as _json_top
import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, 
    QGraphicsScene, QGraphicsView, QGraphicsItem, QGraphicsRectItem, 
    QGraphicsTextItem, QGraphicsItemGroup, QGraphicsLineItem, QListWidget, 
    QListWidgetItem, QComboBox, QLineEdit, QSpinBox, QFormLayout, QGridLayout,
    QApplication, QScrollArea, QStyledItemDelegate, QStyle, QSizePolicy,
    QStackedWidget, QDoubleSpinBox, QCheckBox, QPushButton, QSpacerItem
)
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, QSize, QEvent, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QFontMetrics, QCursor
from components.barcode_design_modal import BarcodeDesignModal
from PySide6.QtWidgets import QDialog
import shiboken6

# Local Imports
from components.standard_button import StandardButton


# ── SAME WITH Registry ────────────────────────────────────────────────────────

class SameWithRegistry:
    """Tracks which components are linked via SAME WITH relationships."""
    _links = {}

    @classmethod
    def register(cls, target_item, source_item):
        cls._links[target_item] = source_item

    @classmethod
    def unregister(cls, target_item):
        if target_item in cls._links:
            del cls._links[target_item]

    @classmethod
    def get_source(cls, target_item):
        return cls._links.get(target_item)

    @classmethod
    def get_targets(cls, source_item):
        return [t for t, s in cls._links.items() if s == source_item]

    @classmethod
    def is_source(cls, item):
        return item in cls._links.values()

    @classmethod
    def clear(cls):
        cls._links.clear()


# ── Checkbox with checkmark (not solid fill) ─────────────────────────────────

class CheckmarkCheckBox(QCheckBox):
    """QCheckBox that draws a dark tick on white, matching the reference UI."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QCheckBox {
                font-size: 11px;
                color: #334155;
                spacing: 6px;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 0px;
                height: 0px;
            }
        """)

    def sizeHint(self):
        sh = super().sizeHint()
        return QSize(sh.width(), max(sh.height(), 18))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        box_size = 14
        y_offset = (self.height() - box_size) // 2

        box_rect = QRect(0, y_offset, box_size, box_size)
        painter.setPen(QPen(QColor("#94A3B8" if not self.isChecked() else "#334155"), 1.5))
        painter.setBrush(QBrush(QColor("white")))
        painter.drawRoundedRect(box_rect, 3, 3)

        if self.isChecked():
            pen = QPen(QColor("#334155"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            x, y = box_rect.x(), box_rect.y()
            s = box_size
            painter.drawLine(
                QPointF(x + s * 0.18, y + s * 0.52),
                QPointF(x + s * 0.42, y + s * 0.76),
            )
            painter.drawLine(
                QPointF(x + s * 0.42, y + s * 0.76),
                QPointF(x + s * 0.82, y + s * 0.24),
            )

        text_x = box_size + 6
        painter.setPen(QColor("#334155"))
        font = self.font()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            QRect(text_x, 0, self.width() - text_x, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft,
            self.text(),
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self.isChecked())
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "border": "#E2E8F0",
    "text_dark": "#1E293B",
    "text_mute": "#64748B",
    "white": "#FFFFFF",
    "prop_bg": "#F1F5F9",
    "canvas_bg": "#E1E7EF",
    "legacy_blue": "#1E3A8A" 
}

MODERN_COMBO_STYLE = ""


# ── Custom combo widget ───────────────────────────────────────────────────────

class _ComboDropdown(QFrame):
    optionSelected = Signal(str)

    _ITEM_H = 32
    _PAD    = 4
    _MAX_H  = 260

    def __init__(self, options, selected, width):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet("QFrame { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; }")
        self._options = [str(o) for o in options]
        self._selected = selected
        self._buttons  = []
        self._build(width)

    def _build(self, width):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                border: none; background: #F4F4F5; width: 6px;
                margin: 4px 2px; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #D4D4D8; border-radius: 3px; min-height: 20px;
            }
            QScrollBar::handle:vertical:hover { background: #A1A1AA; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(self._PAD, self._PAD, self._PAD, self._PAD)
        layout.setSpacing(2)

        for opt in self._options:
            btn = QPushButton(opt)
            btn.setFixedHeight(self._ITEM_H)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.clicked.connect(lambda checked=False, o=opt: self._select(o))
            self._style_btn(btn, opt == self._selected)
            layout.addWidget(btn)
            self._buttons.append(btn)

        scroll.setWidget(inner)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        content_h = self._PAD * 2 + len(self._options) * (self._ITEM_H + 2)
        self.setFixedWidth(max(width, 160))
        self.setFixedHeight(min(content_h + 2, self._MAX_H))

    def _style_btn(self, btn, selected):
        if selected:
            btn.setStyleSheet("""
                QPushButton {
                    background: #EFF6FF; color: #3B82F6;
                    border: none; border-radius: 4px;
                    font-size: 12px; font-weight: 500;
                    text-align: left; padding: 0 10px;
                }
                QPushButton:hover { background: #DBEAFE; color: #3B82F6; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; color: #18181B;
                    border: none; border-radius: 4px;
                    font-size: 12px; font-weight: 400;
                    text-align: left; padding: 0 10px;
                }
                QPushButton:hover { background: #F4F4F5; color: #18181B; }
            """)

    def _select(self, option):
        self._selected = option
        for btn in self._buttons:
            self._style_btn(btn, btn.text() == option)
        self.optionSelected.emit(option)
        self.hide()

    def set_selected(self, option):
        self._selected = option
        for btn in self._buttons:
            self._style_btn(btn, btn.text() == option)

    def popup_below(self, trigger):
        self.setFixedWidth(max(trigger.width(), 160))
        screen = QApplication.primaryScreen().availableGeometry()
        pos_below = trigger.mapToGlobal(trigger.rect().bottomLeft())
        space_below = screen.bottom() - pos_below.y()
        dropdown_height = self.height()
        if space_below < dropdown_height:
            pos_above = trigger.mapToGlobal(trigger.rect().topLeft())
            self.move(pos_above.x(), pos_above.y() - dropdown_height)
        else:
            self.move(pos_below)
        self.show()
        self.raise_()


class CustomCombo(QFrame):
    currentTextChanged = Signal(str)

    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(32)
        self._items           = list(items or [])
        self._current         = self._items[0] if self._items else ""
        self._dropdown        = None
        self._is_open         = False
        self._signals_blocked = False
        self._build_ui()

    def _build_ui(self):
        self._apply_style(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        self._label = QLabel(self._current)
        self._label.setStyleSheet("color: #18181B; font-size: 12px; background: transparent; border: none;")
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)

        self._chevron = QLabel()
        self._chevron.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._chevron.setStyleSheet("background: transparent; border: none;")
        self._set_chevron(False)

        layout.addWidget(self._label, 1)
        layout.addWidget(self._chevron, 0)

    def _apply_style(self, open_):
        border = "#3B82F6" if open_ else "#E5E7EB"
        bw     = "1.5"     if open_ else "1"
        hover  = "#3B82F6" if open_ else "#D4D4D8"
        self.setStyleSheet(f"""
            CustomCombo {{
                background: #FFFFFF;
                border: {bw}px solid {border};
                border-radius: 6px;
            }}
            CustomCombo:hover {{ border-color: {hover}; }}
        """)
        if self.isEnabled() and hasattr(self, '_chevron'):
            self._chevron.setVisible(True)

    def _set_chevron(self, open_):
        self._chevron.setPixmap(
            qta.icon("fa5s.chevron-up" if open_ else "fa5s.chevron-down",
                     color="#3B82F6" if open_ else "#71717A").pixmap(10, 10)
        )

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self._apply_enabled_style(enabled)

    def _apply_enabled_style(self, enabled):
        if enabled:
            self._apply_style(self._is_open)
            self._set_chevron(self._is_open)
        else:
            self.setStyleSheet("""
                CustomCombo {
                    background: #F8FAFC;
                    border: 1px solid #E2E8F0;
                    border-radius: 6px;
                }
                CustomCombo:hover { border-color: #E2E8F0; }
            """)
            self._chevron.setVisible(False)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        if event.button() == Qt.LeftButton:
            if self._is_open:
                self._close()
            else:
                self._open()
        super().mousePressEvent(event)

    def _open(self):
        self._dropdown = _ComboDropdown(list(self._items), self._current, self.width())
        self._dropdown.optionSelected.connect(self._on_selected)
        self._dropdown.popup_below(self)
        self._is_open = True
        self._apply_style(True)
        self._set_chevron(True)
        QApplication.instance().installEventFilter(self)

    def _close(self):
        QApplication.instance().removeEventFilter(self)
        if self._dropdown:
            self._dropdown.hide()
        self._is_open = False
        self._apply_style(False)
        self._set_chevron(False)

    def _on_selected(self, option):
        self._current = option
        self._label.setText(option)
        self._label.setStyleSheet("color: #18181B; font-size: 12px; background: transparent; border: none;")
        self._close()
        if not self._signals_blocked:
            self.currentTextChanged.emit(option)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            gpos = QCursor.pos()
            in_trigger  = self.rect().contains(self.mapFromGlobal(gpos))
            in_dropdown = (self._dropdown is not None and
                           self._dropdown.isVisible() and
                           self._dropdown.rect().contains(self._dropdown.mapFromGlobal(gpos)))
            if not in_trigger and not in_dropdown:
                self._close()
        return False

    def hideEvent(self, event):
        if self._is_open:
            self._close()
        super().hideEvent(event)

    def currentText(self):
        return self._current

    def setCurrentText(self, text):
        if text in self._items:
            self._current = text
            self._label.setText(text)
            self._label.setStyleSheet("color: #18181B; font-size: 12px; background: transparent; border: none;")
            if self._dropdown:
                self._dropdown.set_selected(text)

    def setCurrentIndex(self, index):
        if index == -1:
            self._current = ""
            self._label.setText("")
            self._label.setStyleSheet("color: #71717A; font-size: 12px; background: transparent; border: none;")
        elif 0 <= index < len(self._items):
            self.setCurrentText(self._items[index])

    def currentIndex(self):
        try:
            return self._items.index(self._current)
        except ValueError:
            return -1

    def findText(self, text):
        try:
            return self._items.index(text)
        except ValueError:
            return -1

    def addItems(self, items):
        self._items.extend(items)
        if not self._current and self._items:
            self._current = self._items[0]
            self._label.setText(self._current)

    def addItem(self, item):
        self._items.append(item)

    def count(self):
        return len(self._items)

    def itemText(self, index):
        return self._items[index] if 0 <= index < len(self._items) else ""

    def setPlaceholderText(self, text):
        if not self._current:
            self._label.setText(text)
            self._label.setStyleSheet("color: #71717A; font-size: 12px; background: transparent; border: none;")

    def blockSignals(self, block):
        self._signals_blocked = block
        return super().blockSignals(block)

MODERN_INPUT_STYLE = """
    QLineEdit, QSpinBox, QComboBox, QDoubleSpinBox {
        background-color: white;
        border: 1px solid #CBD5E1;
        border-radius: 4px;
        padding: 5px;
        font-size: 11px;
        color: #334155;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QDoubleSpinBox:focus {
        border: 1.5px solid #6366F1;
    }
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
        subcontrol-origin: border;
        width: 20px;
        border: none;
        background: transparent;
    }
    QSpinBox::up-button, QDoubleSpinBox::up-button {
        subcontrol-position: top right;
        border-left: 1px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
        border-top-right-radius: 4px;
    }
    QSpinBox::down-button, QDoubleSpinBox::down-button {
        subcontrol-position: bottom right;
        border-left: 1px solid #CBD5E1;
        border-bottom-right-radius: 4px;
    }
    QSpinBox::up-button:hover, QSpinBox::down-button:hover,
    QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {
        background: #F1F5F9;
    }
    QSpinBox::up-arrow, QSpinBox::down-arrow,
    QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {
        width: 0px; height: 0px; image: none;
    }
    QComboBox::drop-down { border: 0px; background: transparent; }
    QComboBox::down-arrow { image: none; width: 0; height: 0; }
"""

MODERN_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        border: none;
        background: #F1F5F9;
        width: 12px;
        margin: 4px 2px;
        border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #94A3B8;
        border-radius: 5px;
        min-height: 32px;
        margin: 1px;
    }
    QScrollBar::handle:vertical:hover { background: #6366F1; }
    QScrollBar::handle:vertical:pressed { background: #4338CA; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar:horizontal {
        border: none;
        background: #F1F5F9;
        height: 12px;
        margin: 2px 4px;
        border-radius: 6px;
    }
    QScrollBar::handle:horizontal {
        background: #94A3B8;
        border-radius: 5px;
        min-width: 32px;
        margin: 1px;
    }
    QScrollBar::handle:horizontal:hover { background: #6366F1; }
    QScrollBar::handle:horizontal:pressed { background: #4338CA; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""

TAB_ACTIVE_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        border-bottom: 2px solid #6366F1;
        border-radius: 0px;
        padding: 0px 16px;
        font-size: 11px;
        font-weight: 700;
        color: #6366F1;
        letter-spacing: 0.5px;
    }
"""

TAB_INACTIVE_STYLE = """
    QPushButton {
        background: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0px;
        padding: 0px 16px;
        font-size: 11px;
        font-weight: 600;
        color: #94A3B8;
        letter-spacing: 0.5px;
    }
    QPushButton:hover {
        color: #475569;
        border-bottom: 2px solid #CBD5E1;
    }
"""


# ── Custom scroll area ────────────────────────────────────────────────────────
class ConstrainedScrollArea(QScrollArea):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.widget():
            self.widget().setMaximumWidth(self.viewport().width())


class ChevronSpinBox(QSpinBox):
    _BTN_W = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._px_up   = qta.icon("fa5s.chevron-up",  color="#64748B").pixmap(7, 7)
        self._px_down = qta.icon("fa5s.chevron-down", color="#64748B").pixmap(7, 7)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        h = self.height()
        btn_w = self._BTN_W
        x_left = self.width() - btn_w
        icon_w = self._px_up.width()
        icon_h = self._px_up.height()
        cx = x_left + (btn_w - icon_w) // 2
        painter.drawPixmap(cx, (h // 2 - icon_h) // 2, self._px_up)
        painter.drawPixmap(cx, h // 2 + (h // 2 - icon_h) // 2, self._px_down)
        painter.end()


def make_spin(min_val=0, max_val=5000, value=0) -> ChevronSpinBox:
    spin = ChevronSpinBox()
    spin.setRange(min_val, max_val)
    spin.setValue(value)
    spin.setStyleSheet(MODERN_INPUT_STYLE)
    spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return spin


def make_chevron_combo(items: list, style: str = MODERN_INPUT_STYLE) -> CustomCombo:
    combo = CustomCombo(items)
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return combo


# --- Utilities ---

def keep_within_bounds(item, new_pos):
    scene_rect = item.scene().sceneRect()
    rect = item.sceneBoundingRect()
    x = max(scene_rect.left(), min(new_pos.x(), scene_rect.right() - rect.width()))
    y = max(scene_rect.top(), min(new_pos.y(), scene_rect.bottom() - rect.height()))
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
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(8)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)
        LABEL_W = 70
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W)
            l.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
            return l

        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        layout.addRow(lbl("ALIGNMENT :"), self.align_combo)
        self.font_combo = make_chevron_combo([
            "STANDARD", "ARIAL", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
            "ARIAL BOLD", "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD",
            "FUTURA-CONDENSED-BOL", "FUTURA-NORMAL", "GLORIOLA STD BOLD", "GLORIOLA STD LIGHT",
            "HELVETICANEUE", "MONTSERRAT BOLD", "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD",
            "MYRIAD PRO", "NEO SANS", "NEO SANS BOLD", "OCR-B", "SWIS721", "TAHOMA",
            "UNIVERS CONDENSED",
        ])
        layout.addRow(lbl("FONT NAME :"), self.font_combo)
        self.size_spin = make_spin(1, 100, int(self.item.font().pointSize()))
        self.size_spin.valueChanged.connect(self.apply_font_changes)
        layout.addRow(lbl("FONT SIZE :"), self.size_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y()))
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x()))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(lbl("LEFT :"), self.left_spin)
        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}
        self.angle_combo.currentTextChanged.connect(lambda v: self.item.setRotation(angle_map.get(v, 0)))
        layout.addRow(lbl("ANGLE :"), self.angle_combo)
        self.inverse_combo = make_chevron_combo(["NO", "YES"])
        current_inverse = getattr(self.item, "design_inverse", False)
        self.inverse_combo.setCurrentText("YES" if current_inverse else "NO")
        self.inverse_combo.currentTextChanged.connect(self._apply_inverse)
        layout.addRow(lbl("INVERSE :"), self.inverse_combo)
        self.type_combo = make_chevron_combo([
            "FIX", "INPUT", "LOOKUP", "SAME WITH", "LINK", "SYSTEM", "BATCH NO", "MERGE",
            "TIMBANGAN", "DUPLIKASI", "RUNNING NO", "KONVERSI TIMBANGAN",
        ])
        stored_type = getattr(self.item, "design_type", "FIX")
        self.type_combo.setCurrentText(stored_type)
        self.type_combo.currentTextChanged.connect(lambda v: setattr(self.item, "design_type", v))
        layout.addRow(lbl("TYPE :"), self.type_combo)
        self.editor_combo = make_chevron_combo(["ENABLED", "DISABLED", "INVISIBLE"])
        layout.addRow(lbl("EDITOR :"), self.editor_combo)

        # ── INPUT-only fields: DATA TYPE + MAX LENGTH ─────────────────
        self.data_type_combo = make_chevron_combo(["STRING", "INTEGER", "DECIMAL"])
        self.data_type_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("DATA TYPE :"), self.data_type_combo)

        self.max_length_spin = make_spin(0, 9999, 1)
        self.max_length_spin.setSpecialValueText("")
        layout.addRow(lbl("MAX LENGTH :"), self.max_length_spin)

        # ── SAME WITH-only: component dropdown ───────────────────────
        self.same_with_combo = make_chevron_combo([""])
        try:
            scene = self.item.scene()
            if scene:
                other_names = []
                for scene_item in scene.items():
                    if scene_item.group():
                        continue
                    if scene_item is self.item:
                        continue
                    if not isinstance(scene_item, SelectableTextItem):
                        continue
                    # Prevent circular references
                    if getattr(scene_item, "design_same_with", "") == getattr(self.item, "component_name", ""):
                        continue
                    name = getattr(scene_item, "component_name", "") or "Text"
                    other_names.append(name)
                if other_names:
                    self.same_with_combo._items = [""] + other_names
                    self.same_with_combo._current = ""
                    self.same_with_combo._label.setText("")
                    self.same_with_combo.setPlaceholderText("—")
                else:
                    self.same_with_combo._items = ["—"]
                    self.same_with_combo._current = "—"
                    self.same_with_combo._label.setText("—")
        except Exception:
            pass
        stored_same_with = getattr(self.item, "design_same_with", "")
        if stored_same_with and stored_same_with in self.same_with_combo._items:
            self.same_with_combo.setCurrentText(stored_same_with)
        self.same_with_combo.currentTextChanged.connect(self._on_same_with_changed)
        layout.addRow(lbl("SAME WITH :"), self.same_with_combo)

        DISABLED_STYLE = """
            QComboBox, QSpinBox {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                padding: 5px;
                font-size: 11px;
                color: #94A3B8;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button { background: transparent; border: none; }
        """

        def _on_type_changed(val):
            is_input     = val == "INPUT"
            is_lookup    = val == "LOOKUP"
            is_same_with = val == "SAME WITH"

            if is_same_with:
                # Always lock all fields first — nothing is editable on a SAME WITH item
                self._lock_all_fields(True)
                self.same_with_combo.setEnabled(True)
                source_name = self.same_with_combo.currentText()
                if source_name and source_name not in ("", "(no other components)"):
                    self._apply_same_with_link(source_name)
            else:
                self._clear_same_with()

                # ── INPUT-only: DATA TYPE + MAX LENGTH ────────────────
                if not is_input:
                    self.data_type_combo.setEnabled(False)
                    self.max_length_spin.setEnabled(False)
                    self.data_type_combo.blockSignals(True)
                    self.data_type_combo.setCurrentIndex(-1)
                    self.data_type_combo.blockSignals(False)
                    self.max_length_spin.setValue(0)
                    self.max_length_spin.setStyleSheet(DISABLED_STYLE)
                else:
                    self.data_type_combo.setEnabled(True)
                    self.max_length_spin.setEnabled(True)
                    self.max_length_spin.setStyleSheet(MODERN_INPUT_STYLE)
                    if self.data_type_combo.currentIndex() == -1:
                        self.data_type_combo.setCurrentIndex(0)
                    if self.max_length_spin.value() == 0:
                        self.max_length_spin.setValue(1)

                # ── LOOKUP-only: TABLE, QUERY, FIELD, GROUP ───────────
                self.table_combo.setEnabled(is_lookup)
                self.group_combo.setEnabled(is_lookup)
                self.table_extra.setEnabled(is_lookup)
                self.table_extra.setStyleSheet(
                    MODERN_INPUT_STYLE if is_lookup else """
                        QLineEdit {
                            background-color: #F8FAFC; border: 1px solid #E2E8F0;
                            border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
                        }
                    """
                )
                self.field_edit.setEnabled(is_lookup)
                self.field_edit.setStyleSheet(
                    MODERN_INPUT_STYLE if is_lookup else """
                        QLineEdit {
                            background-color: #F8FAFC; border: 1px solid #E2E8F0;
                            border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
                        }
                    """
                )
                self.same_with_combo.setEnabled(is_same_with)

        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(lbl("TEXT :"), self.text_input)
        self.caption_input = QLineEdit("LABEL 1")
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("CAPTION :"), self.caption_input)
        self.wrap_combo = make_chevron_combo(["NO", "YES"])
        layout.addRow(lbl("WRAP TEXT :"), self.wrap_combo)
        self.wrap_width_spin = make_spin(0, 5000, 1)
        layout.addRow(lbl("WRAP WIDTH :"), self.wrap_width_spin)
        self.group_combo = make_chevron_combo([""])
        layout.addRow(lbl("GROUP :"), self.group_combo)
        self.table_combo = make_chevron_combo([""])
        layout.addRow(lbl("TABLE :"), self.table_combo)
        self.table_extra = QLineEdit(); self.table_extra.setStyleSheet(MODERN_INPUT_STYLE)
        self.table_extra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("QUERY :"), self.table_extra)
        self.field_edit = QLineEdit(); self.field_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.field_edit.setMinimumHeight(52); self.field_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("FIELD :"), self.field_edit)
        self.result_combo = make_chevron_combo([""])
        layout.addRow(lbl("RESULT :"), self.result_combo)
        self._trim_checked = False
        trim_row = QWidget(); trim_row.setStyleSheet("background: transparent; border: none;")
        trim_layout = QHBoxLayout(trim_row); trim_layout.setContentsMargins(0,0,0,0); trim_layout.setSpacing(6)
        self.trim_box = QLabel(); self.trim_box.setFixedSize(14, 14); self.trim_box.setCursor(Qt.PointingHandCursor)
        self._set_trim_style(False); self.trim_box.mousePressEvent = self._toggle_trim
        trim_layout.addWidget(self.trim_box)
        trim_lbl = QLabel("TRIM"); trim_lbl.setStyleSheet(label_style); trim_layout.addWidget(trim_lbl); trim_layout.addStretch()
        layout.addRow(lbl(""), trim_row)
        self.format_edit = QLineEdit(); self.format_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.format_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("FORMAT :"), self.format_edit)
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        visible_val = "TRUE" if current_visible in [True, None] else "FALSE"
        self.visible_combo.setCurrentText(visible_val)
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "SAVE"])
        layout.addRow(lbl("SAVE FIELD :"), self.save_field_combo)
        self.column_spin = make_spin(1, 999, 1)
        layout.addRow(lbl("COLUMN :"), self.column_spin)
        self.mandatory_combo = make_chevron_combo(["FALSE", "TRUE"])
        layout.addRow(lbl("MANDATORY :"), self.mandatory_combo)

        self.align_combo.currentTextChanged.connect(self._apply_alignment)
        self.font_combo.currentTextChanged.connect(self._apply_font_family)
        self.type_combo.currentTextChanged.connect(_on_type_changed)
        _on_type_changed(getattr(self.item, "design_type", "FIX"))

        # Restore SAME WITH link if previously set
        if stored_same_with and stored_same_with in self.same_with_combo._items:
            if getattr(self.item, "design_type", "") == "SAME WITH":
                self._apply_same_with_link(stored_same_with)

        self._update_visibility_indicator()

    # ── SAME WITH methods ─────────────────────────────────────────────────────

    def _on_same_with_changed(self, value):
        if self.type_combo.currentText() == "SAME WITH":
            if value and value not in ("", "(no other components)"):
                self._apply_same_with_link(value)
            else:
                # Blank selected — cut off the link entirely
                SameWithRegistry.unregister(self.item)
                self.item.design_same_with = ""
                self._lock_all_fields(True)
                self.same_with_combo.setEnabled(True)
                return
        self.item.design_same_with = value

    def _apply_same_with_link(self, source_name):
        scene = self.item.scene()
        if not scene:
            return
        source_item = None
        for scene_item in scene.items():
            if scene_item is self.item:
                continue
            if not isinstance(scene_item, SelectableTextItem):
                continue
            if getattr(scene_item, "component_name", "") == source_name:
                source_item = scene_item
                break
        if not source_item:
            return
        # Prevent linking to another SAME WITH item
        if getattr(source_item, "design_type", "") == "SAME WITH":
            return
        SameWithRegistry.register(self.item, source_item)
        self.item.setPlainText(source_item.toPlainText())
        self.item.setFont(QFont(source_item.font().family(), source_item.font().pointSize()))
        self.item.setDefaultTextColor(source_item.defaultTextColor())
        self.item.design_inverse = getattr(source_item, "design_inverse", False)
        self.item.design_visible = getattr(source_item, "design_visible", True)
        self.item.design_same_with = source_name
        self._refresh_ui_from_item()
        self._lock_all_fields(True)
        self.update_callback()

    def _clear_same_with(self):
        SameWithRegistry.unregister(self.item)
        self.item.design_same_with = ""
        self._lock_all_fields(False)

    def _lock_all_fields(self, locked):
        DISABLED_STYLE_FULL = """
            QComboBox, QSpinBox, QLineEdit {
                background-color: #F8FAFC; border: 1px solid #E2E8F0;
                border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
            }
            QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
                background: transparent; border: none;
            }
        """
        LINE_DISABLED = """
            QLineEdit {
                background-color: #F8FAFC; border: 1px solid #E2E8F0;
                border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
            }
        """
        for w in [self.text_input, self.caption_input, self.format_edit]:
            w.setEnabled(not locked)
            w.setStyleSheet(MODERN_INPUT_STYLE if not locked else LINE_DISABLED)
        for w in [self.size_spin, self.top_spin, self.left_spin, self.wrap_width_spin, self.column_spin]:
            w.setEnabled(not locked)
            w.setStyleSheet(MODERN_INPUT_STYLE if not locked else DISABLED_STYLE_FULL)
        for w in [self.align_combo, self.font_combo, self.angle_combo, self.inverse_combo,
                  self.editor_combo, self.wrap_combo, self.data_type_combo,
                  self.table_combo, self.group_combo, self.result_combo,
                  self.visible_combo, self.save_field_combo, self.mandatory_combo]:
            w.setEnabled(not locked)
        self.trim_box.setEnabled(not locked)
        # Keep SAME WITH combo always accessible
        # Keep SAME WITH combo accessible only when locked (i.e. type IS SAME WITH)
        if locked:
            self.same_with_combo.setEnabled(True)

    def _refresh_ui_from_item(self):
        self.text_input.blockSignals(True)
        self.size_spin.blockSignals(True)
        self.text_input.setText(self.item.toPlainText())
        self.size_spin.setValue(int(self.item.font().pointSize()))
        self.top_spin.setValue(int(self.item.pos().y()))
        self.left_spin.setValue(int(self.item.pos().x()))
        angle_map_inv = {0: "0", 270: "90", 180: "180", 90: "270"}
        self.angle_combo.setCurrentText(angle_map_inv.get(int(self.item.rotation()), "0"))
        self.inverse_combo.setCurrentText("YES" if getattr(self.item, "design_inverse", False) else "NO")
        self.visible_combo.setCurrentText("TRUE" if getattr(self.item, "design_visible", True) else "FALSE")
        self.text_input.blockSignals(False)
        self.size_spin.blockSignals(False)

    def _sync_same_with_targets(self):
        targets = SameWithRegistry.get_targets(self.item)
        for target in targets:
            if not target.scene():
                continue
            target.setPlainText(self.item.toPlainText())
            target.setFont(QFont(self.item.font().family(), self.item.font().pointSize()))
            target.setDefaultTextColor(self.item.defaultTextColor())
            target.design_inverse = getattr(self.item, "design_inverse", False)
            target.design_visible = getattr(self.item, "design_visible", True)
        self.update_callback()

    # ── Standard methods ──────────────────────────────────────────────────────

    def _apply_alignment(self, value):
        align_map = {
            "LEFT JUSTIFY":  Qt.AlignLeft,
            "CENTER":        Qt.AlignCenter,
            "RIGHT JUSTIFY": Qt.AlignRight,
        }
        from PySide6.QtGui import QTextCursor, QTextBlockFormat
        alignment = align_map.get(value, Qt.AlignLeft)
        if value == "LEFT JUSTIFY":
            self.item.setTextWidth(-1)
        else:
            w = self.item.boundingRect().width()
            self.item.setTextWidth(w if w > 0 else 200)
        cursor = self.item.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setAlignment(alignment)
        cursor.mergeBlockFormat(fmt)
        self.item.setTextCursor(cursor)
        self.update_callback()

    def _apply_font_family(self, value):
        font_map = {
            "STANDARD":              "Arial",
            "ARIAL":                 "Arial",
            "ARIAL BLACK":           "Arial Black",
            "ARIAL BLACK (GT)":      "Arial Black",
            "ARIAL BLACK NEW":       "Arial Black",
            "ARIAL BOLD":            "Arial",
            "ARIAL NARROW BOLD":     "Arial Narrow",
            "EUROSTILE BOLD OLD":    "Eurostile",
            "FUTURA-CONDENSED-BOL":  "Futura",
            "FUTURA-NORMAL":         "Futura",
            "GLORIOLA STD BOLD":     "Arial",
            "GLORIOLA STD LIGHT":    "Arial",
            "HELVETICANEUE":         "Helvetica Neue",
            "MONTSERRAT BOLD":       "Montserrat",
            "MONTSERRAT SBOLD-CAE":  "Montserrat",
            "MONTSERRAT SEMI BOLD":  "Montserrat",
            "MYRIAD PRO":            "Myriad Pro",
            "NEO SANS":              "Neo Sans",
            "NEO SANS BOLD":         "Neo Sans",
            "OCR-B":                 "OCR B",
            "SWIS721":               "Swiss 721",
            "TAHOMA":                "Tahoma",
            "UNIVERS CONDENSED":     "Univers Condensed",
        }
        bold_fonts = {"ARIAL BOLD", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
                      "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD", "FUTURA-CONDENSED-BOL",
                      "GLORIOLA STD BOLD", "HELVETICANEUE", "MONTSERRAT BOLD",
                      "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD", "NEO SANS BOLD"}
        font = self.item.font()
        font.setFamily(font_map.get(value, "Arial"))
        font.setBold(value in bold_fonts)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _set_trim_style(self, checked):
        if checked:
            self.trim_box.setText("✓"); self.trim_box.setAlignment(Qt.AlignCenter)
            self.trim_box.setStyleSheet("QLabel{border:1.5px solid #6366F1;border-radius:3px;background:#6366F1;color:white;font-size:9px;font-weight:bold;}")
        else:
            self.trim_box.setText(""); self.trim_box.setStyleSheet("QLabel{border:1.5px solid #CBD5E1;border-radius:3px;background:white;}")

    def _toggle_trim(self, event):
        self._trim_checked = not self._trim_checked; self._set_trim_style(self._trim_checked)

    def _apply_inverse(self, value):
        self.item.design_inverse = (value == "YES")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_visible(self, value):
        self.item.design_visible = (value == "TRUE")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _update_visibility_indicator(self):
        pass

    def apply_text_changes(self, text):
        self.item.setPlainText(text)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def apply_font_changes(self, size):
        font = self.item.font()
        font.setPointSize(size)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)


class LinePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setVerticalSpacing(10); layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        LABEL_W = 70
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignBottom); return l
        line = self.item.line(); pen = self.item.pen()
        self.thickness_spin = make_spin(1, 100, int(pen.width())); self.thickness_spin.valueChanged.connect(self.update_thickness); layout.addRow(lbl("THICKNESS :"), self.thickness_spin)
        self.width_spin = make_spin(0, 5000, int(abs(line.dx()))); self.width_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        visible_val = "TRUE" if current_visible in [True, None] else "FALSE"
        self.visible_combo.setCurrentText(visible_val)
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self._update_visibility_indicator()

    def update_geometry(self): self.item.setLine(0, 0, self.width_spin.value(), 0); self.update_callback()
    def update_thickness(self, value): pen = self.item.pen(); pen.setWidth(value); self.item.setPen(pen); self.update_callback()
    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)
    def _apply_visible(self, value):
        self.item.design_visible = (value == "TRUE"); self.update_callback()
    def _update_visibility_indicator(self): pass


class RectanglePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setVerticalSpacing(10); layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        LABEL_W = 70
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignBottom); return l
        rect = self.item.rect(); pen = self.item.pen()
        self.height_spin = make_spin(0, 5000, int(rect.height())); self.height_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("HEIGHT :"), self.height_spin)
        self.width_spin = make_spin(0, 5000, int(rect.width())); self.width_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.border_spin = make_spin(0, 20, int(pen.width())); self.border_spin.valueChanged.connect(self.update_border); layout.addRow(lbl("BORDER WIDTH :"), self.border_spin)
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        visible_val = "TRUE" if current_visible in [True, None] else "FALSE"
        self.visible_combo.setCurrentText(visible_val)
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self._update_visibility_indicator()
        self.column_spin = make_spin(1, 999, 1); layout.addRow(lbl("COLUMN :"), self.column_spin)

    def update_geometry(self): self.item.setRect(0, 0, self.width_spin.value(), self.height_spin.value()); self.update_callback()
    def update_border(self, width): pen = self.item.pen(); pen.setWidth(width); self.item.setPen(pen); self.update_callback()
    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)
    def _apply_visible(self, value):
        self.item.design_visible = (value == "TRUE"); self.update_callback()
    def _update_visibility_indicator(self): pass


class BarcodePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setVerticalSpacing(10); layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)
        label_style = f"color:{COLORS['legacy_blue']}; font-size:9px; text-transform:uppercase; background:transparent; border:none;"
        LABEL_W = 70
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignBottom); return l
        self.design_combo = make_chevron_combo(["CODE128","MINIMAL","EAN13","CODE39","QR MOCK"])
        self.design_combo.setCurrentText(self.item.design); self.design_combo.currentTextChanged.connect(self.update_design); layout.addRow(lbl("DESIGN :"), self.design_combo)
        self.width_spin = make_spin(20, 1000, self.item.container_width); self.width_spin.valueChanged.connect(self.update_size); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.height_spin = make_spin(20, 1000, self.item.container_height); self.height_spin.valueChanged.connect(self.update_size); layout.addRow(lbl("HEIGHT :"), self.height_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.visible_combo = make_chevron_combo(["TRUE","FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        visible_val = "TRUE" if current_visible in [True, None] else "FALSE"
        self.visible_combo.setCurrentText(visible_val)
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self._update_visibility_indicator()

    def update_design(self, new_design):
        old_scene_pos = self.item.scenePos()
        for child in list(self.item.childItems()):
            self.item.removeFromGroup(child)
            if child.scene(): child.scene().removeItem(child)
            child.setParentItem(None); del child
        self.item.setPos(0, 0); self.item.design = new_design
        self.item.bg = QGraphicsRectItem(0, 0, self.item.container_width, self.item.container_height)
        self.item.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine)); self.item.bg.setBrush(QBrush(QColor(255,255,255,100))); self.item.addToGroup(self.item.bg)
        if new_design == "MINIMAL": bar_pattern = [4,2,4,2,4,2,4]
        elif new_design == "EAN13": bar_pattern = [2,2,3,2,2,4,3,2,3,2,2]
        elif new_design == "CODE39": bar_pattern = [3,1,3,1,2,1,3,1,2,1,3]
        elif new_design == "QR MOCK":
            sq = QGraphicsRectItem(40,15,50,50); sq.setBrush(QBrush(Qt.black)); sq.setPen(Qt.NoPen); self.item.addToGroup(sq); bar_pattern = []
        else: bar_pattern = [3,2,3,2,2,3,2,3,3,2,2,3,2,3,2,2,3,2,3]
        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45); bar.setBrush(QBrush(Qt.black)); bar.setPen(Qt.NoPen); self.item.addToGroup(bar)
            x_offset += width
        lbl_item = QGraphicsTextItem("*12345678*"); lbl_item.setFont(QFont("Courier", 9, QFont.Bold)); lbl_item.setPos(35, 58); self.item.addToGroup(lbl_item)
        self.item.setPos(old_scene_pos); self.update_callback()

    def update_size(self):
        self.item.container_width = self.width_spin.value(); self.item.container_height = self.height_spin.value()
        self.item.bg.setRect(0, 0, self.item.container_width, self.item.container_height); self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)

    def _apply_visible(self, value):
        self.item.design_visible = (value == "TRUE"); self.update_callback()

    def _update_visibility_indicator(self): pass


# --- Custom Scene Items ---

class SelectableTextItem(QGraphicsTextItem):
    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        if self.isSelected():
            original_color = self.defaultTextColor()
            self.setDefaultTextColor(QColor("#EF4444"))
            super().paint(painter, option, widget)
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
        self.move_callback = move_callback; self.component_name = "Barcode"
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.container_width = 160; self.container_height = 80; self.design = design
        self.bg = QGraphicsRectItem(0, 0, self.container_width, self.container_height)
        self.bg.setPen(QPen(QColor("#CBD5E1"), 1, Qt.DashLine)); self.bg.setBrush(QBrush(QColor(255,255,255,100))); self.addToGroup(self.bg)
        if design == "MINIMAL": bar_pattern = [4,2,4,2,4,2,4]
        elif design == "EAN13": bar_pattern = [2,2,3,2,2,4,3,2,3,2,2]
        elif design == "CODE39": bar_pattern = [3,1,3,1,2,1,3,1,2,1,3]
        elif design == "QR MOCK":
            sq = QGraphicsRectItem(40,15,50,50); sq.setBrush(QBrush(Qt.black)); sq.setPen(Qt.NoPen); self.addToGroup(sq); bar_pattern = []
        else: bar_pattern = [3,2,3,2,2,3,2,3,3,2,2,3,2,3,2,2,3,2,3]
        x_offset = 15
        for i, width in enumerate(bar_pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, width, 45); bar.setBrush(QBrush(Qt.black)); bar.setPen(Qt.NoPen); self.addToGroup(bar)
            x_offset += width
        lbl = QGraphicsTextItem("*12345678*"); lbl.setFont(QFont("Courier", 9, QFont.Bold)); lbl.setPos(35, 58); self.addToGroup(lbl)

    def boundingRect(self): return self.childrenBoundingRect().adjusted(-2,-2,2,2)

    def paint(self, painter, option, widget=None):
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange and self.scene():
            constrained_pos = keep_within_bounds(self, value)
            if self.move_callback: self.move_callback(constrained_pos)
            return constrained_pos
        return super().itemChange(change, value)


class GridGraphicsScene(QGraphicsScene):
    def __init__(self, rect, grid_size=20, color=QColor("#E2E8F0"), parent=None):
        super().__init__(rect, parent); self.grid_size = grid_size; self.grid_color = color

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        scene_r = self.sceneRect()
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(QColor("#FFFFFF"))); painter.drawRect(scene_r)
        painter.setPen(QPen(self.grid_color, 1))
        left = int(scene_r.left()) - (int(scene_r.left()) % self.grid_size)
        top  = int(scene_r.top())  - (int(scene_r.top())  % self.grid_size)
        x = left
        while x < scene_r.right():
            painter.drawLine(QPointF(x, scene_r.top()), QPointF(x, scene_r.bottom())); x += self.grid_size
        y = top
        while y < scene_r.bottom():
            painter.drawLine(QPointF(scene_r.left(), y), QPointF(scene_r.right(), y)); y += self.grid_size
        painter.setPen(QPen(QColor("#94A3B8"), 1.5)); painter.setBrush(Qt.NoBrush); painter.drawRect(scene_r)


# --- Component List ---

COMPONENT_META = {
    'text':    ('fa5s.font',    '#6366F1', '#FFFFFF', '#4338CA'),
    'barcode': ('fa5s.barcode', '#0EA5E9', '#FFFFFF', '#0369A1'),
    'line':    ('fa5s.minus',   '#10B981', '#FFFFFF', '#047857'),
    'rect':    ('fa5s.square',  '#F59E0B', '#FFFFFF', '#B45309'),
}

def _get_meta(name: str):
    key = name.lower()
    if key.startswith('text'):    return COMPONENT_META['text']
    if key.startswith('barcode'): return COMPONENT_META['barcode']
    if key.startswith('line'):    return COMPONENT_META['line']
    if key.startswith('rect'):    return COMPONENT_META['rect']
    return ('fa5s.cube', '#64748B', '#FFFFFF', '#475569')


class ComponentItemDelegate(QStyledItemDelegate):
    ROW_H = 38; ACCENT_W = 3; CHIP_SIZE = 24; PAD = 8; TRASH_SIZE = 18

    def sizeHint(self, option, index): return QSize(option.rect.width(), self.ROW_H)

    def paint(self, painter, option, index):
        painter.save(); painter.setRenderHint(QPainter.Antialiasing)
        name = index.data(Qt.DisplayRole) or ""
        icon_name, badge_bg, badge_fg, accent = _get_meta(name)
        selected = bool(option.state & QStyle.State_Selected)
        hovered  = bool(option.state & QStyle.State_MouseOver) and not selected
        r = option.rect.adjusted(4, 2, -4, -2)
        bg = QColor("#EEF2FF") if selected else (QColor("#F8FAFC") if hovered else QColor("#FFFFFF"))
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(bg)); painter.drawRoundedRect(r, 6, 6)
        accent_rect = QRect(r.left(), r.top()+6, self.ACCENT_W, r.height()-12)
        painter.setBrush(QBrush(QColor(accent))); painter.drawRoundedRect(accent_rect, 2, 2)
        chip_x = r.left() + self.ACCENT_W + self.PAD; chip_y = r.top() + (r.height()-self.CHIP_SIZE)//2
        chip_r = QRect(chip_x, chip_y, self.CHIP_SIZE, self.CHIP_SIZE)
        chip_bg = QColor(badge_bg); chip_bg.setAlpha(40 if not selected else 60)
        painter.setBrush(QBrush(chip_bg)); painter.drawRoundedRect(chip_r, 5, 5)
        px = qta.icon(icon_name, color=badge_bg).pixmap(13, 13)
        painter.drawPixmap(chip_x+(self.CHIP_SIZE-13)//2, chip_y+(self.CHIP_SIZE-13)//2, px)
        trash_x = r.right()-self.TRASH_SIZE-self.PAD; trash_y = r.top()+(r.height()-self.TRASH_SIZE)//2
        trash_r = QRect(trash_x, trash_y, self.TRASH_SIZE, self.TRASH_SIZE)
        index.model().setData(index, trash_r, Qt.UserRole+1)
        if hovered or selected:
            painter.setBrush(QBrush(QColor("#FEE2E2"))); painter.drawRoundedRect(trash_r, 4, 4)
        trash_px = qta.icon("fa5s.trash-alt", color="#EF4444" if (hovered or selected) else "#CBD5E1").pixmap(11,11)
        painter.drawPixmap(trash_x+(self.TRASH_SIZE-11)//2, trash_y+(self.TRASH_SIZE-11)//2, trash_px)
        text_x = chip_x+self.CHIP_SIZE+self.PAD; text_w = trash_x-text_x-self.PAD
        display_type = name; display_value = ''
        if ': ' in name:
            parts = name.split(': ', 1); display_type = parts[0].strip(); display_value = parts[1].strip()
        type_font = QFont(); type_font.setPointSize(9); type_font.setWeight(QFont.DemiBold)
        painter.setFont(type_font); painter.setPen(QColor('#1E293B') if selected else QColor('#334155'))
        if display_value:
            type_fm = QFontMetrics(type_font)
            painter.drawText(QRect(text_x, r.top()+3, text_w, r.height()//2), Qt.AlignLeft|Qt.AlignBottom, type_fm.elidedText(display_type, Qt.ElideRight, text_w))
            value_font = QFont(); value_font.setPointSize(8); painter.setFont(value_font); painter.setPen(QColor('#94A3B8'))
            value_fm = QFontMetrics(value_font)
            painter.drawText(QRect(text_x, r.top()+r.height()//2, text_w, r.height()//2-3), Qt.AlignLeft|Qt.AlignTop, value_fm.elidedText(display_value, Qt.ElideRight, text_w))
        else:
            type_fm = QFontMetrics(type_font)
            painter.drawText(QRect(text_x, r.top(), text_w, r.height()), Qt.AlignLeft|Qt.AlignVCenter, type_fm.elidedText(display_type, Qt.ElideRight, text_w))
        if selected:
            painter.setPen(QPen(QColor('#6366F1'), 1)); painter.setBrush(Qt.NoBrush); painter.drawRoundedRect(r, 6, 6)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            trash_rect = index.data(Qt.UserRole+1)
            if trash_rect and trash_rect.contains(event.pos()):
                lw = self.parent()
                if hasattr(lw, 'delete_item_requested'): lw.delete_item_requested.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


class DeleteSignalList(QListWidget):
    delete_item_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True); self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.InternalMove); self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        p = self.parent()
        while p:
            if isinstance(p, BarcodeEditorPage): p.sync_z_order_from_list(); p.update_component_list(); break
            p = p.parent()


import json as _json


# ── General Tab ───────────────────────────────────────────────────────────────

def _fetch_sticker_data() -> dict:
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT msstnm, msheig, mswidt, mspixh, mspixw
                  FROM barcodesap.mstckr
                 WHERE msdlfg <> '1'
                 ORDER BY msstnm
                """
            )
            result = {}
            for msstnm, msheig, mswidt, mspixh, mspixw in cur.fetchall():
                result[str(msstnm).strip()] = {
                    "h_in": float(msheig) if msheig is not None else 0.0,
                    "w_in": float(mswidt) if mswidt is not None else 0.0,
                    "h_px": int(mspixh)   if mspixh is not None else 0,
                    "w_px": int(mspixw)   if mspixw is not None else 0,
                }
            return result
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_sticker_data] {e}")
        return {}


class GeneralTab(QWidget):
    stickerChanged = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._sticker_data: dict = _fetch_sticker_data()
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 20)
        root.setSpacing(0)
        label_style = (
            f"color: {COLORS['legacy_blue']}; font-size: 9px; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.4px; background: transparent; border: none;"
        )
        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(label_style)
            l.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            l.setFixedHeight(32)
            return l
        def make_input(placeholder=""):
            le = QLineEdit(); le.setPlaceholderText(placeholder)
            le.setStyleSheet(MODERN_INPUT_STYLE)
            le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return le
        READONLY_STYLE = """
            QLineEdit {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                padding: 4px 6px;
                font-size: 11px;
                color: #64748B;
            }
        """
        def make_readonly(placeholder="—"):
            le = QLineEdit(); le.setPlaceholderText(placeholder)
            le.setReadOnly(True)
            le.setStyleSheet(READONLY_STYLE)
            le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            return le
        muted_style = f"color:{COLORS['text_mute']}; font-size:10px; background:transparent; border:none;"
        card = QFrame()
        card.setStyleSheet("QFrame { background: white; border: 1px solid #E2E8F0; border-radius: 10px; }")
        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(28, 22, 28, 22)
        card_layout.setHorizontalSpacing(0)
        card_layout.setVerticalSpacing(0)
        card_layout.setColumnStretch(0, 1)
        card_layout.setColumnStretch(2, 1)
        card_layout.setColumnStretch(4, 1)
        card_layout.setColumnMinimumWidth(1, 28)
        card_layout.setColumnMinimumWidth(3, 28)
        def vdiv():
            d = QFrame()
            d.setFrameShape(QFrame.VLine)
            d.setStyleSheet("background: #E2E8F0; border: none; min-width: 1px; max-width: 1px;")
            return d
        code_block = QWidget(); code_block.setStyleSheet("background: transparent; border: none;")
        code_form = QFormLayout(code_block)
        code_form.setContentsMargins(0, 0, 32, 16)
        code_form.setVerticalSpacing(18)
        code_form.setHorizontalSpacing(14)
        code_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        code_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        code_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.code_input = make_input("")
        self.code_input.setReadOnly(True)
        self.code_input.setMaximumWidth(220)
        self.code_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFC; border: 1px solid #E2E8F0;
                border-radius: 4px; padding: 5px; font-size: 11px; color: #64748B;
            }
        """)
        self.name_input = make_input("e.g. Member Label A4")
        self.name_input.setMaximumWidth(220)
        self.status_combo = make_chevron_combo(["DISPLAY", "NOT DISPLAY"])
        self.status_combo.setMaximumWidth(220)
        code_form.addRow(lbl("CODE :"),           self.code_input)
        code_form.addRow(lbl("NAME :"),           self.name_input)
        code_form.addRow(lbl("DISPLAY STATUS :"), self.status_combo)
        card_layout.addWidget(code_block, 0, 0, Qt.AlignTop)
        hsep = QFrame()
        hsep.setFrameShape(QFrame.HLine)
        hsep.setStyleSheet("background: #E2E8F0; border: none; min-height: 1px; max-height: 1px;")
        card_layout.addWidget(hsep, 1, 0)
        card_layout.setRowMinimumHeight(1, 20)
        sticker_block = QWidget(); sticker_block.setStyleSheet("background: transparent; border: none;")
        sticker_form = QFormLayout(sticker_block)
        sticker_form.setContentsMargins(0, 16, 32, 0)
        sticker_form.setVerticalSpacing(18)
        sticker_form.setHorizontalSpacing(14)
        sticker_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        sticker_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        sticker_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)
        sticker_keys = list(self._sticker_data.keys())
        self.sticker_combo = make_chevron_combo(sticker_keys)
        self.sticker_combo.setPlaceholderText("— Please select a sticker —")
        self.sticker_combo.setCurrentIndex(-1)
        self.sticker_combo.setMaximumWidth(220)
        sticker_form.addRow(lbl("STICKER :"), self.sticker_combo)
        h_row_w = QWidget(); h_row_w.setStyleSheet("background: transparent; border: none;")
        h_hl = QHBoxLayout(h_row_w); h_hl.setContentsMargins(0, 0, 0, 0); h_hl.setSpacing(4)
        self.height_inch = make_readonly(); self.height_inch.setFixedWidth(70)
        h_hl.addWidget(self.height_inch)
        inch_lbl1 = QLabel("INCH /"); inch_lbl1.setStyleSheet(muted_style); h_hl.addWidget(inch_lbl1)
        self.height_px = make_readonly(); self.height_px.setFixedWidth(70)
        h_hl.addWidget(self.height_px)
        px_lbl1 = QLabel("PIXEL"); px_lbl1.setStyleSheet(muted_style); h_hl.addWidget(px_lbl1)
        h_hl.addStretch()
        sticker_form.addRow(lbl("HEIGHT :"), h_row_w)
        w_row_w = QWidget(); w_row_w.setStyleSheet("background: transparent; border: none;")
        w_hl = QHBoxLayout(w_row_w); w_hl.setContentsMargins(0, 0, 0, 0); w_hl.setSpacing(4)
        self.width_inch = make_readonly(); self.width_inch.setFixedWidth(70)
        w_hl.addWidget(self.width_inch)
        inch_lbl2 = QLabel("INCH /"); inch_lbl2.setStyleSheet(muted_style); w_hl.addWidget(inch_lbl2)
        self.width_px = make_readonly(); self.width_px.setFixedWidth(70)
        w_hl.addWidget(self.width_px)
        px_lbl2 = QLabel("PIXEL"); px_lbl2.setStyleSheet(muted_style); w_hl.addWidget(px_lbl2)
        w_hl.addStretch()
        sticker_form.addRow(lbl("WIDTH :"), w_row_w)
        card_layout.addWidget(sticker_block, 2, 0, Qt.AlignTop)
        card_layout.addWidget(vdiv(), 0, 1, 3, 1)
        card_layout.addWidget(vdiv(), 0, 3, 3, 1)
        col_jenis = QWidget(); col_jenis.setStyleSheet("background: transparent; border: none;")
        jenis_layout = QVBoxLayout(col_jenis)
        jenis_layout.setContentsMargins(24, 0, 0, 0)
        jenis_layout.setSpacing(8)
        jenis_layout.setAlignment(Qt.AlignTop)
        jenis_lbl = QLabel("JENIS CETAK :")
        jenis_lbl.setStyleSheet(label_style)
        jenis_layout.addWidget(jenis_lbl)
        self.chk_barcode_printer = CheckmarkCheckBox("KE BARCODE PRINTER")
        self.chk_report = CheckmarkCheckBox("KE REPORT")
        jenis_layout.addWidget(self.chk_barcode_printer)
        jenis_layout.addWidget(self.chk_report)
        jenis_layout.addStretch()
        card_layout.addWidget(col_jenis, 0, 4, 3, 1, Qt.AlignTop)
        root.addWidget(card)
        root.addStretch()
        self.sticker_combo.currentTextChanged.connect(self._on_sticker_changed)

    def _on_sticker_changed(self, key: str):
        d = self._sticker_data.get(key)
        if d:
            self.height_inch.setText(f"{d['h_in']:.2f}")
            self.height_px.setText(str(d["h_px"]))
            self.width_inch.setText(f"{d['w_in']:.2f}")
            self.width_px.setText(str(d["w_px"]))
            self.stickerChanged.emit(d["w_px"], d["h_px"])
        else:
            self.height_inch.clear(); self.height_px.clear()
            self.width_inch.clear(); self.width_px.clear()

    def sync_from_design(self, code: str, name: str, sticker_name: str = "",
                         h_in: float = 0.0, w_in: float = 0.0,
                         h_px: int = 0, w_px: int = 0, dp_fg: int = 0):
        print(f"[DEBUG sync_from_design] code={repr(code)}")
        self.code_input.setText(code)
        self.name_input.setText(name)
        self.status_combo.blockSignals(True)
        self.status_combo.setCurrentText("DISPLAY" if dp_fg == 1 else "NOT DISPLAY")
        self.status_combo.blockSignals(False)
        self.sticker_combo.blockSignals(True)
        if sticker_name and sticker_name in self._sticker_data:
            idx = self.sticker_combo.findText(sticker_name)
            if idx >= 0:
                self.sticker_combo.setCurrentIndex(idx)
            d = self._sticker_data[sticker_name]
            self.height_inch.setText(f"{d['h_in']:.2f}")
            self.height_px.setText(str(d["h_px"]))
            self.width_inch.setText(f"{d['w_in']:.2f}")
            self.width_px.setText(str(d["w_px"]))
        else:
            self.sticker_combo.setCurrentIndex(-1)
            self.height_inch.setText(f"{h_in:.2f}" if h_in else "")
            self.height_px.setText(str(h_px) if h_px else "")
            self.width_inch.setText(f"{w_in:.2f}" if w_in else "")
            self.width_px.setText(str(w_px) if w_px else "")
        self.sticker_combo.blockSignals(False)

    def get_canvas_size(self) -> tuple[int, int]:
        try: w = int(self.width_px.text())
        except (ValueError, AttributeError): w = 600
        try: h = int(self.height_px.text())
        except (ValueError, AttributeError): h = 400
        return w, h

    def get_dp_fg(self) -> int:
        return 1 if self.status_combo.currentText() == "DISPLAY" else 0


# --- Main Page ---

class BarcodeEditorPage(QWidget):
    design_saved = Signal(dict)
    _pending_code: str = ""
    _COUNTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bc_counter.json")

    @classmethod
    def _load_counter(cls) -> int:
        try:
            with open(cls._COUNTER_FILE, "r") as f:
                return int(_json_top.load(f).get("counter", 0))
        except Exception:
            return 0

    @classmethod
    def _save_counter(cls, value: int, pending: str = ""):
        try:
            with open(cls._COUNTER_FILE, "w") as f:
                _json_top.dump({"counter": value, "pending": pending}, f)
        except Exception:
            pass

    @classmethod
    def _next_code(cls) -> str:
        counter = cls._load_counter() + 1
        cls._save_counter(counter)
        return f"BC{counter:04d}"

    @classmethod
    def _reserve_code(cls) -> str:
        if not cls._pending_code:
            try:
                with open(cls._COUNTER_FILE, "r") as f:
                    data = _json_top.load(f)
                    cls._pending_code = data.get("pending", "")
            except Exception:
                cls._pending_code = ""
        if not cls._pending_code:
            counter = cls._load_counter() + 1
            cls._pending_code = f"BC{counter:04d}"
            cls._save_counter(counter, cls._pending_code)
        return cls._pending_code

    @classmethod
    def _consume_code(cls) -> str:
        code = cls._pending_code if cls._pending_code else cls._next_code()
        cls._pending_code = ""
        counter = cls._load_counter()
        cls._save_counter(counter, "")
        return code

    def __init__(self):
        super().__init__()
        self._canvas_w = 600
        self._canvas_h = 400
        self._design_code = ""
        self._design_name = ""
        self._sticker_name = ""
        self._h_in = 0.0
        self._w_in = 0.0
        self.init_ui()

    def reset_for_new(self, form_data: dict | None = None):
        SameWithRegistry.clear()
        self.scene.clearSelection()
        for item in list(self.scene.items()): self.scene.removeItem(item)
        self.component_list.clear()
        self.comp_count_badge.setText("0")
        self.prop_name_input.setText(""); self.prop_name_input.setEnabled(False)
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.view.setVisible(False)
        self._canvas_placeholder.setVisible(True)
        self._update_toolbar_buttons_state(False)
        if form_data:
            w = int(form_data.get("w_px") or 600)
            h = int(form_data.get("h_px") or 400)
            pk = form_data.get("pk", "")
            print(f"[DEBUG reset_for_new] form_data branch, pk={repr(pk)}")
            self._design_code  = pk if pk else self._reserve_code()
            self._original_pk  = self._design_code
            self._design_name  = form_data.get("name", "")
            self._sticker_name = str(form_data.get("sticker_name") or "")
            self._h_in         = float(form_data.get("h_in") or 0.0)
            self._w_in         = float(form_data.get("w_in") or 0.0)
            self._dp_fg        = int(form_data.get("dp_fg") or 0)
            if self._sticker_name:
                self._update_toolbar_buttons_state(True)
        else:
            w, h = 600, 400
            self._design_code  = self._reserve_code()
            self._original_pk  = self._design_code
            print(f"[DEBUG reset_for_new] else branch, generated code={repr(self._design_code)}")
            self._design_name  = ""
            self._sticker_name = ""
            self._h_in = self._w_in = 0.0
            self._dp_fg = 0
        self._canvas_w, self._canvas_h = w, h
        self.scene.setSceneRect(QRectF(0, 0, w, h))
        self._update_design_subtitle()
        self.general_tab.sync_from_design(
            code=self._design_code, name=self._design_name,
            sticker_name=self._sticker_name, h_in=self._h_in, w_in=self._w_in,
            h_px=h if self._sticker_name else 0, w_px=w if self._sticker_name else 0,
            dp_fg=self._dp_fg,
        )
        self.general_tab.code_input.setText(self._design_code)
        print(f"[DEBUG reset_for_new] setText called with={repr(self._design_code)}, field now={repr(self.general_tab.code_input.text())}")
        self._switch_tab(0)

    def load_design(self, row_data: tuple, row_dict: dict | None):
        self.reset_for_new()
        if row_dict:
            sticker_name = str(row_dict.get("sticker_name") or "").strip()
            w = int(row_dict.get("w_px") or self._canvas_w)
            h = int(row_dict.get("h_px") or self._canvas_h)
            h_in = float(row_dict.get("h_in") or 0.0)
            w_in = float(row_dict.get("w_in") or 0.0)
            dp_fg = int(row_dict.get("dp_fg") or 0)
            try:
                self._canvas_w, self._canvas_h = w, h
                self.scene.setSceneRect(QRectF(0, 0, w, h))
            except (TypeError, ValueError):
                pass
            self._design_code  = str(row_dict.get("pk", ""))
            self._original_pk  = self._design_code
            self._design_name  = str(row_dict.get("name", ""))
            self._sticker_name = sticker_name
            self._h_in = h_in
            self._w_in = w_in
            self._dp_fg = dp_fg
            usrm = row_dict.get("usrm") or row_dict.get("bsusrm") or ""
            if usrm:
                try: self.deserialize_canvas(_json.loads(usrm))
                except Exception as e: print(f"[load_design] Could not deserialize canvas: {e}")
            itrm = row_dict.get("itrm") or row_dict.get("bsitrm") or ""
            if itrm:
                try:
                    meta = _json.loads(itrm)
                    cw = int(meta.get("canvas_w", w)); ch = int(meta.get("canvas_h", h))
                    if cw != w or ch != h:
                        self._canvas_w, self._canvas_h = cw, ch
                        self.scene.setSceneRect(QRectF(0, 0, cw, ch))
                        w, h = cw, ch
                except Exception as e:
                    print(f"[load_design] Could not read itrm meta: {e}")
        else:
            self._design_code  = str(row_data[0]) if row_data else ""
            self._original_pk  = self._design_code
            self._design_name  = str(row_data[1]) if row_data and len(row_data) > 1 else ""
            self._sticker_name = ""
            self._h_in = self._w_in = 0.0
            self._dp_fg = 0
            w, h = self._canvas_w, self._canvas_h
        self._update_design_subtitle()
        self.general_tab.sync_from_design(
            code=self._design_code, name=self._design_name,
            sticker_name=self._sticker_name, h_in=self._h_in, w_in=self._w_in,
            h_px=self._canvas_h, w_px=self._canvas_w, dp_fg=self._dp_fg,
        )
        self._switch_tab(0)
        if self._sticker_name:
            self.view.setVisible(True)
            self._canvas_placeholder.setVisible(False)
            self._update_toolbar_buttons_state(True)
        else:
            self.view.setVisible(False)
            self._canvas_placeholder.setVisible(True)
            self._update_toolbar_buttons_state(False)

    def serialize_canvas(self) -> list[dict]:
        elements = []
        for item in self.scene.items():
            if item.group(): continue
            d = self._serialize_item(item)
            if d: elements.append(d)
        return elements

    def _serialize_item(self, item) -> dict | None:
        design_visible = getattr(item, "design_visible", True)
        base = {"x": round(item.pos().x(),2), "y": round(item.pos().y(),2), "z": item.zValue(),
                "visible": design_visible, "rotation": item.rotation(), "name": getattr(item,"component_name","")}
        if isinstance(item, BarcodeItem):
            base.update({"type":"barcode","design":item.design,"container_width":item.container_width,"container_height":item.container_height}); return base
        if isinstance(item, QGraphicsTextItem):
            font = item.font()
            color = item.defaultTextColor().name()
            base.update({
                "type": "text",
                "text": item.toPlainText(),
                "font_size": font.pointSize(),
                "font_family": font.family(),
                "bold": font.bold(),
                "italic": font.italic(),
                "color": color,
                "inverse": getattr(item, "design_inverse", False),
                "design_same_with": getattr(item, "design_same_with", ""),
                "design_type": getattr(item, "design_type", "FIX"),
            })
            return base
        if isinstance(item, QGraphicsLineItem):
            line = item.line(); pen = item.pen()
            base.update({"type":"line","x2":round(line.x2(),2),"y2":round(line.y2(),2),"thickness":pen.width()}); return base
        if isinstance(item, QGraphicsRectItem):
            rect = item.rect(); pen = item.pen()
            base.update({"type":"rect","width":round(rect.width(),2),"height":round(rect.height(),2),"border_width":pen.width()}); return base
        return None

    def deserialize_canvas(self, elements: list[dict]):
        flags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges
        for d in elements:
            kind = d.get("type"); item = None
            if kind == "text":
                item = SelectableTextItem(d.get("text",""))
                font = QFont(d.get("font_family","Arial"), d.get("font_size",10))
                font.setBold(d.get("bold",False)); font.setItalic(d.get("italic",False))
                item.setFont(font)
                item.setDefaultTextColor(QColor(d.get("color","#000000")))
                item.design_inverse = d.get("inverse", False)
                item.design_same_with = d.get("design_same_with", "")
                item.design_type = d.get("design_type", "FIX")
                item.component_name = d.get("name","Text")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "line":
                item = SelectableLineItem(0, 0, d.get("x2",100), d.get("y2",0))
                item.setPen(QPen(Qt.black, d.get("thickness",2))); item.component_name = d.get("name","Line")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "rect":
                item = SelectableRectItem(0, 0, d.get("width",100), d.get("height",50))
                item.setPen(QPen(Qt.black, d.get("border_width",2))); item.component_name = d.get("name","Rectangle")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "barcode":
                item = BarcodeItem(self.update_pos_label, design=d.get("design","CODE128"))
                item.container_width = d.get("container_width",160); item.container_height = d.get("container_height",80)
                item.component_name = d.get("name","Barcode"); item.bg.setRect(0,0,item.container_width,item.container_height)
            if item is None: continue
            item.setPos(d.get("x",0), d.get("y",0)); item.setZValue(d.get("z",0))
            item.design_visible = d.get("visible", True)
            item.setVisible(True)
            item.setRotation(d.get("rotation",0))
            self.scene.addItem(item)
            li = QListWidgetItem(self.get_component_display_name(item)); li.graphics_item = item
            self.component_list.addItem(li)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.sync_z_order_from_list()
        self._rebuild_same_with_registry()

    def get_design_payload(self) -> dict:
        elements = self.serialize_canvas()
        canvas_meta = {"canvas_w": self._canvas_w, "canvas_h": self._canvas_h}
        return {"usrm": _json.dumps(elements, separators=(",",":")), "itrm": _json.dumps(canvas_meta, separators=(",",":"))}

    def _update_design_subtitle(self): pass

    def _on_sticker_canvas_resize(self, w_px: int, h_px: int):
        if w_px <= 0 or h_px <= 0: return
        self._canvas_w, self._canvas_h = w_px, h_px
        self.scene.setSceneRect(QRectF(0, 0, w_px, h_px))
        self._sticker_name = self.general_tab.sticker_combo.currentText()
        self.view.setVisible(True)
        self._canvas_placeholder.setVisible(False)
        self._update_toolbar_buttons_state(True)

    def _switch_tab(self, index: int):
        self._tab_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            btn.setStyleSheet(TAB_ACTIVE_STYLE if i == index else TAB_INACTIVE_STYLE)

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        header_bar = QWidget()
        header_bar.setStyleSheet("QWidget#headerBar { background: white; border-bottom: 1px solid #E2E8F0; }")
        header_bar.setObjectName("headerBar")
        header_bar.setFixedHeight(56)
        header_bar_layout = QHBoxLayout(header_bar)
        header_bar_layout.setContentsMargins(24, 0, 24, 0)
        header_bar_layout.setSpacing(0)
        self._tab_btns = []
        for i, label in enumerate(["GENERAL", "EDITOR"]):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(56)
            btn.setStyleSheet(TAB_ACTIVE_STYLE if i == 0 else TAB_INACTIVE_STYLE)
            btn.clicked.connect(lambda checked=False, idx=i: self._switch_tab(idx))
            header_bar_layout.addWidget(btn)
            self._tab_btns.append(btn)
        header_bar_layout.addStretch()
        self.back_btn = StandardButton("Cancel", icon_name="fa5s.times", variant="secondary")
        self.back_btn.setToolTip("Cancel and return to list")
        self.back_btn.setFixedHeight(34)
        header_bar_layout.addWidget(self.back_btn)
        header_bar_layout.addSpacing(8)
        self.save_btn = StandardButton("Save Design", icon_name="fa5s.save", variant="primary")
        self.save_btn.setFixedHeight(34)
        header_bar_layout.addWidget(self.save_btn)
        self.main_layout.addWidget(header_bar)
        self._tab_stack = QStackedWidget()
        self._tab_stack.setStyleSheet("background: transparent;")
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setFrameShape(QFrame.NoFrame)
        general_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        general_scroll.setStyleSheet(f"background: {COLORS['bg_main']}; border: none;")
        general_scroll.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.general_tab = GeneralTab()
        general_scroll.setWidget(self.general_tab)
        self._tab_stack.addWidget(general_scroll)
        editor_page = QWidget()
        editor_page.setStyleSheet(f"background: {COLORS['bg_main']};")
        editor_layout = QVBoxLayout(editor_page)
        editor_layout.setContentsMargins(40, 20, 40, 12)
        editor_layout.setSpacing(0)
        self.btn_add_text = StandardButton("Text",    icon_name="fa5s.font",    variant="secondary")
        self.btn_add_rect = StandardButton("Rect",    icon_name="fa5s.square",  variant="secondary")
        self.btn_add_line = StandardButton("Line",    icon_name="fa5s.minus",   variant="secondary")
        self.btn_add_code = StandardButton("Barcode", icon_name="fa5s.barcode", variant="secondary")
        editor_toolbar = QHBoxLayout(); editor_toolbar.setSpacing(6)
        editor_toolbar.addWidget(self.btn_add_text); editor_toolbar.addWidget(self.btn_add_rect)
        editor_toolbar.addWidget(self.btn_add_line); editor_toolbar.addWidget(self.btn_add_code)
        editor_toolbar.addStretch()
        editor_layout.addLayout(editor_toolbar); editor_layout.addSpacing(18)
        workspace_layout = QHBoxLayout()
        self.scene = GridGraphicsScene(QRectF(0,0,self._canvas_w,self._canvas_h), grid_size=20, color=QColor("#E2E8F0"))
        self.scene.setBackgroundBrush(QBrush(QColor(COLORS["canvas_bg"])))
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background: #E8EDF3; border: 1px solid #CBD5E1; border-radius: 8px;")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.view.horizontalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self._canvas_placeholder = QFrame()
        self._canvas_placeholder.setStyleSheet("QFrame { background: #F8FAFC; border: 2px dashed #CBD5E1; border-radius: 8px; }")
        placeholder_layout = QVBoxLayout(self._canvas_placeholder)
        placeholder_layout.setAlignment(Qt.AlignCenter)
        ph_icon = QLabel()
        ph_icon.setPixmap(qta.icon("fa5s.image", color="#CBD5E1").pixmap(40, 40))
        ph_icon.setAlignment(Qt.AlignCenter)
        ph_text = QLabel("Please select a sticker first\nfrom the General tab to enable the canvas.")
        ph_text.setAlignment(Qt.AlignCenter)
        ph_text.setStyleSheet("color: #94A3B8; font-size: 12px; background: transparent; border: none;")
        placeholder_layout.addWidget(ph_icon)
        placeholder_layout.addSpacing(8)
        placeholder_layout.addWidget(ph_text)
        workspace_layout.addWidget(self.view, stretch=3)
        workspace_layout.addWidget(self._canvas_placeholder, stretch=3)
        self.view.setVisible(False)
        self._canvas_placeholder.setVisible(True)
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setStyleSheet(f"QFrame {{ background: {COLORS['white']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}")
        sidebar_layout = QVBoxLayout(self.sidebar); sidebar_layout.setContentsMargins(10,10,10,10); sidebar_layout.setSpacing(10)
        comp_header = QWidget(); comp_header.setStyleSheet("background: transparent; border: none;")
        comp_header_layout = QHBoxLayout(comp_header); comp_header_layout.setContentsMargins(2,4,2,4)
        comp_icon = QLabel(); comp_icon.setPixmap(qta.icon("fa5s.layer-group", color="#6366F1").pixmap(13,13))
        comp_header_layout.addWidget(comp_icon)
        components_label = QLabel("COMPONENTS"); components_label.setStyleSheet("font-weight: 800; font-size: 9pt; color: #1E293B; letter-spacing: 1px;")
        comp_header_layout.addWidget(components_label); comp_header_layout.addStretch()
        self.comp_count_badge = QLabel("0"); self.comp_count_badge.setAlignment(Qt.AlignCenter)
        self.comp_count_badge.setFixedSize(20,20); self.comp_count_badge.setStyleSheet("background: #6366F1; color: white; border-radius: 10px; font-weight: 700;")
        comp_header_layout.addWidget(self.comp_count_badge); sidebar_layout.addWidget(comp_header)
        self.component_list = DeleteSignalList()
        self.component_list.setSpacing(2); self.component_list.setMouseTracking(True)
        self.component_list.viewport().setMouseTracking(True)
        self.component_list.setSelectionMode(QListWidget.SingleSelection); self.component_list.setFocusPolicy(Qt.NoFocus)
        self.component_list.setStyleSheet(f"QListWidget {{ border: none; background: transparent; outline: none; }}\n{MODERN_SCROLLBAR_STYLE}")
        self.component_list.setItemDelegate(ComponentItemDelegate(self.component_list))
        self.component_list.delete_item_requested.connect(self.delete_component)
        self.component_list.itemClicked.connect(self.sync_selection_from_list)
        sidebar_layout.addWidget(self.component_list, stretch=2)
        divider = QFrame(); divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(f"background-color: {COLORS['border']}; min-height: 1px;")
        sidebar_layout.addWidget(divider)
        prop_header = QWidget(); prop_header.setStyleSheet("QWidget { background: transparent; border: none; padding: 2px 0px; }")
        prop_header_layout = QHBoxLayout(prop_header); prop_header_layout.setContentsMargins(8,6,8,6); prop_header_layout.setSpacing(4)
        prop_icon = QLabel(); prop_icon.setPixmap(qta.icon("fa5s.sliders-h", color="#6366F1").pixmap(14,14))
        prop_header_layout.addWidget(prop_icon)
        prop_static_label = QLabel("PROPERTIES")
        prop_static_label.setStyleSheet("font-weight: 700; font-size: 9pt; color: #64748B; letter-spacing: 0.5px; background: transparent; padding: 0px;")
        prop_header_layout.addWidget(prop_static_label)
        separator = QLabel("—"); separator.setStyleSheet("color: #CBD5E1; font-weight: 400; background: transparent; padding: 0px 2px;")
        prop_header_layout.addWidget(separator)
        self.prop_name_input = QLineEdit("")
        self.prop_name_input.setPlaceholderText("select component"); self.prop_name_input.setFixedHeight(24)
        self.prop_name_input.setStyleSheet("""
            QLineEdit { font-weight:700; font-size:9pt; color:#1E293B; letter-spacing:0.3px; background:#EEF2FF; border:none; border-radius:4px; padding:2px 8px; }
            QLineEdit:focus { border:none; background:#E0E7FF; }
            QLineEdit:disabled { background:#F1F5F9; color:#94A3B8; border:none; border-radius:4px; }
        """)
        self.prop_name_input.textChanged.connect(self.update_current_component_name)
        prop_header_layout.addWidget(self.prop_name_input, stretch=1); sidebar_layout.addWidget(prop_header)
        self.scroll_area = ConstrainedScrollArea()
        self.scroll_area.setWidgetResizable(True); self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"QScrollArea {{ background: {COLORS['prop_bg']}; border-radius: 8px; border: none; }}\n{MODERN_SCROLLBAR_STYLE}")
        self.scroll_area.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.inspector_widget = QWidget(); self.inspector_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.inspector_layout = QVBoxLayout(self.inspector_widget); self.inspector_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.inspector_widget); sidebar_layout.addWidget(self.scroll_area, stretch=3)
        workspace_layout.addWidget(self.sidebar, stretch=1)
        editor_layout.addLayout(workspace_layout)
        self._tab_stack.addWidget(editor_page)
        self.main_layout.addWidget(self._tab_stack)
        self._switch_tab(0)
        self.general_tab.stickerChanged.connect(self._on_sticker_canvas_resize)
        self.btn_add_text.clicked.connect(lambda: self.add_element("text"))
        self.btn_add_rect.clicked.connect(lambda: self.add_element("rect"))
        self.btn_add_line.clicked.connect(lambda: self.add_element("line"))
        self.btn_add_code.clicked.connect(lambda: self.add_element("barcode"))
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.scene.selectionChanged.connect(self.on_selection_changed)
        self._clipboard_item = None
        self._setup_copy_paste_shortcuts()
        self.setFocusPolicy(Qt.StrongFocus)
        self.view.setFocusPolicy(Qt.StrongFocus)

    def _setup_copy_paste_shortcuts(self):
        from PySide6.QtGui import QShortcut, QKeySequence
        self._shortcut_copy = QShortcut(QKeySequence("Ctrl+C"), self)
        self._shortcut_copy.setContext(Qt.ApplicationShortcut)
        self._shortcut_copy.activated.connect(self._copy_selected)
        self._shortcut_paste = QShortcut(QKeySequence("Ctrl+V"), self)
        self._shortcut_paste.setContext(Qt.ApplicationShortcut)
        self._shortcut_paste.activated.connect(self._paste_clipboard)
        self._shortcut_duplicate = QShortcut(QKeySequence("Ctrl+D"), self)
        self._shortcut_duplicate.setContext(Qt.ApplicationShortcut)
        self._shortcut_duplicate.activated.connect(self._duplicate_selected)
        self._shortcut_delete = QShortcut(QKeySequence("Delete"), self)
        self._shortcut_delete.setContext(Qt.ApplicationShortcut)
        self._shortcut_delete.activated.connect(self._delete_selected_item)

    def _delete_selected_item(self):
        selected = self.scene.selectedItems()
        if not selected: return
        item = selected[0]
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox(self)
        reply.setWindowTitle("Delete Component")
        reply.setText("Are you sure you want to delete this component?")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        reply.setDefaultButton(QMessageBox.Cancel)
        reply.setIcon(QMessageBox.Warning)
        if reply.exec() != QMessageBox.Yes: return
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == item:
                self.delete_component(i, confirmed=True); break

    def _update_toolbar_buttons_state(self, enabled: bool):
        self.btn_add_text.setEnabled(enabled)
        self.btn_add_rect.setEnabled(enabled)
        self.btn_add_line.setEnabled(enabled)
        self.btn_add_code.setEnabled(enabled)
        disabled_style = """
            QPushButton {
                background: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 6px;
                padding: 6px 12px; font-size: 12px; color: #94A3B8;
            }
            QPushButton:hover { background: #F1F5F9; border: 1px solid #CBD5E1; }
        """
        enabled_style = """
            QPushButton {
                background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px;
                padding: 6px 12px; font-size: 12px; color: #334155;
            }
            QPushButton:hover { background: #F8FAFC; border: 1px solid #94A3B8; }
        """
        style = enabled_style if enabled else disabled_style
        for btn in [self.btn_add_text, self.btn_add_rect, self.btn_add_line, self.btn_add_code]:
            btn.setStyleSheet(style)
            btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)

    def _copy_selected(self):
        selected = self.scene.selectedItems()
        if not selected: return
        self._clipboard_item = self._serialize_item(selected[0])

    def _paste_clipboard(self):
        if not self._clipboard_item or not self._sticker_name: return
        data = self._clipboard_item.copy()
        offset = 20
        data['x'] = max(0, min(data.get('x', 0) + offset, self._canvas_w - 50))
        data['y'] = max(0, min(data.get('y', 0) + offset, self._canvas_h - 50))
        item = self._create_item_from_data(data)
        if not item: return
        self.scene.addItem(item)
        li = QListWidgetItem(self.get_component_display_name(item))
        li.graphics_item = item
        self.component_list.insertItem(0, li)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.scene.clearSelection()
        item.setSelected(True)
        self.sync_z_order_from_list()

    def _duplicate_selected(self):
        self._copy_selected(); self._paste_clipboard()

    def _create_item_from_data(self, data: dict):
        kind = data.get('type')
        flags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges
        if kind == 'text':
            item = SelectableTextItem(data.get('text', ''))
            font = QFont(data.get('font_family', 'Arial'), data.get('font_size', 10))
            font.setBold(data.get('bold', False)); font.setItalic(data.get('italic', False))
            item.setFont(font)
            item.component_name = data.get('name', 'Text')
            item.setDefaultTextColor(QColor(data.get('color', '#000000')))
            item.design_same_with = ""  # new items don't inherit same-with
            item.design_type = "FIX"
            setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
        elif kind == 'line':
            item = SelectableLineItem(0, 0, data.get('x2', 100), data.get('y2', 0))
            item.setPen(QPen(QColor(data.get('color', '#000000')), data.get('thickness', 2)))
            item.component_name = data.get('name', 'Line')
            setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
        elif kind == 'rect':
            item = SelectableRectItem(0, 0, data.get('width', 100), data.get('height', 50))
            item.setPen(QPen(QColor(data.get('border_color', '#000000')), data.get('border_width', 2)))
            item.component_name = data.get('name', 'Rectangle')
            setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
        elif kind == 'barcode':
            item = BarcodeItem(self.update_pos_label, design=data.get('design', 'CODE128'))
            item.container_width = data.get('container_width', 160)
            item.container_height = data.get('container_height', 80)
            item.component_name = data.get('name', 'Barcode')
            item.bg.setRect(0, 0, item.container_width, item.container_height)
        else:
            return None
        item.setPos(data.get('x', 0), data.get('y', 0))
        item.setZValue(data.get('z', 0))
        item.design_visible = data.get('visible', True)
        item.setVisible(True)
        item.setRotation(data.get('rotation', 0))
        return item

    def _on_save_clicked(self):
        selected_sticker = self.general_tab.sticker_combo.currentText()
        if selected_sticker and not selected_sticker.startswith("—"):
            self._sticker_name = selected_sticker
        elif selected_sticker and selected_sticker.startswith("—"):
            self._sticker_name = ""
        code_val = self.general_tab.code_input.text().strip()
        name_val = self.general_tab.name_input.text().strip()
        if self.__class__._pending_code and self._design_code == self.__class__._pending_code:
            self._consume_code()
        if name_val: self._design_name = name_val
        dp_fg = self.general_tab.get_dp_fg()
        try: self._canvas_w = int(self.general_tab.width_px.text())
        except (ValueError, AttributeError): pass
        try: self._canvas_h = int(self.general_tab.height_px.text())
        except (ValueError, AttributeError): pass
        try: h_in = float(self.general_tab.height_inch.text())
        except (ValueError, AttributeError): h_in = getattr(self, "_h_in", 0.0)
        try: w_in = float(self.general_tab.width_inch.text())
        except (ValueError, AttributeError): w_in = getattr(self, "_w_in", 0.0)
        payload = self.get_design_payload()
        payload["pk"]           = self._design_code
        payload["original_pk"]  = getattr(self, "_original_pk", self._design_code)
        payload["name"]         = self._design_name
        payload["dp_fg"]        = dp_fg
        payload["sticker_name"] = self._sticker_name
        payload["w_px"]         = self._canvas_w
        payload["h_px"]         = self._canvas_h
        payload["h_in"]         = h_in
        payload["w_in"]         = w_in
        self.design_saved.emit(payload)

    def sync_z_order_from_list(self):
        count = self.component_list.count()
        for i in range(count):
            li = self.component_list.item(i)
            gi = getattr(li, 'graphics_item', None)
            if gi: gi.setZValue(count - i)

    def delete_component(self, row, confirmed=False):
        li = self.component_list.item(row)
        if not li: return
        if not confirmed:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox(self)
            reply.setWindowTitle("Delete Component")
            reply.setText("Are you sure you want to delete this component?")
            reply.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            reply.setDefaultButton(QMessageBox.Cancel)
            reply.setIcon(QMessageBox.Warning)
            if reply.exec() != QMessageBox.Yes: return
        gi = getattr(li, 'graphics_item', None)
        if gi:
            SameWithRegistry.unregister(gi)
        self.scene.blockSignals(True); self.component_list.blockSignals(True)
        if gi and gi.scene() == self.scene: self.scene.removeItem(gi)
        self.component_list.takeItem(row)
        self.scene.blockSignals(False); self.component_list.blockSignals(False)
        self.comp_count_badge.setText(str(self.component_list.count())); self.on_selection_changed()

    def get_component_display_name(self, item):
        component_name = getattr(item, 'component_name', '')
        if isinstance(item, BarcodeItem):
            comp_type = "Barcode"; comp_value = getattr(item, 'design', 'CODE128')
            if not component_name: component_name = "Barcode"
        elif isinstance(item, QGraphicsTextItem):
            comp_type = "Text"; text_val = item.toPlainText()[:20]; comp_value = text_val if text_val else "Empty"
            if not component_name: component_name = "Text"
        elif isinstance(item, QGraphicsLineItem):
            comp_type = "Line"; comp_value = f"{int(item.line().length())}px"
            if not component_name: component_name = "Line"
        elif isinstance(item, QGraphicsRectItem):
            comp_type = "Rectangle"; rect = item.rect(); comp_value = f"{int(rect.width())}x{int(rect.height())}"
            if not component_name: component_name = "Rectangle"
        else:
            comp_type = "Item"; comp_value = ""
            if not component_name: component_name = "Item"
        return f"{comp_type} - {component_name}: {comp_value}"

    def update_component_list(self):
        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            gi = getattr(li, 'graphics_item', None)
            if gi: li.setText(self.get_component_display_name(gi))
        existing = [getattr(self.component_list.item(i), 'graphics_item', None) for i in range(self.component_list.count())]
        items_to_add = []
        for item in self.scene.items():
            if item.group() or item.scene() != self.scene: continue
            if item not in existing:
                li = QListWidgetItem(self.get_component_display_name(item)); li.graphics_item = item
                self.component_list.insertItem(0, li); items_to_add.append(li)
        if items_to_add:
            self.component_list.scrollToTop()
            sel = self.scene.selectedItems()
            if sel:
                for i in range(self.component_list.count()):
                    li = self.component_list.item(i)
                    if getattr(li, 'graphics_item', None) == sel[0]: self.component_list.setCurrentItem(li); break
        self.comp_count_badge.setText(str(self.component_list.count())); self.component_list.blockSignals(False)
        self._sync_same_with_items()

    def _sync_same_with_items(self):
        """After any item change, sync all SAME WITH dependents from their source."""
        name_to_item = {}
        for scene_item in self.scene.items():
            if scene_item.group(): continue
            if isinstance(scene_item, SelectableTextItem):
                name = getattr(scene_item, "component_name", "")
                if name:
                    name_to_item[name] = scene_item
        for scene_item in self.scene.items():
            if scene_item.group(): continue
            if not isinstance(scene_item, SelectableTextItem): continue
            if getattr(scene_item, "design_type", "") != "SAME WITH": continue
            ref_name = getattr(scene_item, "design_same_with", "")
            if not ref_name: continue
            source = name_to_item.get(ref_name)
            if not source or source is scene_item: continue
            if getattr(source, "design_type", "") == "SAME WITH":
                scene_item.design_same_with = ""
                SameWithRegistry.unregister(scene_item)
                continue
            # Keep registry up-to-date so live-edit sync always works
            SameWithRegistry.register(scene_item, source)
            # Sync all visual + data properties
            if scene_item.toPlainText() != source.toPlainText():
                scene_item.setPlainText(source.toPlainText())
            if scene_item.font() != source.font():
                scene_item.setFont(source.font())
            if scene_item.defaultTextColor() != source.defaultTextColor():
                scene_item.setDefaultTextColor(source.defaultTextColor())
            scene_item.design_inverse = getattr(source, "design_inverse", False)
            scene_item.design_visible = getattr(source, "design_visible", True)

    def _rebuild_same_with_registry(self):
        """Rebuild SameWithRegistry from current scene items.

        Must be called:
          - after deserialize_canvas() so loaded designs work immediately
          - before opening a TextPropertyEditor so SAME WITH lock state is correct
        """
        name_to_item = {}
        for scene_item in self.scene.items():
            if scene_item.group():
                continue
            if isinstance(scene_item, SelectableTextItem):
                name = getattr(scene_item, "component_name", "")
                if name:
                    name_to_item[name] = scene_item
        for scene_item in self.scene.items():
            if scene_item.group():
                continue
            if not isinstance(scene_item, SelectableTextItem):
                continue
            if getattr(scene_item, "design_type", "") != "SAME WITH":
                continue
            ref_name = getattr(scene_item, "design_same_with", "")
            if not ref_name:
                continue
            source = name_to_item.get(ref_name)
            if source and source is not scene_item:
                if getattr(source, "design_type", "") != "SAME WITH":
                    SameWithRegistry.register(scene_item, source)

    def update_current_component_name(self, name):
        sel = self.scene.selectedItems()
        if not sel: return
        item = sel[0]
        old_name = getattr(item, "component_name", "")
        new_name = name if name else "Unnamed"
        item.component_name = new_name
        if old_name != new_name:
            for scene_item in self.scene.items():
                if getattr(scene_item, "design_same_with", "") == old_name:
                    scene_item.design_same_with = new_name
            # If the currently open editor is a SAME WITH item pointing to the
            # renamed component, update its combo to show the new name live
            editor = getattr(self, "current_editor", None)
            if editor and isinstance(editor, TextPropertyEditor):
                combo = editor.same_with_combo
                # Update the item in the list that matched old_name
                combo._items = [new_name if i == old_name else i for i in combo._items]
                if combo._current == old_name:
                    combo._current = new_name
                    combo._label.setText(new_name)
        self.update_component_list()

    def sync_selection_from_list(self, li):
        item = getattr(li, 'graphics_item', None)
        if item:
            self.scene.blockSignals(True); self.scene.clearSelection(); item.setSelected(True)
            self.scene.blockSignals(False); self.on_selection_changed()

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        if not selected_items:
            self.component_list.clearSelection(); self.prop_name_input.setText("")
            self.prop_name_input.setPlaceholderText("select component"); self.prop_name_input.setEnabled(False); return
        selected = selected_items[0]
        current_name = getattr(selected, 'component_name', '')
        self.prop_name_input.blockSignals(True)
        if current_name:
            self.prop_name_input.setText(current_name)
        else:
            defaults = {BarcodeItem:"Barcode", QGraphicsTextItem:"Text", QGraphicsLineItem:"Line", QGraphicsRectItem:"Rectangle"}
            self.prop_name_input.setText(next((v for k,v in defaults.items() if isinstance(selected,k)), "Item"))
        self.prop_name_input.setEnabled(True); self.prop_name_input.blockSignals(False)
        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == selected: self.component_list.setCurrentItem(li); break
        self.component_list.blockSignals(False)
        # Rebuild SameWithRegistry before opening editor so lock state is correct on load
        self._rebuild_same_with_registry()
        self.current_editor = None
        if isinstance(selected, BarcodeItem): self.current_editor = BarcodePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsTextItem): self.current_editor = TextPropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsLineItem): self.current_editor = LinePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsRectItem): self.current_editor = RectanglePropertyEditor(selected, self.update_component_list)
        if self.current_editor: self.inspector_layout.addWidget(self.current_editor)

    def add_element(self, kind):
        self.scene.clearSelection()
        flags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges
        if kind == "text":
            item = SelectableTextItem("LABEL_VAR"); item.setFont(QFont("Arial",10))
            item.component_name = "Text"
            item.design_same_with = ""
            item.design_type = "FIX"
            setup_item_logic(item, self.update_pos_label)
        elif kind == "rect":
            item = SelectableRectItem(0,0,100,50); item.setPen(QPen(Qt.black,2))
            item.component_name = "Rectangle"; setup_item_logic(item, self.update_pos_label)
        elif kind == "line":
            item = SelectableLineItem(0,0,100,0); item.setPen(QPen(Qt.black,2))
            item.component_name = "Line"; setup_item_logic(item, self.update_pos_label)
        elif kind == "barcode":
            item = BarcodeItem(self.update_pos_label)
        if not isinstance(item, BarcodeItem): item.setFlags(flags)
        self.scene.addItem(item)
        li = QListWidgetItem(self.get_component_display_name(item)); li.graphics_item = item
        self.component_list.insertItem(0, li); self.comp_count_badge.setText(str(self.component_list.count()))
        item.setSelected(True); item.setPos(50, 50); self.sync_z_order_from_list()

    def update_pos_label(self, pos):
        editor = getattr(self, "current_editor", None)
        if not editor: return
        if not shiboken6.isValid(editor): self.current_editor = None; return
        if hasattr(editor, "update_position_fields"): editor.update_position_fields(pos)