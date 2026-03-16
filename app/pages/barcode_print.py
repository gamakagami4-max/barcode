"""
barcode_print.py  —  Barcode Print Page
Styled to match the barcode editor (BarcodeEditorPage) exactly:
  - Labels: legacy_blue, 9px, uppercase, same as property panel
  - Inputs: MODERN_INPUT_STYLE from utils
  - Dropdowns: make_chevron_combo from utils
  - Checkboxes: same custom drawn style as editor
  - Card: white surface with border, same as sidebar QFrame
"""

from __future__ import annotations
import hashlib

import qtawesome as qta
from PySide6.QtCore import Qt, QDate, QSize, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QFrame, QSizePolicy, QSplitter, QScrollArea,
    QTextEdit, QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication, QDialog,
)

# ── Import shared styles from utils (same as property editors) ────────────────
try:
    from components.barcode_editor.utils import (
        COLORS, MODERN_INPUT_STYLE, make_chevron_combo,
        make_spin, ChevronSpinBox,
    )
    _LEGACY_BLUE    = COLORS.get("legacy_blue", "#4A5568")
    _BG_MAIN        = COLORS.get("bg_main",     "#F8FAFC")
    _WHITE          = COLORS.get("white",        "#FFFFFF")
    _BORDER         = COLORS.get("border",       "#E2E8F0")
    _CANVAS_BG      = COLORS.get("canvas_bg",    "#F1F4F8")
