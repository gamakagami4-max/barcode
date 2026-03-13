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




# ── Imports for the editor ────────────────────────────────────────────────────

from PySide6.QtWidgets import (
    QSizePolicy, QScrollArea, QLineEdit, QApplication, QTextEdit,
)
from PySide6.QtCore import Qt, Signal, QEvent, QPoint, QTimer
from PySide6.QtGui  import (
    QFont, QColor, QTextCharFormat, QTextCursor,
    QKeyEvent, QTextOption, QPainter, QPen, QBrush,
)

import re as _re

# Property key: non-empty string = chip name, empty/absent = plain text
_CHIP_PROP = QTextCharFormat.UserProperty + 1

_CHIP_BG     = QColor("#EEF2FF")
_CHIP_FG     = QColor("#4338CA")
_CHIP_BORDER = QColor("#C7D2FE")


def _plain_fmt() -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor("#1E293B"))
    f.setBackground(QColor("#FFFFFF"))
    f.setFontWeight(QFont.Normal)
    f.setProperty(_CHIP_PROP, "")
    return f


def _chip_fmt(name: str) -> QTextCharFormat:
    f = QTextCharFormat()
    f.setForeground(QColor("#1E293B"))
    f.setBackground(QColor("#FFFFFF"))
    f.setFontWeight(QFont.Normal)
    f.setProperty(_CHIP_PROP, name)
    return f


# ── _MergeEdit ────────────────────────────────────────────────────────────────

