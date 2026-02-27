# app/components/generic_form_modal.py
# FIXED: Checkbox display now correctly handles pre-formatted labels with " AS "

import qtawesome as qta
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDialogButtonBox,
    QScrollArea, QFrame, QPushButton, QSizePolicy, QMessageBox,
    QGraphicsOpacityEffect, QCheckBox, QTextEdit,
)
from PySide6.QtCore import (
    Qt, Signal, QPropertyAnimation, QEasingCurve, QPoint,
    QParallelAnimationGroup, QEvent, QObject,
)
from PySide6.QtGui import QFont, QCursor

# ------------------------------------------------------------------
# Write a checkmark SVG to a temp file once at import time.
# Qt on Windows does not support base64 data URIs in stylesheets,
# but it does support file:// paths reliably.
# ------------------------------------------------------------------
import os as _os, tempfile as _tempfile
_svg_check = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 12 12">'
    '<polyline points="1.5,6 4.5,9.5 10.5,2.5" fill="none" '
    'stroke="black" stroke-width="1.8" stroke-linecap="round" '
    'stroke-linejoin="round"/></svg>'
)
_CHECKMARK_SVG_PATH = _os.path.join(
    _tempfile.gettempdir(), "gfm_check_indicator.svg"
).replace("\\", "/")
with open(_CHECKMARK_SVG_PATH, "w") as _f:
    _f.write(_svg_check)
del _os, _tempfile, _svg_check, _f

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
    "dd_accent":      "#6366F1",
    "dd_accent_bg":   "#EEF2FF",
    "dd_hover":       "#F9FAFB",
}

_DROPDOWN_ANIM_MS  = 180
_OPTION_HEIGHT     = 34
_DROPDOWN_MAX_H    = 240
_MODAL_ANIM_MS     = 220
_MODAL_SLIDE_PX    = 18


# ==================================================================
# Animated dropdown components
# ==================================================================

class _DropdownTrigger(QFrame):
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
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; min-height: 20px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        inner = QWidget()
        lay = QVBoxLayout(inner)
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
        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(scroll)

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


# ==================================================================
# Outside-click filter for AnimatedCombo
# ==================================================================

class _OutsideClickFilter(QObject):
    def __init__(self, combo: "AnimatedCombo"):
        super().__init__(combo)
        self._combo = combo

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            panel   = self._combo._panel
            trigger = self._combo._trigger

            if panel is None or not panel.isVisible():
                return False

            try:
                gpos = event.globalPosition().toPoint()
            except AttributeError:
                gpos = event.globalPos()

            in_panel   = panel.geometry().contains(gpos)
            in_trigger = trigger.rect().contains(trigger.mapFromGlobal(gpos))

            if not in_panel and not in_trigger:
                self._combo._close()

        return False


# ==================================================================
# Animated combo widget
# ==================================================================

