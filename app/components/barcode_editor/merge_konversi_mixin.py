"""Mixin for MERGE and KONVERSI TIMBANGAN type logic in TextPropertyEditor."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MergeKonversiMixin:
    """
    Mixin for TextPropertyEditor.

    design_merge stores a TEMPLATE string where label variables are wrapped in
    curly braces, e.g.:  "Hello {Label3} your value is {Label8}!"
    Plain text outside the braces is literal.  Empty string = nothing.

    At print-time call MergeKonversiMixin.resolve_merge(item, scene_items)
    to substitute each {LabelX} with its current canvas value.

    Migration note: old comma-separated format "Label3,Label8" is handled
    gracefully by MergeInputWidget.set_selected() — it converts on load.
    """

    def enable_for_merge(self, enabled: bool):
        if not enabled:
            self.merge_combo.clear_all()
            self.item.design_merge = ""
        self.merge_combo.setEnabled(enabled)

    def enable_for_konversi(self, enabled: bool):
        for combo in (self.timbangan_combo, self.weight_combo, self.um_combo):
            combo.setEnabled(enabled)
        if not enabled:
            for combo in (self.timbangan_combo, self.weight_combo, self.um_combo):
                combo.setCurrentIndex(-1)
            self.item.design_timbangan = ""
            self.item.design_weight    = ""
            self.item.design_um        = ""

    def _on_merge_changed(self, value):
        if isinstance(value, list):
            return
        self.item.design_merge = value

    def _on_timbangan_changed(self, v: str):
        self.item.design_timbangan = v if v not in ("", "—") else ""

    def _on_weight_changed(self, v: str):
        self.item.design_weight = v if v not in ("", "—") else ""

    def _on_um_changed(self, v: str):
        self.item.design_um = v if v not in ("", "—") else ""

    @staticmethod
    def resolve_merge(item, scene_items, separator: str = "") -> str:
        raw = getattr(item, "design_merge", "") or ""
        if not raw:
            return item.toPlainText()

        name_to_value: dict[str, str] = {}
        for si in scene_items:
            cname = getattr(si, "component_name", "")
            if not cname or si is item:
                continue
            try:
                name_to_value[cname] = si.toPlainText()
            except AttributeError:
                pass

        def _sub(m: re.Match) -> str:
            label = m.group(1)
            return name_to_value.get(label, f"{{{label}}}")

        result = re.sub(r"\{([^}]+)\}", _sub, raw)
        return result if result else item.toPlainText()


# ── Imports ───────────────────────────────────────────────────────────────────

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy,
    QAbstractItemView, QTextEdit, QScrollArea, QLineEdit,
)
from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPixmap, QPainter, QPen, QIcon,
    QTextCharFormat, QTextCursor, QKeyEvent, QTextOption,
)


# ── MultiSelectCombo — kept for backward-compat ───────────────────────────────

class MultiSelectCombo(QWidget):
    """Kept for backward-compatibility — MERGE WITH now uses MergeInputWidget."""

    selectionChanged = Signal(list)

    def __init__(self, placeholder: str = "— select components —", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._items: list[str] = []
        self._selected: list[str] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignTop)

        self._tag_frame = QFrame()
        self._tag_frame.setMinimumHeight(28)
        self._tag_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._tag_frame.setStyleSheet(
            "QFrame{background:#FFFFFF;border:1px solid #E2E8F0;border-radius:6px;}"
        )
        self._tag_layout = QHBoxLayout(self._tag_frame)
        self._tag_layout.setContentsMargins(6, 3, 6, 3)
        self._tag_layout.setSpacing(4)
        self._tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        lbl = QLabel(placeholder)
        lbl.setStyleSheet("color:#94A3B8;font-size:9pt;background:transparent;border:none;")
        self._tag_layout.addWidget(lbl)
        outer.addWidget(self._tag_frame)

    def set_items(self, names):
        self._items = list(names)

    def set_selected(self, names):
        if isinstance(names, str):
            names = [n.strip() for n in names.split(",") if n.strip()]
        self._selected = [n for n in names if n in self._items]

    def get_selected(self):
        return list(self._selected)

    def clear_selection(self):
        self._selected = []

    def setEnabled(self, enabled):
        super().setEnabled(enabled)


# ── _LabelPickerPanel ─────────────────────────────────────────────────────────

class _LabelPickerPanel(QFrame):
    """Compact floating panel — click a label to insert it at the cursor."""

    labelChosen = Signal(str)

    def __init__(self, items: list[str], parent_widget: QWidget):
        super().__init__(parent_widget.window(), Qt.Popup | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._items = list(items)
        self.setObjectName("labelPickerPanel")
        self.setStyleSheet("""
            QFrame#labelPickerPanel {
                background: #FFFFFF;
                border: 1px solid #C7D2FE;
                border-radius: 10px;
            }
        """)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(5)

        hdr = QLabel("Insert label variable")
        hdr.setStyleSheet(
            "color:#6366F1;font-size:9px;font-weight:700;letter-spacing:0.5px;"
            "background:transparent;border:none;"
        )
        root.addWidget(hdr)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedHeight(26)
        self._search.setClearButtonEnabled(True)
        self._search.setStyleSheet("""
            QLineEdit {
                background:#F8FAFC; border:1px solid #E2E8F0;
                border-radius:5px; padding:0 7px;
                font-size:10px; color:#1E293B;
            }
            QLineEdit:focus { border-color:#6366F1; background:#FFFFFF; }
        """)
        self._search.textChanged.connect(self._filter)
        root.addWidget(self._search)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("""
            QScrollArea { background:transparent; border:none; }
            QScrollBar:vertical {
                background:#F1F5F9; width:5px; border-radius:2px;
            }
            QScrollBar::handle:vertical {
                background:#94A3B8; border-radius:2px; min-height:16px;
            }
            QScrollBar::handle:vertical:hover { background:#6366F1; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)
        self._btn_container = QWidget()
        self._btn_container.setStyleSheet("background:transparent;")
        self._btn_layout = QVBoxLayout(self._btn_container)
        self._btn_layout.setContentsMargins(0, 0, 0, 0)
        self._btn_layout.setSpacing(2)
        self._scroll.setWidget(self._btn_container)
        root.addWidget(self._scroll)

        self._rebuild_buttons(self._items)

    def _rebuild_buttons(self, items: list[str]):
        while self._btn_layout.count():
            child = self._btn_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for name in items:
            btn = QPushButton(f"  {{{name}}}")
            btn.setFixedHeight(26)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setFocusPolicy(Qt.NoFocus)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent; border: none; border-radius: 5px;
                    color: #334155; font-size: 10px; font-weight: 500;
                    text-align: left; padding: 0 6px;
                }
                QPushButton:hover {
                    background: #EEF2FF; color: #4338CA; font-weight: 600;
                }
            """)
            btn.clicked.connect(lambda checked=False, n=name: self._pick(n))
            self._btn_layout.addWidget(btn)

        n = len(items)
        self._scroll.setFixedHeight(min(max(n, 1) * 28 + 4, 180))
        self.adjustSize()

    def _filter(self, text: str):
        q = text.lower()
        filtered = [it for it in self._items if q in it.lower()] if q else self._items
        self._rebuild_buttons(filtered)

    def _pick(self, name: str):
        self.labelChosen.emit(name)
        self.close()


# ── Property key used to mark chip fragments ──────────────────────────────────
_CHIP_PROP = QTextCharFormat.UserProperty + 1


# ── _ChipTextEdit ─────────────────────────────────────────────────────────────

class _ChipTextEdit(QTextEdit):
    """
    Multi-line text editor where:
    - Users can type freely anywhere between chips.
    - {LabelName} chips are protected: cursor skips over them,
      and they are deleted as a whole unit (not character-by-character).
    - Chips are inserted via insert_chip(name) only (from the picker).
    - Emits templateChanged(str) on every change.
    """

    templateChanged = Signal(str)

    _CHIP_BG = "#EEF2FF"
    _CHIP_FG = "#4338CA"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._programmatic = False

        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setMinimumHeight(60)
        self.setMaximumHeight(120)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._apply_base_style(focused=False)

        self.document().contentsChanged.connect(self._on_contents_changed)
        self.cursorPositionChanged.connect(self._on_cursor_moved)

    # ── style ─────────────────────────────────────────────────────────────────

    def _apply_base_style(self, focused: bool):
        border = "#6366F1" if focused else "#E2E8F0"
        self.setStyleSheet(f"""
            QTextEdit {{
                background: #FFFFFF;
                border: 1px solid {border};
                border-right: none;
                border-top-left-radius: 6px;
                border-bottom-left-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                color: #1E293B;
                selection-background-color: #C7D2FE;
            }}
            QTextEdit:disabled {{
                background: #F8FAFC;
                color: #94A3B8;
                border-color: #E2E8F0;
            }}
        """)

    # ── chip helpers ──────────────────────────────────────────────────────────

    @staticmethod
    def _is_chip_fmt(fmt: QTextCharFormat) -> bool:
        return bool(fmt.property(_CHIP_PROP))

    def _chip_span_at(self, pos: int) -> tuple[int, int] | None:
        """
        Return (start, end) of the chip fragment containing document
        position `pos`, or None if `pos` is not inside a chip.
        """
        doc = self.document()
        block = doc.findBlock(pos)
        if not block.isValid():
            return None
        frag_start = block.position()
        it = block.begin()
        while not it.atEnd():
            frag = it.fragment()
            frag_end = frag_start + frag.length()
            if frag_start <= pos < frag_end and self._is_chip_fmt(frag.charFormat()):
                return frag_start, frag_end
            frag_start = frag_end
            it += 1
        return None

    def _skip_into_chip(self, cursor: QTextCursor):
        """If the cursor is inside a chip, jump it just past the chip end."""
        pos = cursor.position()
        span = self._chip_span_at(pos)
        if span:
            cursor.setPosition(span[1])
            self.setTextCursor(cursor)

    # ── public API ────────────────────────────────────────────────────────────

    def set_template(self, template: str):
        """Load a raw template, rendering {Name} tokens as chips."""
        self._programmatic = True
        self.clear()
        cursor = self.textCursor()
        cursor.setCharFormat(self._plain_fmt())

        for segment in re.split(r"(\{[^}]+\})", template):
            if not segment:
                continue
            m = re.fullmatch(r"\{([^}]+)\}", segment)
            if m:
                self._insert_chip_at(cursor, m.group(1))
            else:
                cursor.setCharFormat(self._plain_fmt())
                cursor.insertText(segment)

        self._programmatic = False

    def insert_chip(self, name: str):
        """Insert a chip at the current cursor (called by the ⋯ picker)."""
        cursor = self.textCursor()
        # Push cursor out of any chip it may be inside
        span = self._chip_span_at(cursor.position())
        if span:
            cursor.setPosition(span[1])
        self._insert_chip_at(cursor, name)
        self.setFocus()

    def get_template(self) -> str:
        return self._extract_template()

    # ── internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _plain_fmt() -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#1E293B"))
        fmt.setBackground(QColor("#FFFFFF"))
        fmt.setFontWeight(QFont.Normal)
        fmt.setProperty(_CHIP_PROP, "")  # empty string = not a chip
        return fmt

    def _chip_fmt(self, name: str) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(self._CHIP_FG))
        fmt.setBackground(QColor(self._CHIP_BG))
        fmt.setFontWeight(QFont.Bold)
        fmt.setProperty(_CHIP_PROP, name)  # non-empty = is a chip
        return fmt

    def _insert_chip_at(self, cursor: QTextCursor, name: str):
        cursor.setCharFormat(self._chip_fmt(name))
        cursor.insertText(f"{{{name}}}")
        # Always reset to plain format after a chip
        cursor.setCharFormat(self._plain_fmt())
        cursor.insertText("")
        self.setTextCursor(cursor)

    def _extract_template(self) -> str:
        doc = self.document()
        result = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    result.append(frag.text())
                it += 1
            block = block.next()
            if block.isValid():
                result.append("\n")
        return "".join(result).rstrip("\n")

    def _on_contents_changed(self):
        if self._programmatic:
            return
        self.templateChanged.emit(self._extract_template())

    def _on_cursor_moved(self):
        """Prevent cursor from resting inside a chip."""
        cursor = self.textCursor()
        if cursor.hasSelection():
            return
        self._skip_into_chip(cursor)

    # ── keyboard handling ─────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        cursor = self.textCursor()

        # ── Backspace ─────────────────────────────────────────────────────────
        if event.key() == Qt.Key_Backspace:
            if cursor.hasSelection():
                self._delete_selection(cursor)
                event.accept()
                return
            pos = cursor.position()
            if pos == 0:
                event.ignore()
                return
            # Is the character immediately before the cursor part of a chip?
            span = self._chip_span_at(pos - 1)
            if span:
                c = self.textCursor()
                c.setPosition(span[0])
                c.setPosition(span[1], QTextCursor.KeepAnchor)
                c.removeSelectedText()
                self.setTextCursor(c)
                event.accept()
                return
            super().keyPressEvent(event)
            return

        # ── Delete ────────────────────────────────────────────────────────────
        if event.key() == Qt.Key_Delete:
            if cursor.hasSelection():
                self._delete_selection(cursor)
                event.accept()
                return
            pos = cursor.position()
            span = self._chip_span_at(pos)
            if span:
                c = self.textCursor()
                c.setPosition(span[0])
                c.setPosition(span[1], QTextCursor.KeepAnchor)
                c.removeSelectedText()
                self.setTextCursor(c)
                event.accept()
                return
            super().keyPressEvent(event)
            return

        # ── Left arrow — skip backward over chips ─────────────────────────────
        if event.key() == Qt.Key_Left:
            super().keyPressEvent(event)
            cursor = self.textCursor()
            if not cursor.hasSelection():
                span = self._chip_span_at(cursor.position())
                if span:
                    cursor.setPosition(span[0])
                    self.setTextCursor(cursor)
            event.accept()
            return

        # ── Right arrow — skip forward over chips ─────────────────────────────
        if event.key() == Qt.Key_Right:
            super().keyPressEvent(event)
            cursor = self.textCursor()
            if not cursor.hasSelection():
                span = self._chip_span_at(cursor.position())
                if span:
                    cursor.setPosition(span[1])
                    self.setTextCursor(cursor)
            event.accept()
            return

        # ── Any printable character — ensure plain format ─────────────────────
        if event.text() and event.text().isprintable():
            pos = cursor.position()
            span = self._chip_span_at(pos)
            if span:
                cursor.setPosition(span[1])
                self.setTextCursor(cursor)
            cursor = self.textCursor()
            cursor.setCharFormat(self._plain_fmt())
            self.setTextCursor(cursor)

        super().keyPressEvent(event)

    def _delete_selection(self, cursor: QTextCursor):
        """Delete the current selection, treating chips as atomic units."""
        sel_start = cursor.selectionStart()
        sel_end   = cursor.selectionEnd()

        # Expand to cover any partially-selected chips
        start_span = self._chip_span_at(sel_start)
        if start_span and start_span[0] < sel_start:
            sel_start = start_span[0]

        end_span = self._chip_span_at(sel_end - 1) if sel_end > 0 else None
        if end_span and end_span[1] > sel_end:
            sel_end = end_span[1]

        c = self.textCursor()
        c.setPosition(sel_start)
        c.setPosition(sel_end, QTextCursor.KeepAnchor)
        c.removeSelectedText()
        self.setTextCursor(c)

    # ── Paste — strip any {Token} from pasted text to avoid fake chips ─────────

    def insertFromMimeData(self, source):
        if source.hasText():
            cursor = self.textCursor()
            cursor.setCharFormat(self._plain_fmt())
            plain = re.sub(r"\{[^}]+\}", "", source.text())
            cursor.insertText(plain)

    # ── focus style ───────────────────────────────────────────────────────────

    def focusInEvent(self, event):
        self._apply_base_style(focused=True)
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._apply_base_style(focused=False)
        super().focusOutEvent(event)


# ── MergeInputWidget ──────────────────────────────────────────────────────────

class MergeInputWidget(QWidget):
    """
    MERGE WITH field.

    - Free text can be typed anywhere.
    - {LabelName} chips are inserted via the ⋯ picker button.
    - Chips cannot be edited by typing — they are deleted as whole units.
    - Backspace/Delete next to a chip removes the entire chip.
    - Arrow keys skip over chips rather than entering them.

    Public API (drop-in compatible with old InlineChecklistWidget / MultiSelectCombo):
        set_items(list[str])
        set_template(str)
        set_selected(str | list)
        get_template() -> str
        get_selected() -> list[str]
        clear_all() / clear_selection()
        setEnabled(bool)
        templateChanged  Signal(str)
        selectionChanged Signal(list)   — compat shim
    """

    templateChanged  = Signal(str)
    selectionChanged = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._picker: _LabelPickerPanel | None = None
        self._enabled = True

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(3)

        self._editor = _ChipTextEdit(self)
        self._editor.templateChanged.connect(self._on_editor_changed)

        self._pick_btn = QPushButton("⋯  Insert Label")
        self._pick_btn.setFixedHeight(24)
        self._pick_btn.setCursor(Qt.PointingHandCursor)
        self._pick_btn.setFocusPolicy(Qt.NoFocus)
        self._pick_btn.setToolTip("Insert a label variable")
        self._pick_btn.setStyleSheet(self._btn_style(False))
        self._pick_btn.clicked.connect(self._toggle_picker)

        root.addWidget(self._editor)
        root.addWidget(self._pick_btn)

    # ── styles ────────────────────────────────────────────────────────────────

    def _btn_style(self, active: bool) -> str:
        if active:
            return """QPushButton {
                background:#EEF2FF; border:1px solid #6366F1;
                border-radius:5px;
                color:#4338CA; font-size:11px; font-weight:600;
                min-height:24px; max-height:24px;
                padding: 0 8px;
            }
            QPushButton:hover { background:#E0E7FF; }"""
        return """QPushButton {
            background:#F8FAFC; border:1px solid #E2E8F0;
            border-radius:5px;
            color:#94A3B8; font-size:11px; font-weight:500;
            min-height:24px; max-height:24px;
            padding: 0 8px;
        }
        QPushButton:hover { background:#EEF2FF; border-color:#6366F1; color:#4338CA; }"""

    def _btn_style_disabled(self) -> str:
        return """QPushButton {
            background:#F1F5F9; border:1px solid #E2E8F0;
            border-radius:5px;
            color:#CBD5E1; font-size:11px; font-weight:500;
            min-height:24px; max-height:24px;
            padding: 0 8px;
        }"""

    # ── picker ────────────────────────────────────────────────────────────────

    def _toggle_picker(self):
        if not self._enabled:
            return
        if self._picker and self._picker.isVisible():
            self._close_picker()
        else:
            self._open_picker()

    def _open_picker(self):
        if not self._items:
            return
        self._close_picker()

        from PySide6.QtWidgets import QApplication
        p = _LabelPickerPanel(self._items, self)
        p.labelChosen.connect(self._on_label_chosen)
        p.setAttribute(Qt.WA_DeleteOnClose, True)
        p.setFixedWidth(max(200, self.width()))
        p.adjustSize()

        gpos = self.mapToGlobal(QPoint(0, self.height() + 2))
        screen = QApplication.primaryScreen().availableGeometry()
        if gpos.y() + p.height() > screen.bottom():
            gpos.setY(self.mapToGlobal(QPoint(0, -p.height() - 2)).y())
        p.move(gpos)
        p.show()
        p.installEventFilter(self)
        self._picker = p
        self._pick_btn.setStyleSheet(self._btn_style(True))

    def _close_picker(self):
        if self._picker:
            try:
                self._picker.close()
            except Exception:
                pass
            self._picker = None
        if self._enabled:
            self._pick_btn.setStyleSheet(self._btn_style(False))

    def _on_label_chosen(self, name: str):
        self._editor.insert_chip(name)
        self._close_picker()

    def _on_editor_changed(self, template: str):
        self.templateChanged.emit(template)

    # ── event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if self._picker and obj is self._picker:
            if event.type() == QEvent.Close:
                self._picker = None
                if self._enabled:
                    self._pick_btn.setStyleSheet(self._btn_style(False))
        return super().eventFilter(obj, event)

    # ── public API ────────────────────────────────────────────────────────────

    def set_items(self, items: list[str]):
        self._items = list(items)
        if self._picker and self._picker.isVisible():
            self._picker._items = list(items)
            self._picker._filter(self._picker._search.text())

    def set_template(self, template: str):
        self._editor.set_template(template)

    def set_selected(self, value):
        """
        Compat shim.
        - Template string (contains {) → load as-is.
        - Old comma-separated "Label3,Label8" → "{Label3} {Label8}".
        """
        if isinstance(value, list):
            template = " ".join(f"{{{n}}}" for n in value if n)
            self.set_template(template)
        elif isinstance(value, str):
            if "{" in value or not value:
                self.set_template(value)
            else:
                names = [n.strip() for n in value.split(",") if n.strip()]
                template = " ".join(f"{{{n}}}" for n in names)
                self.set_template(template)

    def get_selected(self) -> list[str]:
        """Compat: return unique label names referenced in the template."""
        return list(dict.fromkeys(re.findall(r"\{([^}]+)\}", self.get_template())))

    def get_template(self) -> str:
        return self._editor.get_template()

    def clear_all(self):
        self._editor.set_template("")

    def clear_selection(self):
        self.clear_all()

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self._enabled = enabled
        self._editor.setEnabled(enabled)
        if not enabled:
            self._close_picker()
            self._pick_btn.setStyleSheet(self._btn_style_disabled())
            self._pick_btn.setCursor(Qt.ArrowCursor)
        else:
            self._pick_btn.setStyleSheet(self._btn_style(False))
            self._pick_btn.setCursor(Qt.PointingHandCursor)