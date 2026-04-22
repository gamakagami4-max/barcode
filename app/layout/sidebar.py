import qtawesome as qta
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QWidget, QScrollArea, QGraphicsOpacityEffect,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, Signal

# --- Style Constants ---
STYLE_NORMAL = """
    QPushButton {
        text-align: left;
        padding: 9px 14px;
        border: none;
        color: #475569;
        font-size: 13px;
        background: transparent;
        outline: none;
        border-radius: 6px;
    }
    QPushButton:hover {
        color: #1E293B;
        background-color: #F1F5F9;
    }
"""

STYLE_ACTIVE = """
    QPushButton {
        text-align: left;
        padding: 9px 14px;
        border: none;
        color: #1E40AF;
        font-size: 13px;
        font-weight: 600;
        background-color: #EFF6FF;
        border-radius: 6px;
        outline: none;
    }
"""

ICON_BTN_STYLE = """
    QPushButton {{
        background: {bg};
        border: none;
        border-radius: 8px;
        outline: none;
    }}
    QPushButton:hover {{
        background-color: #E2E8F0;
    }}
"""


# ── Drag-resize handle ────────────────────────────────────────────────────────

class _ResizeHandle(QWidget):
    def __init__(self, target: "Sidebar", parent=None):
        super().__init__(parent)
        self._target = target
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_width = 0
        self.setFixedWidth(5)
        self.setCursor(Qt.SizeHorCursor)
        self.setStyleSheet("background: transparent;")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start_x = event.globalPosition().toPoint().x()
            self._drag_start_width = self._target.width()
            event.accept()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return
        delta = event.globalPosition().toPoint().x() - self._drag_start_x
        # Drag only widens — minimum is the default expanded width (270px)
        min_drag = self._target._default_expanded_width
        new_width = max(min_drag, min(self._drag_start_width + delta, 480))
        self._target.expanded_width = new_width
        self._target.setFixedWidth(new_width)
        event.accept()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        event.accept()

    def enterEvent(self, event):
        self.setStyleSheet("background: #A5B4FC; border-radius: 2px;")

    def leaveEvent(self, event):
        self.setStyleSheet("background: transparent;")


# ── Collapsible menu ──────────────────────────────────────────────────────────

