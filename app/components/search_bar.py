import qtawesome as qta
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QLabel,
    QLineEdit, QFrame, QPushButton,
    QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtCore import QEvent

# Animation
FILTER_PANEL_ANIM_DURATION = 200
FILTER_OPTION_HEIGHT = 36
DROPDOWN_WIDTH = 200

# Minimal palette
_BG = "#FFFFFF"
_BG_SUBTLE = "#FAFAFA"
_BORDER = "#E5E7EB"
_TEXT = "#18181B"
_TEXT_MUTED = "#71717A"
_ACCENT = "#3B82F6"
_ACCENT_BG = "#EFF6FF"


class FilterTriggerButton(QFrame):
    """Clickable filter trigger showing current selection and chevron."""
    clicked = Signal()

    def __init__(self, label: str, current: str, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._label = label
        self._current = current
        self._is_open = False
        self._build_ui()

    def _build_ui(self):
        self.setFixedHeight(36)
        self.setFixedWidth(DROPDOWN_WIDTH)
        self.setStyleSheet(f"""
            FilterTriggerButton {{
                background: {_BG};
                border: 1px solid {_BORDER};
                border-radius: 6px;
            }}
            FilterTriggerButton:hover {{
                border-color: #D4D4D8;
            }}
        """)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 8, 0)
        layout.setSpacing(6)

        self._current_lbl = QLabel(self._current)
        self._current_lbl.setStyleSheet(
            f"color: {_TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        self._current_lbl.setMinimumWidth(1)
        self._chevron_lbl = QLabel()
        self._chevron_lbl.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._chevron_lbl.setStyleSheet("background: transparent; border: none;")
        self._update_chevron()

        layout.addWidget(self._current_lbl, 1)
        layout.addWidget(self._chevron_lbl, 0)

    def _update_chevron(self):
        icon = "fa5s.chevron-up" if self._is_open else "fa5s.chevron-down"
        self._chevron_lbl.setPixmap(qta.icon(icon, color=_TEXT_MUTED).pixmap(10, 10))

    def set_current(self, text: str):
        self._current = text
        self._current_lbl.setText(text)

    def set_open(self, open: bool):
        self._is_open = open
        self._update_chevron()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AnimatedFilterPanel(QFrame):
    """Panel that slides down to show filter options."""

    def __init__(self, options: list[str], selected: str, parent=None):
        super().__init__(parent)
        self._options = options
        self._selected = selected
        self._height_anim = None
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0.0)
        self.setMaximumHeight(0)
        self.setMinimumHeight(0)
        self.setFixedWidth(DROPDOWN_WIDTH)
        self.setStyleSheet(f"""
            AnimatedFilterPanel {{
                background: {_BG};
                border: 1px solid {_BORDER};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        self._build_options()

    def get_target_height(self):
        return min(16 + len(self._options) * (FILTER_OPTION_HEIGHT + 2), 260)

    def _build_options(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 6)
        layout.setSpacing(2)
        self._buttons = []
        for opt in self._options:
            btn = QPushButton(opt)
            btn.setFixedHeight(FILTER_OPTION_HEIGHT)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked=False, o=opt: self._on_option_clicked(o))
            self._style_button(btn, opt == self._selected)
            layout.addWidget(btn)
            self._buttons.append(btn)

    def _style_button(self, btn: QPushButton, selected: bool):
        if selected:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {_ACCENT_BG};
                    color: {_ACCENT};
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    text-align: left;
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: #DBEAFE;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {_TEXT};
                    border: none;
                    border-radius: 4px;
                    font-size: 12px;
                    text-align: left;
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: {_BG_SUBTLE};
                }}
            """)

    def _on_option_clicked(self, option: str):
        self._selected = option
        for btn in self._buttons:
            self._style_button(btn, btn.text() == option)
        self.optionSelected.emit(option)

    optionSelected = Signal(str)

    def show_animated(self):
        target_h = self.get_target_height()
        self.setMinimumHeight(0)
        self.setMaximumHeight(target_h)
        self._opacity_effect.setOpacity(1.0)

        self._height_anim = QPropertyAnimation(self, b"minimumHeight")
        self._height_anim.setDuration(FILTER_PANEL_ANIM_DURATION)
        self._height_anim.setStartValue(0)
        self._height_anim.setEndValue(target_h)
        self._height_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._height_anim.start()

    def hide_animated(self):
        current_h = self.height()
        self._height_anim = QPropertyAnimation(self, b"minimumHeight")
        self._height_anim.setDuration(FILTER_PANEL_ANIM_DURATION)
        self._height_anim.setStartValue(current_h)
        self._height_anim.setEndValue(0)
        self._height_anim.setEasingCurve(QEasingCurve.InCubic)

        self._opacity_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._opacity_anim.setDuration(FILTER_PANEL_ANIM_DURATION)
        self._opacity_anim.setStartValue(1.0)
        self._opacity_anim.setEndValue(0.0)
        self._opacity_anim.setEasingCurve(QEasingCurve.InCubic)

        self._height_anim.finished.connect(self._on_hide_finished)
        self._height_anim.start()
        self._opacity_anim.start()

    def _on_hide_finished(self):
        self._height_anim.finished.disconnect(self._on_hide_finished)
        self.setMaximumHeight(0)
        self.hide()

    def set_selected(self, option: str):
        self._selected = option
        for btn in self._buttons:
            self._style_button(btn, btn.text() == option)


