import os
import json as _json
import uuid

import qtawesome as qta
import shiboken6

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QGraphicsScene, QGraphicsView, QGraphicsItem,
    QGraphicsRectItem, QGraphicsTextItem, QGraphicsLineItem,
    QListWidget, QListWidgetItem, QApplication, QScrollArea,
    QSizePolicy, QStackedWidget, QPushButton, QLineEdit,
    QStyledItemDelegate, QStyle, QSplitter,
)
from PySide6.QtCore import Qt, QPointF, QRectF, QRect, QSize, QEvent, Signal
from PySide6.QtGui import QColor, QPen, QBrush, QPainter, QFont, QCursor, QShortcut, QKeySequence, QFontMetrics

from components.standard_button import StandardButton

from components.barcode_editor.utils import (
    COLORS, MODERN_SCROLLBAR_STYLE, TAB_ACTIVE_STYLE, TAB_INACTIVE_STYLE,
    setup_item_logic, ConstrainedScrollArea,
)
from components.barcode_editor.scene_items import (
    SelectableTextItem, SelectableLineItem, SelectableRectItem, BarcodeItem,
)
from components.barcode_editor.same_with_mixin import SameWithRegistry
from components.barcode_editor.text_property_editor import TextPropertyEditor
from components.barcode_editor.property_editors import LinePropertyEditor, RectanglePropertyEditor, BarcodePropertyEditor
from components.barcode_editor.merge_konversi_mixin import MultiSelectCombo
from components.barcode_editor.general_tab import GeneralTab


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


def _init_text_item(item: SelectableTextItem):
    item.document().setDocumentMargin(0)


_BARCODE_DEFAULTS = {
    "design_height_cm":      1.0,
    "design_magnification":  "1",
    "design_ratio":          "2",
    "design_check_digit":    "-- NONE --",
    "design_interpretation": "NO INTERPRETATION",
    "design_type":           "FIX",
    "design_editor":         "INVISIBLE",
    "design_text":           "",
    "design_caption":        "",
    "design_group":          "",
    "design_table":          "",
    "design_field":          "",
    "design_result":         "",
    "design_format":         "",
    "design_save_field":     "-- NOT SAVE --",
    "design_column":         1,
}


def _apply_barcode_defaults(item: BarcodeItem):
    """Set all new design attributes with defaults on a freshly created BarcodeItem."""
    for attr, default in _BARCODE_DEFAULTS.items():
        if not hasattr(item, attr):
            setattr(item, attr, default)


