import sys
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

        # ── Box ──────────────────────────────────────────────────────
        box_rect = QRect(0, y_offset, box_size, box_size)
        painter.setPen(QPen(QColor("#94A3B8" if not self.isChecked() else "#334155"), 1.5))
        painter.setBrush(QBrush(QColor("white")))
        painter.drawRoundedRect(box_rect, 3, 3)

        # ── Checkmark ────────────────────────────────────────────────
        if self.isChecked():
            pen = QPen(QColor("#334155"), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            # tick: bottom-left corner → mid-bottom → top-right
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

        # ── Label ─────────────────────────────────────────────────────
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
            event.accept()  # consume event so Qt doesn't toggle again
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
    "canvas_bg": "#F1F5F9",
    "legacy_blue": "#1E3A8A" 
}

MODERN_COMBO_STYLE = ""  # Kept for legacy references; CustomCombo is used instead


# ── Custom combo widget (bypasses Qt native dropdown which ignores stylesheets) ──

class _ComboDropdown(QFrame):
    """Floating dropdown — uses Qt.Tool (not Qt.Popup) to avoid hide-before-click race."""
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
        gpos = trigger.mapToGlobal(trigger.rect().bottomLeft())
        self.setFixedWidth(max(trigger.width(), 160))
        self.move(gpos)
        self.show()
        self.raise_()


class CustomCombo(QFrame):
    """
    Drop-in QComboBox replacement. Uses Qt.Tool popup + app event filter
    for outside-click detection (avoids Qt.Popup hide-before-click race).
    """
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

    def _set_chevron(self, open_):
        self._chevron.setPixmap(
            qta.icon("fa5s.chevron-up" if open_ else "fa5s.chevron-down",
                     color="#3B82F6" if open_ else "#71717A").pixmap(10, 10)
        )

    def mousePressEvent(self, event):
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

    # ── QComboBox-compatible API ──────────────────────────────────────

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
        if 0 <= index < len(self._items):
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
        layout.setSpacing(8)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        LABEL_W = 90  # fixed width so all labels align perfectly
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W)
            l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            return l
        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        layout.addRow(lbl("ALIGNMENT :"), self.align_combo)
        self.font_combo = make_chevron_combo(["STANDARD", "MONOSPACE", "SERIF"])
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
        self.inverse_combo.currentTextChanged.connect(self._apply_inverse)
        layout.addRow(lbl("INVERSE :"), self.inverse_combo)
        self.type_combo = make_chevron_combo(["FIX", "VAR"])
        layout.addRow(lbl("TYPE :"), self.type_combo)
        self.editor_combo = make_chevron_combo(["INVISIBLE", "VISIBLE", "READONLY"])
        layout.addRow(lbl("EDITOR :"), self.editor_combo)
        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(lbl("TEXT :"), self.text_input)
        self.caption_input = QLineEdit("LABEL 1")
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("CAPTION :"), self.caption_input)
        # WRAP TEXT and WIDTH on separate rows
        self.wrap_combo = make_chevron_combo(["NO", "YES"])
        layout.addRow(lbl("WRAP TEXT :"), self.wrap_combo)
        self.wrap_width_spin = make_spin(0, 5000, 1)
        layout.addRow(lbl("WRAP WIDTH :"), self.wrap_width_spin)
        self.group_combo = make_chevron_combo([""])
        layout.addRow(lbl("GROUP :"), self.group_combo)
        # TABLE and extra on separate rows
        self.table_combo = make_chevron_combo([""])
        layout.addRow(lbl("TABLE :"), self.table_combo)
        self.table_extra = QLineEdit(); self.table_extra.setStyleSheet(MODERN_INPUT_STYLE)
        self.table_extra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("TABLE EXTRA :"), self.table_extra)
        self.field_edit = QLineEdit(); self.field_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.field_edit.setMinimumHeight(52); self.field_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(lbl("FIELD :"), self.field_edit)
        # RESULT and TRIM on separate rows
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
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE"))
        layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "SAVE"])
        layout.addRow(lbl("SAVE FIELD :"), self.save_field_combo)
        self.column_spin = make_spin(1, 999, 1)
        layout.addRow(lbl("COLUMN :"), self.column_spin)
        self.mandatory_combo = make_chevron_combo(["FALSE", "TRUE"])
        layout.addRow(lbl("MANDATORY :"), self.mandatory_combo)

    def _set_trim_style(self, checked):
        if checked:
            self.trim_box.setText("✓"); self.trim_box.setAlignment(Qt.AlignCenter)
            self.trim_box.setStyleSheet("QLabel{border:1.5px solid #6366F1;border-radius:3px;background:#6366F1;color:white;font-size:9px;font-weight:bold;}")
        else:
            self.trim_box.setText(""); self.trim_box.setStyleSheet("QLabel{border:1.5px solid #CBD5E1;border-radius:3px;background:white;}")

    def _toggle_trim(self, event):
        self._trim_checked = not self._trim_checked; self._set_trim_style(self._trim_checked)

    def _apply_inverse(self, value):
        self.item.setDefaultTextColor(QColor("white") if value == "YES" else QColor("black"))

    def apply_text_changes(self, text):
        self.item.setPlainText(text); self.update_callback()

    def apply_font_changes(self, size):
        font = self.item.font(); font.setPointSize(size); self.item.setFont(font); self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)


class LinePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setSpacing(10)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        LABEL_W = 90
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); return l
        line = self.item.line(); pen = self.item.pen()
        self.thickness_spin = make_spin(1, 100, int(pen.width())); self.thickness_spin.valueChanged.connect(self.update_thickness); layout.addRow(lbl("THICKNESS :"), self.thickness_spin)
        self.width_spin = make_spin(0, 5000, int(abs(line.dx()))); self.width_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"]); self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE")); layout.addRow(lbl("VISIBLE :"), self.visible_combo)

    def update_geometry(self): self.item.setLine(0, 0, self.width_spin.value(), 0); self.update_callback()
    def update_thickness(self, value): pen = self.item.pen(); pen.setWidth(value); self.item.setPen(pen); self.update_callback()
    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)


class RectanglePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setSpacing(10)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label_style = f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; background: transparent; border: none;"
        LABEL_W = 90
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); return l
        rect = self.item.rect(); pen = self.item.pen()
        self.height_spin = make_spin(0, 5000, int(rect.height())); self.height_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("HEIGHT :"), self.height_spin)
        self.width_spin = make_spin(0, 5000, int(rect.width())); self.width_spin.valueChanged.connect(self.update_geometry); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.border_spin = make_spin(0, 20, int(pen.width())); self.border_spin.valueChanged.connect(self.update_border); layout.addRow(lbl("BORDER WIDTH :"), self.border_spin)
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"]); self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE")); layout.addRow(lbl("VISIBLE :"), self.visible_combo)
        self.column_spin = make_spin(1, 999, 1); layout.addRow(lbl("COLUMN :"), self.column_spin)

    def update_geometry(self): self.item.setRect(0, 0, self.width_spin.value(), self.height_spin.value()); self.update_callback()
    def update_border(self, width): pen = self.item.pen(); pen.setWidth(width); self.item.setPen(pen); self.update_callback()
    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True); self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y())); self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False); self.left_spin.blockSignals(False)