class AnimatedCombo(QWidget):
    currentTextChanged = Signal(str)

    def __init__(self, options: list[str], placeholder: str = "", parent=None):
        super().__init__(parent)
        self._options      = list(options)
        self._placeholder  = placeholder
        self._current      = "" if placeholder else (options[0] if options else "")
        self._panel        = None
        self._global_filter_installed = False

        self.setMinimumHeight(36)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._trigger = _DropdownTrigger(parent=self)
        if placeholder:
            self._trigger.set_text(placeholder)
            self._trigger._lbl.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: 13px;"
                " background: transparent; border: none;"
            )
        else:
            self._trigger.set_text(self._current)
        self._trigger.clicked.connect(self._toggle)
        self._toggle_connected = True
        lay.addWidget(self._trigger)

        self._global_filter = _OutsideClickFilter(self)

    def currentText(self) -> str:
        return self._current

    def setCurrentText(self, text: str):
        if text in self._options:
            self._current = text
            self._trigger.set_text(text)
            self._trigger._lbl.setStyleSheet(
                f"color: {COLORS['text_primary']}; font-size: 13px;"
                " background: transparent; border: none;"
            )
            if self._panel:
                self._panel.set_selected(text)

    def clear(self):
        self._options = []
        self._current = ""
        display = self._placeholder or ""
        self._trigger.set_text(display)
        self._trigger._lbl.setStyleSheet(
            f"color: {COLORS['text_muted'] if display else COLORS['text_primary']}; font-size: 13px;"
            " background: transparent; border: none;"
        )
        if self._panel:
            self._panel.set_options([], "")

    def addItems(self, items: list[str]):
        self._options.extend(items)
        if not self._current and items and not self._placeholder:
            self._current = items[0]
            self._trigger.set_text(self._current)
        if self._panel:
            self._panel.set_options(self._options, self._current)

    def setDisabled(self, disabled: bool):
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
            if self._toggle_connected:
                self._trigger.clicked.disconnect(self._toggle)
                self._toggle_connected = False
        else:
            self._trigger.set_open(False)
            if not self._toggle_connected:
                self._trigger.clicked.connect(self._toggle)
                self._toggle_connected = True

    def _ensure_panel(self):
        if self._panel is None:
            self._panel = _DropdownPanel(self._options, self._current, parent=None)
            self._panel.setWindowFlags(
                Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint
            )
            self._panel.setAttribute(Qt.WA_TranslucentBackground, False)
            self._panel.optionSelected.connect(self._on_picked)
            self._panel.hide()

    def _toggle(self):
        self._ensure_panel()
        if not self._panel.isVisible():
            self._open()
        else:
            self._close()

    def _open(self):
        pt_global = self._trigger.mapToGlobal(QPoint(0, self._trigger.height()))
        w  = self._trigger.width()
        th = self._panel._target_height()

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
        self._panel.show_animated()

        if not self._global_filter_installed:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().installEventFilter(self._global_filter)
            self._global_filter_installed = True

    def _close(self):
        if self._panel and self._panel.isVisible():
            self._trigger.set_open(False)
            self._panel.hide_animated()

        if self._global_filter_installed:
            from PySide6.QtWidgets import QApplication
            QApplication.instance().removeEventFilter(self._global_filter)
            self._global_filter_installed = False

    def _on_picked(self, option: str):
        prev = self._current
        self._current = option
        self._trigger.set_text(option)
        self._trigger._lbl.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: 13px;"
            " background: transparent; border: none;"
        )
        self._close()
        if option != prev:
            self.currentTextChanged.emit(option)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._close()


# ==================================================================
# Checkbox list widget
# ==================================================================