class _MergeEdit(QTextEdit):
    """
    Single QTextEdit where {Label} chips live inline as coloured spans.

    Rules:
    - Free text can be typed anywhere outside a chip.
    - Cursor cannot rest *inside* a chip — it is pushed to the chip boundary.
    - Backspace / Delete next to a chip removes the whole chip atomically.
    - Left/Right arrows skip over chips as a unit.
    - Chips are inserted programmatically via insert_chip(name).
    - Pasted text has {…} patterns stripped so fake chips can't be pasted in.
    - The × button for each chip is drawn by _MergeInputWidget as an overlay;
      this class exposes chip_rects() so the overlay knows where to draw.

    Emits templateChanged(str) on every document change.
    """

    templateChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._programmatic = False

        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setMinimumHeight(72)
        self.setMaximumHeight(140)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.setStyleSheet("""
            QTextEdit {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 11px;
                color: #1E293B;
                selection-background-color: #C7D2FE;
            }
            QTextEdit:focus {
                border: 1px solid #6366F1;
            }
            QTextEdit:disabled {
                background: #F8FAFC;
                color: #94A3B8;
                border-color: #E2E8F0;
            }
        """)

        self.document().contentsChanged.connect(self._on_changed)
        self.cursorPositionChanged.connect(self._guard_cursor)

    # ── public ────────────────────────────────────────────────────────────────

    def set_template(self, template: str):
        self._programmatic = True
        self.setReadOnly(False)
        self.clear()
        cur = self.textCursor()
        cur.setCharFormat(_plain_fmt())
        for seg in _re.split(r"(\{[^}]+\})", template):
            if not seg:
                continue
            m = _re.fullmatch(r"\{([^}]+)\}", seg)
            if m:
                _insert_chip(cur, m.group(1))
            else:
                cur.setCharFormat(_plain_fmt())
                cur.insertText(seg)
        self.setTextCursor(cur)
        self._programmatic = False

    def insert_chip(self, name: str):
        self.setReadOnly(False)
        cur = self.textCursor()
        # If cursor is inside a chip, push to end of chip first
        span = _chip_span_at(self.document(), cur.position())
        if span:
            cur.setPosition(span[1])
        _insert_chip(cur, name)
        self.setTextCursor(cur)
        self.setFocus()
        self.templateChanged.emit(self._extract())

    def get_template(self) -> str:
        return self._extract()

    def chip_spans(self) -> list[tuple[str, int, int]]:
        """Return [(name, doc_start, doc_end), ...] for every chip in doc order."""
        result = []
        doc = self.document()
        block = doc.begin()
        while block.isValid():
            pos = block.position()
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                name = frag.charFormat().property(_CHIP_PROP)
                if name:
                    result.append((name, pos, pos + frag.length()))
                pos += frag.length()
                it += 1
            block = block.next()
        return result

    def remove_chip_at(self, doc_start: int, doc_end: int):
        """Remove the chip spanning [doc_start, doc_end) and emit templateChanged."""
        self.setReadOnly(False)
        cur = self.textCursor()
        cur.setPosition(doc_start)
        cur.setPosition(doc_end, QTextCursor.KeepAnchor)
        cur.setCharFormat(_plain_fmt())
        cur.removeSelectedText()
        # Reset format so typing after removal stays plain
        cur.setCharFormat(_plain_fmt())
        self.setTextCursor(cur)
        self.setReadOnly(False)
        self.templateChanged.emit(self._extract())

    # ── internals ─────────────────────────────────────────────────────────────

    def _extract(self) -> str:
        doc = self.document()
        parts = []
        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    parts.append(frag.text())
                it += 1
            block = block.next()
            if block.isValid():
                parts.append("\n")
        return "".join(parts).rstrip("\n")

    def _on_changed(self):
        if self._programmatic:
            return
        self.templateChanged.emit(self._extract())

    def _guard_cursor(self):
        """Push cursor out of chip interior on every cursor move."""
        cur = self.textCursor()
        if cur.hasSelection():
            return
        span = _chip_span_at(self.document(), cur.position())
        if span:
            # Move to whichever end is closer
            pos = cur.position()
            dist_left  = pos - span[0]
            dist_right = span[1] - pos
            cur.setPosition(span[0] if dist_left <= dist_right else span[1])
            self.blockSignals(True)
            self.setTextCursor(cur)
            self.blockSignals(False)

    # ── keyboard ──────────────────────────────────────────────────────────────

    def keyPressEvent(self, event: QKeyEvent):
        cur = self.textCursor()

        if event.key() == Qt.Key_Backspace:
            if cur.hasSelection():
                _delete_selection_safe(self, cur)
                event.accept(); return
            pos = cur.position()
            if pos == 0:
                event.ignore(); return
            span = _chip_span_at(self.document(), pos - 1)
            if span:
                _delete_span(self, span)
                event.accept(); return
            # Plain backspace — ensure format stays plain after deletion
            super().keyPressEvent(event)
            self._ensure_plain_fmt()
            return

        if event.key() == Qt.Key_Delete:
            if cur.hasSelection():
                _delete_selection_safe(self, cur)
                event.accept(); return
            pos = cur.position()
            span = _chip_span_at(self.document(), pos)
            if span:
                _delete_span(self, span)
                event.accept(); return
            super().keyPressEvent(event)
            self._ensure_plain_fmt()
            return

        if event.key() == Qt.Key_Left:
            super().keyPressEvent(event)
            cur = self.textCursor()
            if not cur.hasSelection():
                span = _chip_span_at(self.document(), cur.position())
                if span:
                    cur.setPosition(span[0])
                    self.setTextCursor(cur)
            event.accept(); return

        if event.key() == Qt.Key_Right:
            super().keyPressEvent(event)
            cur = self.textCursor()
            if not cur.hasSelection():
                span = _chip_span_at(self.document(), cur.position())
                if span:
                    cur.setPosition(span[1])
                    self.setTextCursor(cur)
            event.accept(); return

        # Printable characters — force plain format before inserting
        if event.text() and event.text().isprintable():
            pos = cur.position()
            span = _chip_span_at(self.document(), pos)
            if span:
                cur.setPosition(span[1])
                self.setTextCursor(cur)
            cur = self.textCursor()
            cur.setCharFormat(_plain_fmt())
            self.setTextCursor(cur)

        super().keyPressEvent(event)

    def _ensure_plain_fmt(self):
        cur = self.textCursor()
        if not cur.hasSelection():
            fmt = cur.charFormat()
            if fmt.property(_CHIP_PROP):
                cur.setCharFormat(_plain_fmt())
                self.setTextCursor(cur)

    def insertFromMimeData(self, source):
        """Strip {…} patterns from pasted text."""
        if source.hasText():
            cur = self.textCursor()
            cur.setCharFormat(_plain_fmt())
            cur.insertText(_re.sub(r"\{[^}]+\}", "", source.text()))

    # ── painting — draw chip backgrounds with rounded rect + × badge ──────────






# ── helpers ───────────────────────────────────────────────────────────────────

def _chip_span_at(doc, pos: int):
    """Return (start, end) if pos is inside a chip fragment, else None."""
    block = doc.findBlock(pos)
    if not block.isValid():
        return None
    frag_pos = block.position()
    it = block.begin()
    while not it.atEnd():
        frag = it.fragment()
        frag_end = frag_pos + frag.length()
        if frag_pos <= pos < frag_end and frag.charFormat().property(_CHIP_PROP):
            return frag_pos, frag_end
        frag_pos = frag_end
        it += 1
    return None