except ImportError:
    # Fallback if running standalone
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
        QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {
            border-color: #6366F1;
        }
        QLineEdit:read-only {
            background: #F8FAFC; color: #94A3B8;
        }
        QSpinBox::up-button, QSpinBox::down-button,
        QDateEdit::up-button, QDateEdit::down-button {
            width: 16px;
            border: none;
            border-left: 1px solid #E2E8F0;
            background: #F8FAFC;
            subcontrol-origin: border;
        }
        QSpinBox::up-button {
            subcontrol-position: top right;
            border-bottom: 1px solid #E2E8F0;
        }
        QSpinBox::down-button {
            subcontrol-position: bottom right;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover,
        QDateEdit::up-button:hover, QDateEdit::down-button:hover {
            background: #E2E8F0;
        }
    """

    def make_chevron_combo(options: list[str]) -> QWidget:
        """Fallback plain QComboBox."""
        from PySide6.QtWidgets import QComboBox
        c = QComboBox()
        c.addItems(options)
        c.setStyleSheet("""
            QComboBox {
                background: #FFFFFF; border: 1px solid #CBD5E1;
                border-radius: 4px; padding: 5px 8px;
                font-size: 11px; color: #1E293B; min-height: 26px;
            }
            QComboBox:focus { border-color: #6366F1; }
            QComboBox::drop-down { border: none; padding-right: 6px; }
        """)
        return c



# Appended to spinboxes to restore standard Qt arrow appearance

_SPIN_BTN = ''  # arrows handled by ChevronSpinBox


# Disabled state — matches property editor look (light bg, muted text)
_DISABLED_STYLE = (
    "QLineEdit:disabled, QSpinBox:disabled, QDateEdit:disabled {"
    "  background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }"
    "QComboBox:disabled {"
    "  background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }"
    "QLabel:disabled { color: #94A3B8; }"
)

# ── Local palette constants ────────────────────────────────────────────────────
_ACCENT      = "#6366F1"
_ACCENT_LIGHT= "#EEF2FF"
_BORDER2     = "#CBD5E1"
_TEXT        = "#1E293B"
_MUTED       = "#64748B"
_HINT        = "#94A3B8"
_BLUE        = "#3B82F6"
_SUCCESS     = "#16A34A"
_DANGER      = "#DC2626"

# ── Button styles (matching editor's StandardButton secondary/primary) ─────────
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
    background: #F8FAFC; color: #D1D5DB;
    border-color: {_BORDER};
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

# Card style matching sidebar QFrame in editor
_CARD_STYLE = (
    f"QFrame {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}"
    " QFrame QWidget { border: none; background: transparent; }"
    " QFrame QFrame { border: none; background: transparent; }"
)



# ── Label helper — matches property editor _lbl exactly ──────────────────────

def _lbl(text: str) -> QLabel:
    """Exact replica of property editor label style."""
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_LEGACY_BLUE}; font-size: 9px; text-transform: uppercase; "
        "background: transparent; border: none;"
    )
    l.setFixedWidth(100)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return l


def _divider() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet(f"background: {_BORDER}; border: none; color: {_BORDER};")
    f.setFixedHeight(1)
    return f


def _status_lbl(text: str, ok: bool) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; "
        "font-weight: 600; background: transparent; border: none;"
    )
    return l


# ── Custom checkbox — matches editor style exactly ────────────────────────────

class _CheckBox(QCheckBox):
    """Drawn checkbox: plain border unchecked, dark tick checked."""

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

        # Box — always white fill, grey border
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#94A3B8"), 1.5))
        path = QPainterPath()
        path.addRoundedRect(0, y, b, b, 3, 3)
        p.drawPath(path)

        # Tick — dark, no fill
        if self.isChecked():
            pen = QPen(QColor("#1E293B"), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            cx, cy = b // 2, y + b // 2
            p.drawLine(int(cx - 3), int(cy),     int(cx - 1), int(cy + 3))
            p.drawLine(int(cx - 1), int(cy + 3), int(cx + 4), int(cy - 3))

        # Label text
        p.setPen(QPen(QColor("#1E293B")))
        p.setFont(QFont("Segoe UI", 10))
        tx = b + 7
        p.drawText(tx, 0, self.width() - tx, self.height(),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def mousePressEvent(self, _event):
        self.setChecked(not self.isChecked())
        self.update()


# ── Design picker modal ───────────────────────────────────────────────────────

class _DesignPickerPopup(QDialog):
    """Modal dialog for selecting a barcode design."""

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
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Header
        header = QWidget()
        header.setStyleSheet(f"background: {_WHITE}; border-bottom: 1px solid {_BORDER};")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 14, 16, 14)

        title = QLabel("Select Design")
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {_TEXT}; background: transparent;")
        hl.addWidget(title)
        hl.addStretch()
        vbox.addWidget(header)

        # Search
        search_row = QWidget()
        search_row.setStyleSheet(f"background: #F8FAFC; border-bottom: 1px solid {_BORDER};")
        sr = QHBoxLayout(search_row)
        sr.setContentsMargins(14, 10, 14, 10)
        sr.setSpacing(8)
        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(f"font-size: 15px; color: {_HINT}; background: transparent; border: none;")
        sr.addWidget(search_icon)
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search code or name…")
        self._search.setFrame(False)
        self._search.setStyleSheet(
            f"border: none; background: transparent; font-size: 12px; color: {_TEXT};"
        )
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        sr.addWidget(self._search)
        vbox.addWidget(search_row)

        # Column headers
        col_hdr = QWidget()
        col_hdr.setStyleSheet(f"background: #F1F5F9; border-bottom: 1px solid {_BORDER};")
        ch = QHBoxLayout(col_hdr)
        ch.setContentsMargins(16, 7, 16, 7)
        ch.setSpacing(0)

        def _ch(text, w=None):
            l = QLabel(text)
            l.setStyleSheet(
                f"color: {_LEGACY_BLUE}; font-size: 9px; font-weight: 700; "
                "letter-spacing: 0.5px; background: transparent;"
            )
            if w:
                l.setFixedWidth(w)
            return l

        ch.addWidget(_ch("CODE", 150))
        ch.addWidget(_ch("NAME"))
        vbox.addWidget(col_hdr)

        # List
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
            QScrollBar:vertical {{
                background: transparent; width: 5px;
            }}
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

        # Footer
        footer = QWidget()
        footer.setStyleSheet(f"background: #F8FAFC; border-top: 1px solid {_BORDER};")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(16, 10, 16, 10)
        fl.setSpacing(8)
        self._footer = QLabel()
        self._footer.setStyleSheet(f"font-size: 11px; color: {_HINT}; background: transparent;")
        fl.addWidget(self._footer)
        fl.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)

        self._select_btn = QPushButton("Select")
        self._select_btn.setStyleSheet(_BTN_PRIMARY)
        self._select_btn.setEnabled(False)
        self._select_btn.clicked.connect(self._on_select)

        fl.addWidget(cancel_btn)
        fl.addSpacing(6)
        fl.addWidget(self._select_btn)
        vbox.addWidget(footer)

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
            item = QListWidgetItem()
            item.setData(Qt.UserRole, (code, name))

            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(16, 9, 16, 9)
            rl.setSpacing(0)

            code_lbl = QLabel(code)
            code_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {_LEGACY_BLUE}; "
                "background: transparent; min-width: 150px; max-width: 150px;"
            )
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                f"font-size: 12px; color: {_TEXT}; background: transparent;"
            )
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
        filtered = [
            r for r in self._records
            if q in str(r.get("pk", "")).lower() or q in str(r.get("name", "")).lower()
        ] if q else self._records
        self._rebuild_list(filtered)

    def _on_activated(self, item: QListWidgetItem):
        self._on_select()

    def _on_select(self):
        items = self._list.selectedItems()
        if not items:
            return
        data = items[0].data(Qt.UserRole)
        if data:
            self.design_picked.emit(data[0], data[1])
            self.accept()

    def open_modal(self):
        self._load_records()
        self._search.clear()
        self._rebuild_list(self._records)
        self._search.setFocus()
        self.exec()


# ── Label preview ─────────────────────────────────────────────────────────────

class _LabelPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._code = ""
        self._name = ""
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {_WHITE};")

    def set_design(self, code: str, name: str):
        self._code = code
        self._name = name
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        pad  = 20

        if not self._code:
            p.setPen(QPen(QColor(_HINT)))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Load a design to preview")
            p.end()
            return

        bx   = pad + 12
        bw   = W - 2*pad - 24
        bh   = int((H - 2*pad) * 0.52)
        by   = pad + 12
        seed = int(hashlib.md5(self._code.encode()).hexdigest()[:8], 16)

        p.setBrush(QBrush(Qt.black))
        p.setPen(Qt.NoPen)
        x = bx; i = 0
        while x < bx + bw - 2:
            w = max(1, int(((seed >> (i % 16)) & 3) * 1.4 + 1))
            if i % 2 == 0:
                p.drawRect(int(x), by, max(1, w), bh)
            x += w + 1; i += 1

        f1 = QFont("Courier New", 7)
        p.setFont(f1)
        p.setPen(QPen(QColor(_TEXT)))
        tw = QFontMetrics(f1).horizontalAdvance(self._code)
        p.drawText(bx + (bw - tw) // 2, by + bh + 13, self._code)

        f2 = QFont("Segoe UI", 8)
        p.setFont(f2)
        p.setPen(QPen(QColor(_MUTED)))
        p.drawText(
            self.rect().adjusted(pad + 6, by + bh + 22, -(pad + 6), -4),
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self._name,
        )
        p.end()


# ── Print log ─────────────────────────────────────────────────────────────────

class _PrintLog(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(
            "QTextEdit { background: #0F172A; color: #475569; border: none; "
            "font-family: 'Consolas','Courier New',monospace; font-size: 11px; padding: 8px; }"
        )
        self._put("— print log —", "#334155")

    def _put(self, msg: str, color: str):
        self.append(f"<span style='color:{color};'>{msg}</span>")
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())

    def log(self, msg: str, level: str = "info"):
        c = {"info": "#475569", "ok": "#4ADE80", "error": "#F87171", "warn": "#FCD34D"}.get(level, "#475569")
        self._put(msg, c)

    def clear_log(self):
        self.clear()
        self._put("— print log —", "#334155")


# ── Form row helper ───────────────────────────────────────────────────────────

def _form_row(label: str, widget: QWidget, layout: QVBoxLayout):
    """Add a label + widget pair matching the property editor form style."""
    row = QWidget()
    row.setStyleSheet("background: transparent; border: none;")
    rl = QHBoxLayout(row)
    rl.setContentsMargins(0, 0, 0, 0)
    rl.setSpacing(10)
    rl.setAlignment(Qt.AlignVCenter)
    lbl_w = _lbl(label)
    lbl_w.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    rl.addWidget(lbl_w)
    rl.addWidget(widget, 1)
    layout.addWidget(row)


# ── Main page ─────────────────────────────────────────────────────────────────

class BarcodePrintPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {_BG_MAIN};")
        self._build_ui()
        self._print_fields_with_sep.setEnabled(False)
        self._btn_print.setEnabled(False)

    # ── Build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {_BORDER}; }}")
        spl.addWidget(self._build_left())
        spl.addWidget(self._build_right())
        spl.setSizes([640, 360])
        root.addWidget(spl)

    def _build_left(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet(f"background: {_BG_MAIN};")
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(24, 16, 14, 16)
        vbox.setSpacing(12)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Barcode Print")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {_TEXT};")
        hdr.addWidget(title)
        hdr.addStretch()

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setStyleSheet(_BTN_SECONDARY)
        self._btn_stop.setIcon(qta.icon("fa5s.stop-circle", color=_MUTED))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_print = QPushButton("Print")
        self._btn_print.setStyleSheet(_BTN_PRIMARY)
        self._btn_print.setIcon(qta.icon("fa5s.print", color="#fff"))
        self._btn_print.clicked.connect(self._on_print)

        hdr.addWidget(self._btn_stop)
        hdr.addSpacing(6)
        hdr.addWidget(self._btn_print)
        vbox.addLayout(hdr)

        # Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: transparent; border: none; }}"
            "QScrollBar:vertical { background: transparent; width: 5px; }"
            f"QScrollBar::handle:vertical {{ background: {_BORDER2}; border-radius: 2px; min-height: 20px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 8, 0)
        cv.setSpacing(0)

        # Single card wrapping all sections
        wrapper = QFrame()
        wrapper.setObjectName('printCard')
        wrapper.setStyleSheet(
            f'QFrame#printCard {{ background: {_WHITE}; border: 1px solid {_BORDER}; border-radius: 12px; }}'
            f' QFrame#printCard > QWidget {{ border: none; }}'
        )
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        wv = QVBoxLayout(wrapper)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)

        wv.addWidget(self._build_design_section())

        sep1 = QFrame(); sep1.setFrameShape(QFrame.HLine)
        sep1.setFixedHeight(1)
        sep1.setStyleSheet(f"background: {_BORDER}; border: none;")
        wv.addWidget(sep1)

        wv.addWidget(self._build_printer_section())

        # Print fields + separator grouped
        self._print_fields_with_sep = QWidget()
        self._print_fields_with_sep.setStyleSheet("background: transparent;")
        pfs = QVBoxLayout(self._print_fields_with_sep)
        pfs.setContentsMargins(0, 0, 0, 0)
        pfs.setSpacing(0)

        sep2 = QFrame(); sep2.setFrameShape(QFrame.HLine)
        sep2.setFixedHeight(1)
        sep2.setStyleSheet(f"background: {_BORDER}; border: none;")
        pfs.addWidget(sep2)
        pfs.addWidget(self._build_print_fields_section())
        wv.addWidget(self._print_fields_with_sep)

        cv.addWidget(wrapper)
        cv.addStretch()

        scroll.setWidget(content)
        vbox.addWidget(scroll, 1)
        return outer

    # ── Design section ────────────────────────────────────────────────────────

    def _build_design_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Code + browse
        self._inp_code = QLineEdit()
        self._inp_code.setPlaceholderText("Enter or browse design code…")
        self._inp_code.setStyleSheet(MODERN_INPUT_STYLE + _DISABLED_STYLE)
        self._inp_code.returnPressed.connect(
            lambda: self.load_design_by_code(self._inp_code.text().strip())
        )
        self._btn_browse_code = QPushButton("···")
        self._btn_browse_code.setStyleSheet(_BTN_BROWSE)
        self._btn_browse_code.setToolTip("Browse design codes")
        self._btn_browse_code.clicked.connect(self._on_browse_code)

        code_w = QWidget(); code_w.setStyleSheet("background: transparent; border: none;")
        cr = QHBoxLayout(code_w); cr.setContentsMargins(0,0,0,0); cr.setSpacing(6)
        cr.addWidget(self._inp_code); cr.addWidget(self._btn_browse_code)

        _form_row("CODE :", code_w, layout)

        # Name (read-only)
        self._inp_name = QLineEdit()
        self._inp_name.setReadOnly(True)
        self._inp_name.setFocusPolicy(Qt.NoFocus)
        self._inp_name.setPlaceholderText("Auto-filled from design code")
        self._inp_name.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("NAME :", self._inp_name, layout)

        return w

    # ── Printer settings section ──────────────────────────────────────────────

    def _build_printer_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # COM status
        self._lbl_timbangan = _status_lbl("NOT CONNECTED", False)
        self._lbl_gate      = _status_lbl("NOT CONNECTED", False)
        _form_row("COM TIMBANGAN :", self._lbl_timbangan, layout)
        _form_row("COM GATE :",      self._lbl_gate,      layout)

        # Speed — use make_chevron_combo to match editor dropdowns
        self._combo_speed = make_chevron_combo(["1","2","3","4","5","6","7","8","9","10"])
        try:
            self._combo_speed.setCurrentText("3")
        except AttributeError:
            pass
        speed_w = QWidget(); speed_w.setStyleSheet("background: transparent; border: none;")
        sl = QHBoxLayout(speed_w); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        sl.addWidget(self._combo_speed)
        sl.addStretch()
        _form_row("SPEED :", speed_w, layout)


        # Margin Left
        self._spin_ml = make_spin(-999, 999, 0)
        self._spin_ml.setFixedWidth(80)
        ml_w = QWidget(); ml_w.setStyleSheet("background: transparent; border: none;")
        mll = QHBoxLayout(ml_w); mll.setContentsMargins(0,0,0,0); mll.addWidget(self._spin_ml); mll.addStretch()
        _form_row("MARGIN LEFT :", ml_w, layout)

        # Margin Top + 300 dpi
        self._spin_mt = make_spin(-999, 999, 0)
        self._spin_mt.setFixedWidth(80)
        self._chk_dpi = _CheckBox("300 dpi")

        mt_w = QWidget(); mt_w.setStyleSheet("background: transparent; border: none;")
        mtl = QHBoxLayout(mt_w); mtl.setContentsMargins(0,0,0,0); mtl.setSpacing(14)
        mtl.addWidget(self._spin_mt); mtl.addWidget(self._chk_dpi); mtl.addStretch()
        _form_row("MARGIN TOP :", mt_w, layout)

        # Printer Type
        self._chk_non_zebra = _CheckBox("Non Zebra Printer")
        self._spin_offset = make_spin(-999, 999, -11)
        self._spin_offset.setFixedWidth(70)
        self._spin_offset.setToolTip("Printer offset")

        pt_w = QWidget(); pt_w.setStyleSheet("background: transparent; border: none;")
        ptl = QHBoxLayout(pt_w); ptl.setContentsMargins(0,0,0,0); ptl.setSpacing(14)
        ptl.addWidget(self._chk_non_zebra); ptl.addWidget(self._spin_offset); ptl.addStretch()
        _form_row("PRINTER TYPE :", pt_w, layout)

        return w

    # ── Print fields section ──────────────────────────────────────────────────

    def _build_print_fields_section(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: transparent; border: none;")
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # Part No + browse
        self._inp_part = QLineEdit()
        self._inp_part.setPlaceholderText("Enter or browse part number…")
        self._inp_part.setStyleSheet(MODERN_INPUT_STYLE + _DISABLED_STYLE)
        self._btn_browse_part = QPushButton("···")
        self._btn_browse_part.setStyleSheet(_BTN_BROWSE)
        self._btn_browse_part.clicked.connect(self._on_browse_part)

        part_w = QWidget(); part_w.setStyleSheet("background: transparent; border: none;")
        pl = QHBoxLayout(part_w); pl.setContentsMargins(0,0,0,0); pl.setSpacing(6)
        pl.addWidget(self._inp_part); pl.addWidget(self._btn_browse_part)
        _form_row("PART NO. PRINT :", part_w, layout)

        # QTY
        self._inp_qty = QLineEdit()
        self._inp_qty.setReadOnly(True)
        self._inp_qty.setFocusPolicy(Qt.NoFocus)
        self._inp_qty.setPlaceholderText("Auto-filled")
        self._inp_qty.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("QTY :", self._inp_qty, layout)

        # WHS
        self._inp_whs = QLineEdit()
        self._inp_whs.setReadOnly(True)
        self._inp_whs.setFocusPolicy(Qt.NoFocus)
        self._inp_whs.setPlaceholderText("Auto-filled")
        self._inp_whs.setStyleSheet(MODERN_INPUT_STYLE + "QLineEdit { background: #F8FAFC; color: #94A3B8; border-color: #E2E8F0; }")
        _form_row("WHS :", self._inp_whs, layout)

        # Date Code
        _today = QDate.currentDate()
        _date_items = [_today.addDays(i).toString("dd-MMM-yyyy") for i in range(-30, 31)]
        self._date_combo = make_chevron_combo(_date_items)
        self._date_combo.setCurrentText(_today.toString("dd-MMM-yyyy"))
        self._date_combo.setFixedWidth(200)
        date_w = QWidget(); date_w.setStyleSheet('background: transparent; border: none;')
        dw_l = QHBoxLayout(date_w); dw_l.setContentsMargins(0,0,0,0); dw_l.setSpacing(0)
        dw_l.addWidget(self._date_combo); dw_l.addStretch()
        _form_row("DATE CODE :", date_w, layout)

        # Print QTY
        self._spin_print_qty = make_spin(1, 9999, 1)
        self._spin_print_qty.setFixedWidth(100)
        pq_w = QWidget(); pq_w.setStyleSheet("background: transparent; border: none;")
        pql = QHBoxLayout(pq_w); pql.setContentsMargins(0,0,0,0)
        pql.addWidget(self._spin_print_qty); pql.addStretch()
        _form_row("PRINT QTY :", pq_w, layout)

        return w

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {_BG_MAIN};")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(6, 16, 20, 16)
        vbox.setSpacing(0)

        # Preview
        ph = QHBoxLayout()
        pt = QLabel("Preview")
        pt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        ph.addWidget(pt); ph.addStretch()
        vbox.addLayout(ph)
        vbox.addSpacing(6)

        pf = QFrame()
        pf.setStyleSheet(_CARD_STYLE)
        pf.setMinimumHeight(160)
        pfv = QVBoxLayout(pf); pfv.setContentsMargins(0,0,0,0)
        self._preview = _LabelPreview()
        pfv.addWidget(self._preview)
        vbox.addWidget(pf, 3)
        vbox.addSpacing(12)

        # Log
        lh = QHBoxLayout()
        lt = QLabel("Print Log")
        lt.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {_TEXT};")
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setStyleSheet(_BTN_GHOST)
        self._btn_clear.clicked.connect(lambda: self._log.clear_log())
        lh.addWidget(lt); lh.addStretch(); lh.addWidget(self._btn_clear)
        vbox.addLayout(lh)
        vbox.addSpacing(6)

        lf = QFrame()
        lf.setStyleSheet("background: #0F172A; border: 1px solid #1E293B; border-radius: 8px;")
        lfv = QVBoxLayout(lf); lfv.setContentsMargins(0,0,0,0)
        self._log = _PrintLog()
        lfv.addWidget(self._log)
        vbox.addWidget(lf, 2)

        return w

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_browse_code(self):
        if not hasattr(self, "_design_picker"):
            self._design_picker = _DesignPickerPopup(self)
            self._design_picker.design_picked.connect(
                lambda code, name: self.load_design_by_code(code, name)
            )
        self._design_picker.open_modal()

    def _on_browse_part(self):
        try:
            from PySide6.QtWidgets import QInputDialog
            part, ok = QInputDialog.getText(self, "Browse Part No.", "Enter Part No.:")
            if ok and part.strip():
                self._inp_part.setText(part.strip())
        except Exception as e:
            self._log.log(f"✗  {e}", "error")

    def _on_print(self):
        code = self._inp_code.text().strip()
        if not code:
            self._log.log("✗  No design code selected.", "error")
            return
        try:
            speed = self._combo_speed.currentText()
        except AttributeError:
            speed = "3"
        qty    = self._spin_print_qty.value()
        part   = self._inp_part.text().strip() or "(no part)"
        try:
            date_s = self._date_combo._current or self._date_combo.currentText()
        except AttributeError:
            date_s = self._date_combo.currentText()
        self._log.log(f"▶  [{code}]  ×{qty}  part={part}  date={date_s}  speed={speed}", "ok")
        self._btn_stop.setEnabled(True)
        self._btn_print.setEnabled(False)

    def _on_stop(self):
        self._log.log("■  Stopped.", "warn")
        self._btn_stop.setEnabled(False)
        self._btn_print.setEnabled(True)

    # ── Public API ────────────────────────────────────────────────────────────

    def load_design_by_code(self, code: str, name: str = ""):
        if not code:
            return
        self._inp_code.setText(code)
        self._inp_name.setText(name or code)
        self._preview.set_design(code, name or code)
        self._print_fields_with_sep.setEnabled(True)
        self._btn_print.setEnabled(True)
        self._log.log(f"✓  Design loaded: {code}", "ok")

    def load_design(self, code: str, name: str = ""):
        self.load_design_by_code(code, name)

    def set_part_no(self, part: str, qty: str = "", whs: str = ""):
        self._inp_part.setText(part)
        self._inp_qty.setText(qty)
        self._inp_whs.setText(whs)

    def set_com_status(self, timbangan: bool = False, gate: bool = False):
        def _upd(lbl: QLabel, ok: bool):
            lbl.setText("CONNECTED" if ok else "NOT CONNECTED")
            lbl.setStyleSheet(
                f"color: {_SUCCESS if ok else _DANGER}; font-size: 11px; "
                "font-weight: 600; background: transparent; border: none;"
            )
        _upd(self._lbl_timbangan, timbangan)
        _upd(self._lbl_gate, gate)