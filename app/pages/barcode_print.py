"""
barcode_print.py  —  Barcode Print Page
Dynamic fields derived from design element types, with live preview updates.
"""

from __future__ import annotations
import hashlib
import json as _json
import re
from datetime import datetime

import qtawesome as qta
from PySide6.QtCore import Qt, QDate, QSize, QRectF, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QFrame, QSizePolicy, QSplitter, QScrollArea,
    QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication, QDialog,
    QComboBox, QGraphicsScene, QGraphicsView,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsRectItem,
    QCalendarWidget,
)


# ── Standard button ───────────────────────────────────────────────────────────

class StandardButton(QPushButton):
    def __init__(self, text, icon_name=None, variant="primary", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        self.variants = {
            "primary":   ("#3B82F6", "#2563EB", "#FFFFFF"),
            "secondary": ("#FFFFFF", "#F9FAFB", "#374151"),
            "danger":    ("#EF4444", "#DC2626", "#FFFFFF"),
            "success":   ("#10B981", "#059669", "#FFFFFF"),
        }
        bg, hover, text_color = self.variants.get(variant, self.variants["primary"])
        border_style = "border: 1px solid #E5E7EB;" if variant == "secondary" else "border: none;"
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {text_color};
                border-radius: 6px; padding: 0px 16px;
                font-weight: 600; font-size: 13px; {border_style}
            }}
            QPushButton:hover   {{ background-color: {hover}; }}
            QPushButton:pressed {{ background-color: {bg}; }}
            QPushButton:disabled {{ background-color: #D1D5DB; color: #9CA3AF; }}
        """)
        if icon_name:
            self.setIcon(qta.icon(icon_name, color=text_color))
            self.setIconSize(QSize(16, 16))


# ── Colour / style constants ──────────────────────────────────────────────────

try:
    from components.barcode_editor.utils import (
        COLORS, MODERN_INPUT_STYLE, make_chevron_combo, make_spin, ChevronSpinBox,
    )
    _LEGACY_BLUE = COLORS.get("legacy_blue", "#4A5568")
    _BG_MAIN     = COLORS.get("bg_main",     "#F8FAFC")
    _WHITE       = COLORS.get("white",        "#FFFFFF")
    _BORDER      = COLORS.get("border",       "#E2E8F0")
    _CANVAS_BG   = COLORS.get("canvas_bg",    "#F1F4F8")
except ImportError:
    _LEGACY_BLUE = "#4A5568"
    _BG_MAIN     = "#F8FAFC"
    _WHITE       = "#FFFFFF"
    _BORDER      = "#E2E8F0"
    _CANVAS_BG   = "#F1F4F8"
    MODERN_INPUT_STYLE = """
        QLineEdit, QSpinBox, QDateEdit {
            background: #FFFFFF; border: 1px solid #CBD5E1;
            border-radius: 4px; padding: 5px 8px;
            font-size: 11px; color: #1E293B; min-height: 26px;
        }
        QLineEdit:focus, QSpinBox:focus, QDateEdit:focus { border-color: #6366F1; }
        QLineEdit:disabled, QSpinBox:disabled {
            background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0;
        }
    """
    def make_chevron_combo(options):
        c = QComboBox(); c.addItems(options); return c
    def make_spin(mn, mx, val):
        s = QSpinBox(); s.setRange(mn, mx); s.setValue(val); return s

_READONLY_PICKER_STYLE = (
    "QLineEdit { background: #F8FAFC; color: #1E293B; border: 1px solid #E2E8F0; "
    "border-radius: 4px; padding: 0px 8px; font-size: 11px; "
    "min-height: 30px; max-height: 30px; }"
)
_AUTOFILL_STYLE = (
    MODERN_INPUT_STYLE +
    "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }"
)

_ACCENT       = "#6366F1"
_ACCENT_LIGHT = "#EEF2FF"
_BORDER2      = "#CBD5E1"
_TEXT         = "#1E293B"
_MUTED        = "#64748B"
_HINT         = "#94A3B8"
_BLUE         = "#3B82F6"
_SUCCESS      = "#16A34A"
_DANGER       = "#DC2626"

_BTN_PRIMARY = f"""
QPushButton {{
    background: {_BLUE}; color: #fff; border: none; border-radius: 6px;
    font-size: 12px; font-weight: 600; padding: 6px 16px; min-height: 28px;
}}
QPushButton:hover   {{ background: #2563EB; }}
QPushButton:pressed {{ background: #1D4ED8; }}
QPushButton:disabled{{ background: {_HINT}; color: #fff; }}
"""
_BTN_SECONDARY = f"""
QPushButton {{
    background: {_WHITE}; color: {_MUTED};
    border: 1px solid {_BORDER2}; border-radius: 6px;
    font-size: 12px; padding: 6px 14px; min-height: 28px;
}}
QPushButton:hover   {{ background: #F1F5F9; color: {_TEXT}; }}
QPushButton:pressed {{ background: #E2E8F0; }}
QPushButton:disabled{{ color: {_HINT}; border-color: {_BORDER}; }}
"""
_BTN_BROWSE = f"""
QPushButton {{
    background: #F1F5F9; color: {_MUTED};
    border: 1px solid {_BORDER2}; border-radius: 4px;
    font-size: 12px; padding: 0 10px; min-height: 26px; min-width: 30px;
}}
QPushButton:hover {{
    background: {_ACCENT_LIGHT}; color: {_ACCENT}; border-color: {_ACCENT};
}}
QPushButton:disabled {{
    background: #F8FAFC; color: #D1D5DB; border-color: {_BORDER};
}}
"""
_CARD_STYLE = (
    f"QFrame {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}"
    " QFrame QWidget { border: none; background: transparent; }"
    " QFrame QFrame { border: none; background: transparent; }"
)
_SLIM_SCROLLBAR_STYLE = """
    QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
    QScrollBar::handle:vertical { background: #B0BEC5; border-radius: 3px; min-height: 24px; }
    QScrollBar::handle:vertical:hover { background: #90A4AE; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar:horizontal { background: transparent; height: 6px; margin: 0; }
    QScrollBar::handle:horizontal { background: #B0BEC5; border-radius: 3px; min-width: 24px; }
    QScrollBar::handle:horizontal:hover { background: #90A4AE; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""


def _lbl(text: str, width: int = 120) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_LEGACY_BLUE}; font-size: 9px; text-transform: uppercase; "
        "background: transparent; border: none;"
    )
    l.setFixedWidth(width)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return l


def _status_lbl(text: str, ok: bool) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; "
        "font-weight: 600; background: transparent; border: none;"
    )
    return l


def _form_row(label: str, widget: QWidget, layout, lbl_width: int = 120):
    row = QWidget(); row.setStyleSheet("background: transparent; border: none;")
    rl = QHBoxLayout(row); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(10)
    rl.setAlignment(Qt.AlignVCenter)
    lbl_w = _lbl(label, lbl_width); lbl_w.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    rl.addWidget(lbl_w); rl.addWidget(widget, 1)
    layout.addWidget(row)


# ── CheckBox ──────────────────────────────────────────────────────────────────

class _CheckBox(QCheckBox):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QCheckBox { font-size: 11px; color: #1E293B; spacing: 7px; background: transparent; }"
            "QCheckBox::indicator { width: 0px; height: 0px; }"
        )
        self._box_size = 14

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(QFont("Segoe UI", 10))
        w = self._box_size + 7 + fm.horizontalAdvance(self.text()) + 6
        h = max(self._box_size + 4, fm.height() + 4)
        return QSize(w, h)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        b = self._box_size
        y = (self.height() - b) // 2
        p.setBrush(QColor("#FFFFFF")); p.setPen(QPen(QColor("#94A3B8"), 1.5))
        path = QPainterPath(); path.addRoundedRect(0, y, b, b, 3, 3); p.drawPath(path)
        if self.isChecked():
            pen = QPen(QColor("#1E293B"), 2.0)
            pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen); cx, cy = b // 2, y + b // 2
            p.drawLine(int(cx - 3), int(cy), int(cx - 1), int(cy + 3))
            p.drawLine(int(cx - 1), int(cy + 3), int(cx + 4), int(cy - 3))
        p.setPen(QPen(QColor("#1E293B"))); p.setFont(QFont("Segoe UI", 10))
        tx = b + 7
        p.drawText(tx, 0, self.width() - tx, self.height(),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def mousePressEvent(self, _event):
        self.setChecked(not self.isChecked()); self.update()


# ── Calendar combo ────────────────────────────────────────────────────────────

class _CalendarCombo(QWidget):
    currentTextChanged = Signal(str)
    _MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
               "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(32)
        self._date = QDate.currentDate()
        self._popup: QDialog | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self._btn = QPushButton()
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: #FFFFFF; border: 1px solid #CBD5E1;
                border-radius: 4px; padding: 5px 10px;
                font-size: 12px; color: #1E293B; text-align: left;
            }}
            QPushButton:hover   {{ border-color: #6366F1; }}
            QPushButton:disabled {{ background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }}
        """)
        self._btn.clicked.connect(self._open_popup)
        self._update_btn_text(self._date, open_=False)
        layout.addWidget(self._btn)

    def _update_btn_text(self, d: QDate, open_: bool = False):
        try:
            icon_name = "fa5s.chevron-up" if open_ else "fa5s.chevron-down"
            self._btn.setIcon(qta.icon(icon_name, color="#64748B"))
            self._btn.setIconSize(QSize(10, 10))
            self._btn.setLayoutDirection(Qt.RightToLeft)
        except Exception:
            pass
        self._btn.setText(self._fmt(d))

    @staticmethod
    def _fmt(d: QDate) -> str:
        return f"{d.day():02d}-{_CalendarCombo._MONTHS[d.month() - 1]}-{d.year()}"

    def _open_popup(self):
        if self._popup and self._popup.isVisible():
            self._popup.close(); self._update_btn_text(self._date, open_=False); return
        dlg = QDialog(self, Qt.Popup | Qt.FramelessWindowHint)
        dlg.setStyleSheet("QDialog { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; }")
        v = QVBoxLayout(dlg); v.setContentsMargins(6, 6, 6, 6)
        cal = QCalendarWidget()
        cal.setSelectedDate(self._date); cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet("""
            QCalendarWidget QWidget { background: #FFFFFF; color: #1E293B; }
            QCalendarWidget QAbstractItemView {
                font-size: 12px; selection-background-color: #3B82F6;
                selection-color: #FFFFFF; gridline-color: transparent;
            }
            QCalendarWidget QAbstractItemView:enabled { color: #1E293B; background: #FFFFFF; }
            QCalendarWidget QAbstractItemView:disabled { color: #94A3B8; }
            QCalendarWidget QToolButton {
                color: #1E293B; background: transparent; border: none;
                font-size: 12px; font-weight: 600;
            }
            QCalendarWidget QToolButton:hover { background: #F1F5F9; border-radius: 4px; }
            QCalendarWidget #qt_calendar_navigationbar {
                background: #F8FAFC; border-bottom: 1px solid #E2E8F0;
            }
        """)
        cal.clicked.connect(lambda d: self._on_date_picked(d, dlg))
        v.addWidget(cal); dlg.adjustSize()
        screen = QApplication.primaryScreen().availableGeometry()
        pos_below = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        pos_above = self._btn.mapToGlobal(self._btn.rect().topLeft())
        if pos_below.y() + dlg.height() > screen.bottom():
            dlg.move(pos_above.x(), pos_above.y() - dlg.height())
        else:
            dlg.move(pos_below)
        self._update_btn_text(self._date, open_=True)
        dlg.finished.connect(lambda _: self._update_btn_text(self._date, open_=False))
        self._popup = dlg; dlg.exec()

    def _on_date_picked(self, d: QDate, dlg: QDialog):
        self._date = d; dlg.accept()
        self._update_btn_text(d, open_=False)
        self.currentTextChanged.emit(self._fmt(d))

    def currentText(self) -> str:
        return self._fmt(self._date)

    def setCurrentText(self, text: str):
        for i, m in enumerate(self._MONTHS):
            if m in text:
                parts = text.replace(m, str(i + 1)).split("-")
                try:
                    d = QDate(int(parts[2]), i + 1, int(parts[0]))
                    if d.isValid():
                        self._date = d; self._update_btn_text(d, open_=False)
                except Exception:
                    pass
                break

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled); self._btn.setEnabled(enabled)


# ── Design picker popup ───────────────────────────────────────────────────────

class _DesignPickerPopup(QDialog):
    design_picked = Signal(str, str)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Select Design")
        self.setMinimumSize(520, 460); self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {_WHITE}; }}")
        self._records: list[dict] = []; self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self); vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(0)
        header = QWidget()
        header.setStyleSheet(f"background: {_WHITE}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header); hl.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Select Design")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        hl.addWidget(title); hl.addStretch(); vbox.addWidget(header)

        search_row = QWidget()
        search_row.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {_BORDER};")
        sr = QHBoxLayout(search_row); sr.setContentsMargins(14, 10, 14, 10); sr.setSpacing(8)
        si = QLabel("⌕"); si.setStyleSheet(f"font-size: 15px; color: {_HINT}; background: transparent; border: none;")
        sr.addWidget(si)
        self._search = QLineEdit(); self._search.setPlaceholderText("Search code or name…")
        self._search.setFrame(False)
        self._search.setStyleSheet(f"border: none; background: transparent; font-size: 12px; color: {_TEXT};")
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        sr.addWidget(self._search); vbox.addWidget(search_row)

        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        ch = QHBoxLayout(col_hdr); ch.setContentsMargins(16, 7, 16, 7); ch.setSpacing(0)
        for text, w in [("CODE", 150), ("NAME", None)]:
            l = QLabel(text)
            l.setStyleSheet(f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; background: transparent;")
            if w: l.setFixedWidth(w)
            ch.addWidget(l)
        vbox.addWidget(col_hdr)

        self._list = QListWidget(); self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{ background: {_WHITE}; border: none; font-size: 12px; color: {_TEXT}; outline: none; }}
            QListWidget::item {{ padding: 0px; border-bottom: 1px solid {_BORDER}; }}
            QListWidget::item:selected {{ background: {_ACCENT_LIGHT}; }}
            QListWidget::item:hover:!selected {{ background: #F8FAFC; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {_BORDER2}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._list.itemDoubleClicked.connect(self._on_activated)
        self._list.itemSelectionChanged.connect(
            lambda: self._select_btn.setEnabled(len(self._list.selectedItems()) > 0))
        vbox.addWidget(self._list, 1)

        footer = QWidget()
        footer.setStyleSheet(f"background: #F8FAFC; border-top: 1px solid {_BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16, 10, 16, 10); fl.setSpacing(8)
        self._footer = QLabel()
        self._footer.setStyleSheet(f"font-size: 11px; color: {_HINT}; background: transparent;")
        fl.addWidget(self._footer); fl.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        self._select_btn = QPushButton("Select"); self._select_btn.setStyleSheet(_BTN_PRIMARY)
        self._select_btn.setEnabled(False); self._select_btn.clicked.connect(self._on_select)
        fl.addWidget(cancel_btn); fl.addSpacing(6); fl.addWidget(self._select_btn)
        vbox.addWidget(footer)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape: self.hide(); return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                items = self._list.selectedItems()
                if items: self._on_activated(items[0])
                elif self._list.count() > 0: self._on_activated(self._list.item(0))
                return True
        return super().eventFilter(obj, event)

    def _load_records(self):
        try:
            from server.repositories.mbarcd_repo import fetch_all_mbarcd
            self._records = fetch_all_mbarcd()
        except Exception:
            self._records = []

    def _rebuild_list(self, records):
        self._list.clear()
        for r in records:
            code = str(r.get("pk") or r.get("code") or "")
            name = str(r.get("name") or "")
            item = QListWidgetItem(); item.setData(Qt.UserRole, (code, name))
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w); rl.setContentsMargins(16, 9, 16, 9); rl.setSpacing(0)
            code_lbl = QLabel(code)
            code_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {_LEGACY_BLUE}; "
                "background: transparent; min-width: 150px; max-width: 150px;")
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"font-size: 12px; color: {_TEXT}; background: transparent;")
            rl.addWidget(code_lbl); rl.addWidget(name_lbl, 1)
            item.setSizeHint(QSize(0, 38)); self._list.addItem(item)
            self._list.setItemWidget(item, row_w)
        count = len(records)
        self._footer.setText(f"{count} record{'s' if count != 1 else ''}")
        self._select_btn.setEnabled(False)

    def _filter(self, q: str):
        q = q.lower()
        filtered = ([r for r in self._records
                     if q in str(r.get("pk", "")).lower()
                     or q in str(r.get("name", "")).lower()]
                    if q else self._records)
        self._rebuild_list(filtered)

    def _on_activated(self, _item): self._on_select()

    def _on_select(self):
        items = self._list.selectedItems()
        if not items: return
        data = items[0].data(Qt.UserRole)
        if data:
            self.design_picked.emit(data[0], data[1]); self.accept()

    def open_modal(self):
        self._load_records(); self._search.clear()
        self._rebuild_list(self._records); self._search.setFocus(); self.exec()


# ── Master Item picker ────────────────────────────────────────────────────────

class _MasterItemPickerPopup(QDialog):
    item_picked = Signal(str, str, str, str, str)  # part_no, item_code, name, qty, whs

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Select Master Item")
        self.setMinimumSize(680, 500); self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {_WHITE}; }}")
        self._records: list[dict] = []; self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self); vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(0)

        header = QWidget()
        header.setStyleSheet(f"background: {_WHITE}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header); hl.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Select Master Item")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        hl.addWidget(title); hl.addStretch(); vbox.addWidget(header)

        search_row = QWidget()
        search_row.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {_BORDER};")
        sr = QHBoxLayout(search_row); sr.setContentsMargins(14, 10, 14, 10); sr.setSpacing(8)
        si = QLabel("⌕"); si.setStyleSheet(f"font-size: 15px; color: {_HINT}; background: transparent; border: none;")
        sr.addWidget(si)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search part no., item code, or name…")
        self._search.setFrame(False)
        self._search.setStyleSheet(f"border: none; background: transparent; font-size: 12px; color: {_TEXT};")
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        sr.addWidget(self._search); vbox.addWidget(search_row)

        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        ch = QHBoxLayout(col_hdr); ch.setContentsMargins(16, 7, 16, 7); ch.setSpacing(0)
        for text, w in [("PART NO PRINT", 160), ("ITEM CODE", 160), ("NAME", None)]:
            l = QLabel(text)
            l.setStyleSheet(
                f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; "
                "letter-spacing: 0.5px; background: transparent;")
            if w: l.setFixedWidth(w)
            ch.addWidget(l)
        vbox.addWidget(col_hdr)

        self._list = QListWidget(); self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{ background: {_WHITE}; border: none; font-size: 12px; color: {_TEXT}; outline: none; }}
            QListWidget::item {{ padding: 0px; border-bottom: 1px solid {_BORDER}; }}
            QListWidget::item:selected {{ background: {_ACCENT_LIGHT}; }}
            QListWidget::item:hover:!selected {{ background: #F8FAFC; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{ background: {_BORDER2}; border-radius: 2px; min-height: 20px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._list.itemDoubleClicked.connect(self._on_activated)
        self._list.itemSelectionChanged.connect(
            lambda: self._select_btn.setEnabled(len(self._list.selectedItems()) > 0))
        vbox.addWidget(self._list, 1)

        footer = QWidget()
        footer.setStyleSheet(f"background: #F8FAFC; border-top: 1px solid {_BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16, 10, 16, 10); fl.setSpacing(8)
        self._footer = QLabel()
        self._footer.setStyleSheet(f"font-size: 11px; color: {_HINT}; background: transparent;")
        fl.addWidget(self._footer); fl.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        self._select_btn = QPushButton("Select"); self._select_btn.setStyleSheet(_BTN_PRIMARY)
        self._select_btn.setEnabled(False); self._select_btn.clicked.connect(self._on_select)
        fl.addWidget(cancel_btn); fl.addSpacing(6); fl.addWidget(self._select_btn)
        vbox.addWidget(footer)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape: self.hide(); return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                items = self._list.selectedItems()
                if items: self._on_activated(items[0])
                elif self._list.count() > 0: self._on_activated(self._list.item(0))
                return True
        return super().eventFilter(obj, event)

    def _load_records(self):
        try:
            from server.repositories.mtitms_repo import fetch_all_mtitms
            self._records = fetch_all_mtitms()
        except Exception:
            self._records = []

    def _rebuild_list(self, records: list[dict]):
        self._list.clear()
        for r in records:
            part_no   = str(r.get("po_no")      or "")
            item_code = str(r.get("pk")          or "")
            name      = str(r.get("description") or "")
            qty       = str(r.get("qty")         or "0")
            whs       = str(r.get("warehouse")   or "")
            item = QListWidgetItem()
            item.setData(Qt.UserRole, (part_no, item_code, name, qty, whs))
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w); rl.setContentsMargins(16, 9, 16, 9); rl.setSpacing(0)
            for text, fw in [(part_no, 160), (item_code, 160)]:
                lbl = QLabel(text)
                lbl.setStyleSheet(
                    f"font-size: 12px; font-weight: 600; color: {_LEGACY_BLUE}; "
                    f"background: transparent; min-width: {fw}px; max-width: {fw}px;")
                rl.addWidget(lbl)
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"font-size: 12px; color: {_TEXT}; background: transparent;")
            rl.addWidget(name_lbl, 1)
            item.setSizeHint(QSize(0, 38))
            self._list.addItem(item); self._list.setItemWidget(item, row_w)
        count = len(records)
        self._footer.setText(f"{count} record{'s' if count != 1 else ''}")
        self._select_btn.setEnabled(False)

    def _filter(self, q: str):
        q = q.lower()
        if not q: self._rebuild_list(self._records); return
        filtered = [r for r in self._records
                    if q in str(r.get("po_no", "")).lower()
                    or q in str(r.get("pk", "")).lower()
                    or q in str(r.get("description", "")).lower()]
        self._rebuild_list(filtered)

    def _on_activated(self, _item): self._on_select()

    def _on_select(self):
        items = self._list.selectedItems()
        if not items: return
        data = items[0].data(Qt.UserRole)
        if data:
            self.item_picked.emit(*data); self.accept()

    def open_modal(self):
        self._load_records(); self._search.clear()
        self._rebuild_list(self._records); self._search.setFocus(); self.exec()


# ── Design field analyser ─────────────────────────────────────────────────────

def _analyse_fields(elements: list[dict]) -> list[dict]:
    """
    Walk the element list and return field descriptors for the print-fields
    panel, ordered by design_column.

    design_type rules
    -----------------
    LOOKUP  + editor != INVISIBLE            → picker row (browseable)
    LINK    + editor == ENABLED              → editable free-text
    LINK    + editor != ENABLED              → read-only (auto-filled by parent LOOKUP)
    SYSTEM  + system_value == LOT NO
             + editor != INVISIBLE           → date picker
    SYSTEM  + editor == ENABLED (other SVs)  → free-text
    BATCH NO + editor != INVISIBLE           → auto-filled (qty from batch_ref,
                                               whs from wh_ref element)
    MERGE / FIX / anything with INVISIBLE   → skip (never shown)

    Descriptor keys
    ---------------
    type         : 'lookup' | 'date' | 'autofill' | 'freetext' | 'link_readonly'
    caption      : label shown in UI
    name         : element name  (canvas key for preview binding)
    component_id : str  (LOOKUP only, for resolving LINKs)
    link_to      : component_id of parent LOOKUP (LINK-derived fields)
    system_value : str | None
    column       : int  (for ordering)
    batch_ref    : str  (BATCH NO only — name of the LOOKUP element that feeds qty)
    wh_ref       : str  (BATCH NO only — name of the element that carries whs)
    """
    fields: list[dict] = []

    for e in elements:
        if e.get("type") != "text":
            continue

        dt  = (e.get("design_type")     or "").upper().strip()
        ed  = (e.get("design_editor")   or "").upper().strip()
        sv  = (e.get("design_system_value") or "").upper().strip()
        cap = (e.get("design_caption")  or e.get("name") or "").strip()
        name = e.get("name", "")
        cid  = e.get("component_id", "")
        col  = int(e.get("design_column") or 1)

        # Always skip invisible elements
        if ed == "INVISIBLE":
            continue

        if dt == "LOOKUP":
            fields.append(dict(
                type="lookup", caption=cap, name=name,
                component_id=cid, link_to=None,
                system_value=None, column=col,
                batch_ref="", wh_ref="",
            ))

        elif dt == "LINK":
            fields.append(dict(
                type="freetext" if ed == "ENABLED" else "link_readonly",
                caption=cap, name=name,
                component_id=cid, link_to=e.get("design_link", ""),
                system_value=None, column=col,
                batch_ref="", wh_ref="",
            ))

        elif dt == "SYSTEM":
            if sv == "LOT NO":
                fields.append(dict(
                    type="date", caption=cap, name=name,
                    component_id=cid, link_to=None,
                    system_value=sv, column=col,
                    batch_ref="", wh_ref="",
                ))
            elif ed == "ENABLED":
                fields.append(dict(
                    type="freetext", caption=cap, name=name,
                    component_id=cid, link_to=None,
                    system_value=sv, column=col,
                    batch_ref="", wh_ref="",
                ))

        elif dt == "BATCH NO":
            fields.append(dict(
                type="autofill", caption=cap, name=name,
                component_id=cid, link_to=None,
                system_value=None, column=col,
                batch_ref=e.get("design_batch_no", ""),
                wh_ref=e.get("design_wh", ""),
            ))

        # MERGE, FIX, and anything else → invisible, skip

    fields.sort(key=lambda f: f["column"])
    return fields


# ── Live canvas preview ───────────────────────────────────────────────────────

class _CanvasPreview(QWidget):
    """
    Renders the design at 1:1 scale, scrollable.
    Call set_values({element_name: text}) to update live.
    MERGE elements are recomputed automatically.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._elements: list[dict] = []
        self._text_items: dict[str, QGraphicsTextItem] = {}
        self._canvas_w = 600; self._canvas_h = 400
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        self._scene = QGraphicsScene()
        self._scene.setBackgroundBrush(QBrush(QColor("#FFFFFF")))
        self._view = QGraphicsView(self._scene)
        self._view.setBackgroundBrush(QBrush(Qt.transparent))
        self._view.viewport().setAutoFillBackground(False)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setRenderHint(QPainter.TextAntialiasing)
        self._view.setStyleSheet(
            "QGraphicsView { background: transparent; border: none; }"
            + _SLIM_SCROLLBAR_STYLE)
        self._view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self._view.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._view.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._view.setInteractive(False)
        self._view.setTransformationAnchor(QGraphicsView.NoAnchor)
        self._view.setResizeAnchor(QGraphicsView.NoAnchor)
        layout.addWidget(self._view)
        self._placeholder = QLabel("Load a design to preview")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._placeholder.setStyleSheet(f"color: {_HINT}; font-size: 11px; background: #DCE5ED;")
        layout.addWidget(self._placeholder)
        self._view.setVisible(False)
        self._placeholder.setVisible(True)

    def set_design(self, usrm_json: str, itrm_json: str = ""):
        self._scene.clear(); self._text_items.clear()
        try:
            self._elements = _json.loads(usrm_json) if usrm_json else []
        except Exception:
            self._elements = []
        canvas_w, canvas_h = 600, 400
        if itrm_json:
            try:
                meta = _json.loads(itrm_json)
                canvas_w = int(meta.get("canvas_w", canvas_w))
                canvas_h = int(meta.get("canvas_h", canvas_h))
            except Exception:
                pass
        if not self._elements:
            self._view.setVisible(False); self._placeholder.setVisible(True); return
        self._canvas_w = canvas_w; self._canvas_h = canvas_h
        self._scene.setSceneRect(QRectF(0, 0, canvas_w, canvas_h))
        bg = self._scene.addRect(
            QRectF(0, 0, canvas_w, canvas_h),
            QPen(QColor("#CBD5E1"), 1), QBrush(QColor("#FFFFFF")))
        bg.setZValue(-1000)
        for d in sorted(self._elements, key=lambda x: x.get("z", 0)):
            self._add_element(d)
        self._view.setVisible(True); self._placeholder.setVisible(False)
        self._view.resetTransform()

    def set_values(self, name_to_text: dict[str, str]):
        """Push new values into named text elements and recompute MERGEs."""
        for name, text in name_to_text.items():
            item = self._text_items.get(name)
            if item is not None:
                item.setPlainText(str(text))
        self._recompute_merges()

    def _recompute_merges(self):
        # Snapshot current text of every tracked item
        all_vals: dict[str, str] = {
            name: item.toPlainText()
            for name, item in self._text_items.items()
        }
        for d in self._elements:
            if (d.get("type") == "text"
                    and (d.get("design_type") or "").upper() == "MERGE"):
                result = self._eval_merge(d.get("design_merge", ""), all_vals)
                item = self._text_items.get(d.get("name", ""))
                if item is not None:
                    item.setPlainText(result)

    @staticmethod
    def _eval_merge(template: str, values: dict[str, str]) -> str:
        """Replace {LabelN} tokens; '+' is a separator, not literal text."""
        def replacer(m):
            return values.get(m.group(1), "")
        return re.sub(r"\{(\w+)\}", replacer, template).replace("+", "")

    def _add_element(self, d: dict):
        kind = d.get("type")
        x    = d.get("aabb_x", d.get("x", 0))
        y    = d.get("aabb_y", d.get("y", 0))
        z    = d.get("z", 0)
        rot  = d.get("rotation", 0)
        vis  = d.get("visible", True)
        name = d.get("name", "")
        item = None

        if kind == "text":
            ti = QGraphicsTextItem(d.get("text", ""))
            font = QFont(d.get("font_family", "Arial"), d.get("font_size", 10))
            font.setBold(d.get("bold", False)); font.setItalic(d.get("italic", False))
            ti.setFont(font)
            ti.setDefaultTextColor(QColor(d.get("color", "#000000")))
            ti.document().setDocumentMargin(0)
            if name:
                self._text_items[name] = ti
            item = ti

        elif kind == "line":
            item = QGraphicsLineItem(0, 0, d.get("x2", 100), d.get("y2", 0))
            item.setPen(QPen(Qt.black, max(1, d.get("thickness", 2))))

        elif kind == "rect":
            item = QGraphicsRectItem(0, 0, d.get("width", 100), d.get("height", 50))
            item.setPen(QPen(Qt.black, max(1, d.get("border_width", 2))))
            item.setBrush(Qt.NoBrush)

        elif kind == "barcode":
            w = d.get("container_width", 80); h = d.get("container_height", 80)
            item = _BarcodePreviewItem(w, h, d.get("design", "CODE128"))

        if item is None:
            return

        item.setZValue(z); item.setVisible(vis)
        self._scene.addItem(item)
        if rot != 0:
            br = item.boundingRect()
            item.setTransformOriginPoint(br.center()); item.setRotation(rot)
            # After rotation, correct for the shift in the scene bounding box top-left
            item.setPos(0, 0)
            aabb0 = item.mapToScene(item.boundingRect()).boundingRect()
            item.setPos(x - aabb0.left(), y - aabb0.top())
        else:
            # No rotation — place directly at design coordinates
            item.setPos(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def clear(self):
        self._scene.clear(); self._text_items.clear(); self._elements = []
        self._view.setVisible(False); self._placeholder.setVisible(True)


class _BarcodePreviewItem(QGraphicsRectItem):
    def __init__(self, w: float, h: float, design: str = "CODE128"):
        super().__init__(0, 0, w, h)
        self._design = design; self.setPen(QPen(Qt.NoPen)); self.setBrush(Qt.NoBrush)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect(); w, h = r.width(), r.height()
        painter.fillRect(r, QColor("#FFFFFF"))
        bar_h = h * 0.72; bar_top = r.top()
        seed = int(hashlib.md5(self._design.encode()).hexdigest()[:8], 16)
        painter.setPen(Qt.NoPen); painter.setBrush(QBrush(Qt.black))
        x = r.left() + 2; i = 0
        while x < r.right() - 2:
            bar_w = max(1.0, float(((seed >> (i % 24)) & 3) + 1))
            if i % 2 == 0:
                painter.drawRect(int(x), int(bar_top), max(1, int(bar_w)), int(bar_h))
            x += bar_w + 0.8; i += 1
        label_top = bar_top + bar_h + 2; label_h = h - bar_h - 2
        if label_h > 4:
            font = QFont("Courier New", max(5, int(label_h * 0.55)))
            painter.setFont(font); painter.setPen(QPen(QColor("#1E293B")))
            painter.drawText(int(r.left()), int(label_top), int(w), int(label_h),
                             Qt.AlignHCenter | Qt.AlignVCenter, self._design)
        painter.setPen(QPen(QColor("#CBD5E1"), 0.5)); painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)


# ── Main page ─────────────────────────────────────────────────────────────────

class BarcodePrintPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG_MAIN};")
        self._row_dict: dict | None = None
        self._elements: list[dict] = []
        self._field_descriptors: list[dict] = []
        # element name → current displayed text
        self._current_values: dict[str, str] = {}
        # element name → input widget  (only for visible fields)
        self._field_widgets: dict[str, QWidget] = {}
        # component_id → element name  (for resolving LINK → LOOKUP)
        self._cid_to_name: dict[str, str] = {}
        self._build_ui()
        self._btn_print.setEnabled(False)

    # ── UI skeleton ───────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")
        spl.addWidget(self._build_left())
        spl.addWidget(self._build_right())
        spl.setSizes([640, 360])
        root.addWidget(spl)

    def _build_left(self) -> QWidget:
        outer = QWidget(); outer.setStyleSheet(f"background: {_BG_MAIN};")
        vbox = QVBoxLayout(outer); vbox.setContentsMargins(24, 16, 14, 16); vbox.setSpacing(12)

        hdr = QHBoxLayout()
        title = QLabel("Barcode Print")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {_TEXT};")
        hdr.addWidget(title); hdr.addStretch()
        self._btn_print = StandardButton("Print", icon_name="fa5s.print", variant="primary")
        self._btn_print.clicked.connect(self._on_print)
        hdr.addWidget(self._btn_print)
        vbox.addLayout(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            + _SLIM_SCROLLBAR_STYLE)

        content = QWidget(); content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content); cv.setContentsMargins(0, 0, 8, 0); cv.setSpacing(0)

        wrapper = QFrame(); wrapper.setObjectName("printCard")
        wrapper.setStyleSheet(
            f"QFrame#printCard {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}"
            f" QFrame#printCard > QWidget {{ border: none; }}")
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._card_layout = QVBoxLayout(wrapper)
        self._card_layout.setContentsMargins(0, 0, 0, 0); self._card_layout.setSpacing(0)

        self._card_layout.addWidget(self._build_design_section())
        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine); sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {_BORDER}; border: none;")
        self._card_layout.addWidget(sep1)
        self._card_layout.addWidget(self._build_printer_section())

        # Separator shown only when there are dynamic fields
        self._sep_fields = QFrame(); self._sep_fields.setFrameShape(QFrame.HLine)
        self._sep_fields.setFixedHeight(1)
        self._sep_fields.setStyleSheet(f"background: {_BORDER}; border: none;")
        self._sep_fields.setVisible(False)
        self._card_layout.addWidget(self._sep_fields)

        # Dynamic print-fields container
        self._fields_container = QWidget()
        self._fields_container.setStyleSheet("background: transparent;")
        self._fields_container.setVisible(False)
        self._fields_vbox = QVBoxLayout(self._fields_container)
        self._fields_vbox.setContentsMargins(16, 16, 16, 16); self._fields_vbox.setSpacing(10)
        self._card_layout.addWidget(self._fields_container)

        cv.addWidget(wrapper); cv.addStretch()
        scroll.setWidget(content); vbox.addWidget(scroll, 1)
        return outer

    def _build_design_section(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(10)

        self._inp_code = QLineEdit()
        self._inp_code.setPlaceholderText("Browse to select design code…")
        self._inp_code.setReadOnly(True); self._inp_code.setFocusPolicy(Qt.NoFocus)
        self._inp_code.setFixedHeight(32)
        self._inp_code.setStyleSheet(MODERN_INPUT_STYLE + _READONLY_PICKER_STYLE)
        self._btn_browse_code = QPushButton("···")
        self._btn_browse_code.setFixedHeight(32); self._btn_browse_code.setStyleSheet(_BTN_BROWSE)
        self._btn_browse_code.clicked.connect(self._on_browse_code)
        code_w = QWidget(); code_w.setStyleSheet("background: transparent; border: none;")
        cr = QHBoxLayout(code_w); cr.setContentsMargins(0, 0, 0, 0); cr.setSpacing(6)
        cr.addWidget(self._inp_code); cr.addWidget(self._btn_browse_code)
        _form_row("CODE :", code_w, layout)

        self._inp_name = QLineEdit(); self._inp_name.setReadOnly(True)
        self._inp_name.setFocusPolicy(Qt.NoFocus)
        self._inp_name.setPlaceholderText("")
        self._inp_name.setStyleSheet(
            MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("NAME :", self._inp_name, layout)
        return w

    def _build_printer_section(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16, 16, 16, 16); layout.setSpacing(10)

        self._lbl_timbangan = _status_lbl("NOT CONNECTED", False)
        self._lbl_gate      = _status_lbl("NOT CONNECTED", False)
        _form_row("COM TIMBANGAN :", self._lbl_timbangan, layout)
        _form_row("COM GATE :",      self._lbl_gate,      layout)

        self._combo_speed = make_chevron_combo(["1","2","3","4","5","6","7","8","9","10"])
        try: self._combo_speed.setCurrentText("3")
        except AttributeError: pass
        speed_w = QWidget(); speed_w.setStyleSheet("background: transparent; border: none;")
        sl = QHBoxLayout(speed_w); sl.setContentsMargins(0, 0, 0, 0); sl.setSpacing(0)
        sl.addWidget(self._combo_speed); sl.addStretch()
        _form_row("SPEED :", speed_w, layout)

        self._spin_ml = make_spin(-999, 999, 0); self._spin_ml.setFixedWidth(80)
        ml_w = QWidget(); ml_w.setStyleSheet("background: transparent; border: none;")
        mll = QHBoxLayout(ml_w); mll.setContentsMargins(0, 0, 0, 0)
        mll.addWidget(self._spin_ml); mll.addStretch()
        _form_row("MARGIN LEFT :", ml_w, layout)

        self._spin_mt = make_spin(-999, 999, 0); self._spin_mt.setFixedWidth(80)
        self._chk_dpi = _CheckBox("300 dpi")
        mt_w = QWidget(); mt_w.setStyleSheet("background: transparent; border: none;")
        mtl = QHBoxLayout(mt_w); mtl.setContentsMargins(0, 0, 0, 0); mtl.setSpacing(14)
        mtl.addWidget(self._spin_mt); mtl.addWidget(self._chk_dpi); mtl.addStretch()
        _form_row("MARGIN TOP :", mt_w, layout)

        self._chk_non_zebra = _CheckBox("Non Zebra Printer")
        self._spin_offset = make_spin(-999, 999, -11); self._spin_offset.setFixedWidth(70)
        pt_w = QWidget(); pt_w.setStyleSheet("background: transparent; border: none;")
        ptl = QHBoxLayout(pt_w); ptl.setContentsMargins(0, 0, 0, 0); ptl.setSpacing(14)
        ptl.addWidget(self._chk_non_zebra); ptl.addWidget(self._spin_offset); ptl.addStretch()
        _form_row("PRINTER TYPE :", pt_w, layout)
        return w

    # ── Dynamic fields ────────────────────────────────────────────────────────

    def _clear_dynamic_fields(self):
        while self._fields_vbox.count():
            child = self._fields_vbox.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._field_widgets.clear()
        self._field_descriptors.clear()
        self._current_values.clear()
        self._cid_to_name.clear()
        self._sep_fields.setVisible(False)
        self._fields_container.setVisible(False)

    def _build_dynamic_fields(self, elements: list[dict]):
        self._clear_dynamic_fields()
        self._elements = elements

        # Build component_id → name lookup (used for LINK resolution)
        for e in elements:
            if e.get("type") == "text" and e.get("component_id"):
                self._cid_to_name[e["component_id"]] = e.get("name", "")

        fields = _analyse_fields(elements)
        self._field_descriptors = fields

        if not fields:
            return

        for fd in fields:
            cap   = fd["caption"] or fd["name"]
            name  = fd["name"]
            ftype = fd["type"]

            if ftype == "lookup":
                # Read-only + browse button
                inp = QLineEdit()
                inp.setPlaceholderText(f"Browse to select {cap.lower()}…")
                inp.setReadOnly(True); inp.setFocusPolicy(Qt.NoFocus)
                inp.setFixedHeight(32)
                inp.setStyleSheet(MODERN_INPUT_STYLE + _READONLY_PICKER_STYLE)
                btn = QPushButton("···"); btn.setFixedHeight(32)
                btn.setStyleSheet(_BTN_BROWSE)
                btn.clicked.connect(lambda _checked=False, f=fd: self._on_browse_lookup(f))
                row_w = QWidget(); row_w.setStyleSheet("background: transparent; border: none;")
                rl = QHBoxLayout(row_w); rl.setContentsMargins(0, 0, 0, 0); rl.setSpacing(6)
                rl.addWidget(inp); rl.addWidget(btn)
                _form_row(f"{cap} :", row_w, self._fields_vbox)
                self._field_widgets[name] = inp

            elif ftype == "date":
                cal = _CalendarCombo()
                cal.currentTextChanged.connect(
                    lambda text, n=name: self._on_field_changed(n, text))
                date_w = QWidget(); date_w.setStyleSheet("background: transparent; border: none;")
                dw_l = QHBoxLayout(date_w); dw_l.setContentsMargins(0, 0, 0, 0); dw_l.setSpacing(0)
                dw_l.addWidget(cal); dw_l.addStretch()
                _form_row(f"{cap} :", date_w, self._fields_vbox)
                self._field_widgets[name] = cal
                # Push today's date into the preview immediately
                self._on_field_changed(name, cal.currentText())

            elif ftype == "autofill":
                inp = QLineEdit(); inp.setReadOnly(True); inp.setFocusPolicy(Qt.NoFocus)
                inp.setPlaceholderText(""); inp.setStyleSheet(_AUTOFILL_STYLE)
                _form_row(f"{cap} :", inp, self._fields_vbox)
                self._field_widgets[name] = inp

            elif ftype == "link_readonly":
                inp = QLineEdit(); inp.setReadOnly(True); inp.setFocusPolicy(Qt.NoFocus)
                inp.setPlaceholderText("")
                inp.setStyleSheet(_AUTOFILL_STYLE)
                _form_row(f"{cap} :", inp, self._fields_vbox)
                self._field_widgets[name] = inp

            elif ftype == "freetext":
                inp = QLineEdit()
                inp.setPlaceholderText(f"Enter {cap.lower()}…")
                inp.setStyleSheet(MODERN_INPUT_STYLE)
                inp.textChanged.connect(
                    lambda text, n=name: self._on_field_changed(n, text))
                _form_row(f"{cap} :", inp, self._fields_vbox)
                self._field_widgets[name] = inp

        # PRINT QTY is always the last field regardless of design
        self._spin_print_qty = make_spin(1, 9999, 1); self._spin_print_qty.setFixedWidth(100)
        pq_w = QWidget(); pq_w.setStyleSheet("background: transparent; border: none;")
        pql = QHBoxLayout(pq_w); pql.setContentsMargins(0, 0, 0, 0)
        pql.addWidget(self._spin_print_qty); pql.addStretch()
        _form_row("PRINT QTY :", pq_w, self._fields_vbox)

        self._sep_fields.setVisible(True)
        self._fields_container.setVisible(True)

    # ── Value change propagation ──────────────────────────────────────────────

    def _on_field_changed(self, name: str, text: str):
        """Single entry point for all value changes → updates preview."""
        self._current_values[name] = text
        self._preview.set_values({name: text})

    def _on_browse_lookup(self, fd: dict):
        """Open master-item picker for any LOOKUP field."""
        if not hasattr(self, "_master_item_picker"):
            self._master_item_picker = _MasterItemPickerPopup(self)
            self._master_item_picker.item_picked.connect(self._on_master_item_picked)
        self._active_lookup_fd = fd
        self._master_item_picker.open_modal()

    def _on_master_item_picked(self, part_no: str, item_code: str,
                                name: str, qty: str, whs: str):
        """
        Distribute picked values to:
          • The LOOKUP element  → part_no
          • LINK elements pointing at this LOOKUP → resolved via design_result
          • BATCH NO elements that reference this LOOKUP by name → qty / whs
        """
        fd = getattr(self, "_active_lookup_fd", None)
        if fd is None:
            return

        lookup_name = fd["name"]
        lookup_cid  = fd["component_id"]

        # Mapping from design_result field name → resolved value.
        # Covers all known aliases used in design_result across different designs.
        result_map: dict[str, str] = {
            # generic aliases
            "mmcsap":    item_code,
            "item_code": item_code,
            "itemcode":  item_code,
            "part_no":   part_no,
            "partno":    part_no,
            "qty":       qty,
            "quantity":  qty,
            "whs":       whs,
            "warehouse": whs,
            # design-specific mm* keys
            "mmitno":    item_code,
            "mmcont":    qty,
            "mmwho":     whs,
        }

        updates: dict[str, str] = {}

        # DEBUG — prints to console so you can verify design_result values.
        # Remove this block once field mapping is confirmed correct.
        for e in self._elements:
            if (e.get("type") == "text"
                    and (e.get("design_type") or "").upper() == "LINK"
                    and e.get("design_link", "") == lookup_cid):
                print(f"[DEBUG] LINK element: name={e.get('name')!r} "
                      f"design_result={e.get('design_result')!r} "
                      f"design_link={e.get('design_link')!r}")
        print(f"[DEBUG] lookup_cid={lookup_cid!r}  "
              f"result_map keys={list(result_map.keys())}")
        print(f"[DEBUG] picked → part_no={part_no!r} item_code={item_code!r} "
              f"qty={qty!r} whs={whs!r}")

        # 1. Set the LOOKUP widget itself to part_no
        updates[lookup_name] = part_no
        w = self._field_widgets.get(lookup_name)
        if isinstance(w, QLineEdit):
            w.setText(part_no)

        # 2. Walk all elements for LINKs and BATCH NOs tied to this LOOKUP
        for e in self._elements:
            if e.get("type") != "text":
                continue
            dt       = (e.get("design_type") or "").upper()
            ename    = e.get("name", "")
            res_fld  = (e.get("design_result") or "").lower().strip()

            if dt == "LINK" and e.get("design_link", "") == lookup_cid:
                # Resolve via design_result; fall back to part_no if unknown
                val = result_map.get(res_fld, part_no)
                updates[ename] = val
                widget = self._field_widgets.get(ename)
                if isinstance(widget, QLineEdit):
                    widget.setText(val)

            elif dt == "BATCH NO":
                if e.get("design_batch_no", "") == lookup_name:
                    updates[ename] = qty
                    widget = self._field_widgets.get(ename)
                    if isinstance(widget, QLineEdit):
                        widget.setText(qty)
                wh_elem = e.get("design_wh", "")
                if wh_elem:
                    updates[wh_elem] = whs
                    widget2 = self._field_widgets.get(wh_elem)
                    if isinstance(widget2, QLineEdit):
                        widget2.setText(whs)

        self._current_values.update(updates)
        self._preview.set_values(updates)
        self._lbl_item_code.setText(part_no)

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: #DCE5ED;")
        vbox = QVBoxLayout(w); vbox.setContentsMargins(6, 16, 20, 16); vbox.setSpacing(0)

        ph = QHBoxLayout()
        pt = QLabel("Preview")
        pt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        ph.addWidget(pt); ph.addStretch()
        vbox.addLayout(ph); vbox.addSpacing(6)

        pf = QFrame()
        pf.setStyleSheet(
            f"QFrame {{ background: #DCE5ED; border: 1px solid {_BORDER}; border-radius: 12px; }}")
        pf.setMinimumHeight(200)
        pfv = QVBoxLayout(pf); pfv.setContentsMargins(0, 0, 0, 0)
        self._preview = _CanvasPreview()
        pfv.addWidget(self._preview)
        vbox.addWidget(pf, 5); vbox.addSpacing(12)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFixedHeight(2)
        sep.setStyleSheet(f"background: {_BORDER2}; border: none; margin: 0px;")
        vbox.addSpacing(4); vbox.addWidget(sep); vbox.addSpacing(12)

        th = QHBoxLayout()
        tt = QLabel("Part No. Print")
        tt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        th.addWidget(tt); th.addStretch()
        vbox.addLayout(th); vbox.addSpacing(6)

        tf = QFrame(); tf.setStyleSheet(_CARD_STYLE); tf.setFixedHeight(60)
        tfv = QVBoxLayout(tf); tfv.setContentsMargins(12, 8, 12, 8); tfv.setSpacing(0)
        self._lbl_item_code = QLabel("")
        self._lbl_item_code.setStyleSheet(
            f"color: {_BLUE}; font-size: 18px; font-weight: 700; "
            "background: transparent; border: none;")
        self._lbl_item_code.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._lbl_item_code.setWordWrap(True)
        tfv.addWidget(self._lbl_item_code)
        vbox.addWidget(tf)
        return w

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_browse_code(self):
        if not hasattr(self, "_design_picker"):
            self._design_picker = _DesignPickerPopup(self)
            self._design_picker.design_picked.connect(
                lambda code, _name: self._load_design_from_code(code))
        self._design_picker.open_modal()

    def _load_design_from_code(self, code: str):
        if not code:
            return
        row_dict = None
        try:
            from server.repositories.mbarcd_repo import fetch_mbarcd_by_pk, fetch_mbarcd_layout
            row_dict = fetch_mbarcd_by_pk(code)
            if row_dict:
                layout = fetch_mbarcd_layout(code)
                if layout:
                    row_dict["usrm"] = layout.get("usrm", "")
                    row_dict["itrm"] = layout.get("itrm", "")
        except Exception:
            pass
        dname = (row_dict.get("name", "") if row_dict else "") or code
        self.load_design_by_code(code, dname, row_dict)

    def _on_print(self):
        code = self._inp_code.text().strip()
        if not code:
            return
        try: speed = self._combo_speed.currentText()
        except AttributeError: speed = "3"
        qty    = self._spin_print_qty.value()
        values = dict(self._current_values)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_design_by_code(self, code: str, name: str = "", row_dict: dict | None = None):
        if not code:
            return
        self._inp_code.setText(code)
        self._inp_name.setText(name or code)
        self._btn_print.setEnabled(True)
        self._lbl_item_code.setText("")

        usrm = ""; itrm = ""
        if row_dict:
            self._row_dict = row_dict
            usrm = row_dict.get("usrm") or row_dict.get("bsusrm") or ""
            itrm = row_dict.get("itrm") or row_dict.get("bsitrm") or ""

        # Parse elements first so field builder and preview share the same list
        try:
            elements = _json.loads(usrm) if usrm else []
        except Exception:
            elements = []

        if usrm:
            self._preview.set_design(usrm, itrm)
        else:
            self._preview.clear()
            self._fetch_and_refresh_preview(code)

        self._build_dynamic_fields(elements)

        # Seed the preview with the original static text values from the JSON
        initial: dict[str, str] = {
            e["name"]: str(e.get("text", ""))
            for e in elements
            if e.get("type") == "text" and e.get("name")
        }
        self._current_values.update(initial)

    def _fetch_and_refresh_preview(self, code: str):
        try:
            from server.repositories.mbarcd_repo import fetch_mbarcd_layout
            layout = fetch_mbarcd_layout(code)
            if layout:
                usrm = layout.get("usrm", "")
                itrm = layout.get("itrm", "")
                if usrm:
                    self._preview.set_design(usrm, itrm)
                    try:
                        elements = _json.loads(usrm)
                        self._build_dynamic_fields(elements)
                    except Exception:
                        pass
        except Exception:
            pass

    def load_design(self, code: str, name: str = "", row_dict: dict | None = None):
        self.load_design_by_code(code, name, row_dict)

    def set_com_status(self, timbangan: bool = False, gate: bool = False):
        def _upd(lbl: QLabel, ok: bool):
            lbl.setText("CONNECTED" if ok else "NOT CONNECTED")
            lbl.setStyleSheet(
                f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; "
                "font-weight: 600; background: transparent; border: none;")
        _upd(self._lbl_timbangan, timbangan)
        _upd(self._lbl_gate, gate)