class _CheckboxListWidget(QWidget):
    def __init__(self, options: list[str], checked_options: list[str] | None = None,
                 disabled: bool = False, parent=None):
        super().__init__(parent)
        self._disabled = disabled
        checked_set = set(checked_options if checked_options is not None else options)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFixedHeight(200)
        self._scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)

        self._inner = QWidget()
        self._inner.setStyleSheet(f"""
            QWidget {{
                background: {COLORS['white']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
            }}
        """)
        self._lay = QVBoxLayout(self._inner)
        self._lay.setContentsMargins(10, 8, 10, 8)
        self._lay.setSpacing(4)

        self._checkboxes: dict[str, QCheckBox] = {}
        self._build_checkboxes(options, checked_set)

        self._scroll.setWidget(self._inner)
        outer.addWidget(self._scroll)

        self._empty_lbl = QLabel("Select a table to see its fields")
        self._empty_lbl.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 12px; font-style: italic;"
            " padding: 8px 0; background: transparent;"
        )
        self._empty_lbl.setAlignment(Qt.AlignCenter)
        self._empty_lbl.setVisible(not options)
        outer.addWidget(self._empty_lbl)
        self._scroll.setVisible(bool(options))

    def _build_checkboxes(self, options, checked_set: set):
        """
        options can be:
            ["col1", "col2"]
            OR
            [("col1", "Column 1")]
            OR
            [{"value": "col1", "label": "Column 1"}]
        """

        # Clear layout
        while self._lay.count():
            item = self._lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._checkboxes.clear()

        # Normalize into (value, label)
        normalized = []

        for opt in options:
            if isinstance(opt, dict):
                value = opt.get("value")
                label = opt.get("label", value)
            elif isinstance(opt, tuple):
                value, label = opt
            else:
                value = opt
                label = opt

            normalized.append((value, label))

        # Build checkboxes
        for value, label in normalized:
            # FIX: Check if label already contains " AS " (from fetch_fields)
            # If so, use it as-is; otherwise, format it with value
            if label and label != value:
                if " AS " in label:
                    # Label already formatted (e.g., "column_name AS Comment")
                    display = label
                else:
                    # Label needs formatting
                    display = f"{value} AS {label}"
            else:
                display = value
            
            cb = QCheckBox(display)
            cb.setChecked(value in checked_set)
            cb.setEnabled(not self._disabled)

            # Store actual value (important!)
            cb._value = value

            cb.setStyleSheet(f"""
                QCheckBox {{
                    font-size: 13px;
                    color: {COLORS['text_primary']};
                    background: transparent;
                    border: none;
                    spacing: 8px;
                }}
                QCheckBox::indicator {{
                    width: 15px; height: 15px;
                    border: 1px solid {COLORS['border']};
                    border-radius: 3px;
                    background: {COLORS['white']};
                }}
                QCheckBox::indicator:checked {{
                    background: {COLORS['white']};
                    border-color: {COLORS['border']};
                    image: url({_CHECKMARK_SVG_PATH});
                }}
                QCheckBox::indicator:disabled {{
                    background: {COLORS['readonly_bg']};
                }}
            """)

            self._lay.addWidget(cb)

            # Key must be value (NOT label)
            self._checkboxes[value] = cb

    def get_value(self) -> list[str]:
        return [opt for opt, cb in self._checkboxes.items() if cb.isChecked()]

    def set_options(self, options, checked_options=None):
        """
        options:
            ["col1", "col2"]
            OR
            [{"value": "col1", "label": "Column 1"}]

        checked_options:
            ["col1", "col2"]
        """

        # Normalize options into (value, label)
        normalized = []
        for opt in options:
            if isinstance(opt, dict):
                value = opt.get("value")
                label = opt.get("label", value)
            else:
                value = opt
                label = opt
            normalized.append((value, label))

        # Only hash values (never dicts) — resolve any dict/non-str items to plain strings
        if checked_options is not None:
            resolved = []
            for opt in checked_options:
                if isinstance(opt, dict):
                    val = opt.get("value") or opt.get("name") or opt.get("id")  # try common key names
                    if val is None:
                        val = next(iter(opt.values()), None)                    # last resort: first value in dict
                    if val is not None and not isinstance(val, dict):
                        resolved.append(val)
                else:
                    resolved.append(opt)
            checked_set = set(resolved)
        else:
            checked_set = {value for value, _ in normalized}

        # Rebuild checkboxes
        self._build_checkboxes(normalized, checked_set)

        has_opts = bool(normalized)
        self._scroll.setVisible(has_opts)
        self._empty_lbl.setVisible(not has_opts)

    def set_all_enabled(self, enabled: bool):
        for cb in self._checkboxes.values():
            cb.setEnabled(enabled)
        self._inner.setStyleSheet(f"""
            QWidget {{
                background: {COLORS['white'] if enabled else COLORS['readonly_bg']};
                border: 1px solid {COLORS['border'] if enabled else COLORS['border_light']};
                border-radius: 6px;
            }}
        """)

    def select_all(self):
        for cb in self._checkboxes.values():
            cb.setChecked(True)

    def select_none(self):
        for cb in self._checkboxes.values():
            cb.setChecked(False)


# ==================================================================
# Tab select widget  (left / right pill-style toggle)
# ==================================================================