class BarcodePropertyEditor(QWidget):
    def __init__(self, target_item, update_callback):
        super().__init__()
        self.item = target_item; self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QFormLayout(self); layout.setContentsMargins(10,10,10,10); layout.setSpacing(10)
        layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        label_style = f"color:{COLORS['legacy_blue']}; font-size:9px; text-transform:uppercase; background:transparent; border:none;"
        LABEL_W = 90
        def lbl(t):
            l = QLabel(t); l.setStyleSheet(label_style)
            l.setFixedWidth(LABEL_W); l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter); return l
        self.design_combo = make_chevron_combo(["CODE128","MINIMAL","EAN13","CODE39","QR MOCK"])
        self.design_combo.setCurrentText(self.item.design); self.design_combo.currentTextChanged.connect(self.update_design); layout.addRow(lbl("DESIGN :"), self.design_combo)
        self.width_spin = make_spin(20, 1000, self.item.container_width); self.width_spin.valueChanged.connect(self.update_size); layout.addRow(lbl("WIDTH :"), self.width_spin)
        self.height_spin = make_spin(20, 1000, self.item.container_height); self.height_spin.valueChanged.connect(self.update_size); layout.addRow(lbl("HEIGHT :"), self.height_spin)
        self.top_spin = make_spin(0, 5000, int(self.item.pos().y())); self.top_spin.valueChanged.connect(lambda v: self.item.setY(v)); layout.addRow(lbl("TOP :"), self.top_spin)
        self.left_spin = make_spin(0, 5000, int(self.item.pos().x())); self.left_spin.valueChanged.connect(lambda v: self.item.setX(v)); layout.addRow(lbl("LEFT :"), self.left_spin)
        self.visible_combo = make_chevron_combo(["TRUE","FALSE"]); self.visible_combo.setCurrentText("TRUE" if self.item.isVisible() else "FALSE")
        self.visible_combo.currentTextChanged.connect(lambda v: self.item.setVisible(v == "TRUE")); layout.addRow(lbl("VISIBLE :"), self.visible_combo)

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


