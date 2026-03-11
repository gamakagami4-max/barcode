"""Shared utilities, styles, and small widgets for the barcode editor."""

import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QApplication, QScrollArea, QSizePolicy, QPushButton,
    QSpinBox, QCheckBox
)
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, QSize, QEvent, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QFontMetrics, QCursor

# ── Colour palette ────────────────────────────────────────────────────────────

COLORS = {
    "bg_main":    "#F8FAFC",
    "link":       "#6366F1",
    "border":     "#E2E8F0",
    "text_dark":  "#1E293B",
    "text_mute":  "#64748B",
    "white":      "#FFFFFF",
    "prop_bg":    "#F1F5F9",
    "canvas_bg":  "#E1E7EF",
    "legacy_blue": "#1E3A8A",
}

# ── Stylesheet constants ──────────────────────────────────────────────────────

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
        border: none; background: #F1F5F9; width: 12px;
        margin: 4px 2px; border-radius: 6px;
    }
    QScrollBar::handle:vertical {
        background: #94A3B8; border-radius: 5px; min-height: 32px; margin: 1px;
    }
    QScrollBar::handle:vertical:hover  { background: #6366F1; }
    QScrollBar::handle:vertical:pressed { background: #4338CA; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar:horizontal {
        border: none; background: #F1F5F9; height: 12px;
        margin: 2px 4px; border-radius: 6px;
    }
    QScrollBar::handle:horizontal {
        background: #94A3B8; border-radius: 5px; min-width: 32px; margin: 1px;
    }
    QScrollBar::handle:horizontal:hover  { background: #6366F1; }
    QScrollBar::handle:horizontal:pressed { background: #4338CA; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""

TAB_ACTIVE_STYLE = """
    QPushButton {
        background: transparent; border: none;
        border-bottom: 2px solid #6366F1; border-radius: 0px;
        padding: 0px 16px; font-size: 11px; font-weight: 700;
        color: #6366F1; letter-spacing: 0.5px;
    }
"""

TAB_INACTIVE_STYLE = """
    QPushButton {
        background: transparent; border: none;
        border-bottom: 2px solid transparent; border-radius: 0px;
        padding: 0px 16px; font-size: 11px; font-weight: 600;
        color: #94A3B8; letter-spacing: 0.5px;
    }
    QPushButton:hover { color: #475569; border-bottom: 2px solid #CBD5E1; }
"""

_LINE_DISABLED = """
    QLineEdit {
        background-color: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
    }
"""

# ── Canvas helpers ────────────────────────────────────────────────────────────

def keep_within_bounds(item, new_pos):
    """Constrain item movement so its visual AABB stays within the scene rect.

    The OLD implementation clamped pos() directly to scene bounds:
        x = max(scene_rect.left(), new_pos.x())

    That is wrong for rotated items because pos() is the local origin, not the
    visual top-left.  At 90°/270° the AABB top-left is offset from pos() by
    off_x = (width - height) / 2 ≈ 23-30 px for typical text labels.  Clamping
    pos.x >= 0 therefore prevented the AABB from reaching x=0, producing the
    hard ~30 px floor that users could not drag past.

    The correct approach:
      1. Compute the current AABB→pos() offset (rotation-dependent, but
         constant for a given rotation — independent of translation).
      2. Project new_pos into AABB space, clamp there, project back.
    """
    scene_rect = item.scene().sceneRect()

    # Current AABB in scene coordinates
    aabb = item.mapToScene(item.boundingRect()).boundingRect()

    # Offset between pos() and AABB top-left — constant for a given rotation.
    off_x = aabb.left() - item.pos().x()
    off_y = aabb.top()  - item.pos().y()

    # Where the AABB top-left would land at new_pos
    new_aabb_x = new_pos.x() + off_x
    new_aabb_y = new_pos.y() + off_y

    # Clamp AABB to scene bounds
    clamped_x = max(scene_rect.left(),
                    min(new_aabb_x, scene_rect.right()  - aabb.width()))
    clamped_y = max(scene_rect.top(),
                    min(new_aabb_y, scene_rect.bottom() - aabb.height()))

    # Convert back to pos() space
    return QPointF(clamped_x - off_x, clamped_y - off_y)


def setup_item_logic(item, on_move_callback):
    from PySide6.QtWidgets import QGraphicsItem
    original_item_change = item.itemChange

    def patched_item_change(change, value):
        if change == QGraphicsItem.ItemPositionChange and item.scene():
            new_pos = keep_within_bounds(item, value)
            on_move_callback(new_pos)
            return new_pos
        return original_item_change(change, value)

    item.itemChange = patched_item_change


# ── CheckmarkCheckBox ─────────────────────────────────────────────────────────

class CheckmarkCheckBox(QCheckBox):
    """QCheckBox that draws a dark tick on white."""

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QCheckBox { font-size: 11px; color: #334155; spacing: 6px; background: transparent; }
            QCheckBox::indicator { width: 0px; height: 0px; }
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
            painter.drawLine(QPointF(x + s*0.18, y + s*0.52), QPointF(x + s*0.42, y + s*0.76))
            painter.drawLine(QPointF(x + s*0.42, y + s*0.76), QPointF(x + s*0.82, y + s*0.24))
        text_x = box_size + 6
        painter.setPen(QColor("#334155"))
        font = self.font()
        font.setPixelSize(11)
        painter.setFont(font)
        painter.drawText(
            QRect(text_x, 0, self.width() - text_x, self.height()),
            Qt.AlignVCenter | Qt.AlignLeft, self.text(),
        )
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setChecked(not self.isChecked())
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)


# ── Custom combo dropdown ─────────────────────────────────────────────────────

class _ComboDropdown(QFrame):
    optionSelected = Signal(str)
    _ITEM_H = 32; _PAD = 4; _MAX_H = 260

    def __init__(self, options, selected, width):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet("QFrame { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; }")
        self._options  = [str(o) for o in options]
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
            QScrollBar:vertical { border: none; background: #F4F4F5; width: 6px;
                margin: 4px 2px; border-radius: 3px; }
            QScrollBar::handle:vertical { background: #D4D4D8; border-radius: 3px; min-height: 20px; }
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

        # ── FIX: auto-size width to fit the longest option text ──────────────
        opt_font = QFont()
        opt_font.setPointSize(9)
        fm = QFontMetrics(opt_font)
        max_text_w = max((fm.horizontalAdvance(o) for o in self._options), default=0)
        # btn left+right padding (8+8) + scrollbar room (8) + border (2) + frame padding
        min_content_w = max_text_w + 8 + 8 + 8 + 2 + self._PAD * 2
        self.setFixedWidth(max(width, min_content_w, 160))
        self.setFixedHeight(min(content_h + 2, self._MAX_H))

    def _style_btn(self, btn, selected):
        if selected:
            btn.setStyleSheet("""
                QPushButton { background: #EFF6FF; color: #3B82F6; border: none; border-radius: 4px;
                    font-size: 12px; font-weight: 500; text-align: left; padding: 0 8px; }
                QPushButton:hover { background: #DBEAFE; color: #3B82F6; }
            """)
        else:
            btn.setStyleSheet("""
                QPushButton { background: transparent; color: #18181B; border: none; border-radius: 4px;
                    font-size: 12px; font-weight: 400; text-align: left; padding: 0 8px; }
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
        screen = QApplication.primaryScreen().availableGeometry()

        # Resize width to at least trigger width (content width already set in _build)
        new_w = max(self.width(), trigger.width())
        self.setFixedWidth(new_w)

        pos_below = trigger.mapToGlobal(trigger.rect().bottomLeft())

        # ── FIX: clamp x so dropdown never bleeds off the right (or left) edge ──
        x = pos_below.x()
        if x + self.width() > screen.right():
            x = screen.right() - self.width()
        x = max(screen.left(), x)

        if screen.bottom() - pos_below.y() < self.height():
            pos_above = trigger.mapToGlobal(trigger.rect().topLeft())
            self.move(x, pos_above.y() - self.height())
        else:
            self.move(x, pos_below.y())
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
        self._label = QLabel()
        self._label.setStyleSheet("color: #18181B; font-size: 12px; background: transparent; border: none;")
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._chevron = QLabel()
        self._chevron.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._chevron.setStyleSheet("background: transparent; border: none;")
        self._set_chevron(False)
        layout.addWidget(self._label, 1)
        layout.addWidget(self._chevron, 0)

    def showEvent(self, event):
        super().showEvent(event)
        if self._current:
            self._set_label_text(self._current)

    def _apply_style(self, open_):
        border = "#3B82F6" if open_ else "#E5E7EB"
        bw     = "1.5"     if open_ else "1"
        hover  = "#3B82F6" if open_ else "#D4D4D8"
        self.setStyleSheet(f"""
            CustomCombo {{ background: #FFFFFF; border: {bw}px solid {border}; border-radius: 6px; }}
            CustomCombo:hover {{ border-color: {hover}; }}
        """)
        if self.isEnabled() and hasattr(self, '_chevron'):
            self._chevron.setVisible(True)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, '_label') and self._current:
            self._set_label_text(self._current)

    def _set_label_text(self, text, color="#18181B"):
        self._label.setStyleSheet(f"color: {color}; font-size: 12px; background: transparent; border: none;")
        fm = QFontMetrics(self._label.font())
        available = self.width() - 34
        elided = fm.elidedText(text, Qt.ElideRight, max(available, 20))
        self._label.setText(elided)
        self._label.setToolTip(text if elided != text else "")

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
                CustomCombo { background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; }
                CustomCombo:hover { border-color: #E2E8F0; }
            """)
            self._chevron.setVisible(False)

    def mousePressEvent(self, event):
        if not self.isEnabled():
            event.ignore()
            return
        if event.button() == Qt.LeftButton:
            if self._is_open: self._close()
            else:             self._open()
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
        self._set_label_text(option)
        self._close()
        if not self._signals_blocked:
            self.currentTextChanged.emit(option)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            gpos = QCursor.pos()
            in_trigger  = self.rect().contains(self.mapFromGlobal(gpos))
            in_dropdown = (self._dropdown is not None and self._dropdown.isVisible()
                           and self._dropdown.rect().contains(self._dropdown.mapFromGlobal(gpos)))
            if not in_trigger and not in_dropdown:
                self._close()
        return False

    def hideEvent(self, event):
        if self._is_open:
            self._close()
        super().hideEvent(event)

    def currentText(self):   return self._current
    def count(self):         return len(self._items)
    def itemText(self, i):   return self._items[i] if 0 <= i < len(self._items) else ""

    def setCurrentText(self, text):
        if text in self._items:
            self._current = text
            self._set_label_text(text)
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
        try:    return self._items.index(self._current)
        except ValueError: return -1

    def findText(self, text):
        try:    return self._items.index(text)
        except ValueError: return -1

    def addItems(self, items):
        self._items.extend(items)
        if not self._current and self._items:
            self._current = self._items[0]
            self._label.setText(self._current)

    def addItem(self, item): self._items.append(item)

    def setPlaceholderText(self, text):
        if not self._current:
            self._label.setText(text)
            self._label.setStyleSheet("color: #71717A; font-size: 12px; background: transparent; border: none;")

    def blockSignals(self, block):
        self._signals_blocked = block
        return super().blockSignals(block)


# ── ChevronSpinBox ────────────────────────────────────────────────────────────

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
        h = self.height(); btn_w = self._BTN_W; x_left = self.width() - btn_w
        icon_w = self._px_up.width(); icon_h = self._px_up.height()
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


def make_chevron_combo(items: list) -> CustomCombo:
    combo = CustomCombo(items)
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return combo


# ── ConstrainedScrollArea ─────────────────────────────────────────────────────

class ConstrainedScrollArea(QScrollArea):
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.widget():
            self.widget().setMaximumWidth(self.viewport().width())