class CollapsibleMenu(QWidget):
    def __init__(self, title, icon_name, sub_items_dict, sidebar_ref):
        super().__init__()
        self.sidebar_ref = sidebar_ref
        self.sub_buttons = []
        self.is_expanded = False
        self._icon_name = icon_name
        self._title = title

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("background: transparent;")
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(14, 10, 14, 10)

        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("background: transparent;")
        self.icon_label.setPixmap(qta.icon(icon_name, color="#475569").pixmap(QSize(18, 18)))

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-size: 13px; font-weight: 600; color: #1E293B; border: none; background: transparent;"
        )

        self.chevron_label = QLabel()
        self.chevron_label.setStyleSheet("background: transparent; border: none;")
        self._update_chevron()

        self.header_layout.addWidget(self.icon_label)
        self.header_layout.addSpacing(10)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.chevron_label)

        self.header_widget.setCursor(Qt.PointingHandCursor)
        self.header_widget.mousePressEvent = self.toggle_expansion
        self.header_widget.enterEvent = lambda e: self._on_hover(True)
        self.header_widget.leaveEvent = lambda e: self._on_hover(False)
        self.main_layout.addWidget(self.header_widget)

        # Sub-menu container
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container.setStyleSheet("QWidget { background: transparent; }")
        self.container_layout.setContentsMargins(28, 4, 0, 4)
        self.container_layout.setSpacing(1)

        for item_text, callback in sub_items_dict.items():
            sub_btn = QPushButton(item_text)
            sub_btn.setCursor(Qt.PointingHandCursor)
            sub_btn.setFocusPolicy(Qt.NoFocus)
            sub_btn.setStyleSheet(STYLE_NORMAL)
            sub_btn.clicked.connect(
                lambda chk=False, b=sub_btn, c=callback: self._on_sub_clicked(b, c)
            )
            self.sub_buttons.append(sub_btn)
            self.container_layout.addWidget(sub_btn)

        self.container.setVisible(False)
        self.container.setMaximumHeight(0)
        self.main_layout.addWidget(self.container)

    def _on_hover(self, entering):
        self.header_widget.setStyleSheet(
            "QWidget { background-color: #F1F5F9; border-radius: 6px; }"
            if entering else
            "QWidget { background: transparent; border-radius: 6px; }"
        )

    def _on_sub_clicked(self, button, callback):
        self.sidebar_ref.clear_all_selections()
        button.setStyleSheet(STYLE_ACTIVE)
        callback()

    def _update_chevron(self):
        code = "fa5s.chevron-down" if self.is_expanded else "fa5s.chevron-right"
        self.chevron_label.setPixmap(qta.icon(code, color="#94A3B8").pixmap(QSize(10, 10)))

    def toggle_expansion(self, event):
        if self.sidebar_ref.is_collapsed:
            self.sidebar_ref._apply_expanded_ui(animate=True)
            return
        self.is_expanded = not self.is_expanded
        self._update_chevron()
        if self.is_expanded:
            self.container.setVisible(True)
            target_h = self.container_layout.sizeHint().height()
            self._h_anim = QPropertyAnimation(self.container, b"maximumHeight")
            self._h_anim.setDuration(250)
            self._h_anim.setStartValue(0)
            self._h_anim.setEndValue(target_h)
            self._h_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._op_fx = QGraphicsOpacityEffect()
            self.container.setGraphicsEffect(self._op_fx)
            self._op_anim = QPropertyAnimation(self._op_fx, b"opacity")
            self._op_anim.setDuration(250)
            self._op_anim.setStartValue(0.0)
            self._op_anim.setEndValue(1.0)
            self._op_anim.setEasingCurve(QEasingCurve.OutCubic)
            self._h_anim.start()
            self._op_anim.start()
        else:
            self._h_anim = QPropertyAnimation(self.container, b"maximumHeight")
            self._h_anim.setDuration(200)
            self._h_anim.setStartValue(self.container.height())
            self._h_anim.setEndValue(0)
            self._h_anim.setEasingCurve(QEasingCurve.InCubic)
            if self.container.graphicsEffect():
                self._op_anim = QPropertyAnimation(self.container.graphicsEffect(), b"opacity")
                self._op_anim.setDuration(200)
                self._op_anim.setStartValue(1.0)
                self._op_anim.setEndValue(0.0)
                self._op_anim.setEasingCurve(QEasingCurve.InCubic)
                self._op_anim.start()
            self._h_anim.finished.connect(lambda: self.container.setVisible(False))
            self._h_anim.start()

    def close_submenu(self):
        if self.is_expanded:
            self.is_expanded = False
            self._update_chevron()
            self.container.setVisible(False)
            self.container.setMaximumHeight(0)


# ── Sidebar ───────────────────────────────────────────────────────────────────

