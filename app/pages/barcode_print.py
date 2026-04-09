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
    QCalendarWidget, QMessageBox,
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

            QScrollBar:vertical {{
                background: transparent; width: 6px;
                margin: 4px 2px 4px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #CBD5E1; border-radius: 3px; min-height: 32px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
            QScrollBar::handle:vertical:pressed {{ background: #64748B; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

            QScrollBar:horizontal {{
                background: transparent; height: 6px;
                margin: 0px 0px 2px 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: #CBD5E1; border-radius: 3px; min-width: 32px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: #94A3B8; }}
            QScrollBar::handle:horizontal:pressed {{ background: #64748B; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
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
        r = items[0].data(Qt.UserRole)
        if r:
            if isinstance(r, (tuple, list)) and len(r) >= 2:
                code, name = str(r[0]), str(r[1])
            elif isinstance(r, dict):
                code = str(r.get("pk") or r.get("code") or "")
                name = str(r.get("name") or "")
            else:
                code, name = str(r), ""
            self.design_picked.emit(code, name)
            self.accept()

    def open_modal(self):
        self._load_records(); self._search.clear()
        self._rebuild_list(self._records); self._search.setFocus(); self.exec()


# ── Master Item picker ────────────────────────────────────────────────────────

class _MasterItemPickerPopup(QDialog):
    item_picked = Signal(str, str, str, str, str)  # part_no, item_code, name, qty, whs

    # Maps mm* field names → actual repo dict keys
    _MM_TO_KEY: dict[str, str] = {
        "mmcsap": "sap_code",
        "mmitno": "pk",
        "mmitds": "description",
        "mmpono": "po_no",
        "mmbrad": "brand",
        "mmwho":  "warehouse",
        "mmtyp1": "type1",
        "mmtyp2": "type2",
        "mmweig": "weight",
        "mmcont": "qty",
        "mmumcd": "uom",
        "mmbupc": "upc",
        "mmitc1": "itc1",
        "mmitc2": "itc2",
        "mmitc3": "itc3",
        "mmitc4": "itc4",
        "mmitc5": "itc5",
        "mmitc6": "itc6",
        "mmitc7": "itc7",
        "mmitc8": "itc8",
        "mmadby": "added_by",
        "mmaddt": "added_at",
        "mmchby": "changed_by",
        "mmchdt": "changed_at",
        "mmchno": "changed_no",
        # bare DB key pass-throughs
        "sap_code":      "sap_code",
        "pk":            "pk",
        "description":   "description",
        "po_no":         "po_no",
        "brand":         "brand",
        "warehouse":     "warehouse",
        "qty":           "qty",
        "uom":           "uom",
        "upc":           "upc",
        "part_no_print": "po_no",
        "name":          "name",
    }

    _DEFAULT_COLS: list[tuple[str, str, int]] = [
        ("mmitno",        "ITEM CODE",     190),
        ("mmitds",        "NAME",          160),
        ("mmbrad",        "BRAND",         100),
        ("mmwho",         "WHS",            80),
        ("part_no_print", "PART NO PRINT", 150),
    ]

    _MM_LABELS: dict[str, str] = {
        "mmcsap":  "SAP CODE",
        "mmitno":  "ITEM CODE",
        "mmitds":  "NAME",
        "mmpono":  "PO NO",
        "mmbrad":  "BRAND",
        "mmwho":   "WHS",
        "mmtyp1":  "TYPE 1",
        "mmtyp2":  "TYPE 2",
        "mmweig":  "WEIGHT",
        "mmcont":  "QTY",
        "mmumcd":  "UOM",
        "mmbupc":  "UPC",
        "mmtlup":  "TLUP",
        "mmtldw":  "TLDW",
        "mmitc1":  "ITC 1",
        "mmitc2":  "ITC 2",
        "mmitc3":  "ITC 3",
        "mmitc4":  "ITC 4",
        "mmitc5":  "ITC 5",
        "mmitc6":  "ITC 6",
        "mmitc7":  "ITC 7",
        "mmitc8":  "ITC 8",
        "mmadby":  "ADDED BY",
        "mmaddt":  "ADDED AT",
        "mmchby":  "CHANGED BY",
        "mmchdt":  "CHANGED AT",
        "mmchno":  "CHANGED NO",
        "part_no_print": "PART NO PRINT",
        "sap_code":      "SAP CODE",
        "pk":            "ITEM CODE",
        "description":   "NAME",
        "po_no":         "PO NO",
        "brand":         "BRAND",
        "warehouse":     "WHS",
        "qty":           "QTY",
        "uom":           "UOM",
        "upc":           "UPC",
    }

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Select Master Item")
        self.setMinimumSize(680, 500); self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background: {_WHITE}; }}")
        self._records: list[dict] = []
        self._dyn_columns: list[str] = []
        self._build_ui()

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

        col_hdr_outer = QWidget()
        col_hdr_outer.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        col_hdr_outer.setFixedHeight(28)
        col_hdr_outer_layout = QHBoxLayout(col_hdr_outer)
        col_hdr_outer_layout.setContentsMargins(0, 0, 0, 0)
        col_hdr_outer_layout.setSpacing(0)

        self._col_hdr_scroll = QScrollArea()
        self._col_hdr_scroll.setFrameShape(QFrame.NoFrame)
        self._col_hdr_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._col_hdr_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._col_hdr_scroll.setStyleSheet(
            f"QScrollArea {{ background: #F1F5F9; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: #F1F5F9; }}")

        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: #F1F5F9;")
        ch = QHBoxLayout(col_hdr); ch.setContentsMargins(16, 0, 16, 0); ch.setSpacing(0)
        self._col_hdr_widget = col_hdr
        self._col_hdr_layout = ch

        self._col_hdr_scroll.setWidget(col_hdr)
        self._col_hdr_scroll.setWidgetResizable(False)
        col_hdr_outer_layout.addWidget(self._col_hdr_scroll)
        vbox.addWidget(col_hdr_outer)

        self._list = QListWidget(); self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self._list.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setMouseTracking(True)
        self._list.setStyleSheet(f"""
            QListWidget {{ background: {_WHITE}; border: none; font-size: 12px; color: {_TEXT}; outline: none; }}
            QListWidget::item {{ padding: 0px; border-bottom: 1px solid {_BORDER}; }}
            QListWidget::item:selected {{ background: {_ACCENT_LIGHT}; }}
            QListWidget::item:hover:!selected {{ background: #F8FAFC; }}

            QScrollBar:vertical {{
                background: transparent; width: 6px;
                margin: 4px 2px 4px 0px;
            }}
            QScrollBar::handle:vertical {{
                background: #CBD5E1; border-radius: 3px; min-height: 32px;
            }}
            QScrollBar::handle:vertical:hover {{ background: #94A3B8; }}
            QScrollBar::handle:vertical:pressed {{ background: #64748B; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}

            QScrollBar:horizontal {{
                background: transparent; height: 6px;
                margin: 0px 0px 2px 0px;
            }}
            QScrollBar::handle:horizontal {{
                background: #CBD5E1; border-radius: 3px; min-width: 32px;
            }}
            QScrollBar::handle:horizontal:hover {{ background: #94A3B8; }}
            QScrollBar::handle:horizontal:pressed {{ background: #64748B; }}
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{ background: none; }}
        """)
        self._list.itemDoubleClicked.connect(self._on_activated)
        self._list.itemClicked.connect(self._on_item_clicked)
        self._list.itemSelectionChanged.connect(
            lambda: self._select_btn.setEnabled(len(self._list.selectedItems()) > 0))
        self._list.horizontalScrollBar().valueChanged.connect(
            lambda val: self._col_hdr_scroll.horizontalScrollBar().setValue(val))
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

    def _get_col_specs(self) -> list[tuple[str, str, int]]:
        if not self._dyn_columns:
            return list(self._DEFAULT_COLS)

        specs: list[tuple[str, str, int]] = []
        specs.append(("mmitno", "ITEM CODE", 190))

        for field in self._dyn_columns:
            field = field.strip()
            if not field or field in ("mmitno", "pk"):
                continue
            label = self._MM_LABELS.get(field, field.upper().replace("_", " "))
            specs.append((field, label, 140))

        return specs

    def _rebuild_column_headers(self):
        while self._col_hdr_layout.count():
            item = self._col_hdr_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        col_specs = self._get_col_specs()
        total_w = sum(w for _, _, w in col_specs) + 48

        print(f"[HEADER] col_specs={[(k, l, w) for k, l, w in col_specs]}")
        print(f"[HEADER] total_w={total_w}")
        print(f"[HEADER] col_hdr_widget size before={self._col_hdr_widget.size()}")
        print(f"[HEADER] col_hdr_scroll size={self._col_hdr_scroll.size()}")
        print(f"[HEADER] col_hdr_scroll viewport size={self._col_hdr_scroll.viewport().size()}")

        for _key, label, width in col_specs:
            lbl = QLabel(label)
            lbl.setFixedHeight(28)
            lbl.setStyleSheet(
                f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; "
                f"letter-spacing: 0.5px; background: #F1F5F9; "
                f"min-width: {width}px; max-width: {width}px;")
            self._col_hdr_layout.addWidget(lbl)
            print(f"[HEADER]   added label={label!r} width={width}")
        self._col_hdr_layout.addStretch()

        fixed_w = max(total_w, 400)
        self._col_hdr_widget.setFixedWidth(fixed_w)
        self._col_hdr_widget.setFixedHeight(28)
        print(f"[HEADER] set col_hdr_widget fixedWidth={fixed_w}")
        print(f"[HEADER] col_hdr_widget size after={self._col_hdr_widget.size()}")

        # Force viewport background
        self._col_hdr_scroll.viewport().setStyleSheet("background: #F1F5F9;")
        self._col_hdr_scroll.viewport().setAutoFillBackground(True)
        print(f"[HEADER] viewport autoFill={self._col_hdr_scroll.viewport().autoFillBackground()}")

    def _rebuild_list(self, records: list[dict]):
        self._list.clear()
        col_specs = self._get_col_specs()
        total_w = sum(w for _, _, w in col_specs) + 48

        for r in records:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, r)
            row_w = QWidget(); row_w.setStyleSheet("background: transparent;")
            row_w.setMinimumWidth(total_w)
            row_w.setAttribute(Qt.WA_TransparentForMouseEvents, True)
            rl = QHBoxLayout(row_w); rl.setContentsMargins(16, 9, 16, 9); rl.setSpacing(0)
            for i, (key, _label, width) in enumerate(col_specs):
                db_key = self._MM_TO_KEY.get(key, key)
                val = str(r.get(db_key) or r.get(key) or "")
                lbl = QLabel(val)
                lbl.setStyleSheet(
                    f"font-size: 12px; font-weight: {'600' if i == 0 else '400'}; "
                    f"color: {_LEGACY_BLUE if i == 0 else _TEXT}; "
                    f"background: transparent; "
                    f"min-width: {width}px; max-width: {width}px;")
                rl.addWidget(lbl)
            rl.addStretch()
            item.setSizeHint(QSize(total_w, 38))
            self._list.addItem(item); self._list.setItemWidget(item, row_w)

        count = len(records)
        self._footer.setText(f"{count} record{'s' if count != 1 else ''}")
        self._select_btn.setEnabled(False)

    def _filter(self, q: str):
        q = q.lower()
        if not q:
            self._rebuild_list(self._records); return
        col_specs = self._get_col_specs()
        def _matches(r: dict) -> bool:
            for key, _label, _w in col_specs:
                db_key = self._MM_TO_KEY.get(key, key)
                if q in str(r.get(db_key) or r.get(key) or "").lower():
                    return True
            for fk in ("pk", "description", "part_no_print", "po_no", "sap_code"):
                if q in str(r.get(fk) or "").lower():
                    return True
            return False
        self._rebuild_list([r for r in self._records if _matches(r)])

    def _on_activated(self, _item): self._on_select()

    def _on_item_clicked(self, item: QListWidgetItem):
        item.setSelected(True)
        self._select_btn.setEnabled(True)

    def _on_select(self):
        items = self._list.selectedItems()
        if not items:
            print("[_on_select] No items selected")
            return

        r = items[0].data(Qt.UserRole)
        print(f"[_on_select] Raw row: {r}")

        if r:
            # ✅ CRITICAL FIX — store raw record for later use
            self._last_raw_record = r

            part_no   = str(r.get("part_no_print") or r.get("po_no") or r.get("upc") or "")
            item_code = str(r.get("pk") or r.get("sap_code") or "")
            name      = str(r.get("name") or r.get("description") or "")
            qty       = str(r.get("qty") or "")
            whs       = str(r.get("warehouse") or r.get("whs") or "")

            print(f"[_on_select] Emitting → part_no={part_no!r} item_code={item_code!r} name={name!r} qty={qty!r} whs={whs!r}")

            self.item_picked.emit(part_no, item_code, name, qty, whs)
            self.accept()
        else:
            print("[_on_select] Row data is None/empty")

    def open_modal(self, dyn_columns: list[str] | None = None):
        self._dyn_columns = dyn_columns or []
        self._rebuild_column_headers()
        self._load_records(); self._search.clear()
        self._rebuild_list(self._records); self._search.setFocus(); self.exec()


# ── Design field analyser ─────────────────────────────────────────────────────

def _analyse_fields(elements: list[dict]) -> list[dict]:
    fields: list[dict] = []
    seen_batch_keys: set[tuple] = set()
    seen_captions: set[str] = set()
    batch_no_results: set[str] = set()

    # ── First pass: collect all BATCH NO covered fields ───────────────────
    for e in elements:
        if e.get("type") != "text":
            continue
        if (e.get("design_type") or "").upper().strip() != "BATCH NO":
            continue
        batch_no_results.add("mmcont")
        batch_no_results.add("qty")
        wh_ref = e.get("design_wh", "")
        if wh_ref:
            batch_no_results.add(wh_ref)

    # ── Second pass: build fields ─────────────────────────────────────────
    for e in elements:
        if e.get("type") != "text":
            continue

        dt  = (e.get("design_type")      or "").upper().strip()
        ed  = (e.get("design_editor")    or "").upper().strip()
        sv  = (e.get("design_system_value") or "").upper().strip()
        cap = (e.get("design_caption")   or "").strip()

        # ── Skip truly invisible (except BATCH NO which has no editor) ────
        if ed == "INVISIBLE" and dt != "BATCH NO":
            continue

        # ── Caption fallback ──────────────────────────────────────────────
        if not cap:
            if dt == "BATCH NO":
                cap = "QTY"
            elif dt == "SYSTEM":
                sv_raw  = (e.get("design_system_value") or "").strip()
                ext_raw = (e.get("design_system_extra") or "").strip()
                if sv_raw == "LOT NO" and ext_raw:
                    cap = f"LOT NO ({ext_raw})"
                elif sv_raw:
                    cap = sv_raw.title()
                else:
                    cap = e.get("name", "")
            else:
                cap = e.get("name", "")

        name = e.get("name", "")
        cid  = e.get("component_id", "")
        col  = int(e.get("design_column") or 1)

        # ══════════════════════════════════════════════════════════════════
        # LOOKUP
        # ══════════════════════════════════════════════════════════════════
        if dt == "LOOKUP":
            fields.append(dict(
                type="lookup",
                caption=cap,
                name=name,
                component_id=cid,
                link_to=None,
                system_value=None,
                column=col,
                batch_ref="",
                wh_ref="",
            ))

        # ══════════════════════════════════════════════════════════════════
        # LINK
        # ══════════════════════════════════════════════════════════════════
        elif dt == "LINK":
            design_result = (e.get("design_result") or "").strip()
            if not design_result:
                continue

            # skip if a BATCH NO field already covers this result
            db_key = _MasterItemPickerPopup._MM_TO_KEY.get(
                design_result.lower(), design_result.lower()
            )
            if design_result.lower() in batch_no_results or db_key in batch_no_results:
                continue

            # skip if caption already shown
            if cap.upper() in seen_captions:
                continue

            link_ftype = "freetext" if ed == "ENABLED" else "autofill"
            fields.append(dict(
                type=link_ftype,
                caption=cap,
                name=name,
                component_id=cid,
                link_to=e.get("design_link", ""),
                system_value=None,
                column=col,
                batch_ref="",
                wh_ref="",
            ))
            seen_captions.add(cap.upper())

        # ══════════════════════════════════════════════════════════════════
        # SYSTEM
        # ══════════════════════════════════════════════════════════════════
        elif dt == "SYSTEM":
            if sv == "LOT NO":
                fields.append(dict(
                    type="autofill",
                    caption=cap,
                    name=name,
                    component_id=cid,
                    link_to=None,
                    system_value=sv,
                    column=col,
                    batch_ref="",
                    wh_ref="",
                ))
            elif ed == "ENABLED":
                fields.append(dict(
                    type="freetext",
                    caption=cap,
                    name=name,
                    component_id=cid,
                    link_to=None,
                    system_value=sv,
                    column=col,
                    batch_ref="",
                    wh_ref="",
                ))

        elif dt == "INPUT":
            if ed == "INVISIBLE":
                continue

            if cap.upper() in seen_captions:
                continue

            fields.append(dict(
                type="freetext",
                caption=cap,
                name=name,
                component_id=cid,
                link_to=None,
                system_value=None,
                column=col,
                batch_ref="",
                wh_ref="",
            ))
            seen_captions.add(cap.upper())
            
        # ══════════════════════════════════════════════════════════════════
        # BATCH NO
        # ══════════════════════════════════════════════════════════════════
        elif dt == "BATCH NO":
            cap = "QTY"
            batch_key = (
                e.get("design_batch_no", ""),
                e.get("design_wh", ""),
                col,
            )
            if batch_key in seen_batch_keys:
                continue
            seen_batch_keys.add(batch_key)

            # skip if caption already shown
            if cap.upper() in seen_captions:
                continue

            fields.append(dict(
                type="autofill",
                caption=cap,
                name=name,
                component_id=cid,
                link_to=None,
                system_value=None,
                column=col,
                batch_ref=e.get("design_batch_no", ""),
                wh_ref=e.get("design_wh", ""),
            ))
            seen_captions.add(cap.upper())

    fields.sort(key=lambda f: f["column"])
    return fields

# ── DB function caller ────────────────────────────────────────────────────────

def _call_db_function(func_name: str, *args) -> str:
    """Call a PostgreSQL function and return the result as a string."""
    try:
        try:
            from server.db import get_connection
        except ImportError:
            from server.connection import get_connection

        conn = get_connection()
        cur = conn.cursor()

        cast_args = []
        for a in args:
            if isinstance(a, datetime):
                cast_args.append(a.strftime("%Y-%m-%d %H:%M:%S"))
            else:
                cast_args.append(a)

        placeholders = ", ".join(["%s::timestamp"] * len(cast_args))
        cur.execute(f"SELECT barcodesap.{func_name}({placeholders})", cast_args)
        row = cur.fetchone()
        cur.close()
        return str(row[0]) if row and row[0] is not None else ""
    except Exception as e:
        print(f"[DB FUNC ERROR] {func_name}: {e}")
        return ""


# ── System value resolver ─────────────────────────────────────────────────────

_SYSTEM_EXTRA_TO_FUNC: dict[str, str] = {
    "SAKURA":        "lot_no_sakura",
    "SAKURA_NEW":    "lot_no_sakura_new",
    "FLEETGUARD":    "lot_no_fleetguard",
    "FLEETGUARD2":   "lot_no_fleetguard2",
    "FLEETRITE":     "lot_no_fleetrite",
    "FUSO":          "lot_no_fuso",
    "LUBERFINER":    "lot_no_luberfiner",
    "MULTIFITTING":  "lot_no_multifitting",
    "MULTIFITTING2": "lot_no_multifitting2",
    "OEM":           "lot_no_oem",
    "PREMIUMGUARD":  "lot_no_premiumguard",
    "PTC":           "lot_no_ptc",
    "SANKO":         "lot_no_sanko",
    "YANMAR":        "lot_no_yanmar",
    "FILTECH":       "lot_no_filtech",
}


def _resolve_system_value(design_system_value: str, design_system_extra: str) -> str:
    sv  = (design_system_value or "").upper().strip()
    ext = (design_system_extra or "").upper().strip()

    if sv == "LOT NO":
        func = _SYSTEM_EXTRA_TO_FUNC.get(ext)
        if func:
            return _call_db_function(func, datetime.now())
        return ""

    elif sv == "DATETIME":
        fmt = design_system_extra or "HH:mm:ss"
        fmt = (fmt
               .replace("HH",    "%H")
               .replace("mm",    "%M")
               .replace("ss",    "%S")
               .replace("AM/PM", "%p")
               .replace("dd",    "%d")
               .replace("MM",    "%m")
               .replace("yyyy",  "%Y"))
        return datetime.now().strftime(fmt)

    elif sv == "DATE":
        return datetime.now().strftime("%d-%b-%Y").upper()

    elif sv == "USER ID":
        try:
            from server.session import current_user
            return str(current_user() or "")
        except Exception:
            return ""

    return ""


# ── Live canvas preview ───────────────────────────────────────────────────────

class _CanvasPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._elements: list[dict] = []
        self._text_items: dict[str, QGraphicsTextItem] = {}
        self._same_with_map: dict[str, str] = {}   # target_name → source_name
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

        for e in self._elements:
            if (e.get("type") == "text"
                    and (e.get("design_type") or "").upper() == "SYSTEM"):
                resolved = _resolve_system_value(
                    e.get("design_system_value", ""),
                    e.get("design_system_extra", ""),
                )
                if resolved:
                    e["text"] = resolved

        for d in sorted(self._elements, key=lambda x: x.get("z", 0)):
            self._add_element(d)

        # Build SAME WITH map: target_name → source_name
        self._same_with_map = {}
        cid_to_name = {
            e.get("component_id", ""): e.get("name", "")
            for e in self._elements if e.get("component_id")
        }
        for e in self._elements:
            if (e.get("type") == "text"
                    and (e.get("design_type") or "").upper() == "SAME WITH"):
                target_name = e.get("name", "")
                source_cid  = (e.get("design_same_with") or "").strip()
                source_name = cid_to_name.get(source_cid, "")
                if target_name and source_name:
                    self._same_with_map[target_name] = source_name

        self._view.setVisible(True); self._placeholder.setVisible(False)
        self._view.resetTransform()

    def set_values(self, name_to_text: dict[str, str]):
        for name, text in name_to_text.items():
            item = self._text_items.get(name)
            if item is not None:
                item.setPlainText(str(text))

        # Propagate to SAME WITH targets whose source was just updated
        for target_name, source_name in self._same_with_map.items():
            if source_name in name_to_text:
                target_item = self._text_items.get(target_name)
                if target_item is not None:
                    target_item.setPlainText(str(name_to_text[source_name]))

        self._recompute_merges()

    def _recompute_merges(self):
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
        def replacer(m):
            return values.get(m.group(1), "")
        return re.sub(r"\{(\w+)\}", replacer, template).replace("+", "")

    def _add_element(self, d: dict):
        if not d.get("visible", True):
            return  # Skip elements where visible is False
    
        kind = d.get("type")
        x    = d.get("aabb_x", d.get("x", 0))
        y    = d.get("aabb_y", d.get("y", 0))
        z    = d.get("z", 0)
        rot  = d.get("rotation", 0)
        name = d.get("name", "")
        item = None

        if kind == "text":
            ti = QGraphicsTextItem(d.get("text", ""))
            font = QFont(d.get("font_family", "Arial"), int(d.get("font_size", 10)))
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

        self._scene.addItem(item)
        item.setZValue(z)

        if rot != 0:
            br = item.boundingRect()
            item.setTransformOriginPoint(br.center()); item.setRotation(rot)
            item.setPos(0, 0)
            aabb0 = item.mapToScene(item.boundingRect()).boundingRect()
            item.setPos(x - aabb0.left(), y - aabb0.top())
        else:
            item.setPos(x, y)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def clear(self):
        self._scene.clear(); self._text_items.clear()
        self._same_with_map.clear(); self._elements = []
        self._view.setVisible(False); self._placeholder.setVisible(True)

    @property
    def canvas_w(self) -> int:
        return self._canvas_w

    @property
    def canvas_h(self) -> int:
        return self._canvas_h


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


# ── ZPL send helper ───────────────────────────────────────────────────────────

def _send_zpl_to_printer(zpl: str, copies: int = 1) -> tuple[bool, str]:
    import sys, tempfile, os, subprocess

    if copies > 1:
        zpl = zpl.rstrip()
        if zpl.endswith("^XZ"):
            zpl = zpl[:-3] + f"^PQ{copies},0,1,Y\n^XZ"
        else:
            zpl = zpl + f"\n^PQ{copies},0,1,Y\n^XZ"

    zpl_bytes = zpl.encode("utf-8")

    if sys.platform == "win32":
        try:
            import win32print
            printer_name = win32print.GetDefaultPrinter()
            hprinter = win32print.OpenPrinter(printer_name)
            try:
                hjob = win32print.StartDocPrinter(hprinter, 1, ("ZPL Label", None, "RAW"))
                win32print.StartPagePrinter(hprinter)
                win32print.WritePrinter(hprinter, zpl_bytes)
                win32print.EndPagePrinter(hprinter)
                win32print.EndDocPrinter(hprinter)
            finally:
                win32print.ClosePrinter(hprinter)
            return True, f"Sent to printer: {printer_name}"
        except ImportError:
            pass
        except Exception as exc:
            return False, f"win32print error: {exc}"

        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows NT\CurrentVersion\Windows"
            ) as key:
                printer_name, _ = winreg.QueryValueEx(key, "Device")
                printer_name = printer_name.split(",")[0].strip()
        except Exception:
            printer_name = ""

        try:
            with tempfile.NamedTemporaryFile(suffix=".zpl", delete=False) as tf:
                tf.write(zpl_bytes)
                tmp_path = tf.name
            if printer_name:
                cmd = f'copy /b "{tmp_path}" "{printer_name}"'
            else:
                cmd = f'copy /b "{tmp_path}" PRN'
            result = subprocess.run(["cmd", "/c", cmd], capture_output=True, text=True, timeout=15)
            os.unlink(tmp_path)
            if result.returncode == 0:
                return True, f"Sent via copy /b to: {printer_name or 'PRN'}"
            return False, f"copy /b failed: {result.stderr.strip() or result.stdout.strip()}"
        except Exception as exc:
            return False, f"Fallback copy error: {exc}"

    try:
        with tempfile.NamedTemporaryFile(suffix=".zpl", delete=False) as tf:
            tf.write(zpl_bytes)
            tmp_path = tf.name
        for cmd in (["lpr", "-l", tmp_path], ["lp", "-o", "raw", tmp_path]):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    os.unlink(tmp_path)
                    return True, f"Sent via {cmd[0]}"
            except FileNotFoundError:
                continue
            except Exception:
                continue
        return False, f"No printer command available. ZPL saved to: {tmp_path}"
    except Exception as exc:
        return False, f"Print error: {exc}"


# ── Main page ─────────────────────────────────────────────────────────────────

class BarcodePrintPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG_MAIN};")
        self._row_dict: dict | None = None
        self._elements: list[dict] = []
        self._field_descriptors: list[dict] = []
        self._current_values: dict[str, str] = {}
        self._field_widgets: dict[str, QWidget] = {}
        self._cid_to_name: dict[str, str] = {}
        self._usrm_json: str = ""
        self._itrm_json: str = ""
        self._build_ui()
        self._btn_print.setEnabled(False)

    def _build_ui(self):
        root = QHBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(0)
        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")

        left_w = self._build_left()
        right_w = self._build_right()
        left_w.setMinimumWidth(320)
        right_w.setMinimumWidth(260)

        spl.addWidget(left_w)
        spl.addWidget(right_w)
        spl.setCollapsible(0, False)
        spl.setCollapsible(1, False)
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

        self._sep_fields = QFrame(); self._sep_fields.setFrameShape(QFrame.HLine)
        self._sep_fields.setFixedHeight(1)
        self._sep_fields.setStyleSheet(f"background: {_BORDER}; border: none;")
        self._sep_fields.setVisible(False)
        self._card_layout.addWidget(self._sep_fields)

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

        self._combo_speed = make_spin(1, 10, 3)
        self._combo_speed.setFixedWidth(80)
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

        for e in elements:
            if e.get("type") == "text" and e.get("component_id"):
                self._cid_to_name[e["component_id"]] = e.get("name", "")

        fields = _analyse_fields(elements)
        self._field_descriptors = fields
        print(f"[_build_dynamic_fields] fields={[f['name'] for f in fields]}")

        if not fields:
            return

        # ── Compute label width from the longest caption ───────────────────
        _fm = QFontMetrics(QFont())
        _lbl_w = max(
            120,
            max(_fm.horizontalAdvance(f"{fd['caption'] or fd['name']} :") for fd in fields) + 20,
        )

        for fd in fields:
            cap   = fd["caption"] or fd["name"]
            name  = fd["name"]
            ftype = fd["type"]

            if ftype == "lookup":
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
                _form_row(f"{cap} :", row_w, self._fields_vbox, lbl_width=_lbl_w)
                self._field_widgets[name] = inp

            elif ftype == "autofill":
                inp = QLineEdit(); inp.setReadOnly(True); inp.setFocusPolicy(Qt.NoFocus)
                inp.setPlaceholderText(""); inp.setStyleSheet(_AUTOFILL_STYLE)
                _form_row(f"{cap} :", inp, self._fields_vbox, lbl_width=_lbl_w)
                self._field_widgets[name] = inp

            elif ftype == "link_readonly":
                inp = QLineEdit(); inp.setReadOnly(True); inp.setFocusPolicy(Qt.NoFocus)
                inp.setPlaceholderText("")
                inp.setStyleSheet(_AUTOFILL_STYLE)
                _form_row(f"{cap} :", inp, self._fields_vbox, lbl_width=_lbl_w)
                self._field_widgets[name] = inp

            elif ftype == "freetext":
                inp = QLineEdit()
                inp.setPlaceholderText(f"Enter {cap.lower()}…")
                inp.setStyleSheet(MODERN_INPUT_STYLE)
                inp.textChanged.connect(
                    lambda text, n=name: self._on_field_changed(n, text))
                _form_row(f"{cap} :", inp, self._fields_vbox, lbl_width=_lbl_w)
                self._field_widgets[name] = inp

        # ── Resolve all SYSTEM elements ───────────────────────────────────────
        for e in elements:
            if e.get("type") != "text":
                continue
            if (e.get("design_type") or "").upper() != "SYSTEM":
                continue
            ename  = e.get("name", "")
            sv     = (e.get("design_system_value") or "").upper().strip()
            ext    = (e.get("design_system_extra") or "").strip()
            resolved = _resolve_system_value(sv, ext)
            if not resolved:
                continue
            self._current_values[ename] = resolved
            self._preview.set_values({ename: resolved})
            widget = self._field_widgets.get(ename)
            if widget is not None and isinstance(widget, QLineEdit):
                widget.setText(resolved)

        self._spin_print_qty = make_spin(1, 9999, 1); self._spin_print_qty.setFixedWidth(100)
        pq_w = QWidget(); pq_w.setStyleSheet("background: transparent; border: none;")
        pql = QHBoxLayout(pq_w); pql.setContentsMargins(0, 0, 0, 0)
        pql.addWidget(self._spin_print_qty); pql.addStretch()
        _form_row("PRINT QTY :", pq_w, self._fields_vbox, lbl_width=_lbl_w)

        self._sep_fields.setVisible(True)
        self._fields_container.setVisible(True)

    # ── Value change propagation ──────────────────────────────────────────────

    def _on_field_changed(self, name: str, text: str):
        self._current_values[name] = text
        self._preview.set_values({name: text})

    def _on_browse_lookup(self, fd: dict):
        if not hasattr(self, "_master_item_picker"):
            self._master_item_picker = _MasterItemPickerPopup(self)
            self._master_item_picker.item_picked.connect(self._on_master_item_picked)
        self._active_lookup_fd = fd

        lookup_elem = next(
            (e for e in self._elements
             if e.get("name") == fd["name"] and e.get("type") == "text"),
            None,
        )

        # Primary: use design_field (the checked fields in the editor)
        dyn_columns: list[str] = []
        if lookup_elem:
            raw_field = (lookup_elem.get("design_field") or "").strip()
            if raw_field:
                dyn_columns = [f.strip() for f in raw_field.split(",") if f.strip()]

        # Fallback: derive from design_result of linked LINK elements
        if not dyn_columns:
            lookup_cid = fd.get("component_id", "")
            linked_results: list[str] = []
            if lookup_elem:
                own_result = (lookup_elem.get("design_result") or "").strip()
                if own_result:
                    linked_results.append(own_result)
            for e in self._elements:
                if (e.get("type") == "text"
                        and (e.get("design_type") or "").upper() == "LINK"
                        and e.get("design_link", "") == lookup_cid):
                    res = (e.get("design_result") or "").strip()
                    if res and res not in linked_results:
                        linked_results.append(res)
            dyn_columns = linked_results

        self._master_item_picker.open_modal(dyn_columns=dyn_columns)

    def _on_master_item_picked(self, part_no: str, item_code: str,
                      name: str, qty: str, whs: str):
 
        print("=" * 60)
        print("[MASTER ITEM PICKED] Raw signal values:")
        print(f"  part_no   = {part_no!r}")
        print(f"  item_code = {item_code!r}")
        print(f"  name      = {name!r}")
        print(f"  qty       = {qty!r}")
        print(f"  whs       = {whs!r}")
    
        fd = getattr(self, "_active_lookup_fd", None)
        if fd is None:
            print("[MASTER ITEM PICKED] No active lookup fd — aborting.")
            return
    
        lookup_name = fd["name"]
        lookup_cid  = fd["component_id"]
        raw = getattr(self._master_item_picker, "_last_raw_record", {})
    
        print(f"\n[LOOKUP] lookup_name={lookup_name!r}  lookup_cid={lookup_cid!r}")
        print(f"[RAW RECORD KEYS] {list(raw.keys())}")
        print("=" * 60)
    
        updates: dict[str, str] = {}
    
        # ── LOOKUP field itself ──────────────────────────────────────────────
        updates[lookup_name] = part_no
        w = self._field_widgets.get(lookup_name)
        if isinstance(w, QLineEdit):
            w.setText(part_no)
    
        # ── LINK fields that point at this lookup ────────────────────────────
        # Process ALL link fields — no longer skip WH-target fields.
        # BATCH NO handler below covers qty/wh on the canvas; LINK fields that
        # happen to share the same name as a wh_ref are separate form widgets
        # and must be populated from the raw DB record.
        for e in self._elements:
            if e.get("type") != "text":
                continue
    
            dt    = (e.get("design_type") or "").upper()
            ename = e.get("name", "")
    
            # ── LINK → fill from raw record ──────────────────────────────────
            if dt == "LINK" and e.get("design_link", "") == lookup_cid:
                res_fld = (e.get("design_result") or "").lower().strip()
                if not res_fld:
                    continue
    
                db_key = _MasterItemPickerPopup._MM_TO_KEY.get(res_fld, res_fld)
                val = str(raw.get(db_key) or raw.get(res_fld) or "")
    
                updates[ename] = val
                widget = self._field_widgets.get(ename)
                if isinstance(widget, QLineEdit):
                    widget.setText(val)
    
                print(f"  [LINK] {ename!r} ← {res_fld!r} (db_key={db_key!r}) → {val!r}")
    
            # ── BATCH NO → fill qty and wh targets ──────────────────────────
            elif dt == "BATCH NO" and e.get("design_batch_no", "") == lookup_name:
                updates[ename] = qty
                widget = self._field_widgets.get(ename)
                if isinstance(widget, QLineEdit):
                    widget.setText(qty)
                print(f"  [BATCH NO] {ename!r} ← qty={qty!r}")
    
                wh_target = e.get("design_wh", "")
                if wh_target:
                    updates[wh_target] = whs
                    widget2 = self._field_widgets.get(wh_target)
                    if isinstance(widget2, QLineEdit):
                        widget2.setText(whs)
                    print(f"  [BATCH NO WH] {wh_target!r} ← whs={whs!r}")
    
        # ── Finalise ─────────────────────────────────────────────────────────
        self._current_values.update(updates)
        self._preview.set_values(updates)
        self._lbl_item_code.setText(part_no)

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget(); w.setStyleSheet("background: #EEF2F7;")
        vbox = QVBoxLayout(w); vbox.setContentsMargins(10, 16, 16, 16); vbox.setSpacing(10)

        preview_card = QFrame()
        preview_card.setStyleSheet(
            "QFrame { background: #DCE5ED; border: 1px solid #C8D5E3; border-radius: 12px; }")
        preview_card.setMinimumHeight(200)
        preview_card_v = QVBoxLayout(preview_card)
        preview_card_v.setContentsMargins(10, 10, 10, 10); preview_card_v.setSpacing(6)

        ph = QHBoxLayout()
        pt = QLabel("Preview")
        pt.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {_MUTED}; "
            "background: transparent; border: none; letter-spacing: 0.5px;")
        ph.addWidget(pt); ph.addStretch()
        preview_card_v.addLayout(ph)

        inner_frame = QFrame()
        inner_frame.setStyleSheet(
            f"QFrame {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 8px; }}")
        inner_v = QVBoxLayout(inner_frame); inner_v.setContentsMargins(0, 0, 0, 0)
        self._preview = _CanvasPreview()
        inner_v.addWidget(self._preview)
        preview_card_v.addWidget(inner_frame, 1)

        vbox.addWidget(preview_card, 5)

        part_card = QFrame()
        part_card.setStyleSheet(
            f"QFrame {{ background: #DCE5ED; border: 1px solid {_BORDER}; border-radius: 12px; }}")
        part_card.setFixedHeight(82)
        part_card_v = QVBoxLayout(part_card)
        part_card_v.setContentsMargins(14, 10, 14, 10); part_card_v.setSpacing(2)

        pn_title = QLabel("Part No. Print")
        pn_title.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {_MUTED}; "
            "background: transparent; border: none; letter-spacing: 0.5px;")
        part_card_v.addWidget(pn_title)

        self._lbl_item_code = QLabel("")
        self._lbl_item_code.setStyleSheet(
            f"color: {_BLUE}; font-size: 18px; font-weight: 700; "
            "background: transparent; border: none;")
        self._lbl_item_code.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._lbl_item_code.setWordWrap(True)
        part_card_v.addWidget(self._lbl_item_code)

        vbox.addWidget(part_card)
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

    # ── ZPL module loader ─────────────────────────────────────────────────────

    def _load_zpl_converter(self):
        import sys
        import importlib
        import importlib.util
        from pathlib import Path

        here = Path(__file__).resolve().parent

        candidates = [
            here.parent / "services" / "zpl_generator.py",
            here / "zpl_generator.py",
            here / "zpl_converter.py",
        ]

        for candidate in candidates:
            if candidate.exists():
                spec = importlib.util.spec_from_file_location(
                    candidate.stem, str(candidate))
                mod = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(mod)
                    return mod
                except Exception as exc:
                    QMessageBox.critical(
                        self, "ZPL Load Error",
                        f"Found {candidate.name} but failed to load it:\n{exc}")
                    return None

        for cache_key in ("zpl_generator", "app.services.zpl_generator",
                          "zpl_converter", "app.services.zpl_converter"):
            if cache_key in sys.modules:
                return sys.modules[cache_key]

        for mod_path in ("app.services.zpl_generator", "services.zpl_generator",
                         "app.services.zpl_converter", "services.zpl_converter"):
            try:
                return importlib.import_module(mod_path)
            except ImportError:
                continue

        expected = here.parent / "services" / "zpl_generator.py"
        QMessageBox.critical(
            self, "Missing Module",
            f"Cannot find zpl_generator.py.\n\n"
            f"Expected location:\n  {expected}\n\n"
            "Make sure app/services/zpl_generator.py exists.")
        return None

    # ── Print button handler ──────────────────────────────────────────────────

    def _on_print(self):
        code = self._inp_code.text().strip()
        if not code:
            QMessageBox.warning(self, "No Design", "Please select a design first.")
            return

        if not self._usrm_json:
            QMessageBox.warning(self, "No Canvas", "Design canvas is empty — nothing to print.")
            return

        merged_values: dict[str, str] = dict(self._current_values)
        all_text_vals: dict[str, str] = {
            name: item.toPlainText()
            for name, item in self._preview._text_items.items()
        }
        for e in self._elements:
            if (e.get("type") == "text"
                    and (e.get("design_type") or "").upper() == "MERGE"):
                ename = e.get("name", "")
                if ename in all_text_vals:
                    merged_values[ename] = all_text_vals[ename]

        for e in self._elements:
            if e.get("type") == "text":
                ename = e.get("name", "")
                if ename and ename not in merged_values:
                    merged_values[ename] = str(e.get("text", ""))

        for e in self._elements:
            if e.get("type") != "text":
                continue
            if (e.get("design_type") or "").upper() != "SYSTEM":
                continue
            ename = e.get("name", "")
            if not ename:
                continue
            sv  = (e.get("design_system_value") or "").upper().strip()
            ext = (e.get("design_system_extra") or "").strip()
            resolved = _resolve_system_value(sv, ext)
            if resolved:
                merged_values[ename] = resolved

        dpi   = 300 if self._chk_dpi.isChecked() else 203
        try:
            copies = self._spin_print_qty.value()
        except AttributeError:
            copies = 1

        margin_left = self._spin_ml.value()
        margin_top  = self._spin_mt.value()

        try:
            speed = str(self._combo_speed.value())
        except AttributeError:
            speed = "3"

        zpl_mod = self._load_zpl_converter()
        if zpl_mod is None:
            return

        canvas_to_zpl = (
            getattr(zpl_mod, "canvas_to_zpl", None)
            or getattr(zpl_mod, "generate_zpl", None)
            or getattr(zpl_mod, "zpl_generate", None)
            or getattr(zpl_mod, "convert", None)
        )
        if canvas_to_zpl is None:
            QMessageBox.critical(
                self, "ZPL Error",
                f"zpl_generator.py does not expose a recognised entry-point function.\n"
                "Expected one of: canvas_to_zpl, generate_zpl, zpl_generate, convert.")
            return

        _px_to_dots = getattr(zpl_mod, "_px_to_dots", None)
        if _px_to_dots is None:
            def _px_to_dots(px: float, dpi: int = 203) -> int:
                return max(1, int(round(px)))

        try:
            zpl = canvas_to_zpl(
                canvas_json=self._usrm_json,
                canvas_w=self._preview.canvas_w,
                canvas_h=self._preview.canvas_h,
                dpi=dpi,
                label_name=code,
                value_overrides=merged_values,
            )

            if margin_left != 0 or margin_top != 0:
                lh_dots_x = _px_to_dots(margin_left, dpi)
                lh_dots_y = _px_to_dots(margin_top,  dpi)
                zpl = zpl.replace("^LH0,0", f"^LH{lh_dots_x},{lh_dots_y}", 1)

        except Exception as exc:
            QMessageBox.critical(self, "ZPL Error", f"Failed to generate ZPL:\n{exc}")
            return

        print("=" * 60)
        print(f"[ZPL DEBUG] Design: {code}  DPI: {dpi}  Copies: {copies}")
        print(f"[ZPL DEBUG] Canvas: {self._preview.canvas_w}x{self._preview.canvas_h} dots")
        print("[ZPL DEBUG] --- ELEMENT COORDINATES ---")
        try:
            import json as _dbg_json
            _elems = _dbg_json.loads(self._usrm_json) if self._usrm_json else []
            for _e in _elems:
                _t = _e.get("type","?"); _n = _e.get("name","?")
                _x  = _e.get("x","—");  _y  = _e.get("y","—")
                _ax = _e.get("aabb_x","—"); _ay = _e.get("aabb_y","—")
                _r  = _e.get("rotation", 0)
                print(f"  [{_t}] {_n!r:20s}  x={_x}, y={_y}  |  aabb_x={_ax}, aabb_y={_ay}  rot={_r}")
        except Exception as _dbg_exc:
            print(f"  [coord debug error: {_dbg_exc}]")
        print("[ZPL DEBUG] --- ZPL START ---")
        print(zpl)
        print("[ZPL DEBUG] --- ZPL END ---")
        print("=" * 60)

        self._btn_print.setEnabled(False)
        self._btn_print.setText("Printing…")
        QApplication.processEvents()

        ok, msg = _send_zpl_to_printer(zpl, copies=copies)

        self._btn_print.setEnabled(True)
        self._btn_print.setText("Print")

        if ok:
            QMessageBox.information(
                self, "Print OK",
                f"Label sent successfully.\n{msg}\n\n"
                f"Design: {code}   Copies: {copies}   DPI: {dpi}")
        else:
            dlg = QDialog(self)
            dlg.setWindowTitle("Print Failed — ZPL Output")
            dlg.setMinimumSize(560, 420)
            v = QVBoxLayout(dlg)
            v.addWidget(QLabel(f"<b>Could not send to printer:</b> {msg}"))
            v.addWidget(QLabel("You can copy the ZPL below and send it manually:"))
            ta = __import__("PySide6.QtWidgets", fromlist=["QPlainTextEdit"]).QPlainTextEdit()
            ta.setReadOnly(True); ta.setPlainText(zpl)
            ta.setStyleSheet("font-family: monospace; font-size: 10px;")
            v.addWidget(ta, 1)
            btn_close = QPushButton("Close"); btn_close.clicked.connect(dlg.accept)
            v.addWidget(btn_close)
            dlg.exec()

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

        self._usrm_json = usrm
        self._itrm_json = itrm

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
                    self._usrm_json = usrm
                    self._itrm_json = itrm
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