class StandardSearchBar(QFrame):
    searchChanged = Signal(str, str)

    def __init__(self, filter_options=None, table_headers=None):
        self._just_opened = False
        """
        Initialize the search bar with filter options.
        
        :param filter_options: Legacy parameter - list of filter options (deprecated, use table_headers instead)
        :param table_headers: List of table headers to use as filter options (recommended)
        
        Usage:
            # New way (recommended) - automatically use table headers
            search_bar = StandardSearchBar(table_headers=table_comp.headers())
            
            # Old way (still supported) - manually specify options
            search_bar = StandardSearchBar(filter_options=["CODE", "NAME", "STATUS"])
            
            # Auto-detect mode (searches parent for StandardTable)
            search_bar = StandardSearchBar()  # Will auto-detect from parent's StandardTable
        """
        super().__init__()
        self.setObjectName("SearchBarCard")
        
        # Use table_headers if provided, otherwise fall back to filter_options
        if table_headers is not None:
            self._filter_options = list(table_headers)
        elif filter_options is not None:
            self._filter_options = list(filter_options)
        else:
            # Auto-detect mode - will be populated after being added to parent
            self._filter_options = []
            self._auto_detect = True
            
        self._current_filter = self._filter_options[0] if self._filter_options else ""
        self._setup_style()
        self._init_ui()
    
    def showEvent(self, event):
        """Override showEvent to auto-detect table headers when widget is shown"""
        super().showEvent(event)
        
        # Only auto-detect once, and only if no options were provided
        if hasattr(self, '_auto_detect') and self._auto_detect and not self._filter_options:
            self._auto_detect_headers()
    
    def _auto_detect_headers(self):
        """Automatically detect table headers from parent widget's StandardTable"""
        parent = self.parent()
        if not parent:
            return
        
        # Search for StandardTable in parent's children
        from components.standard_table import StandardTable
        
        for child in parent.findChildren(StandardTable):
            if hasattr(child, 'headers'):
                headers = child.headers()
                if headers:
                    self._filter_options = headers
                    self._current_filter = self._filter_options[0]
                    self._filter_trigger.set_current(self._current_filter)
                    
                    # Rebuild the filter panel with new options
                    self._filter_panel.deleteLater()
                    self._filter_panel = AnimatedFilterPanel(
                        self._filter_options, self._current_filter, self
                    )
                    self._filter_panel.optionSelected.connect(self._on_filter_option_selected)
                    self._filter_panel.hide()
                    break

    def _setup_style(self):
        self.setStyleSheet(f"""
            #SearchBarCard {{
                background: {_BG};
                border-radius: 8px;
                border: 1px solid {_BORDER};
            }}
            QLabel#HeaderLabel {{
                font-size: 11px;
                color: {_TEXT_MUTED};
                background: transparent;
                border: none;
            }}
            QLineEdit {{
                border: 1px solid {_BORDER};
                border-radius: 6px;
                padding: 6px 10px;
                background: {_BG};
                color: {_TEXT};
                font-size: 13px;
            }}
            QLineEdit:focus {{
                border-color: {_ACCENT};
            }}
        """)

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(0)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        filter_vbox = QVBoxLayout()
        filter_vbox.setSpacing(4)
        lbl_filter = QLabel("Filter column by")
        lbl_filter.setObjectName("HeaderLabel")
        self._filter_trigger = FilterTriggerButton("Filter by", self._current_filter)
        self._filter_trigger.clicked.connect(self._toggle_filter_panel)
        filter_vbox.addWidget(lbl_filter)
        filter_vbox.addWidget(self._filter_trigger)
        top_row.addLayout(filter_vbox)

        search_vbox = QVBoxLayout()
        search_vbox.setSpacing(4)
        lbl_search = QLabel("Search")
        lbl_search.setObjectName("HeaderLabel")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Type to filter...")
        self.search_input.setMinimumHeight(36)
        self.search_input.addAction(
            qta.icon("fa5s.search", color=_TEXT_MUTED),
            QLineEdit.LeadingPosition
        )
        self.clear_action = self.search_input.addAction(
            qta.icon("fa5s.times-circle", color=_TEXT_MUTED),
            QLineEdit.TrailingPosition
        )
        self.clear_action.setVisible(False)
        self.clear_action.triggered.connect(self.search_input.clear)
        search_vbox.addWidget(lbl_search)
        search_vbox.addWidget(self.search_input)
        top_row.addLayout(search_vbox, 1)

        main_layout.addLayout(top_row)

        self._filter_panel = AnimatedFilterPanel(
            self._filter_options, self._current_filter, self
        )
        self._filter_panel.optionSelected.connect(self._on_filter_option_selected)
        self._filter_panel.hide()

        self.search_input.textChanged.connect(self._on_text_changed)

    def _toggle_filter_panel(self):
        
        win = self.window()
        if not win:
            return

        # OPEN DROPDOWN
        if not self._filter_panel.isVisible():

            pt_global = self._filter_trigger.mapToGlobal(
                QPoint(0, self._filter_trigger.height())
            )
            pos_in_window = win.mapFromGlobal(pt_global)

            target_h = self._filter_panel.get_target_height()

            self._filter_panel.setParent(win)
            self._filter_panel.setGeometry(
                pos_in_window.x(),
                pos_in_window.y(),
                DROPDOWN_WIDTH,
                target_h
            )

            self._filter_panel.show()
            self._filter_panel.raise_()
            self._filter_trigger.set_open(True)

            self._just_opened = True
            win.installEventFilter(self)

            self._filter_panel.show_animated()


        # CLOSE DROPDOWN
        else:
            self._filter_trigger.set_open(False)
            self._filter_panel.hide_animated()

            # 🔥 remove event filter when closed
            win.removeEventFilter(self)


    def _on_filter_option_selected(self, option: str):
        self._current_filter = option
        self._filter_trigger.set_current(option)
        self._filter_panel.set_selected(option)
        self._filter_trigger.set_open(False)
        self._filter_panel.hide_animated()
        self._emit_search()

    def _on_text_changed(self, text):
        self.clear_action.setVisible(bool(text))
        self._emit_search()

    def _emit_search(self):
        self.searchChanged.emit(
            self._current_filter,
            self.search_input.text().strip()
        )

    def currentText(self):
        return self._current_filter

    @property
    def filter_combo(self):
        class _FilterComboCompat:
            def __init__(self, bar):
                self._bar = bar
            def currentText(self):
                return self._bar._current_filter
        return _FilterComboCompat(self)
    def eventFilter(self, obj, event):

        if self._just_opened:
            self._just_opened = False
            return False

        if not self._filter_panel.isVisible():
            return super().eventFilter(obj, event)

        # 🔥 close if search bar/page becomes hidden
        if not self.isVisible():
            self._close_filter_panel()
            return False

        # 🔥 close if window loses focus
        if event.type() in (
            QEvent.WindowDeactivate,
            QEvent.FocusOut,
        ):
            self._close_filter_panel()
            return False

        # 🔥 outside click detection
        if event.type() == QEvent.MouseButtonPress:
            pos = event.globalPosition().toPoint()

            if not self._filter_panel.geometry().contains(pos) and \
            not self._filter_trigger.geometry().contains(
                self._filter_trigger.mapFromGlobal(pos)
            ):
                self._close_filter_panel()

        return super().eventFilter(obj, event)




    def _close_filter_panel(self):
        if self._filter_panel.isVisible():
            self._filter_trigger.set_open(False)
            self._filter_panel.hide_animated()

            win = self.window()
            if win:
                win.removeEventFilter(self)
