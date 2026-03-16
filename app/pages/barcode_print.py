"""
barcode_print.py  —  Barcode Print Page
Styled to match the General tab: white card, small uppercase blue labels,
flat layout, no group box frames.
"""

from __future__ import annotations
import hashlib

import qtawesome as qta
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics, QPainterPath,
)
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QLineEdit, QSpinBox, QCheckBox,
    QFrame, QSizePolicy, QSplitter, QScrollArea,
    QDateEdit, QTextEdit, QListWidget, QListWidgetItem,
    QAbstractItemView, QApplication,
)

# ─────────────────────────────────────────────────────────────────────────────
# Palette — matches General tab
# ─────────────────────────────────────────────────────────────────────────────
BG        = "#F0F2F5"   # page background (light grey like the app)
CARD      = "#FFFFFF"   # card surface
BORDER    = "#E2E8F0"   # card border
INPUT_BG  = "#F8FAFC"   # input background
INPUT_BD  = "#CBD5E1"   # input border
INPUT_TXT = "#1E293B"   # input text
LABEL_CLR = "#6366F1"   # uppercase label color (blue-purple, matches General tab)
MUTED     = "#64748B"
HINT      = "#94A3B8"
ACCENT    = "#3B82F6"
SUCCESS   = "#16A34A"
DANGER    = "#DC2626"


# ─────────────────────────────────────────────────────────────────────────────
# Styles
# ─────────────────────────────────────────────────────────────────────────────
INPUT_STYLE = (
    "QLineEdit, QSpinBox, QDateEdit {"
    f"  background: {INPUT_BG}; border: 1px solid {INPUT_BD};"
    "   border-radius: 4px; padding: 5px 9px;"
    f"  font-size: 12px; color: {INPUT_TXT}; min-height: 28px; }}"
    "QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {"
    f"  border-color: {ACCENT}; background: #EFF6FF; }}"
    "QLineEdit:read-only {"
    f"  background: {INPUT_BG}; color: {HINT}; border-color: {BORDER}; }}"
    "QSpinBox::up-button, QSpinBox::down-button,"
    "QDateEdit::up-button, QDateEdit::down-button {"
    "   width: 18px; border: none; background: transparent; }"
)

BTN_PRIMARY = (
    "QPushButton {"
    f"  background: {ACCENT}; color: #fff; border: none; border-radius: 5px;"
    "   font-size: 12px; font-weight: 600; padding: 6px 16px; min-height: 28px; }"
    "QPushButton:hover   { background: #2563EB; }"
    "QPushButton:pressed { background: #1D4ED8; }"
    f"QPushButton:disabled {{ background: {HINT}; color: #fff; }}"
)

BTN_OUTLINE = (
    "QPushButton {"
    f"  background: {CARD}; color: {MUTED}; border: 1px solid {INPUT_BD};"
    "   border-radius: 5px; font-size: 12px; padding: 6px 14px; min-height: 28px; }"
    "QPushButton:hover { background: #F1F5F9; }"
    f"QPushButton:disabled {{ color: {HINT}; border-color: {BORDER}; }}"
)

BTN_GHOST = (
    "QPushButton {"
    f"  background: transparent; color: {MUTED}; border: 1px solid {INPUT_BD};"
    "   border-radius: 4px; font-size: 10px; padding: 2px 8px; min-height: 20px; }"
    "QPushButton:hover { background: #F1F5F9; }"
)

BTN_BROWSE = (
    "QPushButton {"
    f"  background: {INPUT_BG}; color: {MUTED}; border: 1px solid {INPUT_BD};"
    "   border-radius: 4px; font-size: 12px; padding: 0 10px; min-height: 28px; min-width: 32px; }"
    f"QPushButton:hover {{ background: #EFF6FF; color: {ACCENT}; border-color: {ACCENT}; }}"
)

CARD_STYLE = (
    f"background: {CARD}; border: none; border-radius: 0px;"
)

DIVIDER_STYLE = f"background: {BORDER}; border: none;"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _field_label(text: str) -> QLabel:
    """Small uppercase colored label — exactly like General tab."""
    l = QLabel(text + " :")
    l.setStyleSheet(
        f"color: {LABEL_CLR}; font-size: 10px; font-weight: 700;"
        "letter-spacing: 0.5px; background: transparent;"
    )
    l.setFixedWidth(120)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    return l


