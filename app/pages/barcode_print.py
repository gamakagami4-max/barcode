"""
barcode_print.py  —  Barcode Print Page
"""

from __future__ import annotations
import hashlib
import json as _json

import qtawesome as qta
from PySide6.QtCore import Qt, QDate, QSize, QRectF, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QFrame, QSizePolicy, QSplitter, QScrollArea,
    QTextEdit, QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication, QDialog,
    QComboBox, QGraphicsScene, QGraphicsView,
    QGraphicsTextItem, QGraphicsLineItem, QGraphicsRectItem,
    QCalendarWidget,
)


class StandardButton(QPushButton):
    """
    A custom button component with pre-defined styles for
    Primary, Secondary, Danger, and Success variants.
    """
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
                background-color: {bg};
                color: {text_color};
                border-radius: 6px;
                padding: 0px 16px;
                font-weight: 600;
                font-size: 13px;
                {border_style}
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {bg};
            }}
            QPushButton:disabled {{
                background-color: #D1D5DB;
                color: #9CA3AF;
            }}
        """)

        if icon_name:
            self.setIcon(qta.icon(icon_name, color=text_color))
            self.setIconSize(QSize(16, 16))

try:
    from components.barcode_editor.utils import (
        COLORS, MODERN_INPUT_STYLE, make_chevron_combo,
        make_spin, ChevronSpinBox,
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

_DISABLED_STYLE = (
    "QLineEdit:disabled, QSpinBox:disabled, QDateEdit:disabled {"
    "  background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }"
    "QComboBox:disabled {"
    "  background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }"
    "QLabel:disabled { color: #94A3B8; }"
)

_READONLY_PICKER_STYLE = (
    "QLineEdit { background: #F8FAFC; color: #1E293B; border: 1px solid #E2E8F0; "
    "border-radius: 4px; padding: 0px 8px; font-size: 11px; "
    "min-height: 30px; max-height: 30px; }"
)

_ACCENT      = "#6366F1"
_ACCENT_LIGHT= "#EEF2FF"
_BORDER2     = "#CBD5E1"
_TEXT        = "#1E293B"
_MUTED       = "#64748B"
_HINT        = "#94A3B8"
_BLUE        = "#3B82F6"
_SUCCESS     = "#16A34A"
_DANGER      = "#DC2626"

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

_BTN_GHOST = f"""
QPushButton {{
    background: transparent; color: {_MUTED};
    border: 1px solid {_BORDER2}; border-radius: 4px;
    font-size: 10px; padding: 2px 8px; min-height: 20px;
}}
QPushButton:hover {{ background: #F1F5F9; }}
"""

_CARD_STYLE = (
    f"QFrame {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}"
    " QFrame QWidget { border: none; background: transparent; }"
    " QFrame QFrame { border: none; background: transparent; }"
)

# Modern slim scrollbar style (6px, rounded handles)
_SLIM_SCROLLBAR_STYLE = """
    QScrollBar:vertical {
        background: transparent; width: 6px; margin: 0;
    }
    QScrollBar::handle:vertical {
        background: #B0BEC5; border-radius: 3px; min-height: 24px;
    }
    QScrollBar::handle:vertical:hover { background: #90A4AE; }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
    QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
    QScrollBar:horizontal {
        background: transparent; height: 6px; margin: 0;
    }
    QScrollBar::handle:horizontal {
        background: #B0BEC5; border-radius: 3px; min-width: 24px;
    }
    QScrollBar::handle:horizontal:hover { background: #90A4AE; }
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
    QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: none; }
"""


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_LEGACY_BLUE}; font-size: 9px; text-transform: uppercase; "
        "background: transparent; border: none;"
    )
    l.setFixedWidth(100)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return l


def _status_lbl(text: str, ok: bool) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; "
        "font-weight: 600; background: transparent; border: none;"
    )
    return l


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
        w  = self._box_size + 7 + fm.horizontalAdvance(self.text()) + 6
        h  = max(self._box_size + 4, fm.height() + 4)
        return QSize(w, h)

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        b = self._box_size
        y = (self.height() - b) // 2
        p.setBrush(QColor("#FFFFFF")); p.setPen(QPen(QColor("#94A3B8"), 1.5))
        path = QPainterPath(); path.addRoundedRect(0, y, b, b, 3, 3); p.drawPath(path)
        if self.isChecked():
            pen = QPen(QColor("#1E293B"), 2.0); pen.setCapStyle(Qt.RoundCap); pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen); cx, cy = b // 2, y + b // 2
            p.drawLine(int(cx-3), int(cy), int(cx-1), int(cy+3))
            p.drawLine(int(cx-1), int(cy+3), int(cx+4), int(cy-3))
        p.setPen(QPen(QColor("#1E293B"))); p.setFont(QFont("Segoe UI", 10))
        tx = b + 7
        p.drawText(tx, 0, self.width()-tx, self.height(), Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def mousePressEvent(self, _event):
        self.setChecked(not self.isChecked()); self.update()


# ── Calendar combo ────────────────────────────────────────────────────────────

class _CalendarCombo(QWidget):
    """
    A button that pops up a compact QCalendarWidget and formats
    the selected date as 'dd-MMM-yyyy', matching the old combo output.
    """
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
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._btn = QPushButton()
        self._btn.setCursor(Qt.PointingHandCursor)
        self._btn.setStyleSheet(f"""
            QPushButton {{
                background: #FFFFFF; border: 1px solid #CBD5E1;
                border-radius: 4px; padding: 5px 10px;
                font-size: 12px; color: #1E293B;
                text-align: left;
            }}
            QPushButton:hover   {{ border-color: #6366F1; }}
            QPushButton:disabled {{
                background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0;
            }}
        """)
        self._btn.clicked.connect(self._open_popup)
        self._update_btn_text(self._date, open_=False)
        layout.addWidget(self._btn)

    def _update_btn_text(self, d: QDate, open_: bool = False):
        chevron = "▴" if open_ else "▾"
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
            self._popup.close()
            self._update_btn_text(self._date, open_=False)
            return

        dlg = QDialog(self, Qt.Popup | Qt.FramelessWindowHint)
        dlg.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
        """)
        v = QVBoxLayout(dlg)
        v.setContentsMargins(6, 6, 6, 6)

        cal = QCalendarWidget()
        cal.setSelectedDate(self._date)
        cal.setGridVisible(False)
        cal.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        cal.setStyleSheet(f"""
            QCalendarWidget QWidget {{ background: #FFFFFF; color: #1E293B; }}
            QCalendarWidget QAbstractItemView {{
                font-size: 12px;
                selection-background-color: #3B82F6;
                selection-color: #FFFFFF;
                gridline-color: transparent;
            }}
            QCalendarWidget QAbstractItemView:enabled {{
                color: #1E293B; background: #FFFFFF;
            }}
            QCalendarWidget QAbstractItemView:disabled {{ color: #94A3B8; }}
            QCalendarWidget QToolButton {{
                color: #1E293B; background: transparent; border: none;
                font-size: 12px; font-weight: 600;
            }}
            QCalendarWidget QToolButton:hover {{
                background: #F1F5F9; border-radius: 4px;
            }}
            QCalendarWidget #qt_calendar_navigationbar {{
                background: #F8FAFC; border-bottom: 1px solid #E2E8F0;
            }}
        """)
        cal.clicked.connect(lambda d: self._on_date_picked(d, dlg))
        v.addWidget(cal)

        dlg.adjustSize()

        screen = QApplication.primaryScreen().availableGeometry()
        pos_below = self._btn.mapToGlobal(self._btn.rect().bottomLeft())
        pos_above = self._btn.mapToGlobal(self._btn.rect().topLeft())
        if pos_below.y() + dlg.height() > screen.bottom():
            dlg.move(pos_above.x(), pos_above.y() - dlg.height())
        else:
            dlg.move(pos_below)

        self._update_btn_text(self._date, open_=True)
        dlg.finished.connect(lambda _: self._update_btn_text(self._date, open_=False))
        self._popup = dlg
        dlg.exec()

    def _on_date_picked(self, d: QDate, dlg: QDialog):
        self._date = d
        dlg.accept()
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
                        self._date = d
                        self._update_btn_text(d, open_=False)
                except Exception:
                    pass
                break

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._btn.setEnabled(enabled)


# ── Design picker ─────────────────────────────────────────────────────────────

class _DesignPickerPopup(QDialog):
    design_picked = Signal(str, str)

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Select Design")
        self.setMinimumSize(520, 460)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {_WHITE}; }}")
        self._records: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self); vbox.setContentsMargins(0,0,0,0); vbox.setSpacing(0)
        header = QWidget(); header.setStyleSheet(f"background: {_WHITE}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header); hl.setContentsMargins(16,14,16,14)
        title = QLabel("Select Design"); title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        hl.addWidget(title); hl.addStretch(); vbox.addWidget(header)

        search_row = QWidget(); search_row.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {_BORDER};")
        sr = QHBoxLayout(search_row); sr.setContentsMargins(14,10,14,10); sr.setSpacing(8)
        search_icon = QLabel("⌕"); search_icon.setStyleSheet(f"font-size: 15px; color: {_HINT}; background: transparent; border: none;")
        sr.addWidget(search_icon)
        self._search = QLineEdit(); self._search.setPlaceholderText("Search code or name…")
        self._search.setFrame(False); self._search.setStyleSheet(f"border: none; background: transparent; font-size: 12px; color: {_TEXT};")
        self._search.textChanged.connect(self._filter); self._search.installEventFilter(self)
        sr.addWidget(self._search); vbox.addWidget(search_row)

        col_hdr = QWidget(); col_hdr.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        ch = QHBoxLayout(col_hdr); ch.setContentsMargins(16,7,16,7); ch.setSpacing(0)
        def _ch(text, w=None):
            l = QLabel(text); l.setStyleSheet(f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; letter-spacing: 0.5px; background: transparent;")
            if w: l.setFixedWidth(w)
            return l
        ch.addWidget(_ch("CODE", 150)); ch.addWidget(_ch("NAME")); vbox.addWidget(col_hdr)

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
        self._list.itemSelectionChanged.connect(lambda: self._select_btn.setEnabled(len(self._list.selectedItems()) > 0))
        vbox.addWidget(self._list, 1)

        footer = QWidget(); footer.setStyleSheet(f"background: #F8FAFC; border-top: 1px solid {_BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16,10,16,10); fl.setSpacing(8)
        self._footer = QLabel(); self._footer.setStyleSheet(f"font-size: 11px; color: {_HINT}; background: transparent;")
        fl.addWidget(self._footer); fl.addStretch()
        cancel_btn = QPushButton("Cancel"); cancel_btn.setStyleSheet(_BTN_SECONDARY); cancel_btn.clicked.connect(self.reject)
        self._select_btn = QPushButton("Select"); self._select_btn.setStyleSheet(_BTN_PRIMARY); self._select_btn.setEnabled(False); self._select_btn.clicked.connect(self._on_select)
        fl.addWidget(cancel_btn); fl.addSpacing(6); fl.addWidget(self._select_btn); vbox.addWidget(footer)

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
            rl = QHBoxLayout(row_w); rl.setContentsMargins(16,9,16,9); rl.setSpacing(0)
            code_lbl = QLabel(code); code_lbl.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {_LEGACY_BLUE}; background: transparent; min-width: 150px; max-width: 150px;")
            name_lbl = QLabel(name); name_lbl.setStyleSheet(f"font-size: 12px; color: {_TEXT}; background: transparent;")
            rl.addWidget(code_lbl); rl.addWidget(name_lbl, 1)
            item.setSizeHint(QSize(0, 38)); self._list.addItem(item); self._list.setItemWidget(item, row_w)
        count = len(records)
        self._footer.setText(f"{count} record{'s' if count != 1 else ''}")
        self._select_btn.setEnabled(False)

    def _filter(self, q: str):
        q = q.lower()
        filtered = [r for r in self._records if q in str(r.get("pk","")).lower() or q in str(r.get("name","")).lower()] if q else self._records
        self._rebuild_list(filtered)

    def _on_activated(self, item): self._on_select()

    def _on_select(self):
        items = self._list.selectedItems()
        if not items: return
        data = items[0].data(Qt.UserRole)
        if data:
            self.design_picked.emit(data[0], data[1])
            self.accept()

    def open_modal(self):
        self._load_records(); self._search.clear(); self._rebuild_list(self._records); self._search.setFocus(); self.exec()


# ── Master Item picker (Part No. Print browser) ───────────────────────────────

class _MasterItemPickerPopup(QDialog):
    """
    Picker modal for Part No. Print.
    Columns: PART NO PRINT | ITEM CODE | NAME
    Emits item_picked(part_no, item_code, name, qty, whs) on selection.
    """
    item_picked = Signal(str, str, str, str, str)   # part_no, item_code, name, qty, whs

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Select Master Item")
        self.setMinimumSize(680, 500)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {_WHITE}; }}")
        self._records: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self); vbox.setContentsMargins(0, 0, 0, 0); vbox.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────────
        header = QWidget()
        header.setStyleSheet(f"background: {_WHITE}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header); hl.setContentsMargins(16, 14, 16, 14)
        title = QLabel("Select Master Item")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        hl.addWidget(title); hl.addStretch()
        vbox.addWidget(header)

        # ── Search bar ────────────────────────────────────────────────────────
        search_row = QWidget()
        search_row.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {_BORDER};")
        sr = QHBoxLayout(search_row); sr.setContentsMargins(14, 10, 14, 10); sr.setSpacing(8)
        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(f"font-size: 15px; color: {_HINT}; background: transparent; border: none;")
        sr.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search part no., item code, or name…")
        self._search.setFrame(False)
        self._search.setStyleSheet(f"border: none; background: transparent; font-size: 12px; color: {_TEXT};")
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        sr.addWidget(self._search)
        vbox.addWidget(search_row)

        # ── Column header ─────────────────────────────────────────────────────
        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        ch = QHBoxLayout(col_hdr); ch.setContentsMargins(16, 7, 16, 7); ch.setSpacing(0)

        def _ch(text, w=None):
            l = QLabel(text)
            l.setStyleSheet(
                f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; "
                "letter-spacing: 0.5px; background: transparent;"
            )
            if w:
                l.setFixedWidth(w)
            return l

        ch.addWidget(_ch("PART NO PRINT", 160))
        ch.addWidget(_ch("ITEM CODE", 160))
        ch.addWidget(_ch("NAME"))
        vbox.addWidget(col_hdr)

        # ── List ──────────────────────────────────────────────────────────────
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {_WHITE}; border: none;
                font-size: 12px; color: {_TEXT}; outline: none;
            }}
            QListWidget::item {{
                padding: 0px; border-bottom: 1px solid {_BORDER};
            }}
            QListWidget::item:selected {{ background: {_ACCENT_LIGHT}; }}
            QListWidget::item:hover:!selected {{ background: #F8FAFC; }}
            QScrollBar:vertical {{ background: transparent; width: 5px; }}
            QScrollBar::handle:vertical {{
                background: {_BORDER2}; border-radius: 2px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._list.itemDoubleClicked.connect(self._on_activated)
        self._list.itemSelectionChanged.connect(
            lambda: self._select_btn.setEnabled(len(self._list.selectedItems()) > 0)
        )
        vbox.addWidget(self._list, 1)

        # ── Footer ────────────────────────────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(f"background: #F8FAFC; border-top: 1px solid {_BORDER};")
        fl = QHBoxLayout(footer); fl.setContentsMargins(16, 10, 16, 10); fl.setSpacing(8)
        self._footer = QLabel()
        self._footer.setStyleSheet(f"font-size: 11px; color: {_HINT}; background: transparent;")
        fl.addWidget(self._footer); fl.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)
        self._select_btn = QPushButton("Select")
        self._select_btn.setStyleSheet(_BTN_PRIMARY)
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select)
        fl.addWidget(cancel_btn); fl.addSpacing(6); fl.addWidget(self._select_btn)
        vbox.addWidget(footer)

    # ── Event filter: keyboard navigation ─────────────────────────────────────

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide(); return True
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                items = self._list.selectedItems()
                if items:
                    self._on_activated(items[0])
                elif self._list.count() > 0:
                    self._on_activated(self._list.item(0))
                return True
        return super().eventFilter(obj, event)

    # ── Data ──────────────────────────────────────────────────────────────────

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
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(16, 9, 16, 9); rl.setSpacing(0)

            part_lbl = QLabel(part_no)
            part_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {_LEGACY_BLUE}; "
                "background: transparent; min-width: 160px; max-width: 160px;"
            )
            code_lbl = QLabel(item_code)
            code_lbl.setStyleSheet(
                f"font-size: 12px; color: {_MUTED}; "
                "background: transparent; min-width: 160px; max-width: 160px;"
            )
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(f"font-size: 12px; color: {_TEXT}; background: transparent;")

            rl.addWidget(part_lbl)
            rl.addWidget(code_lbl)
            rl.addWidget(name_lbl, 1)

            item.setSizeHint(QSize(0, 38))
            self._list.addItem(item)
            self._list.setItemWidget(item, row_w)

        count = len(records)
        self._footer.setText(f"{count} record{'s' if count != 1 else ''}")
        self._select_btn.setEnabled(False)

    def _filter(self, q: str):
        q = q.lower()
        if not q:
            self._rebuild_list(self._records)
            return
        filtered = [
            r for r in self._records
            if q in str(r.get("po_no")      or "").lower()
            or q in str(r.get("pk")          or "").lower()
            or q in str(r.get("description") or "").lower()
        ]
        self._rebuild_list(filtered)

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_activated(self, _item):
        self._on_select()

    def _on_select(self):
        items = self._list.selectedItems()
        if not items:
            return
        data = items[0].data(Qt.UserRole)
        if data:
            part_no, item_code, name, qty, whs = data
            self.item_picked.emit(part_no, item_code, name, qty, whs)
            self.accept()

    def open_modal(self):
        self._load_records()
        self._search.clear()
        self._rebuild_list(self._records)
        self._search.setFocus()
        self.exec()


# ── Real canvas preview using QGraphicsView ───────────────────────────────────

class _CanvasPreview(QWidget):
    """
    Renders the actual barcode design canvas by deserializing the usrm JSON
    into a read-only QGraphicsScene, exactly like the editor does.
    Canvas is shown at 100% (1:1) scale and is scrollable if it overflows.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._usrm: list[dict] = []
        self._canvas_w = 600
        self._canvas_h = 400
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._scene = QGraphicsScene()
        self._scene.setBackgroundBrush(QBrush(QColor("#FFFFFF")))

        self._view = QGraphicsView(self._scene)
        self._view.setBackgroundBrush(QBrush(Qt.transparent))
        self._view.viewport().setAutoFillBackground(False)
        self._view.setRenderHint(QPainter.Antialiasing)
        self._view.setRenderHint(QPainter.TextAntialiasing)
        self._view.setStyleSheet(
            "QGraphicsView { background: transparent; border: none; }"
            + _SLIM_SCROLLBAR_STYLE
        )
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
        self._scene.clear()

        try:
            elements = _json.loads(usrm_json) if usrm_json else []
        except Exception:
            elements = []

        canvas_w, canvas_h = 600, 400
        if itrm_json:
            try:
                meta = _json.loads(itrm_json)
                canvas_w = int(meta.get("canvas_w", canvas_w))
                canvas_h = int(meta.get("canvas_h", canvas_h))
            except Exception:
                pass

        if not elements:
            self._view.setVisible(False)
            self._placeholder.setVisible(True)
            return

        self._canvas_w = canvas_w
        self._canvas_h = canvas_h
        self._scene.setSceneRect(QRectF(0, 0, canvas_w, canvas_h))

        bg = self._scene.addRect(QRectF(0, 0, canvas_w, canvas_h), QPen(QColor("#CBD5E1"), 1), QBrush(QColor("#FFFFFF")))
        bg.setZValue(-1000)

        for d in sorted(elements, key=lambda x: x.get("z", 0)):
            self._add_element(d)

        self._view.setVisible(True)
        self._placeholder.setVisible(False)
        # Show at 1:1 scale — no fitInView
        self._view.resetTransform()

    def _add_element(self, d: dict):
        kind = d.get("type")
        x    = d.get("aabb_x", d.get("x", 0))
        y    = d.get("aabb_y", d.get("y", 0))
        z    = d.get("z", 0)
        rot  = d.get("rotation", 0)
        vis  = d.get("visible", True)

        item = None

        if kind == "text":
            item = QGraphicsTextItem(d.get("text", ""))
            font = QFont(d.get("font_family", "Arial"), d.get("font_size", 10))
            font.setBold(d.get("bold", False))
            font.setItalic(d.get("italic", False))
            item.setFont(font)
            item.setDefaultTextColor(QColor(d.get("color", "#000000")))
            item.document().setDocumentMargin(0)

        elif kind == "line":
            item = QGraphicsLineItem(0, 0, d.get("x2", 100), d.get("y2", 0))
            item.setPen(QPen(Qt.black, max(1, d.get("thickness", 2))))

        elif kind == "rect":
            item = QGraphicsRectItem(0, 0, d.get("width", 100), d.get("height", 50))
            item.setPen(QPen(Qt.black, max(1, d.get("border_width", 2))))
            item.setBrush(Qt.NoBrush)

        elif kind == "barcode":
            w = d.get("container_width", 80)
            h = d.get("container_height", 80)
            item = _BarcodePreviewItem(w, h, d.get("design", "CODE128"))

        if item is None:
            return

        item.setZValue(z)
        item.setVisible(vis)

        if rot != 0:
            br = item.boundingRect()
            item.setTransformOriginPoint(br.center())
            item.setRotation(rot)

        item.setPos(0, 0)
        self._scene.addItem(item)
        aabb0 = item.mapToScene(item.boundingRect()).boundingRect()
        off_x = aabb0.left()
        off_y = aabb0.top()
        item.setPos(x - off_x, y - off_y)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # No auto-fit — canvas stays at 1:1 and scrolls if needed

    def clear(self):
        self._scene.clear()
        self._view.setVisible(False)
        self._placeholder.setVisible(True)


class _BarcodePreviewItem(QGraphicsRectItem):
    def __init__(self, w: float, h: float, design: str = "CODE128"):
        super().__init__(0, 0, w, h)
        self._design = design
        self.setPen(QPen(Qt.NoPen))
        self.setBrush(Qt.NoBrush)

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        w, h = r.width(), r.height()

        painter.fillRect(r, QColor("#FFFFFF"))

        bar_h = h * 0.72
        bar_top = r.top()
        seed = int(hashlib.md5(self._design.encode()).hexdigest()[:8], 16)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(Qt.black))
        x = r.left() + 2
        i = 0
        while x < r.right() - 2:
            bar_w = max(1.0, float(((seed >> (i % 24)) & 3) + 1))
            if i % 2 == 0:
                painter.drawRect(int(x), int(bar_top), max(1, int(bar_w)), int(bar_h))
            x += bar_w + 0.8
            i += 1

        label_top = bar_top + bar_h + 2
        label_h   = h - bar_h - 2
        if label_h > 4:
            font = QFont("Courier New", max(5, int(label_h * 0.55)))
            painter.setFont(font)
            painter.setPen(QPen(QColor("#1E293B")))
            painter.drawText(
                int(r.left()), int(label_top), int(w), int(label_h),
                Qt.AlignHCenter | Qt.AlignVCenter,
                self._design,
            )

        painter.setPen(QPen(QColor("#CBD5E1"), 0.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(r)


def _form_row(label: str, widget: QWidget, layout):
    row = QWidget(); row.setStyleSheet("background: transparent; border: none;")
    rl = QHBoxLayout(row); rl.setContentsMargins(0,0,0,0); rl.setSpacing(10); rl.setAlignment(Qt.AlignVCenter)
    lbl_w = _lbl(label); lbl_w.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    rl.addWidget(lbl_w); rl.addWidget(widget, 1); layout.addWidget(row)


# ── Main page ─────────────────────────────────────────────────────────────────

class BarcodePrintPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG_MAIN};")
        self._row_dict: dict | None = None
        self._build_ui()
        self._print_fields_with_sep.setEnabled(False)
        self._print_fields_with_sep.setVisible(False)
        self._btn_print.setEnabled(False)

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(0)
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")
        spl.addWidget(self._build_left())
        spl.addWidget(self._build_right())
        spl.setSizes([640, 360])
        root.addWidget(spl)

    def _build_left(self) -> QWidget:
        outer = QWidget(); outer.setStyleSheet(f"background: {_BG_MAIN};")
        vbox = QVBoxLayout(outer); vbox.setContentsMargins(24,16,14,16); vbox.setSpacing(12)

        hdr = QHBoxLayout()
        title = QLabel("Barcode Print"); title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {_TEXT};")
        hdr.addWidget(title); hdr.addStretch()

        self._btn_print = StandardButton("Print", icon_name="fa5s.print", variant="primary")
        self._btn_print.clicked.connect(self._on_print)

        hdr.addWidget(self._btn_print)
        vbox.addLayout(hdr)

        scroll = QScrollArea(); scroll.setWidgetResizable(True); scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            + _SLIM_SCROLLBAR_STYLE
        )

        content = QWidget(); content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content); cv.setContentsMargins(0,0,8,0); cv.setSpacing(0)

        wrapper = QFrame(); wrapper.setObjectName('printCard')
        wrapper.setStyleSheet(
            f'QFrame#printCard {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}'
            f' QFrame#printCard > QWidget {{ border: none; }}'
        )
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        wv = QVBoxLayout(wrapper); wv.setContentsMargins(0,0,0,0); wv.setSpacing(0)

        wv.addWidget(self._build_design_section())
        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine); sep1.setFixedHeight(1); sep1.setStyleSheet(f"background: {_BORDER}; border: none;")
        wv.addWidget(sep1)
        wv.addWidget(self._build_printer_section())

        self._print_fields_with_sep = QWidget(); self._print_fields_with_sep.setStyleSheet("background: transparent;")
        pfs = QVBoxLayout(self._print_fields_with_sep); pfs.setContentsMargins(0,0,0,0); pfs.setSpacing(0)
        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine); sep2.setFixedHeight(1); sep2.setStyleSheet(f"background: {_BORDER}; border: none;")
        pfs.addWidget(sep2)
        pfs.addWidget(self._build_print_fields_section())
        wv.addWidget(self._print_fields_with_sep)

        cv.addWidget(wrapper); cv.addStretch()
        scroll.setWidget(content); vbox.addWidget(scroll, 1)
        return outer

    def _build_design_section(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16); layout.setSpacing(10)

        # CODE: read-only, populated only via the browse picker
        self._inp_code = QLineEdit()
        self._inp_code.setPlaceholderText("Browse to select design code…")
        self._inp_code.setReadOnly(True)
        self._inp_code.setFocusPolicy(Qt.NoFocus)
        self._inp_code.setFixedHeight(32)
        self._inp_code.setStyleSheet(MODERN_INPUT_STYLE + _READONLY_PICKER_STYLE)

        self._btn_browse_code = QPushButton("···"); self._btn_browse_code.setFixedHeight(32); self._btn_browse_code.setStyleSheet(_BTN_BROWSE)
        self._btn_browse_code.setToolTip("Browse design codes"); self._btn_browse_code.clicked.connect(self._on_browse_code)
        code_w = QWidget(); code_w.setStyleSheet("background: transparent; border: none;")
        cr = QHBoxLayout(code_w); cr.setContentsMargins(0,0,0,0); cr.setSpacing(6)
        cr.addWidget(self._inp_code); cr.addWidget(self._btn_browse_code)
        _form_row("CODE :", code_w, layout)

        self._inp_name = QLineEdit(); self._inp_name.setReadOnly(True); self._inp_name.setFocusPolicy(Qt.NoFocus)
        self._inp_name.setPlaceholderText("Auto-filled from design code")
        self._inp_name.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("NAME :", self._inp_name, layout)
        return w

    def _build_printer_section(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16); layout.setSpacing(10)

        self._lbl_timbangan = _status_lbl("NOT CONNECTED", False)
        self._lbl_gate      = _status_lbl("NOT CONNECTED", False)
        _form_row("COM TIMBANGAN :", self._lbl_timbangan, layout)
        _form_row("COM GATE :",      self._lbl_gate,      layout)

        self._combo_speed = make_chevron_combo(["1","2","3","4","5","6","7","8","9","10"])
        try: self._combo_speed.setCurrentText("3")
        except AttributeError: pass
        speed_w = QWidget(); speed_w.setStyleSheet("background: transparent; border: none;")
        sl = QHBoxLayout(speed_w); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0); sl.addWidget(self._combo_speed); sl.addStretch()
        _form_row("SPEED :", speed_w, layout)

        self._spin_ml = make_spin(-999, 999, 0); self._spin_ml.setFixedWidth(80)
        ml_w = QWidget(); ml_w.setStyleSheet("background: transparent; border: none;")
        mll = QHBoxLayout(ml_w); mll.setContentsMargins(0,0,0,0); mll.addWidget(self._spin_ml); mll.addStretch()
        _form_row("MARGIN LEFT :", ml_w, layout)

        self._spin_mt = make_spin(-999, 999, 0); self._spin_mt.setFixedWidth(80)
        self._chk_dpi = _CheckBox("300 dpi")
        mt_w = QWidget(); mt_w.setStyleSheet("background: transparent; border: none;")
        mtl = QHBoxLayout(mt_w); mtl.setContentsMargins(0,0,0,0); mtl.setSpacing(14); mtl.addWidget(self._spin_mt); mtl.addWidget(self._chk_dpi); mtl.addStretch()
        _form_row("MARGIN TOP :", mt_w, layout)

        self._chk_non_zebra = _CheckBox("Non Zebra Printer")
        self._spin_offset = make_spin(-999, 999, -11); self._spin_offset.setFixedWidth(70); self._spin_offset.setToolTip("Printer offset")
        pt_w = QWidget(); pt_w.setStyleSheet("background: transparent; border: none;")
        ptl = QHBoxLayout(pt_w); ptl.setContentsMargins(0,0,0,0); ptl.setSpacing(14); ptl.addWidget(self._chk_non_zebra); ptl.addWidget(self._spin_offset); ptl.addStretch()
        _form_row("PRINTER TYPE :", pt_w, layout)
        return w

    def _build_print_fields_section(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w); layout.setContentsMargins(16,16,16,16); layout.setSpacing(10)

        # PART NO. PRINT: read-only, populated only via the browse picker
        self._inp_part = QLineEdit()
        self._inp_part.setPlaceholderText("Browse to select part number…")
        self._inp_part.setReadOnly(True)
        self._inp_part.setFocusPolicy(Qt.NoFocus)
        self._inp_part.setFixedHeight(32)
        self._inp_part.setStyleSheet(MODERN_INPUT_STYLE + _READONLY_PICKER_STYLE)

        self._btn_browse_part = QPushButton("···"); self._btn_browse_part.setFixedHeight(32); self._btn_browse_part.setStyleSheet(_BTN_BROWSE)
        self._btn_browse_part.setToolTip("Browse master items")
        self._btn_browse_part.clicked.connect(self._on_browse_part)
        part_w = QWidget(); part_w.setStyleSheet("background: transparent; border: none;")
        pl = QHBoxLayout(part_w); pl.setContentsMargins(0,0,0,0); pl.setSpacing(6)
        pl.addWidget(self._inp_part); pl.addWidget(self._btn_browse_part)
        _form_row("PART NO. PRINT :", part_w, layout)

        self._inp_qty = QLineEdit(); self._inp_qty.setReadOnly(True); self._inp_qty.setFocusPolicy(Qt.NoFocus)
        self._inp_qty.setPlaceholderText("Auto-filled")
        self._inp_qty.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("QTY :", self._inp_qty, layout)

        self._inp_whs = QLineEdit(); self._inp_whs.setReadOnly(True); self._inp_whs.setFocusPolicy(Qt.NoFocus)
        self._inp_whs.setPlaceholderText("Auto-filled")
        self._inp_whs.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("WHS :", self._inp_whs, layout)

        self._date_combo = _CalendarCombo()
        self._date_combo.setFixedWidth(200)
        date_w = QWidget(); date_w.setStyleSheet('background: transparent; border: none;')
        dw_l = QHBoxLayout(date_w); dw_l.setContentsMargins(0,0,0,0); dw_l.setSpacing(0)
        dw_l.addWidget(self._date_combo); dw_l.addStretch()
        _form_row("DATE CODE :", date_w, layout)

        self._spin_print_qty = make_spin(1, 9999, 1); self._spin_print_qty.setFixedWidth(100)
        pq_w = QWidget(); pq_w.setStyleSheet("background: transparent; border: none;")
        pql = QHBoxLayout(pq_w); pql.setContentsMargins(0,0,0,0); pql.addWidget(self._spin_print_qty); pql.addStretch()
        _form_row("PRINT QTY :", pq_w, layout)
        return w

    def _build_right(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: #DCE5ED;")
        vbox = QVBoxLayout(w); vbox.setContentsMargins(6,16,20,16); vbox.setSpacing(0)

        ph = QHBoxLayout()
        pt = QLabel("Preview"); pt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        ph.addWidget(pt); ph.addStretch()
        vbox.addLayout(ph); vbox.addSpacing(6)

        pf = QFrame()
        pf.setStyleSheet(f"QFrame {{ background: #DCE5ED; border: 1px solid {_BORDER}; border-radius: 12px; }}")
        pf.setMinimumHeight(200)
        pfv = QVBoxLayout(pf); pfv.setContentsMargins(0,0,0,0)
        self._preview = _CanvasPreview()
        pfv.addWidget(self._preview)
        # Preview gets the lion's share of vertical space
        vbox.addWidget(pf, 5)
        vbox.addSpacing(12)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine); sep.setFixedHeight(2)
        sep.setStyleSheet(f"background: {_BORDER2}; border: none; margin: 0px;")
        vbox.addSpacing(4); vbox.addWidget(sep); vbox.addSpacing(12)

        th = QHBoxLayout()
        tt = QLabel("Item Code"); tt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        th.addWidget(tt); th.addStretch()
        vbox.addLayout(th); vbox.addSpacing(6)

        tf = QFrame()
        tf.setStyleSheet(_CARD_STYLE)
        tf.setFixedHeight(60)  # compact — preview gets the space instead
        tfv = QVBoxLayout(tf); tfv.setContentsMargins(12, 8, 12, 8); tfv.setSpacing(0)
        self._lbl_item_code = QLabel("")
        self._lbl_item_code.setStyleSheet(
            f"color: {_BLUE}; font-size: 18px; font-weight: 700; "
            "background: transparent; border: none;"
        )
        self._lbl_item_code.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._lbl_item_code.setWordWrap(True)
        tfv.addWidget(self._lbl_item_code)
        # No stretch — fixed height card
        vbox.addWidget(tf)

        return w

    # ── Internal: load design ─────────────────────────────────────────────────

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

        name = (row_dict.get("name", "") if row_dict else "") or code
        self.load_design_by_code(code, name, row_dict)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_browse_code(self):
        if not hasattr(self, "_design_picker"):
            self._design_picker = _DesignPickerPopup(self)
            self._design_picker.design_picked.connect(
                lambda code, name: self._load_design_from_code(code)
            )
        self._design_picker.open_modal()

    def _on_browse_part(self):
        """Open the master item picker and populate Part No. / QTY / WHS on selection."""
        if not hasattr(self, "_master_item_picker"):
            self._master_item_picker = _MasterItemPickerPopup(self)
            self._master_item_picker.item_picked.connect(self._on_master_item_picked)
        self._master_item_picker.open_modal()

    def _on_master_item_picked(self, part_no: str, item_code: str, name: str, qty: str, whs: str):
        self._inp_part.setText(part_no)
        self._inp_qty.setText(qty)
        self._inp_whs.setText(whs)
        self._lbl_item_code.setText(item_code)

    def _on_print(self):
        code = self._inp_code.text().strip()
        if not code:
            return
        try: speed = self._combo_speed.currentText()
        except AttributeError: speed = "3"
        qty  = self._spin_print_qty.value()
        part = self._inp_part.text().strip() or "(no part)"
        date_s = self._date_combo.currentText()

    # ── Public API ────────────────────────────────────────────────────────────

    def load_design_by_code(self, code: str, name: str = "", row_dict: dict | None = None):
        if not code:
            return

        self._inp_code.setText(code)
        self._inp_name.setText(name or code)
        self._print_fields_with_sep.setEnabled(True)
        self._print_fields_with_sep.setVisible(True)
        self._btn_print.setEnabled(True)

        usrm = ""
        itrm = ""
        if row_dict:
            self._row_dict = row_dict
            usrm = row_dict.get("usrm") or row_dict.get("bsusrm") or ""
            itrm = row_dict.get("itrm") or row_dict.get("bsitrm") or ""

        if usrm:
            self._preview.set_design(usrm, itrm)
        else:
            self._preview.clear()
            self._fetch_and_refresh_preview(code)

    def _fetch_and_refresh_preview(self, code: str):
        try:
            from server.repositories.mbarcd_repo import fetch_mbarcd_layout
            layout = fetch_mbarcd_layout(code)
            if layout:
                usrm = layout.get("usrm", "")
                itrm = layout.get("itrm", "")
                if usrm:
                    self._preview.set_design(usrm, itrm)
        except Exception:
            pass

    def load_design(self, code: str, name: str = "", row_dict: dict | None = None):
        self.load_design_by_code(code, name, row_dict)

    def set_part_no(self, part: str, qty: str = "", whs: str = ""):
        self._inp_part.setText(part); self._inp_qty.setText(qty); self._inp_whs.setText(whs)

    def set_com_status(self, timbangan: bool = False, gate: bool = False):
        def _upd(lbl: QLabel, ok: bool):
            lbl.setText("CONNECTED" if ok else "NOT CONNECTED")
            lbl.setStyleSheet(f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        _upd(self._lbl_timbangan, timbangan)
        _upd(self._lbl_gate, gate)