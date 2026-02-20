"""
generic_modal.py
----------------
Unified modal component that handles both read-only detail view and form submission.
View mode now reuses the exact same form layout as add/edit — fields look identical
but are non-editable. Both tuple-based and dict-based field configs are supported
for view mode (backward-compatible).

Now features:
  - Animated modal open/close (fade + slide-up)
  - Animated custom dropdowns (combo/cascade_combo/text_with_unit unit selector)
    replacing native QComboBox with FilterTriggerButton + AnimatedFilterPanel style.
  - Unified single-design layout for view / add / edit modes

Usage — View mode (tuple list, backward-compatible):
----------------------------------------------
    from components.generic_modal import GenericFormModal

    fields = [
        ("Connection",  row[1]),
        ("Table Name",  row[2]),
        ("Added By",    row[4]),
    ]
    modal = GenericFormModal(
        title="Row Detail",
        subtitle="Full details for the selected record.",
        mode="view",
        fields=fields,
        parent=self,
    )
    modal.exec()


Usage — View mode (schema dict list, same as add/edit):
----------------------------------------------
    from components.generic_modal import GenericFormModal

    schema = [
        {"name": "name",  "label": "Name",  "type": "text"},
        {"name": "role",  "label": "Role",  "type": "combo", "options": ["Admin", "User"]},
    ]
    modal = GenericFormModal(
        title="Row Detail",
        mode="view",
        fields=schema,
        initial_data={"name": "Alice", "role": "Admin"},
        parent=self,
    )
    modal.exec()


Usage — Form mode:
----------------------------------------------
    from components.generic_modal import GenericFormModal

    schema = [
        {"name": "name",  "label": "Name",  "type": "text",  "required": True},
        {"name": "role",  "label": "Role",  "type": "combo", "options": ["Admin", "User"], "required": True},
        {"name": "height","label": "Height","type": "text_with_unit",
         "units": ["inch", "px"], "default_unit": "inch", "required": True},
        {"name": "added_by", "label": "Added By", "type": "readonly"},
        {
            "name": "conn", "label": "Connection", "type": "cascade_combo",
            "options": {"Server A": ["Table1", "Table2"], "Server B": ["Orders"]},
            "child": "table_name",
        },
        {"name": "table_name", "label": "Table Name", "type": "combo", "options": []},
        {"name": "height", "label": "Height", "type": "dimension_pair", "dpi": 96, "required": True},
    ]
    modal = GenericFormModal(
        title="Add Record",
        mode="add",
        fields=schema,
        parent=self,
    )
    modal.formSubmitted.connect(lambda data: print(data))
    modal.exec()
"""

import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDialogButtonBox,
    QScrollArea, QFrame, QPushButton, QSizePolicy, QMessageBox,
    QGraphicsOpacityEffect,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint,
    QParallelAnimationGroup, QSequentialAnimationGroup, QEvent,
    QRect,
)
from PySide6.QtGui import QFont, QCursor

# ------------------------------------------------------------------
# Design tokens
# ------------------------------------------------------------------
COLORS = {
    "bg_main":        "#F8FAFC",
    "text_primary":   "#111827",
    "text_secondary": "#64748B",
    "text_muted":     "#6B7280",
    "border":         "#E2E8F0",
    "border_light":   "#E5E7EB",
    "link":           "#6366F1",
    "field_bg":       "#F9FAFB",
    "white":          "#FFFFFF",
    "readonly_bg":    "#F3F4F6",
    "readonly_text":  "#9CA3AF",
    # dropdown-specific
    "dd_accent":      "#6366F1",
    "dd_accent_bg":   "#EEF2FF",
    "dd_hover":       "#F9FAFB",
}

# Dropdown geometry / animation
_DROPDOWN_ANIM_MS  = 180
_OPTION_HEIGHT     = 34
_DROPDOWN_MAX_H    = 240

# Modal entrance animation
_MODAL_ANIM_MS     = 220
_MODAL_SLIDE_PX    = 18   # how many px upward the modal slides in


# ==================================================================
# Animated dropdown — reusable components
# ==================================================================