class Sidebar(QFrame):
    collapsed_changed = Signal(bool)

    def __init__(self, nav_callback, current_user: dict | None = None, logout_callback=None):
        super().__init__()
        self.nav_callback = nav_callback
        self._current_user = current_user or {}
        self._logout_callback = logout_callback
        self.menus: list[CollapsibleMenu] = []
        self._icon_btns: list[QPushButton] = []
        self.is_collapsed = False
        self.expanded_width         = 270
        self._default_expanded_width = 190  # minimum for drag resize
        self.collapsed_width         = 56

        self.setFixedWidth(self.expanded_width)
        self.setStyleSheet("""
            QFrame {
                background-color: #E2E8F0;
                border-right: 1px solid #CBD5E1;
            }
        """)

        # Root: inner content + resize handle
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._inner = QWidget()
        self._inner.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._inner.setStyleSheet("background: transparent;")
        self.main_sidebar_layout = QVBoxLayout(self._inner)
        self.main_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.main_sidebar_layout.setSpacing(0)

        # ── Toggle button (always visible) ───────────────────────────────────
        toggle_row = QWidget()
        toggle_row.setStyleSheet("background: transparent;")
        tr_layout = QHBoxLayout(toggle_row)
        tr_layout.setContentsMargins(10, 14, 10, 14)
        tr_layout.setSpacing(0)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(qta.icon("fa5s.bars", color="#475569"))
        self.toggle_btn.setIconSize(QSize(18, 18))
        self.toggle_btn.setFixedSize(36, 36)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFocusPolicy(Qt.NoFocus)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none;
                border-radius: 8px; outline: none;
            }
            QPushButton:hover { background-color: #CBD5E1; }
        """)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        tr_layout.addWidget(self.toggle_btn, alignment=Qt.AlignLeft)
        self.main_sidebar_layout.addWidget(toggle_row)

        # ── Expanded content (scroll area) ────────────────────────────────────
        self._expanded_widget = QWidget()
        self._expanded_widget.setStyleSheet("background: transparent;")
        exp_vbox = QVBoxLayout(self._expanded_widget)
        exp_vbox.setContentsMargins(0, 0, 0, 0)
        exp_vbox.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; min-height: 30px; }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
        """)

        self.content_container = QWidget()
        self.content_container.setObjectName("content_container")
        self.content_container.setStyleSheet("#content_container { background: #E2E8F0; }")
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(14, 10, 14, 20)
        self.content_layout.setSpacing(3)
        self.scroll.setWidget(self.content_container)
        exp_vbox.addWidget(self.scroll)
        self.main_sidebar_layout.addWidget(self._expanded_widget)

        # ── Collapsed content (icon-only column) ──────────────────────────────
        self._collapsed_widget = QWidget()
        self._collapsed_widget.setStyleSheet("background: transparent;")
        self._collapsed_widget.setVisible(False)
        col_vbox = QVBoxLayout(self._collapsed_widget)
        col_vbox.setContentsMargins(8, 8, 8, 8)
        col_vbox.setSpacing(6)
        col_vbox.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self._col_vbox = col_vbox
        self.main_sidebar_layout.addWidget(self._collapsed_widget)

        # ── User panel ────────────────────────────────────────────────────────
        self.user_panel = self._make_user_panel()
        self.main_sidebar_layout.addWidget(self.user_panel)

        root.addWidget(self._inner)
        root.addWidget(_ResizeHandle(self))

        self._build_menus()

    # ── User panel ────────────────────────────────────────────────────────────

    def _make_user_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("user_panel")
        panel.setStyleSheet("""
            #user_panel { background-color: #E2E8F0; border-top: 1px solid #CBD5E1; }
        """)
        # We'll use a stacked approach: one QWidget for expanded, one for collapsed
        root_layout = QVBoxLayout(panel)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Expanded row (horizontal) ─────────────────────────────────────────
        self._user_expanded = QWidget()
        self._user_expanded.setStyleSheet("background:transparent;")
        exp_row = QHBoxLayout(self._user_expanded)
        exp_row.setContentsMargins(10, 12, 10, 12)
        exp_row.setSpacing(0)

        avatar_exp = self._make_avatar()
        display_name = self._current_user.get("description") or self._current_user.get("pk", "User")
        self._user_info = QLabel(
            f"{display_name}<br><span style='color:#6B7280;font-size:10px;'>"
            f"{self._current_user.get('pk', '')}</span>"
        )
        self._user_info.setTextFormat(Qt.RichText)
        self._user_info.setStyleSheet(
            "font-size:12px; font-weight:600; color:#111827; background:transparent; border:none;"
        )
        self._exit_btn = QPushButton()
        self._exit_btn.setIcon(qta.icon("fa5s.sign-out-alt", color="#9CA3AF"))
        self._exit_btn.setIconSize(QSize(16, 16))
        self._exit_btn.setFixedSize(28, 28)
        self._exit_btn.setCursor(Qt.PointingHandCursor)
        self._exit_btn.setFocusPolicy(Qt.NoFocus)
        self._exit_btn.setStyleSheet("""
            QPushButton { background:transparent; border:none; border-radius:6px; outline:none; }
            QPushButton:hover { background-color:#FEE2E2; }
        """)
        exp_row.addWidget(avatar_exp, alignment=Qt.AlignVCenter)
        exp_row.addSpacing(10)
        exp_row.addWidget(self._user_info)
        exp_row.addStretch()
        exp_row.addWidget(self._exit_btn)
        if self._logout_callback:
            self._exit_btn.clicked.connect(self._logout_callback)

        # ── Collapsed column (vertical, centered) ─────────────────────────────
        self._user_collapsed = QWidget()
        self._user_collapsed.setStyleSheet("background:transparent;")
        self._user_collapsed.setVisible(False)
        col_col = QVBoxLayout(self._user_collapsed)
        col_col.setContentsMargins(8, 10, 8, 10)
        col_col.setSpacing(6)
        col_col.setAlignment(Qt.AlignHCenter)

        avatar_col = self._make_avatar()
        exit_col = QPushButton()
        exit_col.setIcon(qta.icon("fa5s.sign-out-alt", color="#9CA3AF"))
        exit_col.setIconSize(QSize(14, 14))
        exit_col.setFixedSize(32, 32)
        exit_col.setCursor(Qt.PointingHandCursor)
        exit_col.setFocusPolicy(Qt.NoFocus)
        exit_col.setToolTip("Sign out")
        exit_col.setStyleSheet("""
            QPushButton { background:transparent; border:none; border-radius:6px; outline:none; }
            QPushButton:hover { background-color:#FEE2E2; }
        """)
        col_col.addWidget(avatar_col, alignment=Qt.AlignHCenter)
        col_col.addWidget(exit_col, alignment=Qt.AlignHCenter)
        if self._logout_callback:
            exit_col.clicked.connect(self._logout_callback)

        root_layout.addWidget(self._user_expanded)
        root_layout.addWidget(self._user_collapsed)
        return panel

    def _make_avatar(self) -> QWidget:
        avatar = QWidget()
        avatar.setFixedSize(36, 36)
        avatar.setStyleSheet(
            "background-color:#EFF6FF; border:2px solid #DBEAFE; border-radius:18px;"
        )
        av = QHBoxLayout(avatar)
        av.setContentsMargins(0, 0, 0, 0)
        av.setAlignment(Qt.AlignCenter)
        ic = QLabel()
        ic.setStyleSheet("background:transparent; border:none;")
        ic.setPixmap(qta.icon("fa5s.user", color="#2563EB").pixmap(QSize(16, 16)))
        av.addWidget(ic)
        return avatar

    # ── Build menus ───────────────────────────────────────────────────────────

    def _build_menus(self):
        # Title
        title_w = QWidget()
        title_w.setStyleSheet("background:transparent;")
        tl = QVBoxLayout(title_w)
        tl.setContentsMargins(12, 8, 12, 16)
        lbl = QLabel("Menu")
        lbl.setStyleSheet("font-size:17px; font-weight:700; color:#111827; background:transparent;")
        tl.addWidget(lbl)
        self.content_layout.addWidget(title_w)

        menu_defs = [
            ("File",    "fa5s.folder",   {"Dashboard": lambda: self.nav_callback(0)}),
            ("Master",  "fa5s.database", {
                "Source Data Group":   lambda: self.nav_callback(2),
                "Master Sticker":      lambda: self.nav_callback(3),
                "Master Filter Type":  lambda: self.nav_callback(4),
                "Master Brand":        lambda: self.nav_callback(5),
                "Master Product Type": lambda: self.nav_callback(6),
                "Master Item":         lambda: self.nav_callback(7),
                "Master Brand Case":   lambda: self.nav_callback(8),
            }),
            ("Barcode", "fa5s.barcode",  {
                "Barcode Design": lambda: self.nav_callback(9),
                "Barcode Print":  lambda: self.nav_callback(10), 
            }),
            
        ]

        for title, icon, items in menu_defs:
            self.content_layout.addSpacing(2)
            menu = CollapsibleMenu(title, icon, items, self)
            self.content_layout.addWidget(menu)
            self.menus.append(menu)

            # Collapsed icon button
            btn = QPushButton()
            btn.setIcon(qta.icon(icon, color="#475569"))
            btn.setIconSize(QSize(20, 20))
            btn.setFixedSize(40, 40)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setToolTip(title)
            btn.setStyleSheet(ICON_BTN_STYLE.format(bg="transparent"))
            btn.clicked.connect(
                lambda chk=False, m=menu: self._on_collapsed_icon_click(m)
            )
            self._col_vbox.addWidget(btn, alignment=Qt.AlignHCenter)
            self._icon_btns.append(btn)

        self.content_layout.addStretch()
        self._col_vbox.addStretch()

    def _on_collapsed_icon_click(self, menu: CollapsibleMenu):
        self._apply_expanded_ui(animate=True)
        if not menu.is_expanded:
            menu.toggle_expansion(None)

    # ── Expand / collapse ─────────────────────────────────────────────────────

    def _apply_expanded_ui(self, animate=False, set_width=True):
        self.is_collapsed = False
        self.toggle_btn.setIcon(qta.icon("fa5s.bars", color="#475569"))
        self._collapsed_widget.setVisible(False)
        self._expanded_widget.setVisible(True)
        self._user_expanded.setVisible(True)
        self._user_collapsed.setVisible(False)
        if set_width:
            if animate:
                self._animate_width(self.expanded_width)
            else:
                self.setFixedWidth(self.expanded_width)
        self.collapsed_changed.emit(False)

    def _apply_collapsed_ui(self, animate=False):
        self.is_collapsed = True
        self.toggle_btn.setIcon(qta.icon("fa5s.chevron-right", color="#475569"))
        self._expanded_widget.setVisible(False)
        self._collapsed_widget.setVisible(True)
        self._user_expanded.setVisible(False)
        self._user_collapsed.setVisible(True)
        for m in self.menus:
            m.close_submenu()
        if animate:
            self._animate_width(self.collapsed_width)
        else:
            self.setFixedWidth(self.collapsed_width)
        self.collapsed_changed.emit(True)

    def toggle_sidebar(self):
        if self.is_collapsed:
            self._apply_expanded_ui(animate=True)
        else:
            self._apply_collapsed_ui(animate=True)

    def _animate_width(self, target: int):
        # Reset constraints so animation isn't blocked by a previous min/max
        self.setMinimumWidth(0)
        self.setMaximumWidth(16777215)
        for prop in (b"minimumWidth", b"maximumWidth"):
            anim = QPropertyAnimation(self, prop)
            anim.setDuration(280)
            anim.setStartValue(self.width())
            anim.setEndValue(target)
            anim.setEasingCurve(QEasingCurve.InOutCubic)
            anim.start()
            setattr(self, f"_anim_{prop.decode()}", anim)  # keep reference

    # ── Selection ─────────────────────────────────────────────────────────────

    def clear_all_selections(self):
        for menu in self.menus:
            for btn in menu.sub_buttons:
                btn.setStyleSheet(STYLE_NORMAL)
        for btn in self._icon_btns:
            btn.setStyleSheet(ICON_BTN_STYLE.format(bg="transparent"))

    def set_active(self, page_id: int):
        self.clear_all_selections()
        mapping = {
            0: ("Dashboard",        0),
            2: ("Source Data Group",1),
            3: ("Master Sticker",   1),
            4: ("Master Filter Type",1),
            5: ("Master Brand",     1),
            6: ("Master Product Type",1),
            7: ("Master Item",      1),
            8: ("Master Brand Case",1),
            9: ("Barcode Design",   2),
            10: ("Barcode Print",   2)
        }
        entry = mapping.get(page_id)
        if not entry:
            return
        target_text, menu_idx = entry
        if menu_idx < len(self._icon_btns):
            self._icon_btns[menu_idx].setStyleSheet(
                ICON_BTN_STYLE.format(bg="#EFF6FF")
            )
        for menu in self.menus:
            for btn in menu.sub_buttons:
                if btn.text() == target_text:
                    btn.setStyleSheet(STYLE_ACTIVE)
                    if not menu.is_expanded and not self.is_collapsed:
                        menu.toggle_expansion(None)
                    return

    def create_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "font-size:10px; color:#9CA3AF; font-weight:700; "
            "letter-spacing:0.8px; padding:6px 12px 4px 12px; background:transparent;"
        )
        return lbl