def _insert_chip(cur: QTextCursor, name: str):
    cur.setCharFormat(_chip_fmt(name))
    # trailing spaces give visual room for the × button
    cur.insertText(f"{{{name}}}")
    cur.setCharFormat(_plain_fmt())
    cur.insertText("")


def _delete_span(editor: "_MergeEdit", span: tuple):
    editor.setReadOnly(False)
    c = editor.textCursor()
    c.setPosition(span[0])
    c.setPosition(span[1], QTextCursor.KeepAnchor)
    c.removeSelectedText()
    c.setCharFormat(_plain_fmt())
    editor.setTextCursor(c)


def _delete_selection_safe(editor: "_MergeEdit", cur: QTextCursor):
    """Delete selection, expanding to cover any partially-selected chips."""
    editor.setReadOnly(False)
    s, e = cur.selectionStart(), cur.selectionEnd()
    span_s = _chip_span_at(editor.document(), s)
    if span_s and span_s[0] < s:
        s = span_s[0]
    span_e = _chip_span_at(editor.document(), e - 1) if e > 0 else None
    if span_e and span_e[1] > e:
        e = span_e[1]
    c = editor.textCursor()
    c.setPosition(s)
    c.setPosition(e, QTextCursor.KeepAnchor)
    c.removeSelectedText()
    c.setCharFormat(_plain_fmt())
    editor.setTextCursor(c)


# ── MergeInputWidget ──────────────────────────────────────────────────────────

class MergeInputWidget(QWidget):
    """
    MERGE WITH field.
    - Single text area — type freely anywhere.
    - {LabelName} chips appear inline as blue rounded pills.
    - Each chip has a drawn × button; click it to remove the chip.
    - Backspace/Delete next to a chip removes the whole chip.
    - Arrow keys skip chips as a unit.
    - ⋯ Insert Label button opens the picker to insert at cursor.
    """

    templateChanged  = Signal(str)
    selectionChanged = Signal(list)   # compat shim

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: list[str] = []
        self._picker = None
        self._enabled = True
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self._build_ui()

    def _build_ui(self):
        from PySide6.QtWidgets import QVBoxLayout
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(3)

        self._editor = _MergeEdit(self)
        self._editor.templateChanged.connect(self._on_editor_changed)

        self._pick_btn = QPushButton("⋯  Insert Label")
        self._pick_btn.setFixedHeight(24)
        self._pick_btn.setCursor(Qt.PointingHandCursor)
        self._pick_btn.setFocusPolicy(Qt.NoFocus)
        self._pick_btn.setToolTip("Insert a label variable at cursor")
        self._pick_btn.setStyleSheet(self._btn_style(False))
        self._pick_btn.clicked.connect(self._toggle_picker)

        root.addWidget(self._editor)
        root.addWidget(self._pick_btn)

    def _btn_style(self, active: bool) -> str:
        if active:
            return ("QPushButton{background:#EEF2FF;border:1px solid #6366F1;"
                    "border-radius:5px;color:#4338CA;font-size:11px;font-weight:600;"
                    "min-height:24px;max-height:24px;padding:0 8px;}"
                    "QPushButton:hover{background:#E0E7FF;}")
        return ("QPushButton{background:#F8FAFC;border:1px solid #E2E8F0;"
                "border-radius:5px;color:#94A3B8;font-size:11px;font-weight:500;"
                "min-height:24px;max-height:24px;padding:0 8px;}"
                "QPushButton:hover{background:#EEF2FF;border-color:#6366F1;color:#4338CA;}")

    def _btn_style_disabled(self) -> str:
        return ("QPushButton{background:#F1F5F9;border:1px solid #E2E8F0;"
                "border-radius:5px;color:#CBD5E1;font-size:11px;font-weight:500;"
                "min-height:24px;max-height:24px;padding:0 8px;}")

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
        if isinstance(value, list):
            self.set_template(" ".join(f"{{{n}}}" for n in value if n))
        elif isinstance(value, str):
            if "{" in value or not value:
                self.set_template(value)
            else:
                names = [n.strip() for n in value.split(",") if n.strip()]
                self.set_template(" ".join(f"{{{n}}}" for n in names))

    def get_selected(self) -> list[str]:
        return list(dict.fromkeys(_re.findall(r"\{([^}]+)\}", self.get_template())))

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