class _TabSelectWidget(QWidget):
    currentTextChanged = Signal(str)

    def __init__(self, options: list[str], parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._current = options[0] if options else ""

        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self._buttons: dict[str, QPushButton] = {}
        n = len(options)
        for i, opt in enumerate(options):
            btn = QPushButton(opt)
            btn.setFixedHeight(36)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            btn.clicked.connect(lambda _=False, o=opt: self._select(o))

            if n == 1:
                self._btn_radius = {opt: "6px"}
            elif i == 0:
                btn._tab_radius = "6px 0 0 6px"
            elif i == n - 1:
                btn._tab_radius = "0 6px 6px 0"
            else:
                btn._tab_radius = "0"

            self._buttons[opt] = btn
            lay.addWidget(btn)

        self._apply_styles()

    def _select(self, option: str, emit: bool = True):
        prev = self._current
        self._current = option
        self._apply_styles()
        if emit and option != prev:
            self.currentTextChanged.emit(option)

    def _apply_styles(self):
        options = self._options
        n = len(options)
        for i, opt in enumerate(options):
            btn = self._buttons[opt]
            selected = (opt == self._current)

            border_left = "none" if i > 0 else f"1px solid {COLORS['border']}"

            if i == 0:
                radius = "6px 0 0 6px"
            elif i == n - 1:
                radius = "0 6px 6px 0"
            else:
                radius = "0"

            if selected:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['dd_accent']};
                        color: white;
                        border-top:    1px solid {COLORS['dd_accent']};
                        border-bottom: 1px solid {COLORS['dd_accent']};
                        border-right:  1px solid {COLORS['dd_accent']};
                        border-left:   {border_left};
                        border-radius: {radius};
                        font-size: 13px;
                        font-weight: 600;
                        padding: 0 16px;
                    }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: {COLORS['white']};
                        color: {COLORS['text_secondary']};
                        border-top:    1px solid {COLORS['border']};
                        border-bottom: 1px solid {COLORS['border']};
                        border-right:  1px solid {COLORS['border']};
                        border-left:   {border_left};
                        border-radius: {radius};
                        font-size: 13px;
                        padding: 0 16px;
                    }}
                    QPushButton:hover {{
                        background: {COLORS['bg_main']};
                        color: {COLORS['text_primary']};
                    }}
                """)

    def currentText(self) -> str:
        return self._current

    def setCurrentText(self, text: str):
        if text in self._options:
            self._select(text, emit=False)

    def setDisabled(self, disabled: bool):
        super().setDisabled(disabled)
        for btn in self._buttons.values():
            btn.setEnabled(not disabled)
            btn.setCursor(Qt.ArrowCursor if disabled else Qt.PointingHandCursor)


# ==================================================================
# Main modal
# ==================================================================

class GenericFormModal(QDialog):
    formSubmitted = Signal(dict)
    fieldChanged  = Signal(str, str)
    opened        = Signal()
    closed        = Signal()

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

        self.mode         = mode
        self.initial_data = initial_data or {}

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
        self.setWindowFlags(
            Qt.Dialog | Qt.CustomizeWindowHint |
            Qt.WindowTitleHint | Qt.WindowCloseButtonHint
        )
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")

        self._build_ui(title, subtitle)
        self._populate_initial_data()

        self._opacity_fx = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_fx)
        self._opacity_fx.setOpacity(0.0)
        self._entrance_done = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_field_value(self, name: str) -> str:
        widget = self.inputs.get(name)
        if widget is None:
            return ""
        if isinstance(widget, QTextEdit):
            return widget.toPlainText().strip()
        if isinstance(widget, QLineEdit):
            return widget.text().strip()
        if isinstance(widget, _TabSelectWidget):
            return widget.currentText()
        if isinstance(widget, (AnimatedCombo, QComboBox)):
            return widget.currentText()
        if isinstance(widget, _CheckboxListWidget):
            return ",".join(widget.get_value())
        return ""

    def set_field_value(self, name: str, value: str):
        widget = self.inputs.get(name)
        if widget is None:
            return
        if isinstance(widget, QTextEdit):
            widget.setPlainText(value)
        elif isinstance(widget, QLineEdit):
            widget.setText(value)
        elif isinstance(widget, _TabSelectWidget):
            widget.setCurrentText(value)
        elif isinstance(widget, (AnimatedCombo, QComboBox)):
            widget.setCurrentText(value)

    def set_field_disabled(self, name: str, disabled: bool):
        widget = self.inputs.get(name)
        if widget is None:
            return

        if isinstance(widget, QTextEdit):
            widget.setReadOnly(disabled)
            if disabled:
                widget.setStyleSheet(f"""
                    QTextEdit {{
                        padding: 8px 12px;
                        border: 1px solid {COLORS['border_light']};
                        border-radius: 6px;
                        background-color: {COLORS['readonly_bg']};
                        color: {COLORS['text_muted']};
                        font-size: 13px;
                    }}
                """)
            else:
                widget.setStyleSheet(f"""
                    QTextEdit {{
                        padding: 8px 12px;
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        background-color: {COLORS['white']};
                        color: {COLORS['text_primary']};
                        font-size: 13px;
                    }}
                    QTextEdit:focus {{ border-color: {COLORS['link']}; }}
                """)

        elif isinstance(widget, QLineEdit):
            widget.setReadOnly(disabled)
            widget.setStyleSheet(
                self._readonly_line_edit_style() if disabled else self._style_input_str()
            )

        elif isinstance(widget, AnimatedCombo):
            widget.setDisabled(disabled)

        elif isinstance(widget, _TabSelectWidget):
            widget.setDisabled(disabled)

        elif isinstance(widget, _CheckboxListWidget):
            widget.set_all_enabled(not disabled)

        elif hasattr(widget, '_checkbox_widget'):
            cbw: _CheckboxListWidget = widget._checkbox_widget
            cbw.set_all_enabled(not disabled)
            for i in range(widget.layout().count()):
                item = widget.layout().itemAt(i)
                if item and item.layout():
                    sub = item.layout()
                    for j in range(sub.count()):
                        sub_item = sub.itemAt(j)
                        if sub_item and sub_item.widget():
                            sub_item.widget().setEnabled(not disabled)

        elif hasattr(widget, 'text_input'):
            widget.text_input.setReadOnly(disabled)
            widget.text_input.setStyleSheet(
                self._readonly_line_edit_style() if disabled else self._style_input_str()
            )
            widget.unit_combo.setDisabled(disabled)

    def update_field_options(self, name: str, options: list[str],
                             checked: list[str] | None = None):
        widget = self.inputs.get(name)
        if widget is None:
            return
        if isinstance(widget, _TabSelectWidget):
            return
        if isinstance(widget, _CheckboxListWidget):
            widget.set_options(options, checked)
        elif hasattr(widget, '_checkbox_widget'):
            widget._checkbox_widget.set_options(options, checked)
        elif isinstance(widget, AnimatedCombo):
            widget.clear()
            if options:
                widget.addItems(options)
                if not widget._placeholder:
                    widget._current = options[0]
                    widget._trigger.set_text(options[0])
                    if widget._panel:
                        widget._panel.set_options(options, options[0])
        elif isinstance(widget, QComboBox):
            widget.blockSignals(True)
            widget.clear()
            widget.addItems(options)
            widget.blockSignals(False)

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
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, subtitle: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

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
        root.addLayout(header_row)
        root.addSpacing(20)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(
            f"color: {COLORS['border_light']}; background-color: {COLORS['border_light']}; max-height: 1px;"
        )
        root.addWidget(divider)
        root.addSpacing(20)

        self._build_form_body(root)

    def _build_form_body(self, root: QVBoxLayout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(800)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setSingleStep(12)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: transparent; width: 6px; margin: 0; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 3px; min-height: 24px; }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::handle:vertical:pressed { background: #6B7280; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
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

            label_text = field.get("label", field["name"])
            comment_text = field.get("comment")

            if field.get("required") and self.mode != "view":
                label_text += " *"

            # Main label
            label_widget = QLabel(label_text)

            if field.get("type") == "readonly":
                label_widget.setStyleSheet(
                    f"color: {COLORS['readonly_text']}; font-size: 13px;"
                )
            else:
                label_widget.setStyleSheet("font-size: 13px; font-weight: 500;")

            # If comment exists → stack it under the label
            if comment_text:
                comment_label = QLabel(comment_text)
                comment_label.setWordWrap(True)
                comment_label.setStyleSheet("""
                    font-size: 11px;
                    color: #6B7280;
                    margin-top: 2px;
                """)

                label_container = QVBoxLayout()
                label_container.setSpacing(2)
                label_container.setContentsMargins(0, 0, 0, 0)
                label_container.addWidget(label_widget)
                label_container.addWidget(comment_label)

                label_wrapper = QWidget()
                label_wrapper.setLayout(label_container)

                form_layout.addRow(label_wrapper, widget)

            else:
                form_layout.addRow(label_widget, widget)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll)
        root.addSpacing(16)
        root.addStretch()

        if self.mode != "view":
            btn_row = QHBoxLayout()
            btn_row.setSpacing(8)
            btn_row.addStretch()

            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedHeight(36)
            cancel_btn.setCursor(Qt.PointingHandCursor)
            cancel_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                    min-width: 100px;
                    background-color: {COLORS['white']};
                    color: {COLORS['text_secondary']};
                    border: 1px solid {COLORS['border']};
                }}
                QPushButton:hover {{ background-color: {COLORS['bg_main']}; }}
            """)
            cancel_btn.clicked.connect(self.reject)

            submit_text = "Create" if self.mode == "add" else "Save Changes"
            submit_btn = QPushButton(submit_text)
            submit_btn.setFixedHeight(36)
            submit_btn.setCursor(Qt.PointingHandCursor)
            submit_btn.setStyleSheet(f"""
                QPushButton {{
                    padding: 8px 16px;
                    border-radius: 6px;
                    font-weight: 600;
                    font-size: 13px;
                    min-width: 100px;
                    background-color: {COLORS['link']};
                    color: white;
                    border: none;
                }}
                QPushButton:hover {{ background-color: #4F46E5; }}
            """)
            submit_btn.clicked.connect(self._on_submit)

            btn_row.addWidget(cancel_btn)
            btn_row.addWidget(submit_btn)
            root.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Widget factory
    # ------------------------------------------------------------------

    def _wrap_in_box(self, widget: QWidget) -> QWidget:
        box = QFrame()
        box.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['white']};
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
            }}
        """)
        box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(0)
        lay.addWidget(widget)
        return box

    def _create_form_widget(self, field: dict) -> QWidget:
        field_type = field.get("type", "text")
        editable   = (self.mode != "view") and (field_type != "readonly")

        if field_type in ("text", "readonly"):
            w = QLineEdit()
            w.setMinimumHeight(36)
            if editable:
                w.setPlaceholderText(field.get("placeholder", ""))
                self._style_input(w)
            else:
                w.setReadOnly(True)
                w.setPlaceholderText("")
                if field_type == "readonly":
                    w.setStyleSheet(self._readonly_line_edit_style())
                    w.setCursor(QCursor(Qt.ForbiddenCursor))
                else:
                    w.setStyleSheet(self._view_line_edit_style())
            return w

        elif field_type == "textarea":
            w = QTextEdit()
            height = field.get("height", 120)
            w.setFixedHeight(height)
            if editable:
                w.setPlaceholderText(field.get("placeholder", ""))
                w.setStyleSheet(f"""
                    QTextEdit {{
                        padding: 8px 12px;
                        border: 1px solid {COLORS['border']};
                        border-radius: 6px;
                        background-color: {COLORS['white']};
                        color: {COLORS['text_primary']};
                        font-size: 13px;
                    }}
                    QTextEdit:focus {{ border-color: {COLORS['link']}; }}
                """)
            else:
                w.setReadOnly(True)
                w.setStyleSheet(f"""
                    QTextEdit {{
                        padding: 8px 12px;
                        border: 1px solid {COLORS['border_light']};
                        border-radius: 6px;
                        background-color: {COLORS['readonly_bg']};
                        color: {COLORS['text_primary']};
                        font-size: 13px;
                    }}
                """)
            return w

        elif field_type in ("combo", "select"):
            options     = field.get("options", [])
            placeholder = field.get("placeholder", "")
            w = AnimatedCombo(options, placeholder=placeholder)
            if editable:
                w.currentTextChanged.connect(
                    lambda val, fname=field["name"]: self.fieldChanged.emit(fname, val)
                )
            else:
                w.setDisabled(True)
            return w

        elif field_type == "tab_select":
            options = field.get("options", [])
            w = _TabSelectWidget(options)
            if editable:
                w.currentTextChanged.connect(
                    lambda val, fname=field["name"]: self.fieldChanged.emit(fname, val)
                )
            else:
                w.setDisabled(True)
            return w

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
                w.currentTextChanged.connect(
                    lambda val, fname=field["name"]: self.fieldChanged.emit(fname, val)
                )
            else:
                w.setDisabled(True)
            return w

        elif field_type == "checkbox_list":
            options         = field.get("options", [])
            initial_checked = field.get("initial_checked", {})
            checked_list    = [k for k, v in initial_checked.items() if v] if initial_checked else options

            w = _CheckboxListWidget(
                options=options,
                checked_options=checked_list,
                disabled=not editable,
            )

            if editable:
                container = QWidget()
                container.setStyleSheet("background: transparent;")
                container.setMinimumHeight(230)
                vlay = QVBoxLayout(container)
                vlay.setContentsMargins(0, 0, 0, 0)
                vlay.setSpacing(4)

                btn_row = QHBoxLayout()
                btn_row.setSpacing(6)

                # ── Clean pill-chip buttons ────────────────────────────
                def _btn(label, slot):
                    b = QPushButton(label)
                    b.setFixedHeight(22)
                    b.setCursor(Qt.PointingHandCursor)
                    b.setStyleSheet(f"""
                        QPushButton {{
                            font-size: 11px;
                            font-weight: 600;
                            color: {COLORS['dd_accent']};
                            background: {COLORS['dd_accent_bg']};
                            border: 1px solid #C7D2FE;
                            border-radius: 11px;
                            padding: 0 10px;
                        }}
                        QPushButton:hover {{
                            background: #E0E7FF;
                            border-color: {COLORS['dd_accent']};
                        }}
                        QPushButton:pressed {{
                            background: #C7D2FE;
                        }}
                    """)
                    b.clicked.connect(slot)
                    return b

                self._select_all_btn  = _btn("Select All",  w.select_all)
                self._select_none_btn = _btn("Select None", w.select_none)
                # Hidden until a table name is selected
                self._select_all_btn.setVisible(False)
                self._select_none_btn.setVisible(False)
                btn_row.addWidget(self._select_all_btn)
                btn_row.addWidget(self._select_none_btn)
                btn_row.addStretch()

                vlay.addLayout(btn_row)
                vlay.addWidget(w)

                container._checkbox_widget = w
                container.get_value        = w.get_value
                container.set_options      = w.set_options

                _a, _n = self._select_all_btn, self._select_none_btn
                container.set_actions_visible = lambda vis, a=_a, n=_n: (
                    a.setVisible(vis), n.setVisible(vis)
                )
                return container

            return self._wrap_in_box(w)

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
                hl = QHBoxLayout(cell)
                hl.setContentsMargins(0, 0, 0, 0)
                hl.setSpacing(6)

                inp = QLineEdit()
                inp.setMinimumHeight(36)
                inp.setFixedWidth(120)  # optional: keeps both sides balanced

                if editable:
                    inp.setPlaceholderText(placeholder)
                    self._style_input(inp)
                else:
                    inp.setReadOnly(True)
                    inp.setStyleSheet(self._view_line_edit_style())

                header_lbl = QLabel(label_text)
                header_lbl.setFixedWidth(40)
                header_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                header_lbl.setStyleSheet(
                    f"""
                    font-size: 11px;
                    font-weight: 600;
                    color: {COLORS['text_muted']};
                    letter-spacing: 0.04em;
                    background: transparent;
                    """
                )

                err_lbl = QLabel("")
                err_lbl.setStyleSheet("font-size: 11px; color: #EF4444; background: transparent;")
                err_lbl.setVisible(False)

                # input + error stacked
                input_container = QWidget()
                vl = QVBoxLayout(input_container)
                vl.setContentsMargins(0, 0, 0, 0)
                vl.setSpacing(2)
                vl.addWidget(inp)
                vl.addWidget(err_lbl)

                # 🔁 Reversed order (box first, label second)
                hl.addWidget(input_container)
                hl.addWidget(header_lbl)

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
                from PySide6.QtCore import QLocale
                inch_validator = QDoubleValidator(0.0001, 99999.0, 4)
                inch_validator.setLocale(QLocale(QLocale.English))
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

    def _style_input_str(self) -> str:
        return f"""
            QLineEdit {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                background-color: {COLORS['white']};
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {COLORS['link']}; }}
        """

    def _view_line_edit_style(self) -> str:
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

        new_child_val = child_options[0] if child_options else ""
        self.fieldChanged.emit(child_name, new_child_val)

    # ------------------------------------------------------------------
    # Populate initial data
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

            if isinstance(widget, QTextEdit):
                widget.setPlainText(str(value))
            elif isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, _TabSelectWidget):
                widget.setCurrentText(str(value))
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
    # Validate / collect / submit
    # ------------------------------------------------------------------

    def _validate(self) -> list[str]:
        errors = []
        for field in self.fields_config:
            if field.get("type") in ("readonly", "checkbox_list"):
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

            elif isinstance(widget, QTextEdit):
                if widget.isReadOnly():
                    continue
                if is_required and not widget.toPlainText().strip():
                    errors.append(f"{label} is required")
                    widget.setStyleSheet(f"""
                        QTextEdit {{
                            padding: 8px 12px; border: 1.5px solid #EF4444;
                            border-radius: 6px; background-color: #FEF2F2;
                            color: {COLORS['text_primary']}; font-size: 13px;
                        }}
                    """)
                else:
                    widget.setStyleSheet(f"""
                        QTextEdit {{
                            padding: 8px 12px; border: 1px solid {COLORS['border']};
                            border-radius: 6px; background-color: {COLORS['white']};
                            color: {COLORS['text_primary']}; font-size: 13px;
                        }}
                    """)

            elif isinstance(widget, QLineEdit):
                if widget.isReadOnly():
                    continue
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
                if isinstance(widget, AnimatedCombo) and not widget.isEnabled():
                    continue
                if is_required and not widget.currentText():
                    errors.append(f"{label} is required")

            elif isinstance(widget, _TabSelectWidget):
                pass

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
            elif isinstance(widget, QTextEdit):
                data[name] = widget.toPlainText().strip()
            elif isinstance(widget, QLineEdit):
                data[name] = widget.text().strip()
            elif isinstance(widget, _TabSelectWidget):
                data[name] = widget.currentText()
            elif isinstance(widget, (AnimatedCombo, QComboBox)):
                data[name] = widget.currentText()
            elif isinstance(widget, _CheckboxListWidget):
                data[name] = widget.get_value()
            elif hasattr(widget, "get_value"):
                data[name] = widget.get_value()
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


GenericModal = GenericFormModal