class _DropdownTrigger(QFrame):
    """Pill-shaped trigger that shows the current value + chevron."""
    clicked = Signal()

    def __init__(self, placeholder: str = "Select…", parent=None):
        super().__init__(parent)
        self._is_open = False
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._build()

    def _build(self):
        self.setStyleSheet(f"""
            _DropdownTrigger {{
                background: {COLORS['white']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
            _DropdownTrigger:hover {{ border-color: #C7D2FE; }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 8, 0)
        lay.setSpacing(6)

        self._lbl = QLabel()
        self._lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 13px;"
            " background: transparent; border: none;"
        )
        self._chevron = QLabel()
        self._chevron.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._chevron.setStyleSheet("background: transparent; border: none;")
        self._refresh_chevron()

        lay.addWidget(self._lbl, 1)
        lay.addWidget(self._chevron, 0)

    def _refresh_chevron(self):
        icon = "fa5s.chevron-up" if self._is_open else "fa5s.chevron-down"
        self._chevron.setPixmap(
            qta.icon(icon, color=COLORS["text_muted"]).pixmap(10, 10)
        )

    def set_text(self, text: str):
        self._lbl.setText(text)

    def text(self) -> str:
        return self._lbl.text()

    def set_open(self, open_: bool):
        self._is_open = open_
        self._refresh_chevron()
        border_color = COLORS["dd_accent"] if open_ else COLORS["border"]
        self.setStyleSheet(f"""
            _DropdownTrigger {{
                background: {COLORS['white']};
                border: 1px solid {border_color};
                border-radius: 6px;
            }}
            _DropdownTrigger:hover {{ border-color: #C7D2FE; }}
        """)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class _DropdownPanel(QFrame):
    """Animated option panel that pops out of the window layer."""
    optionSelected = Signal(str)

    def __init__(self, options: list[str], selected: str, parent=None):
        super().__init__(parent)
        self._options  = options
        self._selected = selected
        self._buttons  = []
        self._h_anim   = None
        self._op_anim  = None

        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._opacity_fx.setOpacity(0.0)

        self.setMaximumHeight(0)
        self.setMinimumHeight(0)
        self.setStyleSheet(f"""
            _DropdownPanel {{
                background: {COLORS['white']};
                border: 1px solid {COLORS['border_light']};
                border-top: none;
                border-radius: 0 0 6px 6px;
            }}
        """)
        self._build_options()

    def _target_height(self) -> int:
        return min(8 + len(self._options) * (_OPTION_HEIGHT + 2), _DROPDOWN_MAX_H)

    def _build_options(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.setSpacing(2)
        for opt in self._options:
            btn = QPushButton(opt)
            btn.setFixedHeight(_OPTION_HEIGHT)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, o=opt: self._pick(o))
            self._style_btn(btn, opt == self._selected)
            lay.addWidget(btn)
            self._buttons.append(btn)

    def _style_btn(self, btn: QPushButton, selected: bool):
        if selected:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {COLORS['dd_accent_bg']}; color: {COLORS['dd_accent']};
                    border: none; border-radius: 4px;
                    font-size: 12px; text-align: left; padding: 0 10px;
                }}
                QPushButton:hover {{ background: #E0E7FF; }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; color: {COLORS['text_primary']};
                    border: none; border-radius: 4px;
                    font-size: 12px; text-align: left; padding: 0 10px;
                }}
                QPushButton:hover {{ background: {COLORS['dd_hover']}; }}
            """)

    def _pick(self, option: str):
        self._selected = option
        for btn in self._buttons:
            self._style_btn(btn, btn.text() == option)
        self.optionSelected.emit(option)

    def set_selected(self, option: str):
        self._selected = option
        for btn in self._buttons:
            self._style_btn(btn, btn.text() == option)

    def set_options(self, options: list[str], selected: str = ""):
        """Replace the option list (used by cascade_combo child refresh)."""
        lay = self.layout()
        while lay.count():
            item = lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._buttons.clear()
        self._options  = options
        self._selected = selected
        for opt in options:
            btn = QPushButton(opt)
            btn.setFixedHeight(_OPTION_HEIGHT)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, o=opt: self._pick(o))
            self._style_btn(btn, opt == selected)
            lay.addWidget(btn)
            self._buttons.append(btn)

    def show_animated(self):
        th = self._target_height()
        self.setMinimumHeight(0)
        self.setMaximumHeight(th)
        self._opacity_fx.setOpacity(1.0)

        self._h_anim = QPropertyAnimation(self, b"minimumHeight")
        self._h_anim.setDuration(_DROPDOWN_ANIM_MS)
        self._h_anim.setStartValue(0)
        self._h_anim.setEndValue(th)
        self._h_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._h_anim.start()

    def hide_animated(self):
        cur = self.height()

        self._h_anim = QPropertyAnimation(self, b"minimumHeight")
        self._h_anim.setDuration(_DROPDOWN_ANIM_MS)
        self._h_anim.setStartValue(cur)
        self._h_anim.setEndValue(0)
        self._h_anim.setEasingCurve(QEasingCurve.InCubic)

        self._op_anim = QPropertyAnimation(self._opacity_fx, b"opacity")
        self._op_anim.setDuration(_DROPDOWN_ANIM_MS)
        self._op_anim.setStartValue(1.0)
        self._op_anim.setEndValue(0.0)
        self._op_anim.setEasingCurve(QEasingCurve.InCubic)

        self._h_anim.finished.connect(self._finish_hide)
        self._h_anim.start()
        self._op_anim.start()

    def _finish_hide(self):
        try:
            self._h_anim.finished.disconnect(self._finish_hide)
        except RuntimeError:
            pass
        self.setMaximumHeight(0)
        self.hide()


class AnimatedCombo(QWidget):
    """
    Drop-in replacement for QComboBox using _DropdownTrigger + _DropdownPanel.
    The panel is a frameless top-level Qt.Popup so it escapes the dialog's
    clipping bounds and can render freely over any other window content.
    """
    currentTextChanged = Signal(str)

    def __init__(self, options: list[str], parent=None):
        super().__init__(parent)
        self._options     = list(options)
        self._current     = options[0] if options else ""
        self._panel       = None
        self._just_opened = False

        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._trigger = _DropdownTrigger(parent=self)
        self._trigger.set_text(self._current)
        self._trigger.clicked.connect(self._toggle)
        lay.addWidget(self._trigger)

    # ── QComboBox-compatible API ──────────────────────────────────────

    def currentText(self) -> str:
        return self._current

    def setCurrentText(self, text: str):
        if text in self._options:
            self._current = text
            self._trigger.set_text(text)
            if self._panel:
                self._panel.set_selected(text)

    def clear(self):
        self._options = []
        self._current = ""
        self._trigger.set_text("")
        if self._panel:
            self._panel.set_options([], "")

    def addItems(self, items: list[str]):
        self._options.extend(items)
        if not self._current and items:
            self._current = items[0]
            self._trigger.set_text(self._current)
        if self._panel:
            self._panel.set_options(self._options, self._current)

    def setDisabled(self, disabled: bool):
        """Disable interaction — used in view mode."""
        super().setDisabled(disabled)
        self._trigger.setCursor(Qt.ArrowCursor if disabled else Qt.PointingHandCursor)
        if disabled:
            self._trigger.setStyleSheet(f"""
                _DropdownTrigger {{
                    background: {COLORS['readonly_bg']};
                    border: 1px solid {COLORS['border_light']};
                    border-radius: 6px;
                }}
            """)
            # Disconnect click so panel never opens
            try:
                self._trigger.clicked.disconnect(self._toggle)
            except RuntimeError:
                pass

    # ── internal toggle ───────────────────────────────────────────────

    def _ensure_panel(self):
        if self._panel is None:
            self._panel = _DropdownPanel(self._options, self._current, parent=None)
            self._panel.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
            self._panel.setAttribute(Qt.WA_TranslucentBackground, False)
            self._panel.optionSelected.connect(self._on_picked)
            self._panel.hide()

    def _toggle(self):
        self._ensure_panel()

        if not self._panel.isVisible():
            pt_global = self._trigger.mapToGlobal(QPoint(0, self._trigger.height()))
            w         = self._trigger.width()
            th        = self._panel._target_height()

            from PySide6.QtWidgets import QApplication
            screen = QApplication.screenAt(pt_global)
            if screen:
                screen_bottom = screen.availableGeometry().bottom()
                if pt_global.y() + th > screen_bottom:
                    pt_global = self._trigger.mapToGlobal(QPoint(0, -th))

            self._panel.setGeometry(pt_global.x(), pt_global.y(), w, th)
            self._panel.show()
            self._panel.raise_()
            self._trigger.set_open(True)
            self._just_opened = True

            self._panel.installEventFilter(self)
            self._panel.show_animated()
        else:
            self._close()

    def _close(self):
        if self._panel and self._panel.isVisible():
            self._trigger.set_open(False)
            self._panel.hide_animated()

    def _on_picked(self, option: str):
        prev = self._current
        self._current = option
        self._trigger.set_text(option)
        self._close()
        if option != prev:
            self.currentTextChanged.emit(option)

    def eventFilter(self, obj, event):
        if self._just_opened:
            self._just_opened = False
            return False
        return super().eventFilter(obj, event)


# ==================================================================
# Main modal
# ==================================================================

class GenericFormModal(QDialog):
    """
    Single modal for read-only detail view and editable forms.

    View mode now renders the exact same form layout as add/edit — same
    field containers, same spacing, same typography — but with all inputs
    locked (readonly QLineEdit, disabled AnimatedCombo, etc.).

    Field config for view mode accepts either:
      - List of (label, value) tuples  → auto-converted to text schema
      - List of dicts (same schema as add/edit)  → rendered directly
    """

    formSubmitted = Signal(dict)
    opened = Signal()   # emitted once the modal is visible
    closed = Signal()   # emitted after the modal is fully dismissed

    def __init__(
        self,
        title: str = "Detail",
        subtitle: str = "",
        mode: str = "view",
        fields=None,
        initial_data: dict | None = None,
        parent=None,
        min_width: int = 560,
    ):
        super().__init__(parent)

        if mode not in ("view", "add", "edit"):
            raise ValueError(f"mode must be 'view', 'add', or 'edit', got {mode!r}")

        self.mode = mode
        self.initial_data = initial_data or {}

        # ── Normalise field config ─────────────────────────────────────
        # Tuple list → convert to schema dicts and fold values into initial_data
        raw_fields = fields or []
        if raw_fields and isinstance(raw_fields[0], (tuple, list)):
            schema = []
            for label, value in raw_fields:
                name = label.lower().replace(" ", "_")
                schema.append({"name": name, "label": label, "type": "text"})
                if name not in self.initial_data:
                    self.initial_data[name] = value
            self.fields_config = schema
        else:
            self.fields_config = raw_fields

        self.inputs: dict[str, QWidget] = {}
        self._cascade_map:     dict[str, str]  = {}
        self._cascade_options: dict[str, dict] = {}

        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setModal(False)

        # ── Unified window style (same for all modes) ─────────────────
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")

        self._build_ui(title, subtitle)
        self._populate_initial_data()

        # ── entrance animation setup ──────────────────────────────────
        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._opacity_fx.setOpacity(0.0)
        self._entrance_done = False

    # ------------------------------------------------------------------
    # Exec / show with animation
    # ------------------------------------------------------------------

    def exec(self):
        self.show()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._entrance_done:
            self._entrance_done = True
            self._animate_in()
            self.opened.emit()

    def closeEvent(self, event):
        event.ignore()
        self._animate_out(lambda: QDialog.reject(self))

    def reject(self):
        self._animate_out(lambda: super(GenericFormModal, self).reject())

    def accept(self):
        self._animate_out(lambda: super(GenericFormModal, self).accept())

    # ── entrance / exit helpers ───────────────────────────────────────

    def _animate_in(self):
        start_pos = self.pos() + QPoint(0, _MODAL_SLIDE_PX)
        end_pos   = self.pos()

        fade = QPropertyAnimation(self._opacity_fx, b"opacity")
        fade.setDuration(_MODAL_ANIM_MS)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.setEasingCurve(QEasingCurve.OutCubic)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(_MODAL_ANIM_MS)
        slide.setStartValue(start_pos)
        slide.setEndValue(end_pos)
        slide.setEasingCurve(QEasingCurve.OutCubic)

        self._in_group = QParallelAnimationGroup()
        self._in_group.addAnimation(fade)
        self._in_group.addAnimation(slide)
        self._in_group.start()

    def _animate_out(self, callback):
        fade = QPropertyAnimation(self._opacity_fx, b"opacity")
        fade.setDuration(_MODAL_ANIM_MS)
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(QEasingCurve.InCubic)

        slide = QPropertyAnimation(self, b"pos")
        slide.setDuration(_MODAL_ANIM_MS)
        slide.setStartValue(self.pos())
        slide.setEndValue(self.pos() + QPoint(0, _MODAL_SLIDE_PX))
        slide.setEasingCurve(QEasingCurve.InCubic)

        def _finish():
            callback()
            self.closed.emit()

        self._out_group = QParallelAnimationGroup()
        self._out_group.addAnimation(fade)
        self._out_group.addAnimation(slide)
        self._out_group.finished.connect(_finish)
        self._out_group.start()

    # ------------------------------------------------------------------
    # UI construction — single shared layout for all modes
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, subtitle: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        text_block = QVBoxLayout()
        text_block.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;"
        )
        text_block.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent;"
            )
            text_block.addWidget(sub_lbl)

        header_row.addLayout(text_block)
        header_row.addStretch()

        # Close button for view mode (no save/cancel row at bottom)
        if self.mode == "view":
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(32, 32)
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.setToolTip("Close")
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: none; border-radius: 6px;
                    font-size: 14px; font-weight: 600;
                }}
                QPushButton:hover {{ background-color: #F3F4F6; color: {COLORS['text_primary']}; }}
                QPushButton:pressed {{ background-color: {COLORS['border_light']}; }}
            """)
            close_btn.clicked.connect(self.reject)
            header_row.addWidget(close_btn, alignment=Qt.AlignTop)

        root.addLayout(header_row)
        root.addSpacing(20)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(
            f"color: {COLORS['border_light']}; background-color: {COLORS['border_light']}; max-height: 1px;"
        )
        root.addWidget(divider)
        root.addSpacing(20)

        # ── Shared form body ──────────────────────────────────────────
        self._build_form_body(root)

    # ------------------------------------------------------------------
    # Form body — used by all modes; view mode just disables everything
    # ------------------------------------------------------------------

    def _build_form_body(self, root: QVBoxLayout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(460)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setSingleStep(12)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0px; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::handle:vertical:pressed { background: #6B7280; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")

        form_layout = QFormLayout(scroll_content)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(0, 0, 12, 0)
        form_layout.setLabelAlignment(Qt.AlignRight)

        for field in self.fields_config:
            widget = self._create_form_widget(field)
            self.inputs[field["name"]] = widget

            label = field.get("label", field["name"])
            # Only show required asterisk in add/edit mode
            if field.get("required") and self.mode != "view":
                label += " *"

            # Dim label colour for readonly-typed fields
            if field.get("type") == "readonly":
                lbl = QLabel(label)
                lbl.setStyleSheet(f"color: {COLORS['readonly_text']}; font-size: 13px;")
                form_layout.addRow(lbl, widget)
            else:
                form_layout.addRow(label, widget)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll)
        root.addSpacing(16)
        root.addStretch()

        # ── Buttons — only for add/edit ───────────────────────────────
        if self.mode != "view":
            submit_text = "Create" if self.mode == "add" else "Save Changes"
            buttons = QDialogButtonBox()
            buttons.addButton(submit_text, QDialogButtonBox.AcceptRole)
            buttons.addButton("Cancel", QDialogButtonBox.RejectRole)
            buttons.accepted.connect(self._on_submit)
            buttons.rejected.connect(self.reject)
            buttons.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                    min-width: 100px;
                }}
                QPushButton[text="{submit_text}"] {{
                    background-color: {COLORS['link']};
                    color: white;
                    border: none;
                }}
                QPushButton[text="Cancel"] {{
                    background-color: {COLORS['white']};
                    color: {COLORS['text_secondary']};
                    border: 1px solid {COLORS['border']};
                }}
            """)
            root.addWidget(buttons)

    # ------------------------------------------------------------------
    # Widget factory
    #
    # A single function handles all modes. The `editable` flag drives
    # every branching decision — no per-mode scattered conditionals.
    #
    # editable=True  → normal interactive widget  (add / edit mode)
    # editable=False → same visual, but locked    (view mode, or
    #                  fields with type="readonly")
    # ------------------------------------------------------------------

    def _create_form_widget(self, field: dict) -> QWidget:
        field_type = field.get("type", "text")
        # view mode makes everything non-editable; "readonly" type is
        # always locked regardless of mode
        editable = (self.mode != "view") and (field_type != "readonly")

        # ── text / readonly ───────────────────────────────────────────
        if field_type in ("text", "readonly"):
            w = QLineEdit()
            w.setMinimumHeight(36)
            if editable:
                w.setPlaceholderText(field.get("placeholder", ""))
                self._style_input(w)
            else:
                w.setReadOnly(True)
                w.setPlaceholderText("")
                # "readonly" schema fields get italic muted style;
                # view-mode locked fields stay full-colour but shaded
                if field_type == "readonly":
                    w.setStyleSheet(self._readonly_line_edit_style())
                    w.setCursor(QCursor(Qt.ForbiddenCursor))
                else:
                    w.setStyleSheet(self._view_line_edit_style())
            return w

        # ── combo / select ────────────────────────────────────────────
        elif field_type in ("combo", "select"):
            w = AnimatedCombo(field.get("options", []))
            if not editable:
                w.setDisabled(True)
            return w

        # ── cascade_combo ─────────────────────────────────────────────
        elif field_type == "cascade_combo":
            options_map: dict = field.get("options", {})
            child_name: str   = field.get("child", "")

            w = AnimatedCombo(list(options_map.keys()))
            self._cascade_map[field["name"]]     = child_name
            self._cascade_options[field["name"]] = options_map

            if editable:
                w.currentTextChanged.connect(
                    lambda text, pname=field["name"]: self._on_cascade_changed(pname, text)
                )
            else:
                w.setDisabled(True)
            return w

        # ── text_with_unit ────────────────────────────────────────────
        elif field_type == "text_with_unit":
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)

            text_input = QLineEdit()
            text_input.setMinimumHeight(36)
            if editable:
                text_input.setPlaceholderText(field.get("placeholder", ""))
                self._style_input(text_input)
            else:
                text_input.setReadOnly(True)
                text_input.setStyleSheet(self._view_line_edit_style())

            units      = field.get("units", ["unit"])
            unit_combo = AnimatedCombo(units)
            unit_combo.setFixedWidth(100)
            default_unit = field.get("default_unit")
            if default_unit and default_unit in units:
                unit_combo.setCurrentText(default_unit)
            if not editable:
                unit_combo.setDisabled(True)

            h.addWidget(text_input, stretch=1)
            h.addWidget(unit_combo)

            container.text_input = text_input
            container.unit_combo = unit_combo
            return container

        # ── dimension_pair ────────────────────────────────────────────
        elif field_type == "dimension_pair":
            from PySide6.QtGui import QDoubleValidator, QIntValidator
            from PySide6.QtCore import QLocale

            dpi = field.get("dpi", 96)
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            outer = QHBoxLayout(container)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(10)

            def _labeled_input(label_text, placeholder):
                cell = QWidget()
                cell.setStyleSheet("background: transparent;")
                vl = QVBoxLayout(cell)
                vl.setContentsMargins(0, 0, 0, 0)
                vl.setSpacing(3)

                header_lbl = QLabel(label_text)
                header_lbl.setStyleSheet(
                    f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};"
                    " letter-spacing: 0.04em; background: transparent;"
                )
                inp = QLineEdit()
                inp.setMinimumHeight(36)
                if editable:
                    inp.setPlaceholderText(placeholder)
                    self._style_input(inp)
                else:
                    inp.setReadOnly(True)
                    inp.setStyleSheet(self._view_line_edit_style())

                err_lbl = QLabel("")
                err_lbl.setStyleSheet("font-size: 11px; color: #EF4444; background: transparent;")
                err_lbl.setVisible(False)

                vl.addWidget(header_lbl)
                vl.addWidget(inp)
                vl.addWidget(err_lbl)
                return cell, inp, err_lbl

            inch_cell, inch_input, inch_err = _labeled_input("INCH", "e.g. 2.5")
            px_cell,   px_input,   px_err   = _labeled_input("PX",   "e.g. 240")

            outer.addWidget(inch_cell, stretch=1)
            outer.addWidget(px_cell,   stretch=1)

            container._converting = False

            def _set_error(inp_widget, err_widget, msg: str):
                if msg:
                    inp_widget.setStyleSheet(
                        f"QLineEdit {{ padding: 8px 12px; border: 1.5px solid #EF4444;"
                        f" border-radius: 6px; background-color: #FEF2F2;"
                        f" color: {COLORS['text_primary']}; font-size: 13px; }}"
                    )
                    err_widget.setText(msg)
                    err_widget.setVisible(True)
                else:
                    self._style_input(inp_widget)
                    err_widget.setVisible(False)

            if editable:
                inch_validator = QDoubleValidator(0.0001, 99999.0, 4)
                inch_validator.setLocale(QLocale(QLocale.English))
                inch_validator.setNotation(QDoubleValidator.StandardNotation)
                inch_input.setValidator(inch_validator)
                px_input.setValidator(QIntValidator(1, 999999))

                def _inch_changed(text, _dpi=dpi):
                    if container._converting:
                        return
                    container._converting = True
                    try:
                        val = float(text)
                        if val <= 0:
                            raise ValueError
                        px_input.setText(str(int(round(val * _dpi))))
                        _set_error(inch_input, inch_err, "")
                        _set_error(px_input,   px_err,   "")
                    except ValueError:
                        px_input.clear()
                        if text.strip():
                            _set_error(inch_input, inch_err, "Must be a positive number")
                        else:
                            _set_error(inch_input, inch_err, "")
                    finally:
                        container._converting = False

                def _px_changed(text, _dpi=dpi):
                    if container._converting:
                        return
                    container._converting = True
                    try:
                        val = int(text)
                        if val <= 0:
                            raise ValueError
                        inch_input.setText(f"{val / _dpi:.4f}")
                        _set_error(px_input,   px_err,   "")
                        _set_error(inch_input, inch_err, "")
                    except ValueError:
                        inch_input.clear()
                        if text.strip():
                            _set_error(px_input, px_err, "Must be a positive whole number")
                        else:
                            _set_error(px_input, px_err, "")
                    finally:
                        container._converting = False

                inch_input.textEdited.connect(_inch_changed)
                px_input.textEdited.connect(_px_changed)

            container.inch_input  = inch_input
            container.px_input    = px_input
            container.inch_err    = inch_err
            container.px_err      = px_err
            container._set_error  = _set_error
            container._field_type = "dimension_pair"
            return container

        else:
            raise ValueError(f"Unsupported field type: {field_type!r}")

    # ------------------------------------------------------------------
    # Style helpers
    # ------------------------------------------------------------------

    def _style_input(self, widget):
        widget.setMinimumHeight(36)
        widget.setStyleSheet(f"""
            QLineEdit, QComboBox {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                background-color: {COLORS['white']};
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color: {COLORS['link']}; }}
        """)

    def _view_line_edit_style(self) -> str:
        """Readonly field in view mode — same shape as editable, softer colours."""
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                background-color: {COLORS['readonly_bg']};
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
        """

    def _readonly_line_edit_style(self) -> str:
        """Explicitly readonly schema fields (italic, muted)."""
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border_light']};
                border-radius: 6px;
                background-color: {COLORS['readonly_bg']};
                color: {COLORS['readonly_text']};
                font-size: 13px;
                font-style: italic;
            }}
        """

    # ------------------------------------------------------------------
    # Cascade logic
    # ------------------------------------------------------------------

    def _on_cascade_changed(self, parent_name: str, selected_text: str):
        child_name = self._cascade_map.get(parent_name)
        if not child_name or child_name not in self.inputs:
            return

        child_widget  = self.inputs[child_name]
        options_map   = self._cascade_options.get(parent_name, {})
        child_options = options_map.get(selected_text, [])

        if isinstance(child_widget, AnimatedCombo):
            child_widget.clear()
            child_widget.addItems(child_options)
        elif isinstance(child_widget, QComboBox):
            child_widget.blockSignals(True)
            child_widget.clear()
            child_widget.addItems(child_options)
            child_widget.blockSignals(False)

    # ------------------------------------------------------------------
    # Populate initial data (called for all modes)
    # ------------------------------------------------------------------

    def _populate_initial_data(self):
        for name, widget in self.inputs.items():
            if name not in self.initial_data and \
               f"{name}_in" not in self.initial_data and \
               f"{name}_px" not in self.initial_data:
                continue

            if getattr(widget, "_field_type", None) == "dimension_pair":
                in_val = self.initial_data.get(f"{name}_in") or self.initial_data.get(name, "")
                px_val = self.initial_data.get(f"{name}_px", "")
                if in_val:
                    widget.inch_input.setText(str(in_val))
                    if not px_val:
                        try:
                            dpi = next(
                                (f.get("dpi", 96) for f in self.fields_config if f.get("name") == name), 96
                            )
                            px_val = str(int(round(float(in_val) * dpi)))
                        except ValueError:
                            pass
                if px_val:
                    widget.px_input.setText(str(px_val))
                continue

            value = self.initial_data.get(name)
            if value is None:
                continue

            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, AnimatedCombo):
                if name in self._cascade_map:
                    self._on_cascade_changed(name, str(value))
                widget.setCurrentText(str(value))
                if name in self._cascade_map:
                    child_name   = self._cascade_map[name]
                    child_val    = self.initial_data.get(child_name, "")
                    child_widget = self.inputs.get(child_name)
                    if isinstance(child_widget, AnimatedCombo) and child_val:
                        child_widget.setCurrentText(str(child_val))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif hasattr(widget, "text_input"):
                widget.text_input.setText(str(value))
                unit_key = f"{name}_unit"
                if unit_key in self.initial_data and hasattr(widget, "unit_combo"):
                    widget.unit_combo.setCurrentText(str(self.initial_data[unit_key]))

    # ------------------------------------------------------------------
    # Validate / collect / submit (add/edit only)
    # ------------------------------------------------------------------

    def _validate(self) -> list[str]:
        errors = []
        for field in self.fields_config:
            if field.get("type") in ("readonly",):
                continue
            widget      = self.inputs[field["name"]]
            label       = field.get("label", field["name"])
            is_required = field.get("required", False)

            if getattr(widget, "_field_type", None) == "dimension_pair":
                in_text = widget.inch_input.text().strip()
                px_text = widget.px_input.text().strip()
                if is_required and not in_text and not px_text:
                    errors.append(f"{label}: both Inch and PX are empty")
                    widget._set_error(widget.inch_input, widget.inch_err, "Required")
                    widget._set_error(widget.px_input,   widget.px_err,   "Required")
                    continue
                if in_text:
                    try:
                        if float(in_text) <= 0:
                            raise ValueError
                        widget._set_error(widget.inch_input, widget.inch_err, "")
                    except ValueError:
                        errors.append(f"{label} (Inch): must be a positive number")
                        widget._set_error(widget.inch_input, widget.inch_err, "Must be a positive number")
                if px_text:
                    try:
                        if int(px_text) <= 0:
                            raise ValueError
                        widget._set_error(widget.px_input, widget.px_err, "")
                    except ValueError:
                        errors.append(f"{label} (PX): must be a positive whole number")
                        widget._set_error(widget.px_input, widget.px_err, "Must be a positive whole number")

            elif isinstance(widget, QLineEdit):
                if is_required and not widget.text().strip():
                    errors.append(f"{label} is required")
                    widget.setStyleSheet(
                        f"QLineEdit {{ padding: 8px 12px; border: 1.5px solid #EF4444;"
                        f" border-radius: 6px; background-color: #FEF2F2;"
                        f" color: {COLORS['text_primary']}; font-size: 13px; }}"
                    )
                else:
                    self._style_input(widget)

            elif isinstance(widget, (AnimatedCombo, QComboBox)):
                if is_required and not widget.currentText():
                    errors.append(f"{label} is required")

            elif hasattr(widget, "text_input"):
                if is_required and not widget.text_input.text().strip():
                    errors.append(f"{label} is required")

        return errors

    def _collect_data(self) -> dict:
        data = {}
        for name, widget in self.inputs.items():
            if getattr(widget, "_field_type", None) == "dimension_pair":
                data[f"{name}_in"] = widget.inch_input.text().strip()
                data[f"{name}_px"] = widget.px_input.text().strip()
            elif isinstance(widget, QLineEdit):
                data[name] = widget.text().strip()
            elif isinstance(widget, (AnimatedCombo, QComboBox)):
                data[name] = widget.currentText()
            elif hasattr(widget, "text_input"):
                data[name] = widget.text_input.text().strip()
                data[f"{name}_unit"] = widget.unit_combo.currentText()
        return data

    def _on_submit(self):
        errors = self._validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        self.formSubmitted.emit(self._collect_data())
        self.accept()


# Back-compat alias
GenericModal = GenericFormModal