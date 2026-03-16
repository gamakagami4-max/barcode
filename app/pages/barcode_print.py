"""
barcode_print.py  —  Barcode Print Page
Place this file in your  pages/  folder.

Wire it up in main.py:
  1. Add to imports:
       from pages.barcode_print import BarcodePrintPage
  2. Add to PAGE_REGISTRY:
       10: {"title": "Barcode Print", "class": BarcodePrintPage, "icon": "🖨️"},
  3. Add to sidebar menu_defs in sidebar.py  (optional shortcut button):
       inside the "Barcode" CollapsibleMenu sub_items_dict add:
         "Barcode Print": lambda: self.nav_callback(10),
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

import qtawesome as qta
from PySide6.QtCore import (
    Qt, QSize, QRect, QPoint, QMarginsF, Signal,
)
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QPageLayout, QPageSize, QPainterPath, QIcon,
)
from PySide6.QtPrintSupport import QPrinter, QPrintPreviewDialog, QPrintDialog
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox,
    QComboBox, QLineEdit, QGroupBox, QScrollArea,
    QSizePolicy, QFrame, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSplitter, QFormLayout, QToolButton, QButtonGroup,
    QAbstractButton, QMessageBox, QApplication,
)

# ── Palette (mirrors your existing sidebar palette) ───────────────────────────
C_BG        = "#F8FAFC"
C_SURFACE   = "#FFFFFF"
C_BORDER    = "#E2E8F0"
C_BORDER2   = "#CBD5E1"
C_TEXT      = "#1E293B"
C_MUTED     = "#64748B"
C_ACCENT    = "#3B82F6"
C_ACCENT_BG = "#EFF6FF"
C_DANGER    = "#EF4444"
C_SUCCESS   = "#22C55E"


# ── Button styles ─────────────────────────────────────────────────────────────
BTN_PRIMARY = f"""
QPushButton {{
    background: {C_ACCENT}; color: #FFFFFF;
    border: none; border-radius: 7px;
    font-size: 13px; font-weight: 600;
    padding: 8px 18px;
}}
QPushButton:hover  {{ background: #2563EB; }}
QPushButton:pressed{{ background: #1D4ED8; }}
QPushButton:disabled{{ background: #94A3B8; }}
"""

BTN_SECONDARY = f"""
QPushButton {{
    background: {C_SURFACE}; color: {C_TEXT};
    border: 1px solid {C_BORDER2}; border-radius: 7px;
    font-size: 13px; padding: 8px 18px;
}}
QPushButton:hover  {{ background: #F1F5F9; }}
QPushButton:pressed{{ background: #E2E8F0; }}
"""

BTN_DANGER = f"""
QPushButton {{
    background: {C_SURFACE}; color: {C_DANGER};
    border: 1px solid #FECACA; border-radius: 7px;
    font-size: 13px; padding: 8px 18px;
}}
QPushButton:hover  {{ background: #FFF1F2; border-color: {C_DANGER}; }}
"""

SPIN_STYLE = f"""
QSpinBox, QDoubleSpinBox, QLineEdit, QComboBox {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER2};
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 13px;
    color: {C_TEXT};
    min-height: 28px;
}}
QSpinBox:focus, QDoubleSpinBox:focus, QLineEdit:focus, QComboBox:focus {{
    border-color: {C_ACCENT};
}}
QComboBox::drop-down {{ border: none; padding-right: 6px; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    width: 18px; border: none;
    background: transparent;
}}
"""

GROUP_STYLE = f"""
QGroupBox {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 10px;
    margin-top: 18px;
    font-size: 12px;
    font-weight: 700;
    color: {C_MUTED};
    letter-spacing: 0.6px;
    padding: 8px 4px 4px 4px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    left: 14px;
}}
"""

TABLE_STYLE = f"""
QTableWidget {{
    background: {C_SURFACE};
    border: 1px solid {C_BORDER};
    border-radius: 8px;
    gridline-color: {C_BORDER};
    font-size: 13px;
    color: {C_TEXT};
    outline: none;
}}
QTableWidget::item {{
    padding: 6px 10px;
    border: none;
}}
QTableWidget::item:selected {{
    background: {C_ACCENT_BG};
    color: {C_ACCENT};
}}
QHeaderView::section {{
    background: #F1F5F9;
    color: {C_MUTED};
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.5px;
    border: none;
    border-bottom: 1px solid {C_BORDER};
    padding: 7px 10px;
}}
"""


# ── Data ──────────────────────────────────────────────────────────────────────
@dataclass
class BarcodeItem:
    code:     str   = ""
    label:    str   = ""
    qty:      int   = 1
    selected: bool  = True


# ── Barcode renderer (Code 128 simplified visual) ─────────────────────────────
class BarcodeRenderer:
    """
    Renders a simple barcode stripe pattern for display & print.
    Uses a deterministic pattern derived from the code string so every
    unique code gets a visually distinct (though not GS1-compliant) pattern.
    For production use, swap _encode() with a real Code-128 library.
    """

    BAR_W = 1.8     # narrow bar width (pt)
    SPACE = 0.9     # narrow space width (pt)
    QUIET  = 8.0    # quiet zone each side (pt)

    @staticmethod
    def _encode(code: str) -> list[int]:
        """Return a list of widths (alternating bar / space) in narrow-bar units."""
        # Start sentinel: 3-wide bar
        pattern = [3, 1]
        for ch in code:
            v = ord(ch)
            # 5 elements per character (bar, space, bar, space, bar)
            pattern += [
                1 + (v >> 5 & 3),
                1 + (v >> 3 & 1),
                1 + (v >> 1 & 3),
                1 + (v      & 1),
                1 + (v >> 4 & 2),
            ]
        # Stop sentinel
        pattern += [3, 1, 2]
        return pattern

    @classmethod
    def draw(
        cls,
        painter: QPainter,
        rect: QRect,
        code: str,
        label: str = "",
        show_label: bool = True,
        font_size: int = 7,
    ):
        pattern = cls._encode(code or "000000")
        n       = cls.BAR_W
        total_u = sum(pattern)
        avail_w = rect.width() - 2 * cls.QUIET
        scale   = avail_w / (total_u * n)

        bar_h = rect.height() - (20 if show_label else 4)
        x     = rect.x() + cls.QUIET
        y     = rect.y() + 2

        painter.setBrush(QBrush(Qt.black))
        painter.setPen(Qt.NoPen)

        for i, width in enumerate(pattern):
            w_px = width * n * scale
            if i % 2 == 0:                    # even = bar
                painter.drawRect(
                    QRect(int(x), int(y), max(1, int(w_px)), int(bar_h))
                )
            x += w_px

        if show_label and label:
            f = QFont("Courier New", font_size)
            painter.setFont(f)
            painter.setPen(QPen(QColor(C_TEXT)))
            fm  = QFontMetrics(f)
            tw  = fm.horizontalAdvance(label)
            tx  = rect.x() + (rect.width() - tw) // 2
            ty  = rect.y() + bar_h + 14
            painter.drawText(tx, ty, label)


# ── Label preview widget ──────────────────────────────────────────────────────
class LabelPreviewWidget(QWidget):
    """
    Renders a single label cell as it will appear on paper.
    Draws the barcode + text label inside a rounded-rect frame.
    """

    def __init__(
        self,
        item: Optional[BarcodeItem] = None,
        label_w_mm: float = 50.0,
        label_h_mm: float = 25.0,
        parent=None,
    ):
        super().__init__(parent)
        self._item     = item
        self._w_mm     = label_w_mm
        self._h_mm     = label_h_mm
        self._scale    = 3.0           # screen pixels per mm
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self._update_fixed_size()

    def _update_fixed_size(self):
        self.setFixedSize(
            int(self._w_mm * self._scale) + 4,
            int(self._h_mm * self._scale) + 4,
        )

    def set_item(self, item: Optional[BarcodeItem]):
        self._item = item
        self.update()

    def set_size(self, w_mm: float, h_mm: float):
        self._w_mm = w_mm
        self._h_mm = h_mm
        self._update_fixed_size()
        self.update()

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        W = int(self._w_mm * self._scale)
        H = int(self._h_mm * self._scale)
        ox, oy = 2, 2

        # Shadow
        shadow = QPainterPath()
        shadow.addRoundedRect(ox + 2, oy + 2, W, H, 5, 5)
        p.fillPath(shadow, QColor(0, 0, 0, 18))

        # Label background
        path = QPainterPath()
        path.addRoundedRect(ox, oy, W, H, 5, 5)
        p.fillPath(path, QColor(C_SURFACE))
        p.setPen(QPen(QColor(C_BORDER2), 0.8))
        p.drawPath(path)

        if self._item:
            margin = int(3 * self._scale / 3)
            draw_rect = QRect(ox + margin, oy + margin, W - 2 * margin, H - 2 * margin)
            BarcodeRenderer.draw(
                p,
                draw_rect,
                self._item.code,
                label=self._item.label or self._item.code,
                show_label=True,
                font_size=max(5, int(self._scale * 2.2)),
            )
        else:
            p.setPen(QPen(QColor(C_BORDER), 1, Qt.DashLine))
            p.drawRect(ox + 6, oy + 6, W - 12, H - 12)
            p.setPen(QPen(QColor(C_MUTED)))
            f = QFont("Segoe UI", 8)
            p.setFont(f)
            p.drawText(QRect(ox, oy, W, H), Qt.AlignCenter, "Empty")

        p.end()


# ── Sheet preview (all labels on one page) ────────────────────────────────────
class SheetPreviewWidget(QWidget):
    """Renders a miniature preview of the whole print sheet."""

    PAPER_W = 210   # A4 mm
    PAPER_H = 297   # A4 mm

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(300)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet(f"background: {C_BG};")

        # Layout params (mm)
        self._cols       = 3
        self._rows       = 8
        self._label_w    = 60.0
        self._label_h    = 30.0
        self._margin_lr  = 10.0
        self._margin_tb  = 10.0
        self._gap_h      = 3.0
        self._gap_v      = 3.0

        self._items: list[BarcodeItem] = []

    # ── Public setters ────────────────────────────────────────────────────────
    def set_items(self, items: list[BarcodeItem]):
        self._items = items
        self.update()

    def set_layout(
        self,
        cols: int, rows: int,
        label_w: float, label_h: float,
        margin_lr: float, margin_tb: float,
        gap_h: float, gap_v: float,
    ):
        self._cols      = max(1, cols)
        self._rows      = max(1, rows)
        self._label_w   = label_w
        self._label_h   = label_h
        self._margin_lr = margin_lr
        self._margin_tb = margin_tb
        self._gap_h     = gap_h
        self._gap_v     = gap_v
        self.update()

    # ── Paint ─────────────────────────────────────────────────────────────────
    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.TextAntialiasing)

        # Fit A4 into widget
        avail_w = self.width()  - 32
        avail_h = self.height() - 32
        scale   = min(avail_w / self.PAPER_W, avail_h / self.PAPER_H)
        pw      = int(self.PAPER_W * scale)
        ph      = int(self.PAPER_H * scale)
        ox      = (self.width()  - pw) // 2
        oy      = (self.height() - ph) // 2

        # Paper shadow
        shadow = QPainterPath()
        shadow.addRoundedRect(ox + 3, oy + 3, pw, ph, 4, 4)
        p.fillPath(shadow, QColor(0, 0, 0, 22))

        # Paper
        paper = QPainterPath()
        paper.addRoundedRect(ox, oy, pw, ph, 4, 4)
        p.fillPath(paper, QColor(C_SURFACE))
        p.setPen(QPen(QColor(C_BORDER2), 0.5))
        p.drawPath(paper)

        # Labels
        lw = self._label_w * scale
        lh = self._label_h * scale
        gh = self._gap_h   * scale
        gv = self._gap_v   * scale
        ml = self._margin_lr * scale
        mt = self._margin_tb * scale

        idx = 0
        items_flat: list[BarcodeItem] = []
        for item in self._items:
            items_flat.extend([item] * item.qty)

        for r in range(self._rows):
            for c in range(self._cols):
                lx = ox + ml + c * (lw + gh)
                ly = oy + mt + r * (lh + gv)

                # Label cell background
                cell = QPainterPath()
                cell.addRoundedRect(lx, ly, lw, lh, 2, 2)

                if idx < len(items_flat):
                    item = items_flat[idx]
                    p.fillPath(cell, QColor(C_SURFACE))
                    p.setPen(QPen(QColor(C_BORDER), 0.4))
                    p.drawPath(cell)

                    # Draw barcode stripes inside cell
                    inner = QRect(int(lx + 2), int(ly + 2), int(lw - 4), int(lh - 4))
                    BarcodeRenderer.draw(
                        p, inner,
                        item.code,
                        label=item.label or item.code,
                        show_label=True,
                        font_size=max(4, int(scale * 2.5)),
                    )
                    idx += 1
                else:
                    p.fillPath(cell, QColor("#F8FAFC"))
                    p.setPen(QPen(QColor(C_BORDER), 0.3, Qt.DashLine))
                    p.drawPath(cell)

        p.end()


# ── Item table ────────────────────────────────────────────────────────────────
class ItemTable(QTableWidget):
    items_changed = Signal()

    COLS = ["", "Barcode Code", "Label Text", "Qty"]

    def __init__(self, parent=None):
        super().__init__(0, len(self.COLS), parent)
        self.setStyleSheet(TABLE_STYLE)
        self.setHorizontalHeaderLabels(self.COLS)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed)
        self.setAlternatingRowColors(True)
        self.setStyleSheet(TABLE_STYLE + "QTableWidget { alternate-background-color: #F8FAFC; }")
        self.verticalHeader().hide()
        self.setFocusPolicy(Qt.StrongFocus)

        hh = self.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Fixed)
        hh.setSectionResizeMode(1, QHeaderView.Stretch)
        hh.setSectionResizeMode(2, QHeaderView.Stretch)
        hh.setSectionResizeMode(3, QHeaderView.Fixed)
        self.setColumnWidth(0, 36)
        self.setColumnWidth(3, 70)
        self.setShowGrid(False)
        self.verticalHeader().setDefaultSectionSize(36)

        self.itemChanged.connect(self._on_item_changed)

    # ── Row helpers ───────────────────────────────────────────────────────────
    def add_item(self, item: BarcodeItem):
        self.blockSignals(True)
        row = self.rowCount()
        self.insertRow(row)

        chk = QTableWidgetItem()
        chk.setCheckState(Qt.Checked if item.selected else Qt.Unchecked)
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        self.setItem(row, 0, chk)

        code_item = QTableWidgetItem(item.code)
        self.setItem(row, 1, code_item)

        label_item = QTableWidgetItem(item.label)
        self.setItem(row, 2, label_item)

        qty_item = QTableWidgetItem(str(item.qty))
        qty_item.setTextAlignment(Qt.AlignCenter)
        self.setItem(row, 3, qty_item)

        self.blockSignals(False)

    def get_items(self) -> list[BarcodeItem]:
        items = []
        for row in range(self.rowCount()):
            chk  = self.item(row, 0)
            code = self.item(row, 1)
            lbl  = self.item(row, 2)
            qty  = self.item(row, 3)
            if not code:
                continue
            try:
                q = max(1, int((qty.text() if qty else "1") or "1"))
            except ValueError:
                q = 1
            items.append(BarcodeItem(
                code     = code.text().strip(),
                label    = lbl.text().strip() if lbl else "",
                qty      = q,
                selected = (chk.checkState() == Qt.Checked) if chk else True,
            ))
        return items

    def get_selected_items(self) -> list[BarcodeItem]:
        return [i for i in self.get_items() if i.selected]

    def remove_selected_rows(self):
        rows = sorted({i.row() for i in self.selectedItems()}, reverse=True)
        for r in rows:
            self.removeRow(r)
        self.items_changed.emit()

    def _on_item_changed(self, _item):
        self.items_changed.emit()


# ── Print engine ──────────────────────────────────────────────────────────────
class PrintEngine:
    """Renders all label pages onto a QPrinter."""

    def __init__(
        self,
        items: list[BarcodeItem],
        cols: int,
        rows: int,
        label_w_mm: float,
        label_h_mm: float,
        margin_lr_mm: float,
        margin_tb_mm: float,
        gap_h_mm: float,
        gap_v_mm: float,
    ):
        self._items      = items
        self._cols       = cols
        self._rows       = rows
        self._label_w    = label_w_mm
        self._label_h    = label_h_mm
        self._ml         = margin_lr_mm
        self._mt         = margin_tb_mm
        self._gh         = gap_h_mm
        self._gv         = gap_v_mm

    def print_to(self, printer: QPrinter):
        p   = QPainter()
        ok  = p.begin(printer)
        if not ok:
            return

        dpi   = printer.resolution()
        mm2pt = dpi / 25.4

        lw = self._label_w * mm2pt
        lh = self._label_h * mm2pt
        gh = self._gh      * mm2pt
        gv = self._gv      * mm2pt
        ml = self._ml      * mm2pt
        mt = self._mt      * mm2pt

        per_page = self._cols * self._rows
        items_flat: list[BarcodeItem] = []
        for item in self._items:
            items_flat.extend([item] * item.qty)

        total = len(items_flat)
        pages = max(1, math.ceil(total / per_page))

        for pg in range(pages):
            if pg > 0:
                printer.newPage()
            start = pg * per_page
            page_items = items_flat[start: start + per_page]
            idx = 0
            for r in range(self._rows):
                for c in range(self._cols):
                    if idx >= len(page_items):
                        break
                    x = int(ml + c * (lw + gh))
                    y = int(mt + r * (lh + gv))
                    rect = QRect(x, y, int(lw), int(lh))
                    item = page_items[idx]
                    BarcodeRenderer.draw(
                        p, rect, item.code,
                        label=item.label or item.code,
                        show_label=True,
                        font_size=6,
                    )
                    idx += 1

        p.end()


# ── Main page widget ──────────────────────────────────────────────────────────
class BarcodePrintPage(QWidget):
    """
    Full barcode print page.

    Left panel  : item list (add / remove / edit barcodes + quantities)
    Right panel : layout settings + live sheet preview + print button
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C_BG};")
        self._build_ui()
        self._load_defaults()
        self._refresh_preview()

    # ── UI construction ───────────────────────────────────────────────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setStyleSheet(f"QSplitter::handle {{ background: {C_BORDER}; }}")

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([480, 560])

        root.addWidget(splitter)

    # ── Left panel: item list ─────────────────────────────────────────────────
    def _build_left_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C_BG};")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(20, 20, 12, 20)
        vbox.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────────
        header = QHBoxLayout()
        title  = QLabel("Barcode Items")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {C_TEXT};")
        header.addWidget(title)
        header.addStretch()

        self._count_lbl = QLabel("0 items")
        self._count_lbl.setStyleSheet(f"font-size: 12px; color: {C_MUTED};")
        header.addWidget(self._count_lbl)
        vbox.addLayout(header)

        # ── Quick-add row ─────────────────────────────────────────────────────
        add_box = QGroupBox("ADD ITEM")
        add_box.setStyleSheet(GROUP_STYLE)
        form = QFormLayout(add_box)
        form.setContentsMargins(14, 18, 14, 12)
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignRight)

        self._inp_code  = QLineEdit()
        self._inp_code.setPlaceholderText("e.g. 1234567890")
        self._inp_code.setStyleSheet(SPIN_STYLE)

        self._inp_label = QLineEdit()
        self._inp_label.setPlaceholderText("Display text (optional)")
        self._inp_label.setStyleSheet(SPIN_STYLE)

        self._inp_qty   = QSpinBox()
        self._inp_qty.setRange(1, 9999)
        self._inp_qty.setValue(1)
        self._inp_qty.setStyleSheet(SPIN_STYLE)
        self._inp_qty.setFixedWidth(80)

        form.addRow("Code:", self._inp_code)
        form.addRow("Label:", self._inp_label)
        form.addRow("Qty:", self._inp_qty)

        btn_row = QHBoxLayout()
        self._btn_add = QPushButton("Add")
        self._btn_add.setStyleSheet(BTN_PRIMARY)
        self._btn_add.setIcon(qta.icon("fa5s.plus", color="#FFFFFF"))
        self._btn_add.clicked.connect(self._on_add_item)
        self._inp_code.returnPressed.connect(self._on_add_item)

        btn_row.addStretch()
        btn_row.addWidget(self._btn_add)
        form.addRow("", btn_row)
        vbox.addWidget(add_box)

        # ── Table ─────────────────────────────────────────────────────────────
        self._table = ItemTable()
        self._table.items_changed.connect(self._refresh_preview)
        vbox.addWidget(self._table, stretch=1)

        # ── Table toolbar ─────────────────────────────────────────────────────
        tbar = QHBoxLayout()
        self._btn_remove = QPushButton("Remove Selected")
        self._btn_remove.setStyleSheet(BTN_DANGER)
        self._btn_remove.setIcon(qta.icon("fa5s.trash-alt", color=C_DANGER))
        self._btn_remove.clicked.connect(self._on_remove_items)

        self._btn_clear = QPushButton("Clear All")
        self._btn_clear.setStyleSheet(BTN_SECONDARY)
        self._btn_clear.setIcon(qta.icon("fa5s.broom", color=C_MUTED))
        self._btn_clear.clicked.connect(self._on_clear_all)

        self._btn_demo = QPushButton("Load Demo Data")
        self._btn_demo.setStyleSheet(BTN_SECONDARY)
        self._btn_demo.setIcon(qta.icon("fa5s.database", color=C_MUTED))
        self._btn_demo.clicked.connect(self._on_load_demo)

        tbar.addWidget(self._btn_remove)
        tbar.addWidget(self._btn_clear)
        tbar.addStretch()
        tbar.addWidget(self._btn_demo)
        vbox.addLayout(tbar)

        return w

    # ── Right panel: settings + preview ──────────────────────────────────────
    def _build_right_panel(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background: {C_BG};")
        vbox = QVBoxLayout(w)
        vbox.setContentsMargins(12, 20, 20, 20)
        vbox.setSpacing(14)

        # ── Header + print buttons ────────────────────────────────────────────
        header = QHBoxLayout()
        title  = QLabel("Print Layout")
        title.setStyleSheet(f"font-size: 17px; font-weight: 700; color: {C_TEXT};")
        header.addWidget(title)
        header.addStretch()

        self._btn_preview = QPushButton("Preview")
        self._btn_preview.setStyleSheet(BTN_SECONDARY)
        self._btn_preview.setIcon(qta.icon("fa5s.eye", color=C_MUTED))
        self._btn_preview.clicked.connect(self._on_print_preview)

        self._btn_print = QPushButton("Print")
        self._btn_print.setStyleSheet(BTN_PRIMARY)
        self._btn_print.setIcon(qta.icon("fa5s.print", color="#FFFFFF"))
        self._btn_print.clicked.connect(self._on_print)

        header.addWidget(self._btn_preview)
        header.addSpacing(8)
        header.addWidget(self._btn_print)
        vbox.addLayout(header)

        # ── Layout settings ────────────────────────────────────────────────────
        settings_box = QGroupBox("LABEL LAYOUT")
        settings_box.setStyleSheet(GROUP_STYLE)
        grid = QGridLayout(settings_box)
        grid.setContentsMargins(14, 18, 14, 12)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"font-size: 12px; color: {C_MUTED}; font-weight: 500;")
            return l

        # Paper size
        self._paper_combo = QComboBox()
        self._paper_combo.setStyleSheet(SPIN_STYLE)
        self._paper_combo.addItems(["A4 (210 × 297 mm)", "Letter (216 × 279 mm)", "A5 (148 × 210 mm)"])
        grid.addWidget(lbl("Paper:"),       0, 0)
        grid.addWidget(self._paper_combo,   0, 1, 1, 3)

        # Columns / Rows
        self._spin_cols = QSpinBox(); self._spin_cols.setRange(1, 10); self._spin_cols.setValue(3)
        self._spin_rows = QSpinBox(); self._spin_rows.setRange(1, 20); self._spin_rows.setValue(8)
        self._spin_cols.setStyleSheet(SPIN_STYLE)
        self._spin_rows.setStyleSheet(SPIN_STYLE)
        grid.addWidget(lbl("Columns:"),     1, 0);  grid.addWidget(self._spin_cols, 1, 1)
        grid.addWidget(lbl("Rows:"),        1, 2);  grid.addWidget(self._spin_rows, 1, 3)

        # Label size
        self._spin_lw = QDoubleSpinBox(); self._spin_lw.setRange(10, 200); self._spin_lw.setSuffix(" mm"); self._spin_lw.setValue(60)
        self._spin_lh = QDoubleSpinBox(); self._spin_lh.setRange(5,  100); self._spin_lh.setSuffix(" mm"); self._spin_lh.setValue(30)
        self._spin_lw.setStyleSheet(SPIN_STYLE)
        self._spin_lh.setStyleSheet(SPIN_STYLE)
        grid.addWidget(lbl("Label W:"),     2, 0);  grid.addWidget(self._spin_lw, 2, 1)
        grid.addWidget(lbl("Label H:"),     2, 2);  grid.addWidget(self._spin_lh, 2, 3)

        # Margins
        self._spin_ml = QDoubleSpinBox(); self._spin_ml.setRange(0, 50); self._spin_ml.setSuffix(" mm"); self._spin_ml.setValue(10)
        self._spin_mt = QDoubleSpinBox(); self._spin_mt.setRange(0, 50); self._spin_mt.setSuffix(" mm"); self._spin_mt.setValue(10)
        self._spin_ml.setStyleSheet(SPIN_STYLE)
        self._spin_mt.setStyleSheet(SPIN_STYLE)
        grid.addWidget(lbl("Margin L/R:"),  3, 0);  grid.addWidget(self._spin_ml, 3, 1)
        grid.addWidget(lbl("Margin T/B:"),  3, 2);  grid.addWidget(self._spin_mt, 3, 3)

        # Gap
        self._spin_gh = QDoubleSpinBox(); self._spin_gh.setRange(0, 20); self._spin_gh.setSuffix(" mm"); self._spin_gh.setValue(3)
        self._spin_gv = QDoubleSpinBox(); self._spin_gv.setRange(0, 20); self._spin_gv.setSuffix(" mm"); self._spin_gv.setValue(3)
        self._spin_gh.setStyleSheet(SPIN_STYLE)
        self._spin_gv.setStyleSheet(SPIN_STYLE)
        grid.addWidget(lbl("Gap H:"),       4, 0);  grid.addWidget(self._spin_gh, 4, 1)
        grid.addWidget(lbl("Gap V:"),       4, 2);  grid.addWidget(self._spin_gv, 4, 3)

        vbox.addWidget(settings_box)

        # Connect all layout spinners to preview refresh
        for sp in [self._spin_cols, self._spin_rows]:
            sp.valueChanged.connect(self._refresh_preview)
        for sp in [self._spin_lw, self._spin_lh, self._spin_ml, self._spin_mt, self._spin_gh, self._spin_gv]:
            sp.valueChanged.connect(self._refresh_preview)
        self._paper_combo.currentIndexChanged.connect(self._refresh_preview)

        # ── Summary strip ──────────────────────────────────────────────────────
        summ = QHBoxLayout()
        self._lbl_total  = self._make_chip("Total labels", "0")
        self._lbl_pages  = self._make_chip("Pages needed", "0")
        self._lbl_perp   = self._make_chip("Per page", "0")
        summ.addWidget(self._lbl_total)
        summ.addWidget(self._lbl_pages)
        summ.addWidget(self._lbl_perp)
        summ.addStretch()
        vbox.addLayout(summ)

        # ── Sheet preview ──────────────────────────────────────────────────────
        prev_box = QGroupBox("SHEET PREVIEW")
        prev_box.setStyleSheet(GROUP_STYLE)
        prev_vbox = QVBoxLayout(prev_box)
        prev_vbox.setContentsMargins(8, 16, 8, 8)

        self._sheet_preview = SheetPreviewWidget()
        prev_vbox.addWidget(self._sheet_preview)
        vbox.addWidget(prev_box, stretch=1)

        return w

    @staticmethod
    def _make_chip(title: str, value: str) -> QLabel:
        lbl = QLabel(f"<b style='color:{C_TEXT};font-size:18px;'>{value}</b><br>"
                     f"<span style='color:{C_MUTED};font-size:11px;'>{title}</span>")
        lbl.setTextFormat(Qt.RichText)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            f"background:{C_SURFACE}; border:1px solid {C_BORDER};"
            f"border-radius:8px; padding:8px 18px; min-width:100px;"
        )
        return lbl

    # ── Defaults ──────────────────────────────────────────────────────────────
    def _load_defaults(self):
        pass   # Layout spinners already have default values from _build_right_panel

    # ── Slots ─────────────────────────────────────────────────────────────────
    def _on_add_item(self):
        code = self._inp_code.text().strip()
        if not code:
            self._inp_code.setFocus()
            return
        label = self._inp_label.text().strip()
        qty   = self._inp_qty.value()
        self._table.add_item(BarcodeItem(code=code, label=label, qty=qty))
        self._inp_code.clear()
        self._inp_label.clear()
        self._inp_qty.setValue(1)
        self._inp_code.setFocus()
        self._refresh_preview()

    def _on_remove_items(self):
        self._table.remove_selected_rows()

    def _on_clear_all(self):
        if self._table.rowCount() == 0:
            return
        ans = QMessageBox.question(
            self, "Clear All",
            "Remove all items from the print list?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if ans == QMessageBox.Yes:
            self._table.setRowCount(0)
            self._refresh_preview()

    def _on_load_demo(self):
        demo = [
            BarcodeItem("8991234567890", "Aqua 600ml",     3),
            BarcodeItem("8990987654321", "Fruit Tea Lemon", 2),
            BarcodeItem("8991111222333", "Green Tea 500ml", 5),
            BarcodeItem("8994444555666", "Mineral Water",   4),
            BarcodeItem("8997777888999", "Sparkling Water", 2),
            BarcodeItem("8990001112222", "Energy Drink",    1),
        ]
        self._table.setRowCount(0)
        for item in demo:
            self._table.add_item(item)
        self._refresh_preview()

    def _refresh_preview(self):
        items    = self._table.get_selected_items()
        cols     = self._spin_cols.value()
        rows     = self._spin_rows.value()
        per_page = cols * rows

        total = sum(i.qty for i in items)
        pages = max(1, math.ceil(total / per_page)) if total else 0

        # Update chips
        def _set(lbl: QLabel, val: int, title: str):
            lbl.setText(
                f"<b style='color:{C_TEXT};font-size:18px;'>{val}</b><br>"
                f"<span style='color:{C_MUTED};font-size:11px;'>{title}</span>"
            )
        _set(self._lbl_total,  total,    "Total labels")
        _set(self._lbl_pages,  pages,    "Pages needed")
        _set(self._lbl_perp,   per_page, "Per page")

        # Update count label
        row_count = self._table.rowCount()
        self._count_lbl.setText(
            f"{row_count} item{'s' if row_count != 1 else ''}"
        )

        # Update sheet preview
        self._sheet_preview.set_layout(
            cols   = cols,
            rows   = rows,
            label_w  = self._spin_lw.value(),
            label_h  = self._spin_lh.value(),
            margin_lr= self._spin_ml.value(),
            margin_tb= self._spin_mt.value(),
            gap_h    = self._spin_gh.value(),
            gap_v    = self._spin_gv.value(),
        )
        self._sheet_preview.set_items(items)

    def _get_engine(self) -> PrintEngine:
        return PrintEngine(
            items       = self._table.get_selected_items(),
            cols        = self._spin_cols.value(),
            rows        = self._spin_rows.value(),
            label_w_mm  = self._spin_lw.value(),
            label_h_mm  = self._spin_lh.value(),
            margin_lr_mm= self._spin_ml.value(),
            margin_tb_mm= self._spin_mt.value(),
            gap_h_mm    = self._spin_gh.value(),
            gap_v_mm    = self._spin_gv.value(),
        )

    def _setup_printer(self, printer: QPrinter):
        idx  = self._paper_combo.currentIndex()
        size = [QPageSize.A4, QPageSize.Letter, QPageSize.A5][idx]
        printer.setPageSize(QPageSize(size))
        printer.setPageOrientation(QPageLayout.Portrait)
        printer.setFullPage(True)

    def _on_print_preview(self):
        if not self._table.get_selected_items():
            QMessageBox.information(self, "No Items", "Please add at least one item to print.")
            return
        printer = QPrinter(QPrinter.HighResolution)
        self._setup_printer(printer)

        dialog = QPrintPreviewDialog(printer, self)
        dialog.setWindowTitle("Barcode Print Preview")
        dialog.paintRequested.connect(lambda p: self._get_engine().print_to(p))
        dialog.resize(900, 700)
        dialog.exec()

    def _on_print(self):
        items = self._table.get_selected_items()
        if not items:
            QMessageBox.information(self, "No Items", "Please add at least one item to print.")
            return
        printer = QPrinter(QPrinter.HighResolution)
        self._setup_printer(printer)
        dlg = QPrintDialog(printer, self)
        dlg.setWindowTitle("Print Barcodes")
        if dlg.exec() == QPrintDialog.Accepted:
            self._get_engine().print_to(printer)