# --- Custom Scene Items ---

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
        root.setContentsMargins(20, 12, 20, 12)
        root.setSpacing(10)

        label_style = (
            f"color: {COLORS['legacy_blue']}; font-size: 9px; font-weight: 700; "
            "text-transform: uppercase; letter-spacing: 0.4px; background: transparent; border: none;"
        )

        def lbl(text):
            l = QLabel(text)
            l.setStyleSheet(label_style)
            l.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
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

        check_style = ""  # handled by CheckmarkCheckBox class below

        muted_style = f"color:{COLORS['text_mute']}; font-size:10px; background:transparent; border:none;"

        # ── Card ──────────────────────────────────────────────────────
        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: white; border: none; border-radius: 8px; }"
        )

        card_layout = QGridLayout(card)
        card_layout.setContentsMargins(16, 14, 16, 14)
        card_layout.setHorizontalSpacing(10)
        card_layout.setVerticalSpacing(10)
        card_layout.setColumnStretch(3, 1)  # stretch between left block and jenis cetak

        # ── LEFT TOP: Code / Name / Display Status ────────────────────
        self.code_input = make_input("e.g. BC001")
        self.code_input.setFixedWidth(160)
        self.name_input = make_input("e.g. Member Label A4")
        self.name_input.setFixedWidth(220)
        self.status_combo = make_chevron_combo(["DISPLAY", "NOT DISPLAY"])
        self.status_combo.setFixedWidth(160)

        card_layout.addWidget(lbl("CODE :"),           0, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(self.code_input,          0, 1, Qt.AlignVCenter)
        card_layout.addWidget(lbl("NAME :"),            1, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(self.name_input,          1, 1, Qt.AlignVCenter)
        card_layout.addWidget(lbl("DISPLAY STATUS :"), 2, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(self.status_combo,        2, 1, Qt.AlignVCenter)

        # ── Separator row ─────────────────────────────────────────────
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("background: #E2E8F0; border: none; min-height: 1px; max-height: 1px;")
        card_layout.addWidget(sep, 3, 0, 1, 2)
        card_layout.setRowMinimumHeight(3, 10)

        # ── LEFT BOTTOM: Sticker / Height / Width ─────────────────────
        sticker_keys = list(self._sticker_data.keys())
        self.sticker_combo = make_chevron_combo(["— Please select a sticker —"] + sticker_keys)
        self.sticker_combo.setCurrentIndex(0)
        self.sticker_combo.setFixedWidth(220)
        card_layout.addWidget(lbl("STICKER :"), 4, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(self.sticker_combo, 4, 1, Qt.AlignVCenter)

        h_row_w = QWidget(); h_row_w.setStyleSheet("background: transparent; border: none;")
        h_hl = QHBoxLayout(h_row_w); h_hl.setContentsMargins(0, 0, 0, 0); h_hl.setSpacing(4)
        self.height_inch = make_readonly(); self.height_inch.setFixedWidth(70)
        h_hl.addWidget(self.height_inch)
        inch_lbl1 = QLabel("INCH /"); inch_lbl1.setStyleSheet(muted_style); h_hl.addWidget(inch_lbl1)
        self.height_px = make_readonly(); self.height_px.setFixedWidth(70)
        h_hl.addWidget(self.height_px)
        px_lbl1 = QLabel("PIXEL"); px_lbl1.setStyleSheet(muted_style); h_hl.addWidget(px_lbl1)
        h_hl.addStretch()
        card_layout.addWidget(lbl("HEIGHT :"), 5, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(h_row_w, 5, 1, Qt.AlignVCenter)

        w_row_w = QWidget(); w_row_w.setStyleSheet("background: transparent; border: none;")
        w_hl = QHBoxLayout(w_row_w); w_hl.setContentsMargins(0, 0, 0, 0); w_hl.setSpacing(4)
        self.width_inch = make_readonly(); self.width_inch.setFixedWidth(70)
        w_hl.addWidget(self.width_inch)
        inch_lbl2 = QLabel("INCH /"); inch_lbl2.setStyleSheet(muted_style); w_hl.addWidget(inch_lbl2)
        self.width_px = make_readonly(); self.width_px.setFixedWidth(70)
        w_hl.addWidget(self.width_px)
        px_lbl2 = QLabel("PIXEL"); px_lbl2.setStyleSheet(muted_style); w_hl.addWidget(px_lbl2)
        w_hl.addStretch()
        card_layout.addWidget(lbl("WIDTH :"), 6, 0, Qt.AlignVCenter | Qt.AlignLeft)
        card_layout.addWidget(w_row_w, 6, 1, Qt.AlignVCenter)

        # ── Vertical divider (left block | empty middle | jenis cetak) ─
        vdiv2 = QFrame()
        vdiv2.setFrameShape(QFrame.VLine)
        vdiv2.setStyleSheet("background: #E2E8F0; border: none; min-width: 1px; max-width: 1px;")
        card_layout.addWidget(vdiv2, 0, 2, 7, 1)
        card_layout.setColumnMinimumWidth(2, 24)

        # ── RIGHT: Jenis Cetak — pinned to far right via col stretch ──
        right_w = QWidget()
        right_w.setStyleSheet("background: transparent; border: none;")
        right_layout = QVBoxLayout(right_w)
        right_layout.setSpacing(6)
        right_layout.setContentsMargins(0, 0, 0, 0)

        jenis_lbl = QLabel("JENIS CETAK :")
        jenis_lbl.setStyleSheet(label_style)
        right_layout.addWidget(jenis_lbl)

        self.chk_barcode_printer = CheckmarkCheckBox("KE BARCODE PRINTER")
        self.chk_report = CheckmarkCheckBox("KE REPORT")
        right_layout.addWidget(self.chk_barcode_printer)
        right_layout.addWidget(self.chk_report)

        card_layout.addWidget(right_w, 0, 4, 3, 1, Qt.AlignTop | Qt.AlignRight)

        root.addWidget(card)
        root.addStretch()

        self.sticker_combo.currentTextChanged.connect(self._on_sticker_changed)

    # ── Sticker selection handler ─────────────────────────────────────

    def _on_sticker_changed(self, key: str):
        d = self._sticker_data.get(key)
        if d:
            self.height_inch.setText(f"{d['h_in']:.2f}")
            self.height_px.setText(str(d["h_px"]))
            self.width_inch.setText(f"{d['w_in']:.2f}")
            self.width_px.setText(str(d["w_px"]))
            self.stickerChanged.emit(d["w_px"], d["h_px"])
        else:
            self.height_inch.clear()
            self.height_px.clear()
            self.width_inch.clear()
            self.width_px.clear()

    # ── Public API ────────────────────────────────────────────────────

    def sync_from_design(self, code: str, name: str, sticker_name: str = "",
                         h_in: float = 0.0, w_in: float = 0.0,
                         h_px: int = 0, w_px: int = 0,
                         dp_fg: int = 0):
        self.code_input.setText(code)
        self.name_input.setText(name)

        # Sync display status combo
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
            # No sticker — reset to placeholder
            self.sticker_combo.setCurrentIndex(0)
            self.height_inch.setText(f"{h_in:.2f}" if h_in else "")
            self.height_px.setText(str(h_px) if h_px else "")
            self.width_inch.setText(f"{w_in:.2f}" if w_in else "")
            self.width_px.setText(str(w_px) if w_px else "")
        self.sticker_combo.blockSignals(False)

    def get_canvas_size(self) -> tuple[int, int]:
        try:
            w = int(self.width_px.text())
        except (ValueError, AttributeError):
            w = 600
        try:
            h = int(self.height_px.text())
        except (ValueError, AttributeError):
            h = 400
        return w, h

    def get_dp_fg(self) -> int:
        """Return 1 if DISPLAY, 0 otherwise."""
        return 1 if self.status_combo.currentText() == "DISPLAY" else 0


# --- Main Page ---

class BarcodeEditorPage(QWidget):
    design_saved = Signal(dict)

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
        self.scene.clearSelection()
        for item in list(self.scene.items()): self.scene.removeItem(item)
        self.component_list.clear()
        self.comp_count_badge.setText("0")
        self.prop_name_input.setText(""); self.prop_name_input.setEnabled(False)
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        if form_data:
            w = int(form_data.get("w_px") or 600)
            h = int(form_data.get("h_px") or 400)
            self._design_code  = form_data.get("pk", "")
            self._original_pk  = self._design_code  # pk as it exists in DB
            self._design_name  = form_data.get("name", "")
            self._sticker_name = str(form_data.get("sticker_name") or "")
            self._h_in         = float(form_data.get("h_in") or 0.0)
            self._w_in         = float(form_data.get("w_in") or 0.0)
            self._dp_fg        = int(form_data.get("dp_fg") or 0)
        else:
            w, h = 600, 400
            self._design_code  = ""
            self._original_pk  = ""
            self._design_name  = ""
            self._sticker_name = ""
            self._h_in = self._w_in = 0.0
            self._dp_fg = 0

        self._canvas_w, self._canvas_h = w, h
        self.scene.setSceneRect(QRectF(0, 0, w, h))
        self._update_design_subtitle()
        self.general_tab.sync_from_design(
            code         = self._design_code,
            name         = self._design_name,
            sticker_name = self._sticker_name,
            h_in         = self._h_in,
            w_in         = self._w_in,
            h_px         = h,
            w_px         = w,
            dp_fg        = self._dp_fg,
        )
        self._switch_tab(0)  # always open on General tab

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
            self._original_pk  = self._design_code  # pk as it exists in DB
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
            code         = self._design_code,
            name         = self._design_name,
            sticker_name = self._sticker_name,
            h_in         = self._h_in,
            w_in         = self._w_in,
            h_px         = self._canvas_h,
            w_px         = self._canvas_w,
            dp_fg        = self._dp_fg,
        )
        self._switch_tab(0)  # always open on General tab

    def serialize_canvas(self) -> list[dict]:
        elements = []
        for item in self.scene.items():
            if item.group(): continue
            d = self._serialize_item(item)
            if d: elements.append(d)
        return elements

    def _serialize_item(self, item) -> dict | None:
        base = {"x": round(item.pos().x(),2), "y": round(item.pos().y(),2), "z": item.zValue(),
                "visible": item.isVisible(), "rotation": item.rotation(), "name": getattr(item,"component_name","")}
        if isinstance(item, BarcodeItem):
            base.update({"type":"barcode","design":item.design,"container_width":item.container_width,"container_height":item.container_height}); return base
        if isinstance(item, QGraphicsTextItem):
            font = item.font()
            base.update({"type":"text","text":item.toPlainText(),"font_size":font.pointSize(),"font_family":font.family(),"bold":font.bold(),"italic":font.italic()}); return base
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
                item = QGraphicsTextItem(d.get("text",""))
                font = QFont(d.get("font_family","Arial"), d.get("font_size",10))
                font.setBold(d.get("bold",False)); font.setItalic(d.get("italic",False))
                item.setFont(font); item.component_name = d.get("name","Text")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "line":
                item = QGraphicsLineItem(0, 0, d.get("x2",100), d.get("y2",0))
                item.setPen(QPen(Qt.black, d.get("thickness",2))); item.component_name = d.get("name","Line")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "rect":
                item = QGraphicsRectItem(0, 0, d.get("width",100), d.get("height",50))
                item.setPen(QPen(Qt.black, d.get("border_width",2))); item.component_name = d.get("name","Rectangle")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "barcode":
                item = BarcodeItem(self.update_pos_label, design=d.get("design","CODE128"))
                item.container_width = d.get("container_width",160); item.container_height = d.get("container_height",80)
                item.component_name = d.get("name","Barcode"); item.bg.setRect(0,0,item.container_width,item.container_height)
            if item is None: continue
            item.setPos(d.get("x",0), d.get("y",0)); item.setZValue(d.get("z",0))
            item.setVisible(d.get("visible",True)); item.setRotation(d.get("rotation",0))
            self.scene.addItem(item)
            li = QListWidgetItem(self.get_component_display_name(item)); li.graphics_item = item
            self.component_list.addItem(li)
        self.comp_count_badge.setText(str(self.component_list.count())); self.sync_z_order_from_list()

    def get_design_payload(self) -> dict:
        elements = self.serialize_canvas()
        canvas_meta = {"canvas_w": self._canvas_w, "canvas_h": self._canvas_h}
        return {"usrm": _json.dumps(elements, separators=(",",":")), "itrm": _json.dumps(canvas_meta, separators=(",",":"))}

    def _update_design_subtitle(self):
        pass  # subtitle removed from header

    def _on_sticker_canvas_resize(self, w_px: int, h_px: int):
        if w_px <= 0 or h_px <= 0:
            return
        self._canvas_w, self._canvas_h = w_px, h_px
        self.scene.setSceneRect(QRectF(0, 0, w_px, h_px))
        self._sticker_name = self.general_tab.sticker_combo.currentText()

    def _switch_tab(self, index: int):
        self._tab_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            btn.setStyleSheet(TAB_ACTIVE_STYLE if i == index else TAB_INACTIVE_STYLE)

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # ── Header bar ────────────────────────────────────────────────
        header_bar = QWidget()
        header_bar.setStyleSheet(
            "QWidget#headerBar { background: white; border-bottom: 1px solid #E2E8F0; }"
        )
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

        # Save + Cancel side by side on the right
        self.save_btn = StandardButton("Save Design", icon_name="fa5s.save", variant="primary")
        self.save_btn.setFixedHeight(34)
        header_bar_layout.addWidget(self.save_btn)

        header_bar_layout.addSpacing(8)

        self.back_btn = StandardButton("Cancel", icon_name="fa5s.times", variant="secondary")
        self.back_btn.setToolTip("Cancel and return to list")
        self.back_btn.setFixedHeight(34)
        header_bar_layout.addWidget(self.back_btn)

        self.main_layout.addWidget(header_bar)

        # ── Stacked content ───────────────────────────────────────────
        self._tab_stack = QStackedWidget()
        self._tab_stack.setStyleSheet("background: transparent;")

        # ── Page 0: General ───────────────────────────────────────────
        general_scroll = QScrollArea()
        general_scroll.setWidgetResizable(True)
        general_scroll.setFrameShape(QFrame.NoFrame)
        general_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        general_scroll.setStyleSheet(f"background: {COLORS['bg_main']}; border: none;")
        general_scroll.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.general_tab = GeneralTab()
        general_scroll.setWidget(self.general_tab)
        self._tab_stack.addWidget(general_scroll)   # index 0

        # ── Page 1: Editor ────────────────────────────────────────────
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
        workspace_layout.addWidget(self.view, stretch=3)

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
        self._tab_stack.addWidget(editor_page)   # index 1

        self.main_layout.addWidget(self._tab_stack)

        self._switch_tab(0)

        self.general_tab.stickerChanged.connect(self._on_sticker_canvas_resize)

        self.btn_add_text.clicked.connect(lambda: self.add_element("text"))
        self.btn_add_rect.clicked.connect(lambda: self.add_element("rect"))
        self.btn_add_line.clicked.connect(lambda: self.add_element("line"))
        self.btn_add_code.clicked.connect(lambda: self.add_element("barcode"))
        self.save_btn.clicked.connect(self._on_save_clicked)
        self.scene.selectionChanged.connect(self.on_selection_changed)

    def _on_save_clicked(self):
        # Read all fields from the General tab
        selected_sticker = self.general_tab.sticker_combo.currentText()
        # Ignore the placeholder item
        if selected_sticker and not selected_sticker.startswith("—"):
            self._sticker_name = selected_sticker
        elif selected_sticker and selected_sticker.startswith("—"):
            self._sticker_name = ""

        code_val = self.general_tab.code_input.text().strip()
        name_val = self.general_tab.name_input.text().strip()
        if code_val:
            self._design_code = code_val
        if name_val:
            self._design_name = name_val

        # Read dp_fg from status combo (DISPLAY = 1, NOT DISPLAY = 0)
        dp_fg = self.general_tab.get_dp_fg()

        try:
            self._canvas_w = int(self.general_tab.width_px.text())
        except (ValueError, AttributeError):
            pass
        try:
            self._canvas_h = int(self.general_tab.height_px.text())
        except (ValueError, AttributeError):
            pass
        try:
            h_in = float(self.general_tab.height_inch.text())
        except (ValueError, AttributeError):
            h_in = getattr(self, "_h_in", 0.0)
        try:
            w_in = float(self.general_tab.width_inch.text())
        except (ValueError, AttributeError):
            w_in = getattr(self, "_w_in", 0.0)

        payload = self.get_design_payload()
        payload["pk"]           = self._design_code
        payload["original_pk"]  = getattr(self, "_original_pk", self._design_code)
        payload["name"]         = self._design_name
        payload["dp_fg"]        = dp_fg          # ← now included
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

    def delete_component(self, row):
        li = self.component_list.item(row)
        if not li: return
        gi = getattr(li, 'graphics_item', None)
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

    def update_current_component_name(self, name):
        sel = self.scene.selectedItems()
        if sel: sel[0].component_name = name if name else "Unnamed"; self.update_component_list()

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
        self.current_editor = None
        if isinstance(selected, QGraphicsTextItem): self.current_editor = TextPropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsLineItem): self.current_editor = LinePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsRectItem): self.current_editor = RectanglePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, BarcodeItem): self.current_editor = BarcodePropertyEditor(selected, self.update_component_list)
        if self.current_editor: self.inspector_layout.addWidget(self.current_editor)

    def add_element(self, kind):
        self.scene.clearSelection()
        flags = QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges
        if kind == "text":
            item = QGraphicsTextItem("LABEL_VAR"); item.setFont(QFont("Arial",10))
            item.component_name = "Text"; setup_item_logic(item, self.update_pos_label)
        elif kind == "rect":
            item = QGraphicsRectItem(0,0,100,50); item.setPen(QPen(Qt.black,2))
            item.component_name = "Rectangle"; setup_item_logic(item, self.update_pos_label)
        elif kind == "line":
            item = QGraphicsLineItem(0,0,100,0); item.setPen(QPen(Qt.black,2))
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