class ComponentItemDelegate(QStyledItemDelegate):
    # Layout constants for row geometry
    ROW_H = 38; ACCENT_W = 3; CHIP_SIZE = 24; PAD = 8; TRASH_SIZE = 18

    def sizeHint(self, option, index):
        return QSize(0, self.ROW_H)

    def paint(self, painter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        name = index.data(Qt.DisplayRole) or ""
        icon_name, badge_bg, badge_fg, accent = _get_meta(name)

        selected = bool(option.state & QStyle.State_Selected)
        hovered  = bool(option.state & QStyle.State_MouseOver) and not selected

        r = option.rect.adjusted(4, 2, -4, -2)

        bg = (QColor("#EEF2FF") if selected
              else QColor("#F8FAFC") if hovered
              else QColor("#FFFFFF"))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg))
        painter.drawRoundedRect(r, 6, 6)

        accent_rect = QRect(r.left(), r.top() + 6, self.ACCENT_W, r.height() - 12)
        painter.setBrush(QBrush(QColor(accent)))
        painter.drawRoundedRect(accent_rect, 2, 2)

        chip_x = r.left() + self.ACCENT_W + self.PAD
        chip_y = r.top() + (r.height() - self.CHIP_SIZE) // 2
        chip_r = QRect(chip_x, chip_y, self.CHIP_SIZE, self.CHIP_SIZE)
        chip_bg = QColor(badge_bg)
        chip_bg.setAlpha(40 if not selected else 60)
        painter.setBrush(QBrush(chip_bg))
        painter.drawRoundedRect(chip_r, 5, 5)

        px = qta.icon(icon_name, color=badge_bg).pixmap(13, 13)
        painter.drawPixmap(chip_x + (self.CHIP_SIZE - 13) // 2, chip_y + (self.CHIP_SIZE - 13) // 2, px)

        trash_x = r.right() - self.TRASH_SIZE - self.PAD
        trash_y = r.top() + (r.height() - self.TRASH_SIZE) // 2
        trash_r = QRect(trash_x, trash_y, self.TRASH_SIZE, self.TRASH_SIZE)

        index.model().setData(index, trash_r, Qt.UserRole + 1)

        if hovered or selected:
            painter.setBrush(QBrush(QColor("#FEE2E2")))
            painter.drawRoundedRect(trash_r, 4, 4)

        trash_px = qta.icon(
            "fa5s.trash-alt",
            color="#EF4444" if (hovered or selected) else "#CBD5E1",
        ).pixmap(11, 11)
        painter.drawPixmap(trash_x + (self.TRASH_SIZE - 11) // 2, trash_y + (self.TRASH_SIZE - 11) // 2, trash_px)

        text_x = chip_x + self.CHIP_SIZE + self.PAD
        text_w = trash_x - text_x - self.PAD

        display_type = name
        display_value = ''
        if ': ' in name:
            parts = name.split(': ', 1)
            display_type  = parts[0].strip()
            display_value = parts[1].strip()
        type_font = QFont(); type_font.setPointSize(9); type_font.setWeight(QFont.DemiBold)
        painter.setFont(type_font)
        painter.setPen(QColor('#1E293B') if selected else QColor('#334155'))
        if display_value:
            type_fm = QFontMetrics(type_font)
            painter.drawText(
                QRect(text_x, r.top() + 3, text_w, r.height() // 2),
                Qt.AlignLeft | Qt.AlignBottom,
                type_fm.elidedText(display_type, Qt.ElideRight, text_w),
            )
            value_font = QFont(); value_font.setPointSize(8)
            painter.setFont(value_font)
            painter.setPen(QColor('#94A3B8'))
            value_fm = QFontMetrics(value_font)
            painter.drawText(
                QRect(text_x, r.top() + r.height() // 2, text_w, r.height() // 2 - 3),
                Qt.AlignLeft | Qt.AlignTop,
                value_fm.elidedText(display_value, Qt.ElideRight, text_w),
            )
        else:
            type_fm = QFontMetrics(type_font)
            painter.drawText(
                QRect(text_x, r.top(), text_w, r.height()),
                Qt.AlignLeft | Qt.AlignVCenter,
                type_fm.elidedText(display_type, Qt.ElideRight, text_w),
            )

        if selected:
            painter.setPen(QPen(QColor('#6366F1'), 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, 6, 6)
        painter.restore()

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.MouseButtonRelease:
            trash_rect = index.data(Qt.UserRole + 1)
            if trash_rect and trash_rect.contains(event.pos()):
                lw = self.parent()
                if hasattr(lw, 'delete_item_requested'):
                    lw.delete_item_requested.emit(index.row())
                return True
        return super().editorEvent(event, model, option, index)


class DeleteSignalList(QListWidget):
    delete_item_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)

    def dropEvent(self, event):
        super().dropEvent(event)
        p = self.parent()
        while p:
            if isinstance(p, BarcodeEditorPage):
                p.sync_z_order_from_list()
                p.update_component_list()
                break
            p = p.parent()


# ── Grid scene ────────────────────────────────────────────────────────────────

class GridGraphicsScene(QGraphicsScene):
    def __init__(self, rect, grid_size=20, color=QColor("#E2E8F0"), parent=None):
        super().__init__(rect, parent)
        self.grid_size  = grid_size
        self.grid_color = color

    def drawBackground(self, painter, rect):
        super().drawBackground(painter, rect)
        sr = self.sceneRect()

        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawRect(sr)

        painter.setPen(QPen(self.grid_color, 1))

        left = int(sr.left()) - (int(sr.left()) % self.grid_size)
        top  = int(sr.top())  - (int(sr.top())  % self.grid_size)

        x = left
        while x < sr.right():
            painter.drawLine(QPointF(x, sr.top()), QPointF(x, sr.bottom()))
            x += self.grid_size

        y = top
        while y < sr.bottom():
            painter.drawLine(QPointF(sr.left(), y), QPointF(sr.right(), y))
            y += self.grid_size

        painter.setPen(QPen(QColor("#94A3B8"), 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(sr)


# ── Main page ─────────────────────────────────────────────────────────────────

class BarcodeEditorPage(QWidget):
    design_saved  = Signal(dict)
    _pending_code: str = ""
    _COUNTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bc_counter.json")

    @classmethod
    def _load_counter(cls) -> int:
        try:
            with open(cls._COUNTER_FILE) as f:
                return int(_json.load(f).get("counter", 0))
        except Exception:
            return 0

    @classmethod
    def _save_counter(cls, value: int, pending: str = ""):
        try:
            with open(cls._COUNTER_FILE, "w") as f:
                _json.dump({"counter": value, "pending": pending}, f)
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
                with open(cls._COUNTER_FILE) as f:
                    cls._pending_code = _json.load(f).get("pending", "")
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
        cls._save_counter(cls._load_counter(), "")
        return code

    def __init__(self):
        super().__init__()
        self._canvas_w     = 600
        self._canvas_h     = 400
        self._design_code  = ""
        self._design_name  = ""
        self._sticker_name = ""
        self._h_in = self._w_in = 0.0
        self.init_ui()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        header_bar = QWidget()
        header_bar.setObjectName("headerBar")
        header_bar.setStyleSheet(
            "QWidget#headerBar { background: white; border-bottom: 1px solid #E2E8F0; }"
        )
        header_bar.setFixedHeight(56)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(24, 0, 24, 0)
        header_layout.setSpacing(0)

        self._tab_btns: list[QPushButton] = []
        for i, label in enumerate(["GENERAL", "EDITOR"]):
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFixedHeight(56)
            btn.setStyleSheet(TAB_ACTIVE_STYLE if i == 0 else TAB_INACTIVE_STYLE)
            btn.clicked.connect(lambda checked=False, idx=i: self._switch_tab(idx))
            header_layout.addWidget(btn)
            self._tab_btns.append(btn)

        header_layout.addStretch()
        self.back_btn = StandardButton("Cancel", icon_name="fa5s.times", variant="secondary")
        self.back_btn.setToolTip("Cancel and return to list")
        self.back_btn.setFixedHeight(34)
        header_layout.addWidget(self.back_btn)
        header_layout.addSpacing(8)
        self.save_btn = StandardButton("Save Design", icon_name="fa5s.save", variant="primary")
        self.save_btn.setFixedHeight(34)
        header_layout.addWidget(self.save_btn)
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
        toolbar = QHBoxLayout(); toolbar.setSpacing(6)
        for btn in (self.btn_add_text, self.btn_add_rect, self.btn_add_line, self.btn_add_code):
            toolbar.addWidget(btn)
        toolbar.addStretch()

        self._zoom_level = 1.0
        self.zoom_label = QLabel("100%")
        self.zoom_label.setFixedWidth(44)
        self.zoom_label.setAlignment(Qt.AlignCenter)
        self.zoom_label.setStyleSheet(
            "font-size:11px; color:#94A3B8; font-weight:500; background:transparent;"
        )
        self.zoom_label.setToolTip("Ctrl + Scroll to zoom")
        toolbar.addWidget(self.zoom_label)

        editor_layout.addLayout(toolbar)
        editor_layout.addSpacing(18)

        workspace = QHBoxLayout()

        self.scene = GridGraphicsScene(
            QRectF(0, 0, self._canvas_w, self._canvas_h),
            grid_size=20, color=QColor("#E2E8F0"),
        )
        self.scene.setBackgroundBrush(QBrush(QColor(COLORS["canvas_bg"])))

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setStyleSheet("background: #E8EDF3; border: 1px solid #CBD5E1; border-radius: 8px;")
        self.view.setAlignment(Qt.AlignCenter)
        self.view.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.view.horizontalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.view.wheelEvent = self._view_wheel_event

        self._canvas_placeholder = QFrame()
        self._canvas_placeholder.setStyleSheet(
            "QFrame { background: #F8FAFC; border: 2px dashed #CBD5E1; border-radius: 8px; }"
        )
        ph_layout = QVBoxLayout(self._canvas_placeholder)
        ph_layout.setAlignment(Qt.AlignCenter)
        ph_icon = QLabel()
        ph_icon.setPixmap(qta.icon("fa5s.image", color="#CBD5E1").pixmap(40, 40))
        ph_icon.setAlignment(Qt.AlignCenter)
        ph_text = QLabel("Please select a sticker first\nfrom the General tab to enable the canvas.")
        ph_text.setAlignment(Qt.AlignCenter)
        ph_text.setStyleSheet("color: #94A3B8; font-size: 12px; background: transparent; border: none;")
        ph_layout.addWidget(ph_icon)
        ph_layout.addSpacing(8)
        ph_layout.addWidget(ph_text)
        workspace.addWidget(self.view, stretch=3)
        workspace.addWidget(self._canvas_placeholder, stretch=3)
        self.view.setVisible(False)
        self._canvas_placeholder.setVisible(True)

        # ── Sidebar ───────────────────────────────────────────────────────────
        self.sidebar = QFrame()
        self.sidebar.setMinimumWidth(280)
        self.sidebar.setStyleSheet(
            f"QFrame {{ background: {COLORS['white']}; border: 1px solid {COLORS['border']}; border-radius: 12px; }}"
        )
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)
        sidebar_layout.setSpacing(10)

        comp_header = QWidget(); comp_header.setStyleSheet("background: transparent; border: none;")
        ch_layout = QHBoxLayout(comp_header); ch_layout.setContentsMargins(2, 4, 2, 4)
        comp_icon = QLabel(); comp_icon.setPixmap(qta.icon("fa5s.layer-group", color="#6366F1").pixmap(13, 13))
        ch_layout.addWidget(comp_icon)
        ch_layout.addWidget(QLabel("COMPONENTS", styleSheet="font-weight:800;font-size:9pt;color:#1E293B;letter-spacing:1px;"))
        ch_layout.addStretch()
        self.comp_count_badge = QLabel("0")
        self.comp_count_badge.setAlignment(Qt.AlignCenter)
        self.comp_count_badge.setFixedSize(20, 20)
        self.comp_count_badge.setStyleSheet("background:#6366F1;color:white;border-radius:10px;font-weight:700;")
        ch_layout.addWidget(self.comp_count_badge)
        sidebar_layout.addWidget(comp_header)

        self.component_list = DeleteSignalList()
        self.component_list.setSpacing(2)
        self.component_list.setMouseTracking(True)
        self.component_list.viewport().setMouseTracking(True)
        self.component_list.setSelectionMode(QListWidget.SingleSelection)
        self.component_list.setFocusPolicy(Qt.NoFocus)
        self.component_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.component_list.setStyleSheet(
            f"QListWidget {{ border: none; background: transparent; outline: none; }}\n{MODERN_SCROLLBAR_STYLE}"
        )
        self.component_list.setItemDelegate(ComponentItemDelegate(self.component_list))
        self.component_list.delete_item_requested.connect(self.delete_component)
        self.component_list.itemClicked.connect(self.sync_selection_from_list)

        prop_panel = QWidget()
        prop_panel.setStyleSheet("background: transparent; border: none;")
        prop_panel_layout = QVBoxLayout(prop_panel)
        prop_panel_layout.setContentsMargins(0, 0, 0, 0)
        prop_panel_layout.setSpacing(4)

        prop_header = QWidget()
        prop_header.setStyleSheet("QWidget { background: transparent; border: none; padding: 2px 0px; }")
        ph2_layout = QHBoxLayout(prop_header)
        ph2_layout.setContentsMargins(8, 6, 8, 6)
        ph2_layout.setSpacing(4)
        prop_icon = QLabel(); prop_icon.setPixmap(qta.icon("fa5s.sliders-h", color="#6366F1").pixmap(14, 14))
        ph2_layout.addWidget(prop_icon)
        ph2_layout.addWidget(QLabel("PROPERTIES", styleSheet="font-weight:700;font-size:9pt;color:#64748B;letter-spacing:0.5px;background:transparent;padding:0px;"))
        ph2_layout.addWidget(QLabel("—", styleSheet="color:#CBD5E1;font-weight:400;background:transparent;padding:0px 2px;"))
        self.prop_name_input = QLineEdit("")
        self.prop_name_input.setPlaceholderText("select component")
        self.prop_name_input.setFixedHeight(24)
        self.prop_name_input.setStyleSheet("""
            QLineEdit { font-weight:700;font-size:9pt;color:#1E293B;letter-spacing:0.3px;background:#EEF2FF;border:none;border-radius:4px;padding:2px 8px; }
            QLineEdit:focus { border:none; background:#E0E7FF; }
            QLineEdit:disabled { background:#F1F5F9; color:#94A3B8; border:none; border-radius:4px; }
        """)
        self.prop_name_input.textChanged.connect(self.update_current_component_name)
        ph2_layout.addWidget(self.prop_name_input, stretch=1)
        prop_panel_layout.addWidget(prop_header)

        self.scroll_area = ConstrainedScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            f"QScrollArea {{ background: {COLORS['canvas_bg']}; border-radius: 8px; border: none; }}\n{MODERN_SCROLLBAR_STYLE}"
        )
        self.scroll_area.verticalScrollBar().setStyleSheet(MODERN_SCROLLBAR_STYLE)
        self.inspector_widget = QWidget()
        self.inspector_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.inspector_layout = QVBoxLayout(self.inspector_widget)
        self.inspector_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.inspector_widget)
        prop_panel_layout.addWidget(self.scroll_area)

        splitter = QSplitter(Qt.Vertical)
        splitter.setHandleWidth(8)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #E2E8F0;
                border-top: 1px solid #CBD5E1;
                border-bottom: 1px solid #CBD5E1;
            }
            QSplitter::handle:hover { background: #C7D2FE; }
            QSplitter::handle:pressed { background: #A5B4FC; }
        """)
        splitter.addWidget(self.component_list)
        splitter.addWidget(prop_panel)
        splitter.setSizes([200, 300])
        splitter.setChildrenCollapsible(False)

        sidebar_layout.addWidget(splitter, stretch=1)

        workspace.addWidget(self.sidebar, stretch=1)
        editor_layout.addLayout(workspace)
        self._tab_stack.addWidget(editor_page)
        self.main_layout.addWidget(self._tab_stack)

        self.general_tab.stickerChanged.connect(self._on_sticker_canvas_resize)
        self.btn_add_text.clicked.connect(lambda: self.add_element("text"))
        self.btn_add_rect.clicked.connect(lambda: self.add_element("rect"))
        self.btn_add_line.clicked.connect(lambda: self.add_element("line"))
        self.btn_add_code.clicked.connect(lambda: self.add_element("barcode"))
        self.save_btn.clicked.connect(self._on_save_clicked)

        self.scene.selectionChanged.connect(self.on_selection_changed)

        self._clipboard_item = None
        self._setup_shortcuts()
        self.setFocusPolicy(Qt.StrongFocus)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self._switch_tab(0)

    def _setup_shortcuts(self):
        for seq, slot in (
            ("Ctrl+C", self._copy_selected),
            ("Ctrl+V", self._paste_clipboard),
            ("Ctrl+D", self._duplicate_selected),
        ):
            sc = QShortcut(QKeySequence(seq), self)
            sc.setContext(Qt.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)

    def keyPressEvent(self, event):
        if (event.key() == Qt.Key_Delete
                and self.view.isVisible()
                and self._tab_stack.currentIndex() == 1
                and self.scene.selectedItems()):
            self._delete_selected_item()
            event.accept()
            return
        super().keyPressEvent(event)

    def _switch_tab(self, index: int):
        self._tab_stack.setCurrentIndex(index)
        for i, btn in enumerate(self._tab_btns):
            btn.setStyleSheet(TAB_ACTIVE_STYLE if i == index else TAB_INACTIVE_STYLE)

    def _on_sticker_canvas_resize(self, w_px: int, h_px: int):
        if w_px <= 0 or h_px <= 0:
            return
        self._canvas_w, self._canvas_h = w_px, h_px
        self.scene.setSceneRect(QRectF(0, 0, w_px, h_px))
        self._sticker_name = self.general_tab.sticker_combo.currentText()
        self.view.setVisible(True)
        self._canvas_placeholder.setVisible(False)
        self._update_toolbar_buttons_state(True)

    def _update_toolbar_buttons_state(self, enabled: bool):
        for btn in (self.btn_add_text, self.btn_add_rect, self.btn_add_line, self.btn_add_code):
            btn.setEnabled(enabled)
            btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ForbiddenCursor)

    def reset_for_new(self, form_data: dict | None = None):
        SameWithRegistry.clear()
        self.scene.clearSelection()
        for item in list(self.scene.items()):
            self.scene.removeItem(item)
        self.component_list.clear()
        self.comp_count_badge.setText("0")
        self.prop_name_input.setText("")
        self.prop_name_input.setEnabled(False)
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.view.setVisible(False)
        self._canvas_placeholder.setVisible(True)
        self._update_toolbar_buttons_state(False)

        w, h = 600, 400
        if form_data:
            w = int(form_data.get("w_px") or 600)
            h = int(form_data.get("h_px") or 400)
            pk = form_data.get("pk", "")
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
            self._design_code  = self._reserve_code()
            self._original_pk  = self._design_code
            self._design_name  = ""
            self._sticker_name = ""
            self._h_in = self._w_in = 0.0
            self._dp_fg = 1
            self.general_tab.status_combo._current = "DISPLAY"
            self.general_tab.status_combo._label.setText("DISPLAY")

        self._canvas_w, self._canvas_h = w, h
        self.scene.setSceneRect(QRectF(0, 0, w, h))
        self._update_design_subtitle()
        self.general_tab.sync_from_design(
            code=self._design_code, name=self._design_name,
            sticker_name=self._sticker_name, h_in=self._h_in, w_in=self._w_in,
            h_px=h if self._sticker_name else 0,
            w_px=w if self._sticker_name else 0,
            dp_fg=self._dp_fg,
        )
        self.general_tab.code_input.setText(self._design_code)
        self._switch_tab(0)

    def load_design(self, row_data: tuple, row_dict: dict | None):
        real_pk = str(row_dict.get("pk", "")) if row_dict else (str(row_data[0]) if row_data else "")
        stub = {"pk": real_pk, "name": "", "sticker_name": "", "h_in": 0.0,
                "w_in": 0.0, "h_px": 0, "w_px": 0, "dp_fg": 0}
        self.reset_for_new(stub)
        if row_dict:
            sticker_name = str(row_dict.get("sticker_name") or "").strip()
            w    = int(row_dict.get("w_px") or self._canvas_w)
            h    = int(row_dict.get("h_px") or self._canvas_h)
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
            self._h_in = h_in; self._w_in = w_in; self._dp_fg = dp_fg
            usrm = row_dict.get("usrm") or row_dict.get("bsusrm") or ""
            if usrm:
                try:
                    self.deserialize_canvas(_json.loads(usrm))
                except Exception as e:
                    print(f"[load_design] deserialize error: {e}")
            itrm = row_dict.get("itrm") or row_dict.get("bsitrm") or ""
            if itrm:
                try:
                    meta = _json.loads(itrm)
                    cw = int(meta.get("canvas_w", w)); ch = int(meta.get("canvas_h", h))
                    if cw != w or ch != h:
                        self._canvas_w, self._canvas_h = cw, ch
                        self.scene.setSceneRect(QRectF(0, 0, cw, ch))
                except Exception as e:
                    print(f"[load_design] itrm meta error: {e}")
        else:
            self._design_code  = str(row_data[0]) if row_data else ""
            self._original_pk  = self._design_code
            self._design_name  = str(row_data[1]) if row_data and len(row_data) > 1 else ""
            self._sticker_name = ""
            self._h_in = self._w_in = 0.0; self._dp_fg = 1

        self._update_design_subtitle()
        self.general_tab.sync_from_design(
            code=self._design_code, name=self._design_name,
            sticker_name=self._sticker_name, h_in=self._h_in, w_in=self._w_in,
            h_px=self._canvas_h, w_px=self._canvas_w, dp_fg=self._dp_fg,
        )
        self._switch_tab(0)
        if self._sticker_name:
            self.view.setVisible(True); self._canvas_placeholder.setVisible(False)
            self._update_toolbar_buttons_state(True)
        else:
            self.view.setVisible(False); self._canvas_placeholder.setVisible(True)
            self._update_toolbar_buttons_state(False)

    # ── Serialization ─────────────────────────────────────────────────────────

    def serialize_canvas(self) -> list[dict]:
        return [
            d for item in self.scene.items()
            if not item.group()
            for d in [self._serialize_item(item)] if d
        ]

    def _serialize_item(self, item) -> dict | None:
        base = {
            "x": round(item.pos().x(), 2), "y": round(item.pos().y(), 2),
            "z": item.zValue(), "visible": getattr(item, "design_visible", True),
            "rotation": item.rotation(), "name": getattr(item, "component_name", ""),
            "aabb_x": round(item.mapToScene(item.boundingRect()).boundingRect().left(), 2),
            "aabb_y": round(item.mapToScene(item.boundingRect()).boundingRect().top(), 2),
        }
        if isinstance(item, BarcodeItem):
            base.update({
                "type":             "barcode",
                "design":           item.design,
                "container_width":  item.container_width,
                "container_height": item.container_height,
                "design_height_cm":      getattr(item, "design_height_cm",      1.0),
                "design_magnification":  getattr(item, "design_magnification",  "1"),
                "design_ratio":          getattr(item, "design_ratio",          "2"),
                "design_check_digit":    getattr(item, "design_check_digit",    "-- NONE --"),
                "design_interpretation": getattr(item, "design_interpretation", "NO INTERPRETATION"),
                "design_type":           getattr(item, "design_type",           "FIX"),
                "design_editor":         getattr(item, "design_editor",         "INVISIBLE"),
                "design_text":           getattr(item, "design_text",           ""),
                "design_caption":        getattr(item, "design_caption",        ""),
                "design_group":          getattr(item, "design_group",          ""),
                "design_table":          getattr(item, "design_table",          ""),
                "design_field":          getattr(item, "design_field",          ""),
                "design_result":         getattr(item, "design_result",         ""),
                "design_format":         getattr(item, "design_format",         ""),
                "design_save_field":     getattr(item, "design_save_field",     "-- NOT SAVE --"),
                "design_column":         getattr(item, "design_column",         1),
            })
            return base
        if isinstance(item, QGraphicsTextItem):
            font = item.font()
            base.update({
                "type": "text", "text": item.toPlainText(),
                "font_size": font.pointSize(), "font_family": font.family(),
                "bold": font.bold(), "italic": font.italic(),
                "color": item._original_color.name() if hasattr(item, "_original_color") else item.defaultTextColor().name(),
                "component_id":        getattr(item, "component_id",         ""),
                "inverse":             getattr(item, "design_inverse",       False),
                "design_same_with":    getattr(item, "design_same_with",     ""),
                "design_link":         getattr(item, "design_link",          ""),
                "design_group":        getattr(item, "design_group",         ""),
                "design_table":        getattr(item, "design_table",         ""),
                "design_query":        getattr(item, "design_query",         ""),
                "design_field":        getattr(item, "design_field",         ""),
                "design_result":       getattr(item, "design_result",        ""),
                "design_type":         getattr(item, "design_type",          "FIX"),
                "design_system_value": getattr(item, "design_system_value",  "USER ID"),
                "design_system_extra": getattr(item, "design_system_extra",  ""),
                "design_merge":        getattr(item, "design_merge",         ""),
                "design_timbangan":    getattr(item, "design_timbangan",     ""),
                "design_weight":       getattr(item, "design_weight",        ""),
                "design_um":           getattr(item, "design_um",            ""),
                "design_alignment":    getattr(item, "design_alignment",     "LEFT JUSTIFY"),
                "design_editor":       getattr(item, "design_editor",        "ENABLED"),
                "design_data_type":    getattr(item, "design_data_type",     "STRING"),
                "design_max_length":   getattr(item, "design_max_length",    1),
                "design_save_field":   getattr(item, "design_save_field",    "-- NOT SAVE --"),
                "design_column":       getattr(item, "design_column",        1),
                "design_mandatory":    getattr(item, "design_mandatory",     "FALSE"),
                "design_format":       getattr(item, "design_format",        ""),
                "design_trim":         getattr(item, "design_trim",          False),
                "design_caption":      getattr(item, "design_caption",       ""),
                "design_wrap_text":    getattr(item, "design_wrap_text",     False),
                "design_wrap_width":   getattr(item, "design_wrap_width",    1),
            })
            return base
        if isinstance(item, QGraphicsLineItem):
            line = item.line(); pen = item.pen()
            base.update({"type": "line", "x2": round(line.x2(), 2),
                          "y2": round(line.y2(), 2), "thickness": pen.width()})
            return base
        if isinstance(item, QGraphicsRectItem):
            rect = item.rect(); pen = item.pen()
            base.update({"type": "rect", "width": round(rect.width(), 2),
                          "height": round(rect.height(), 2), "border_width": pen.width()})
            return base
        return None

    def deserialize_canvas(self, elements: list[dict]):
        flags = (QGraphicsItem.ItemIsMovable
                | QGraphicsItem.ItemIsSelectable
                | QGraphicsItem.ItemSendsGeometryChanges)
        for d in elements:
            kind = d.get("type")
            item = None
            if kind == "text":
                item = SelectableTextItem(d.get("text", ""))
                _init_text_item(item)
                font = QFont(d.get("font_family", "Arial"), d.get("font_size", 10))
                font.setBold(d.get("bold", False)); font.setItalic(d.get("italic", False))
                item.setFont(font)
                item.setDefaultTextColor(QColor(d.get("color", "#000000")))

                saved_id = d.get("component_id", "")
                item.component_id = saved_id if saved_id else str(uuid.uuid4())

                for attr in ("inverse", "design_same_with", "design_link", "design_group",
                            "design_table", "design_query", "design_field", "design_result",
                            "design_type", "design_system_value", "design_system_extra",
                            "design_merge", "design_timbangan", "design_weight", "design_um",
                            "design_alignment", "design_editor", "design_data_type",
                            "design_save_field", "design_mandatory", "design_format",
                            "design_caption"):
                    key = attr.replace("design_", "") if attr.startswith("design_") else attr
                    setattr(item, attr, d.get(attr, d.get(key, "")))
                item.design_inverse     = d.get("inverse", False)
                item.design_type        = d.get("design_type", "FIX")
                item.design_max_length  = int(d.get("design_max_length", 1) or 1)
                item.design_column      = int(d.get("design_column", 1) or 1)
                item.design_trim        = bool(d.get("design_trim", False))
                item.design_wrap_text   = bool(d.get("design_wrap_text", False))
                item.design_wrap_width  = int(d.get("design_wrap_width", 1) or 1)
                item.component_name = d.get("name", "Text")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "line":
                item = SelectableLineItem(0, 0, d.get("x2", 100), d.get("y2", 0))
                item.setPen(QPen(Qt.black, d.get("thickness", 2)))
                item.component_name = d.get("name", "Line")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "rect":
                item = SelectableRectItem(0, 0, d.get("width", 100), d.get("height", 50))
                item.setPen(QPen(Qt.black, d.get("border_width", 2)))
                item.component_name = d.get("name", "Rectangle")
                setup_item_logic(item, self.update_pos_label); item.setFlags(flags)
            elif kind == "barcode":
                item = BarcodeItem(self.update_pos_label, design=d.get("design", "CODE128"))
                item.container_width  = d.get("container_width",  80)
                item.container_height = d.get("container_height", 80)
                item.component_name   = d.get("name", "Barcode")
                # ── FIXED: no more item.bg — resize via item.setRect ──────────
                item.setRect(item.container_width, item.container_height)
                for attr, default in _BARCODE_DEFAULTS.items():
                    setattr(item, attr, d.get(attr, default))
                item.design_column = int(item.design_column or 1)
            if item is None:
                continue
            item.setZValue(d.get("z", 0))
            item.design_visible = d.get("visible", True)
            item.setVisible(True)
            _rotation = d.get("rotation", 0)
            item.setRotation(_rotation)
            if _rotation != 0:
                br = item.boundingRect()
                item.setTransformOriginPoint(br.center())
            item.setPos(0, 0)
            _aabb0 = item.mapToScene(item.boundingRect()).boundingRect()
            _off_x = _aabb0.left()
            _off_y = _aabb0.top()
            _vis_x = d.get("aabb_x") if d.get("aabb_x") is not None else d.get("x", 0)
            _vis_y = d.get("aabb_y") if d.get("aabb_y") is not None else d.get("y", 0)
            item.setPos(_vis_x - _off_x, _vis_y - _off_y)
            self.scene.addItem(item)
            li = QListWidgetItem(self.get_component_display_name(item))
            li.graphics_item = item
            self.component_list.addItem(li)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.sync_z_order_from_list()
        self._rebuild_same_with_registry()

    def get_design_payload(self) -> dict:
        return {
            "usrm": _json.dumps(self.serialize_canvas(), separators=(",", ":")),
            "itrm": _json.dumps({"canvas_w": self._canvas_w, "canvas_h": self._canvas_h},
                                 separators=(",", ":")),
        }

    def _on_save_clicked(self):
        selected_sticker = self.general_tab.sticker_combo.currentText()
        self._sticker_name = selected_sticker if (selected_sticker and not selected_sticker.startswith("—")) else ""
        name_val = self.general_tab.name_input.text().strip()
        if self.__class__._pending_code and self._design_code == self.__class__._pending_code:
            self._consume_code()
        if name_val:
            self._design_name = name_val
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
        payload.update({
            "pk":           self._design_code,
            "original_pk":  getattr(self, "_original_pk", self._design_code),
            "name":         self._design_name,
            "dp_fg":        dp_fg,
            "sticker_name": self._sticker_name,
            "w_px":         self._canvas_w,
            "h_px":         self._canvas_h,
            "h_in":         h_in,
            "w_in":         w_in,
        })
        self.scene.clearSelection()
        for item in self.scene.items():
            if isinstance(item, SelectableTextItem) and not item.isSelected():
                item.setDefaultTextColor(item._original_color)
        self.scene.update()
        self.design_saved.emit(payload)

    def sync_z_order_from_list(self):
        count = self.component_list.count()
        for i in range(count):
            li = self.component_list.item(i)
            gi = getattr(li, 'graphics_item', None)
            if gi:
                gi.setZValue(count - i)

    def delete_component(self, row, confirmed=False):
        li = self.component_list.item(row)
        if not li:
            return
        if not confirmed:
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox(self)
            reply.setWindowTitle("Delete Component")
            reply.setText("Are you sure you want to delete this component?")
            reply.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
            reply.setDefaultButton(QMessageBox.Cancel)
            reply.setIcon(QMessageBox.Warning)
            if reply.exec() != QMessageBox.Yes:
                return
        gi = getattr(li, 'graphics_item', None)
        if gi:
            SameWithRegistry.unregister(gi)
        self.scene.blockSignals(True); self.component_list.blockSignals(True)
        if gi and gi.scene() == self.scene:
            self.scene.removeItem(gi)
        self.component_list.takeItem(row)
        self.scene.blockSignals(False); self.component_list.blockSignals(False)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.on_selection_changed()

    def _delete_selected_item(self):
        if not self.view.isVisible() or self._tab_stack.currentIndex() != 1:
            return
        selected = self.scene.selectedItems()
        if not selected:
            return
        item = selected[0]
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox(self)
        reply.setWindowTitle("Delete Component")
        reply.setText("Are you sure you want to delete this component?")
        reply.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        reply.setDefaultButton(QMessageBox.Cancel)
        reply.setIcon(QMessageBox.Warning)
        if reply.exec() != QMessageBox.Yes:
            return
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == item:
                self.delete_component(i, confirmed=True)
                break

    def get_component_display_name(self, item) -> str:
        name = getattr(item, 'component_name', '')
        if isinstance(item, BarcodeItem):
            return f"Barcode - {name or 'Barcode'}: {getattr(item, 'design', 'CODE128')}"
        if isinstance(item, QGraphicsTextItem):
            val = item.toPlainText()[:20] or "Empty"
            return f"Text - {name or 'Text'}: {val}"
        if isinstance(item, QGraphicsLineItem):
            return f"Line - {name or 'Line'}: {int(item.line().length())}px"
        if isinstance(item, QGraphicsRectItem):
            r = item.rect()
            return f"Rect - {name or 'Rect'}: {int(r.width())}x{int(r.height())}"
        return f"Item - {name or 'Item'}"

    def update_component_list(self):
        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            gi = getattr(li, 'graphics_item', None)
            if gi:
                li.setText(self.get_component_display_name(gi))
        existing = [
            getattr(self.component_list.item(i), 'graphics_item', None)
            for i in range(self.component_list.count())
        ]
        for item in self.scene.items():
            if item.group() or item.scene() != self.scene or item in existing:
                continue
            li = QListWidgetItem(self.get_component_display_name(item))
            li.graphics_item = item
            self.component_list.addItem(li)
        sel = self.scene.selectedItems()
        if sel:
            for i in range(self.component_list.count()):
                li = self.component_list.item(i)
                if getattr(li, 'graphics_item', None) == sel[0]:
                    self.component_list.setCurrentItem(li)
                    break
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.component_list.blockSignals(False)
        self._sync_same_with_items()

    def update_current_component_name(self, name: str):
        sel = self.scene.selectedItems()
        if not sel:
            return
        item = sel[0]
        item.component_name = name or "Unnamed"
        old_name = getattr(item, "_last_component_name", item.component_name)
        new_name = item.component_name
        item._last_component_name = new_name
        if old_name != new_name:
            self._propagate_name_rename(old_name, new_name)
        self.update_component_list()

    def _propagate_name_rename(self, old_name: str, new_name: str):
        NAME_ATTRS = ("design_timbangan", "design_weight", "design_um")
        for si in self.scene.items():
            for attr in NAME_ATTRS:
                if getattr(si, attr, "") == old_name:
                    setattr(si, attr, new_name)
            raw = getattr(si, "design_merge", "")
            if raw:
                parts = [
                    new_name if seg.strip() == old_name else seg.strip()
                    for seg in raw.split(",")
                ]
                setattr(si, "design_merge", ",".join(parts))

        editor = getattr(self, "current_editor", None)
        if editor is None or not isinstance(editor, TextPropertyEditor):
            return

        for combo in (editor.timbangan_combo, editor.weight_combo, editor.um_combo):
            combo._items = [new_name if x == old_name else x for x in combo._items]
            if getattr(combo, "_id_map", None):
                combo._id_map = {
                    (new_name if k == old_name else k): v
                    for k, v in combo._id_map.items()
                }
                combo._id_map_inv = {v: k for k, v in combo._id_map.items()}
            if getattr(combo, "_current", None) == old_name:
                combo._current = new_name
                combo._set_label_text(new_name)

        if isinstance(editor.merge_combo, MultiSelectCombo):
            mc = editor.merge_combo
            mc._items    = [new_name if x == old_name else x for x in mc._items]
            mc._selected = [new_name if x == old_name else x for x in mc._selected]
            for _refresh in ("_refresh_button_label", "_update_label",
                             "_refresh_label", "_update_display", "refresh"):
                fn = getattr(mc, _refresh, None)
                if callable(fn):
                    fn()
                    break

    def sync_selection_from_list(self, li):
        item = getattr(li, 'graphics_item', None)
        if item:
            self.scene.blockSignals(True)
            self.scene.clearSelection()
            item.setSelected(True)
            self.scene.blockSignals(False)
            self.on_selection_changed()

    def on_selection_changed(self):
        selected_items = self.scene.selectedItems()
        while self.inspector_layout.count():
            child = self.inspector_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not selected_items:
            self.component_list.clearSelection()
            self.prop_name_input.setText("")
            self.prop_name_input.setPlaceholderText("select component")
            self.prop_name_input.setEnabled(False)
            return
        selected = selected_items[0]
        current_name = getattr(selected, 'component_name', '')
        self.prop_name_input.blockSignals(True)
        if current_name:
            self.prop_name_input.setText(current_name)
        else:
            defaults = {BarcodeItem: "Barcode", QGraphicsTextItem: "Text",
                        QGraphicsLineItem: "Line", QGraphicsRectItem: "Rectangle"}
            self.prop_name_input.setText(
                next((v for k, v in defaults.items() if isinstance(selected, k)), "Item")
            )
        self.prop_name_input.setEnabled(True)
        self.prop_name_input.blockSignals(False)

        self.component_list.blockSignals(True)
        for i in range(self.component_list.count()):
            li = self.component_list.item(i)
            if getattr(li, 'graphics_item', None) == selected:
                self.component_list.setCurrentItem(li)
                break
        self.component_list.blockSignals(False)

        self._rebuild_same_with_registry()
        self.current_editor = None
        if isinstance(selected, BarcodeItem):
            self.current_editor = BarcodePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsTextItem):
            self.current_editor = TextPropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsLineItem):
            self.current_editor = LinePropertyEditor(selected, self.update_component_list)
        elif isinstance(selected, QGraphicsRectItem):
            self.current_editor = RectanglePropertyEditor(selected, self.update_component_list)
        if self.current_editor:
            self.inspector_layout.addWidget(self.current_editor)

    def add_element(self, kind: str):
        self.scene.clearSelection()
        flags = (QGraphicsItem.ItemIsMovable
                 | QGraphicsItem.ItemIsSelectable
                 | QGraphicsItem.ItemSendsGeometryChanges)
        if kind == "text":
            text_count = sum(
                1 for si in self.scene.items()
                if isinstance(si, QGraphicsTextItem) and not si.group()
            )
            _label = f"Label{text_count + 1}"
            item = SelectableTextItem(_label)
            _init_text_item(item)
            item.setFont(QFont("Arial", 10))
            item.component_name = _label
            for attr in ("design_same_with", "design_link", "design_group", "design_table",
                         "design_query", "design_field", "design_result", "design_merge",
                         "design_timbangan", "design_weight", "design_um",
                         "design_alignment", "design_editor", "design_data_type",
                         "design_save_field", "design_mandatory", "design_format"):
                setattr(item, attr, "")
            item.design_type         = "FIX"
            item.design_system_value = "USER ID"
            item.design_system_extra = ""
            item.design_max_length   = 1
            item.design_column       = 1
            item.design_trim         = False
            item.design_caption      = ""
            item.design_wrap_text    = False
            item.design_wrap_width   = 1
            setup_item_logic(item, self.update_pos_label)
        elif kind == "rect":
            rect_count = sum(
                1 for si in self.scene.items()
                if isinstance(si, QGraphicsRectItem) and not si.group()
            )
            _label = f"Rect{rect_count + 1}"
            item = SelectableRectItem(0, 0, 100, 50); item.setPen(QPen(Qt.black, 2))
            item.component_name = _label; setup_item_logic(item, self.update_pos_label)
        elif kind == "line":
            line_count = sum(
                1 for si in self.scene.items()
                if isinstance(si, QGraphicsLineItem) and not si.group()
            )
            _label = f"Line{line_count + 1}"
            item = SelectableLineItem(0, 0, 100, 0); item.setPen(QPen(Qt.black, 2))
            item.component_name = _label; setup_item_logic(item, self.update_pos_label)
        elif kind == "barcode":
            barcode_count = sum(
                1 for si in self.scene.items()
                if isinstance(si, BarcodeItem) and not si.group()
            )
            _label = f"Barcode{barcode_count + 1}"
            item = BarcodeItem(self.update_pos_label)
            item.component_name = _label
            _apply_barcode_defaults(item)
        if not isinstance(item, BarcodeItem):
            item.setFlags(flags)
        self.scene.addItem(item)
        li = QListWidgetItem(self.get_component_display_name(item))
        li.graphics_item = item
        self.component_list.addItem(li)
        self.comp_count_badge.setText(str(self.component_list.count()))
        item.setSelected(True)
        item.setPos(50, 50)
        self.sync_z_order_from_list()

    def _copy_selected(self):
        selected = self.scene.selectedItems()
        if selected:
            self._clipboard_item = self._serialize_item(selected[0])

    def _paste_clipboard(self):
        if not self._clipboard_item or not self._sticker_name:
            return
        data = self._clipboard_item.copy()
        offset = 20
        data['aabb_x'] = data.get('aabb_x', data.get('x', 0)) + offset
        data['aabb_y'] = data.get('aabb_y', data.get('y', 0)) + offset
        if data.get("type") == "text":
            data["component_id"] = str(uuid.uuid4())
        item = self._create_item_from_data(data)
        if not item:
            return
        self.scene.addItem(item)
        li = QListWidgetItem(self.get_component_display_name(item))
        li.graphics_item = item
        self.component_list.addItem(li)
        self.comp_count_badge.setText(str(self.component_list.count()))
        self.scene.clearSelection()
        item.setSelected(True)
        self.sync_z_order_from_list()

    def _duplicate_selected(self):
        self._copy_selected()
        self._paste_clipboard()

    def _create_item_from_data(self, data: dict):
        flags = (QGraphicsItem.ItemIsMovable
                 | QGraphicsItem.ItemIsSelectable
                 | QGraphicsItem.ItemSendsGeometryChanges)
        kind = data.get('type')
        item = None

        if kind == 'text':
            item = SelectableTextItem(data.get('text', ''))
            _init_text_item(item)
            font = QFont(data.get('font_family', 'Arial'), data.get('font_size', 10))
            font.setBold(data.get('bold', False))
            font.setItalic(data.get('italic', False))
            item.setFont(font)
            item.setDefaultTextColor(QColor(data.get('color', '#000000')))

            saved_id = data.get("component_id", "")
            item.component_id = saved_id if saved_id else str(uuid.uuid4())

            for attr in ("inverse", "design_same_with", "design_link", "design_group",
                         "design_table", "design_query", "design_field", "design_result",
                         "design_type", "design_system_value", "design_system_extra",
                         "design_merge", "design_timbangan", "design_weight", "design_um",
                         "design_alignment", "design_editor", "design_data_type",
                         "design_save_field", "design_mandatory", "design_format",
                         "design_caption"):
                key = attr.replace("design_", "") if attr.startswith("design_") else attr
                setattr(item, attr, data.get(attr, data.get(key, "")))

            item.design_inverse    = data.get("inverse", False)
            item.design_type       = data.get("design_type", "FIX")
            item.design_max_length = int(data.get("design_max_length", 1) or 1)
            item.design_column     = int(data.get("design_column", 1) or 1)
            item.design_trim       = bool(data.get("design_trim", False))
            item.design_wrap_text  = bool(data.get("design_wrap_text", False))
            item.design_wrap_width = int(data.get("design_wrap_width", 1) or 1)

            item.component_name = data.get('name', 'Text')
            setup_item_logic(item, self.update_pos_label)
            item.setFlags(flags)

        elif kind == 'line':
            item = SelectableLineItem(0, 0, data.get('x2', 100), data.get('y2', 0))
            item.setPen(QPen(Qt.black, data.get('thickness', 2)))
            item.component_name = data.get('name', 'Line')
            setup_item_logic(item, self.update_pos_label)
            item.setFlags(flags)

        elif kind == 'rect':
            item = SelectableRectItem(0, 0, data.get('width', 100), data.get('height', 50))
            item.setPen(QPen(Qt.black, data.get('border_width', 2)))
            item.component_name = data.get('name', 'Rectangle')
            setup_item_logic(item, self.update_pos_label)
            item.setFlags(flags)

        elif kind == 'barcode':
            item = BarcodeItem(self.update_pos_label, design=data.get('design', 'CODE128'))
            item.container_width  = data.get('container_width', 80)
            item.container_height = data.get('container_height', 80)
            # ── FIXED: no more item.bg — resize via item.setRect ──────────────
            item.setRect(item.container_width, item.container_height)
            for attr, default in _BARCODE_DEFAULTS.items():
                setattr(item, attr, data.get(attr, default))
            item.design_column  = int(item.design_column or 1)
            item.component_name = data.get('name', 'Barcode')

        if item is None:
            return None

        item.setZValue(data.get('z', 0))
        item.design_visible = data.get('visible', True)
        item.setVisible(True)
        rotation = data.get('rotation', 0)
        item.setRotation(rotation)
        if rotation != 0:
            br = item.boundingRect()
            item.setTransformOriginPoint(br.center())

        item.setPos(0, 0)
        aabb0  = item.mapToScene(item.boundingRect()).boundingRect()
        off_x  = aabb0.left()
        off_y  = aabb0.top()
        vis_x  = data.get('aabb_x', data.get('x', 0))
        vis_y  = data.get('aabb_y', data.get('y', 0))
        item.setPos(vis_x - off_x, vis_y - off_y)

        return item

    def _sync_same_with_items(self):
        id_to_item = {
            getattr(si, "component_id", ""): si
            for si in self.scene.items()
            if not si.group() and isinstance(si, SelectableTextItem)
            and getattr(si, "component_id", "")
        }
        name_to_item = {
            getattr(si, "component_name", ""): si
            for si in self.scene.items()
            if not si.group() and isinstance(si, SelectableTextItem)
            and getattr(si, "component_name", "")
        }
        for si in self.scene.items():
            if si.group() or not isinstance(si, SelectableTextItem):
                continue
            if getattr(si, "design_type", "") != "SAME WITH":
                continue
            ref = getattr(si, "design_same_with", "")
            source = id_to_item.get(ref) or name_to_item.get(ref)
            if not source or source is si:
                continue
            if getattr(source, "design_type", "") == "SAME WITH":
                si.design_same_with = ""; SameWithRegistry.unregister(si); continue
            SameWithRegistry.register(si, source)
            if si.toPlainText() != source.toPlainText(): si.setPlainText(source.toPlainText())
            if si.font() != source.font(): si.setFont(source.font())
            if si.defaultTextColor() != source.defaultTextColor(): si.setDefaultTextColor(source.defaultTextColor())
            si.design_inverse = getattr(source, "design_inverse", False)
            si.design_visible = getattr(source, "design_visible", True)

    def _rebuild_same_with_registry(self):
        id_to_item = {
            getattr(si, "component_id", ""): si
            for si in self.scene.items()
            if not si.group() and isinstance(si, SelectableTextItem)
            and getattr(si, "component_id", "")
        }
        name_to_item = {
            getattr(si, "component_name", ""): si
            for si in self.scene.items()
            if not si.group() and isinstance(si, SelectableTextItem)
            and getattr(si, "component_name", "")
        }
        for si in self.scene.items():
            if si.group() or not isinstance(si, SelectableTextItem):
                continue
            if getattr(si, "design_type", "") != "SAME WITH":
                continue
            ref = getattr(si, "design_same_with", "")
            source = id_to_item.get(ref) or name_to_item.get(ref)
            if source and source is not si and getattr(source, "design_type", "") != "SAME WITH":
                SameWithRegistry.register(si, source)

    def update_pos_label(self, pos):
        editor = getattr(self, "current_editor", None)
        if not editor:
            return
        if not shiboken6.isValid(editor):
            self.current_editor = None
            return
        if hasattr(editor, "update_position_fields"):
            editor.update_position_fields(pos)

    def _view_wheel_event(self, event):
        if event.modifiers() & Qt.ControlModifier:
            if event.angleDelta().y() > 0:
                self._zoom_in()
            else:
                self._zoom_out()
            event.accept()
        else:
            from PySide6.QtWidgets import QGraphicsView
            QGraphicsView.wheelEvent(self.view, event)

    def _zoom_in(self):
        self._zoom_level = min(round(self._zoom_level + 0.1, 2), 5.0)
        self._apply_zoom()

    def _zoom_out(self):
        self._zoom_level = max(round(self._zoom_level - 0.1, 2), 0.1)
        self._apply_zoom()

    def _zoom_fit(self):
        if not self.view.isVisible():
            return
        self.view.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)
        transform = self.view.transform()
        self._zoom_level = transform.m11()
        self._update_zoom_label()

    def _apply_zoom(self):
        self.view.resetTransform()
        self.view.scale(self._zoom_level, self._zoom_level)
        self._update_zoom_label()

    def _update_zoom_label(self):
        self.zoom_label.setText(f"{int(self._zoom_level * 100)}%")

    def _update_design_subtitle(self): pass