def _section_sep(title: str = "") -> QWidget:
    """Thin horizontal rule with optional label, like a sub-section divider."""
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 4, 0, 4)
    h.setSpacing(8)
    if title:
        lbl = QLabel(title)
        lbl.setStyleSheet(
            f"color: {HINT}; font-size: 9px; font-weight: 700;"
            "letter-spacing: 0.6px; background: transparent;"
        )
        h.addWidget(lbl)
    line = QFrame()
    line.setFrameShape(QFrame.HLine)
    line.setStyleSheet(DIVIDER_STYLE)
    line.setFixedHeight(1)
    h.addWidget(line, 1)
    return w


def _status_lbl(text: str, ok: bool) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color: {SUCCESS if ok else DANGER}; font-size: 12px;"
        "font-weight: 600; background: transparent;"
    )
    return l


class _CheckBox(QCheckBox):
    """Checkbox: plain border when unchecked, checkmark only when checked."""
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet(
            "QCheckBox { font-size: 12px; color: #1E293B; spacing: 7px; background: transparent; }"
            "QCheckBox::indicator { width: 0px; height: 0px; }"
        )
        self._box_size = 15

    def paintEvent(self, event):
        from PySide6.QtGui import QPainter, QPen, QColor, QPainterPath
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        b = self._box_size
        y = (self.height() - b) // 2
        x = 0

        # Box outline only — never filled
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(QColor("#94A3B8"), 1.5))
        path = QPainterPath()
        path.addRoundedRect(x, y, b, b, 3, 3)
        p.drawPath(path)

        # Checkmark — drawn over the box when checked
        if self.isChecked():
            pen = QPen(QColor("#1E293B"), 2.0)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            cx = x + b // 2
            cy = y + b // 2
            p.drawLine(int(cx - 3.5), int(cy),     int(cx - 1), int(cy + 3))
            p.drawLine(int(cx - 1),   int(cy + 3), int(cx + 4), int(cy - 3))

        # Label
        from PySide6.QtGui import QFont
        p.setPen(QPen(QColor("#1E293B")))
        p.setFont(QFont("Segoe UI", 11))
        tx = x + b + 7
        p.drawText(tx, 0, self.width() - tx, self.height(),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        p.end()

    def mousePressEvent(self, event):
        self.setChecked(not self.isChecked())
        self.update()





# ─────────────────────────────────────────────────────────────────────────────
# Design picker popup
# ─────────────────────────────────────────────────────────────────────────────

class _DesignPickerPopup(QFrame):
    """
    Floating popup showing all barcode design records.
    Emits design_picked(code, name) when a row is selected.
    """
    design_picked = Signal(str, str)

    def __init__(self, parent: QWidget):
        super().__init__(parent.window(), Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setStyleSheet(
            f"QFrame {{ background: {CARD}; border: 1px solid {INPUT_BD};"
            "border-radius: 8px; }}"
        )
        self.setFixedWidth(480)
        self._records: list[dict] = []
        self._build_ui()

    def _build_ui(self):
        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # Search bar
        search_row = QWidget()
        search_row.setStyleSheet(
            f"background: {CARD}; border-bottom: 1px solid {BORDER};"
        )
        sr = QHBoxLayout(search_row)
        sr.setContentsMargins(10, 8, 10, 8)
        sr.setSpacing(8)

        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(
            f"font-size: 14px; color: {HINT}; border: none; background: transparent;"
        )
        sr.addWidget(search_icon)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search code or name…")
        self._search.setFrame(False)
        self._search.setStyleSheet(
            f"border: none; background: transparent; font-size: 12px; color: {INPUT_TXT};"
        )
        self._search.textChanged.connect(self._filter)
        self._search.installEventFilter(self)
        sr.addWidget(self._search)
        vbox.addWidget(search_row)

        # Column headers
        hdr = QWidget()
        hdr.setStyleSheet(
            f"background: #F8FAFC; border-bottom: 1px solid {BORDER};"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(12, 6, 12, 6)
        hl.setSpacing(0)

        def _hdr_lbl(text, w=None):
            l = QLabel(text)
            l.setStyleSheet(
                f"font-size: 10px; font-weight: 700; color: {HINT};"
                "letter-spacing: 0.5px; background: transparent;"
            )
            if w:
                l.setFixedWidth(w)
            return l

        hl.addWidget(_hdr_lbl("CODE", 140))
        hl.addWidget(_hdr_lbl("NAME"))
        vbox.addWidget(hdr)

        # List
        self._list = QListWidget()
        self._list.setFrameShape(QFrame.NoFrame)
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list.setSelectionMode(QAbstractItemView.SingleSelection)
        self._list.setStyleSheet(f"""
            QListWidget {{
                background: {CARD}; border: none;
                font-size: 12px; color: {INPUT_TXT};
                outline: none;
            }}
            QListWidget::item {{
                padding: 8px 12px; border-bottom: 1px solid {BORDER};
            }}
            QListWidget::item:selected {{
                background: #EFF6FF; color: {ACCENT};
            }}
            QListWidget::item:hover:!selected {{
                background: #F8FAFC;
            }}
            QScrollBar:vertical {{
                background: transparent; width: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {INPUT_BD}; border-radius: 2px; min-height: 16px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        self._list.setFixedHeight(280)
        self._list.itemActivated.connect(self._on_activated)
        self._list.itemClicked.connect(self._on_activated)
        vbox.addWidget(self._list)

        # Footer count
        self._footer = QLabel()
        self._footer.setStyleSheet(
            f"font-size: 10px; color: {HINT}; background: #F8FAFC;"
            f"border-top: 1px solid {BORDER}; padding: 5px 12px;"
        )
        vbox.addWidget(self._footer)

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self._search and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Escape:
                self.hide()
                return True
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                self._list.setFocus()
                return True
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
            # Use a widget for two-column layout
            row_w = QWidget()
            row_w.setStyleSheet("background: transparent;")
            rl = QHBoxLayout(row_w)
            rl.setContentsMargins(0, 0, 0, 0)
            rl.setSpacing(0)

            code_lbl = QLabel(code)
            code_lbl.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {LABEL_CLR};"
                "background: transparent; min-width: 140px; max-width: 140px;"
            )
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet(
                f"font-size: 12px; color: {INPUT_TXT}; background: transparent;"
            )
            name_lbl.setWordWrap(False)
            rl.addWidget(code_lbl)
            rl.addWidget(name_lbl, 1)

            item.setSizeHint(row_w.sizeHint().expandedTo(
                __import__("PySide6.QtCore", fromlist=["QSize"]).QSize(0, 36)
            ))
            self._list.addItem(item)
            self._list.setItemWidget(item, row_w)

        self._footer.setText(f"{len(records)} record{'s' if len(records) != 1 else ''}")

    def _filter(self, q: str):
        q = q.lower()
        filtered = [
            r for r in self._records
            if q in str(r.get("pk", "")).lower() or q in str(r.get("name", "")).lower()
        ] if q else self._records
        self._rebuild_list(filtered)

    def _on_activated(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data:
            self.design_picked.emit(data[0], data[1])
            self.hide()

    def show_below(self, anchor: QWidget):
        self._load_records()
        self._search.clear()
        self._rebuild_list(self._records)
        self.adjustSize()
        gp = anchor.mapToGlobal(anchor.rect().bottomLeft())
        screen = QApplication.primaryScreen().availableGeometry()
        if gp.y() + self.height() > screen.bottom():
            gp = anchor.mapToGlobal(anchor.rect().topLeft())
            gp.setY(gp.y() - self.height() - 2)
        else:
            gp.setY(gp.y() + 4)
        self.move(gp)
        self.show()
        self._search.setFocus()


# ─────────────────────────────────────────────────────────────────────────────
# Label preview
# ─────────────────────────────────────────────────────────────────────────────

class _LabelPreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._code = ""
        self._name = ""
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {CARD};")

    def set_design(self, code: str, name: str):
        self._code = code
        self._name = name
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        W, H = self.width(), self.height()
        pad  = 18

        if not self._code:
            p.setPen(QPen(QColor(HINT)))
            p.setFont(QFont("Segoe UI", 9))
            p.drawText(self.rect(), Qt.AlignCenter, "Load a design to preview")
            p.end()
            return

        bx   = pad + 12
        bw   = W - 2*pad - 24
        bh   = int((H - 2*pad) * 0.55)
        by   = pad + 10
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
        p.setPen(QPen(QColor(INPUT_TXT)))
        tw = QFontMetrics(f1).horizontalAdvance(self._code)
        p.drawText(bx + (bw - tw) // 2, by + bh + 13, self._code)

        f2 = QFont("Segoe UI", 8)
        p.setFont(f2)
        p.setPen(QPen(QColor(MUTED)))
        p.drawText(
            self.rect().adjusted(pad + 6, by + bh + 22, -(pad + 6), -4),
            Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap, self._name,
        )
        p.end()


# ─────────────────────────────────────────────────────────────────────────────
# Print log
# ─────────────────────────────────────────────────────────────────────────────

class _PrintLog(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setStyleSheet(
            "QTextEdit { background: #0F172A; color: #475569; border: none;"
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


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

class BarcodePrintPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {BG};")
        self._build_ui()
        self._print_fields_card.setVisible(False)
        self._btn_print.setEnabled(False)

    # ── build ─────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        spl = QSplitter(Qt.Horizontal)
        spl.setHandleWidth(1)
        spl.setStyleSheet(f"QSplitter::handle {{ background: {BORDER}; }}")
        spl.addWidget(self._build_left())
        spl.addWidget(self._build_right())
        spl.setSizes([620, 360])
        root.addWidget(spl)

    # ── Left panel ────────────────────────────────────────────────────────────

    def _build_left(self) -> QWidget:
        outer = QWidget()
        outer.setStyleSheet(f"background: {BG};")
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(20, 16, 12, 16)
        vbox.setSpacing(12)

        # Page title + action buttons
        hdr = QHBoxLayout()
        title = QLabel("Barcode Print")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {INPUT_TXT};")
        hdr.addWidget(title)
        hdr.addStretch()

        self._btn_stop = QPushButton("Stop")
        self._btn_stop.setStyleSheet(BTN_OUTLINE)
        self._btn_stop.setIcon(qta.icon("fa5s.stop-circle", color=MUTED))
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_print = QPushButton("Print")
        self._btn_print.setStyleSheet(BTN_PRIMARY)
        self._btn_print.setIcon(qta.icon("fa5s.print", color="#fff"))
        self._btn_print.clicked.connect(self._on_print)

        hdr.addWidget(self._btn_stop)
        hdr.addSpacing(6)
        hdr.addWidget(self._btn_print)
        vbox.addLayout(hdr)

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { background: transparent; width: 4px; }"
            f"QScrollBar::handle:vertical {{ background: {INPUT_BD}; border-radius: 2px; min-height: 16px; }}"
            "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
        )
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        cv = QVBoxLayout(content)
        cv.setContentsMargins(0, 0, 6, 0)
        cv.setSpacing(0)

        # Wrap all cards in one bordered container (matches General tab)
        from PySide6.QtWidgets import QFrame as _QF
        wrapper = _QF()
        wrapper.setStyleSheet(
            f'background: {CARD}; border: 1px solid {BORDER}; border-radius: 8px;'
        )
        wrapper.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        wv = QVBoxLayout(wrapper)
        wv.setContentsMargins(0, 0, 0, 0)
        wv.setSpacing(0)
        wv.addWidget(self._build_design_card())
        _sep = QFrame(); _sep.setFrameShape(QFrame.HLine)
        _sep.setFixedHeight(1)
        _sep.setStyleSheet(f'background: {BORDER}; border: none;')
        wv.addWidget(_sep)
        wv.addWidget(self._build_printer_card())
        self._print_fields_card = self._build_print_fields_card()
        wv.addWidget(self._print_fields_card)
        cv.addWidget(wrapper)
        cv.addStretch()

        scroll.setWidget(content)
        vbox.addWidget(scroll, 1)
        return outer

    # ── Design card ───────────────────────────────────────────────────────────

    def _build_design_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        g = QGridLayout(card)
        g.setContentsMargins(20, 16, 20, 16)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(12)

        # Design Code
        self._inp_code = QLineEdit()
        self._inp_code.setPlaceholderText("Enter or browse design code…")
        self._inp_code.setStyleSheet(INPUT_STYLE)
        self._inp_code.returnPressed.connect(
            lambda: self.load_design_by_code(self._inp_code.text().strip())
        )
        self._btn_browse_code = QPushButton("···")
        self._btn_browse_code.setStyleSheet(BTN_BROWSE)
        self._btn_browse_code.setToolTip("Browse design codes")
        self._btn_browse_code.clicked.connect(self._on_browse_code)

        code_w = QWidget(); code_w.setStyleSheet("background:transparent;")
        cr = QHBoxLayout(code_w); cr.setContentsMargins(0,0,0,0); cr.setSpacing(6)
        cr.addWidget(self._inp_code); cr.addWidget(self._btn_browse_code)

        g.addWidget(_field_label("CODE"), 0, 0)
        g.addWidget(code_w, 0, 1)

        # Name
        self._inp_name = QLineEdit()
        self._inp_name.setReadOnly(True)
        self._inp_name.setPlaceholderText("Auto-filled from design code")
        self._inp_name.setStyleSheet(INPUT_STYLE)
        g.addWidget(_field_label("NAME"), 1, 0)
        g.addWidget(self._inp_name, 1, 1)

        g.setColumnStretch(1, 1)
        return card

    # ── Printer settings card ─────────────────────────────────────────────────

    def _build_printer_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        g = QGridLayout(card)
        g.setContentsMargins(20, 16, 20, 16)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(12)

        # COM status
        self._lbl_timbangan = _status_lbl("NOT CONNECTED", False)
        self._lbl_gate      = _status_lbl("NOT CONNECTED", False)
        g.addWidget(_field_label("COM TIMBANGAN"), 0, 0)
        g.addWidget(self._lbl_timbangan, 0, 1)
        g.addWidget(_field_label("COM GATE"), 1, 0)
        g.addWidget(self._lbl_gate, 1, 1)

        # Speed
        self._spin_speed = QSpinBox()
        self._spin_speed.setRange(1, 10); self._spin_speed.setValue(3)
        self._spin_speed.setStyleSheet(INPUT_STYLE); self._spin_speed.setFixedWidth(80)
        g.addWidget(_field_label("SPEED"), 2, 0)
        g.addWidget(self._spin_speed, 2, 1, Qt.AlignLeft)

        # Divider


        # Margin Left
        self._spin_ml = QSpinBox()
        self._spin_ml.setRange(-999, 999); self._spin_ml.setValue(0)
        self._spin_ml.setStyleSheet(INPUT_STYLE); self._spin_ml.setFixedWidth(80)
        g.addWidget(_field_label("MARGIN LEFT"), 4, 0)
        g.addWidget(self._spin_ml, 4, 1, Qt.AlignLeft)

        # Margin Top + 300 dpi
        self._spin_mt = QSpinBox()
        self._spin_mt.setRange(-999, 999); self._spin_mt.setValue(0)
        self._spin_mt.setStyleSheet(INPUT_STYLE); self._spin_mt.setFixedWidth(80)
        self._chk_dpi = _CheckBox("300 dpi")
        mt_w = QWidget(); mt_w.setStyleSheet("background:transparent;")
        ml = QHBoxLayout(mt_w); ml.setContentsMargins(0,0,0,0); ml.setSpacing(12)
        ml.addWidget(self._spin_mt); ml.addWidget(self._chk_dpi); ml.addStretch()
        g.addWidget(_field_label("MARGIN TOP"), 5, 0)
        g.addWidget(mt_w, 5, 1)

        # Printer Type
        self._chk_non_zebra = _CheckBox("Non Zebra Printer")
        self._spin_offset = QSpinBox()
        self._spin_offset.setRange(-999, 999); self._spin_offset.setValue(-11)
        self._spin_offset.setStyleSheet(INPUT_STYLE); self._spin_offset.setFixedWidth(70)
        pt_w = QWidget(); pt_w.setStyleSheet("background:transparent;")
        pl = QHBoxLayout(pt_w); pl.setContentsMargins(0,0,0,0); pl.setSpacing(12)
        pl.addWidget(self._chk_non_zebra); pl.addWidget(self._spin_offset); pl.addStretch()
        g.addWidget(_field_label("PRINTER TYPE"), 6, 0)
        g.addWidget(pt_w, 6, 1)

        g.setColumnStretch(1, 1)
        return card

    # ── Print fields card ─────────────────────────────────────────────────────

    def _build_print_fields_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(CARD_STYLE)
        g = QGridLayout(card)
        g.setContentsMargins(20, 16, 20, 16)
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(12)

        # Part No
        self._inp_part = QLineEdit()
        self._inp_part.setPlaceholderText("Enter or browse part number…")
        self._inp_part.setStyleSheet(INPUT_STYLE)
        self._btn_browse_part = QPushButton("···")
        self._btn_browse_part.setStyleSheet(BTN_BROWSE)
        self._btn_browse_part.clicked.connect(self._on_browse_part)
        part_w = QWidget(); part_w.setStyleSheet("background:transparent;")
        pw = QHBoxLayout(part_w); pw.setContentsMargins(0,0,0,0); pw.setSpacing(6)
        pw.addWidget(self._inp_part); pw.addWidget(self._btn_browse_part)
        g.addWidget(_field_label("PART NO. PRINT"), 0, 0)
        g.addWidget(part_w, 0, 1)

        # QTY
        self._inp_qty = QLineEdit()
        self._inp_qty.setReadOnly(True)
        self._inp_qty.setPlaceholderText("Auto-filled")
        self._inp_qty.setStyleSheet(INPUT_STYLE)
        g.addWidget(_field_label("QTY"), 1, 0)
        g.addWidget(self._inp_qty, 1, 1)

        # WHS
        self._inp_whs = QLineEdit()
        self._inp_whs.setReadOnly(True)
        self._inp_whs.setPlaceholderText("Auto-filled")
        self._inp_whs.setStyleSheet(INPUT_STYLE)
        g.addWidget(_field_label("WHS"), 2, 0)
        g.addWidget(self._inp_whs, 2, 1)

        # Date Code
        self._inp_date = QDateEdit()
        self._inp_date.setCalendarPopup(True)
        self._inp_date.setDate(QDate.currentDate())
        self._inp_date.setDisplayFormat("dd-MMM-yyyy")
        self._inp_date.setStyleSheet(INPUT_STYLE)
        self._inp_date.setFixedWidth(160)
        g.addWidget(_field_label("DATE CODE"), 3, 0)
        g.addWidget(self._inp_date, 3, 1, Qt.AlignLeft)

        # Print QTY
        self._spin_print_qty = QSpinBox()
        self._spin_print_qty.setRange(1, 9999); self._spin_print_qty.setValue(1)
        self._spin_print_qty.setStyleSheet(INPUT_STYLE); self._spin_print_qty.setFixedWidth(100)
        g.addWidget(_field_label("PRINT QTY"), 4, 0)
        g.addWidget(self._spin_print_qty, 4, 1, Qt.AlignLeft)

        g.setColumnStretch(1, 1)
        return card

    # ── Right panel ───────────────────────────────────────────────────────────

    def _build_right(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {BG};")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(6, 16, 16, 16)
        vbox.setSpacing(0)

        # Preview card
        p_hdr = QHBoxLayout()
        p_title = QLabel("Preview")
        p_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {INPUT_TXT};")
        p_hdr.addWidget(p_title); p_hdr.addStretch()
        vbox.addLayout(p_hdr)
        vbox.addSpacing(6)

        pf = QFrame()
        pf.setStyleSheet(CARD_STYLE)
        pf.setMinimumHeight(160)
        pfv = QVBoxLayout(pf); pfv.setContentsMargins(0,0,0,0)
        self._preview = _LabelPreview()
        pfv.addWidget(self._preview)
        vbox.addWidget(pf, 3)

        vbox.addSpacing(10)

        # Log card
        l_hdr = QHBoxLayout()
        l_title = QLabel("Print Log")
        l_title.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {INPUT_TXT};")
        self._btn_clear = QPushButton("Clear")
        self._btn_clear.setStyleSheet(BTN_GHOST)
        self._btn_clear.clicked.connect(lambda: self._log.clear_log())
        l_hdr.addWidget(l_title); l_hdr.addStretch(); l_hdr.addWidget(self._btn_clear)
        vbox.addLayout(l_hdr)
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
        if not hasattr(self, '_design_picker'):
            self._design_picker = _DesignPickerPopup(self)
            self._design_picker.design_picked.connect(
                lambda code, name: self.load_design_by_code(code, name)
            )
        self._design_picker.show_below(self._btn_browse_code)

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
        qty    = self._spin_print_qty.value()
        part   = self._inp_part.text().strip() or "(no part)"
        date_s = self._inp_date.date().toString("dd-MMM-yyyy")
        self._log.log(f"▶  [{code}]  ×{qty}  part={part}  date={date_s}", "ok")
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
        self._print_fields_card.setVisible(True)
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
                f"color: {SUCCESS if ok else DANGER}; font-size: 12px;"
                "font-weight: 600; background: transparent;"
            )
        _upd(self._lbl_timbangan, timbangan)
        _upd(self._lbl_gate, gate)