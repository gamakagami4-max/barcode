"""Mixin for MERGE and KONVERSI TIMBANGAN type logic in TextPropertyEditor."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class MergeKonversiMixin:
    """
    Mixin for TextPropertyEditor.

    Requires self.item and the following widgets:
      merge_combo        – an InlineChecklistWidget
      timbangan_combo    – single-select custom combo
      weight_combo       – single-select custom combo
      um_combo           – single-select custom combo

    design_merge is stored as a comma-separated string of component names,
    e.g.  "Text1,Text2,Text3".  An empty string means "nothing selected".
    At print-time call MergeKonversiMixin.resolve_merge(item, scene_items)
    to get the single merged value that should be printed.
    """

    # ── public API called by _on_type_changed ─────────────────────────────────

    def enable_for_merge(self, enabled: bool):
        """Enable / disable the merge inline checklist widget."""
        if not enabled:
            # Clear first so _apply_disabled_appearance sees empty _selected
            self.merge_combo.clear_selection()
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

    # ── combo change handlers ─────────────────────────────────────────────────

    def _on_merge_changed(self, selected_names: list[str]):
        """
        Called by InlineChecklistWidget when the selection changes.
        selected_names is a list of component-name strings.
        Stores the result as a comma-separated string on self.item.design_merge.
        """
        cleaned = [n for n in selected_names if n and n != "—"]
        self.item.design_merge = ",".join(cleaned)

    def _on_timbangan_changed(self, v: str):
        self.item.design_timbangan = v if v not in ("", "—") else ""

    def _on_weight_changed(self, v: str):
        self.item.design_weight = v if v not in ("", "—") else ""

    def _on_um_changed(self, v: str):
        self.item.design_um = v if v not in ("", "—") else ""

    # ── print-time helper (static / class method) ─────────────────────────────

    @staticmethod
    def resolve_merge(item, scene_items, separator: str = " ") -> str:
        """
        Return the single merged string that should be printed for *item*.

        Parameters
        ----------
        item        : the QGraphicsTextItem whose design_type == "MERGE"
        scene_items : iterable of all QGraphicsItem objects in the scene
                      (scene.items() is fine)
        separator   : string placed between each merged value (default: space)

        Returns
        -------
        Merged text string, e.g. "Alice 30 Manager"
        If no components are listed or none are found, returns item's own
        plain-text as a fallback.
        """
        raw = getattr(item, "design_merge", "") or ""
        names = [n.strip() for n in raw.split(",") if n.strip()]
        if not names:
            return item.toPlainText()

        name_to_value: dict[str, str] = {}
        for si in scene_items:
            cname = getattr(si, "component_name", "")
            if not cname:
                continue
            # Avoid circular self-reference
            if si is item:
                continue
            try:
                text_val = si.toPlainText()
            except AttributeError:
                continue
            name_to_value[cname] = text_val

        parts = []
        for name in names:
            val = name_to_value.get(name)
            if val is not None:
                parts.append(val)
            # silently skip components that no longer exist on the canvas

        return separator.join(parts) if parts else item.toPlainText()


# ── MultiSelectCombo widget ────────────────────────────────────────────────────
# Kept for backward-compatibility (may be used elsewhere), but MERGE WITH
# now uses InlineChecklistWidget from text_property_editor.py instead.

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QListWidget, QListWidgetItem, QSizePolicy,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QFont, QColor, QPixmap, QPainter, QPen, QIcon


class MultiSelectCombo(QWidget):
    """
    Tag-strip + popup-list multi-select widget.

    NOTE: For the MERGE WITH field in TextPropertyEditor, InlineChecklistWidget
    is now used instead. This class is retained for any other usages.

    Signals
    -------
    selectionChanged(list[str])
        Emitted whenever the set of selected names changes.
    """

    selectionChanged = Signal(list)   # list[str] of selected component names

    # ── construction ──────────────────────────────────────────────────────────

    def __init__(self, placeholder: str = "— select components —", parent=None):
        super().__init__(parent)
        self._placeholder = placeholder
        self._items: list[str] = []       # all available names
        self._selected: list[str] = []    # currently chosen names (ordered)
        self._popup: QFrame | None = None
        self._list_widget: QListWidget | None = None
        self._check_icon = self._build_check_icon()

        # ── outer layout: tag-frame only ─────────────────────────────────────
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.setAlignment(Qt.AlignTop)

        # Tag frame (acts as the clickable "input")
        self._tag_frame = QFrame()
        self._tag_frame.setMinimumHeight(28)
        self._tag_frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self._tag_frame.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }
            QFrame:hover {
                border: 1px solid #6366F1;
            }
        """)
        self._tag_frame.setCursor(Qt.PointingHandCursor)
        self._tag_frame.installEventFilter(self)

        self._tag_layout = QHBoxLayout(self._tag_frame)
        self._tag_layout.setContentsMargins(6, 3, 6, 3)
        self._tag_layout.setSpacing(4)
        self._tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        # Placeholder label (shown when nothing is selected)
        self._placeholder_lbl = QLabel(placeholder)
        self._placeholder_lbl.setStyleSheet(
            "color: #94A3B8; font-size: 9pt; background: transparent; border: none;"
        )
        self._tag_layout.addWidget(self._placeholder_lbl)

        outer.addWidget(self._tag_frame)

        # ── popup (built once per open) ───────────────────────────────────────
        self._popup = None

        self._refresh_tags()

    # ── public API ────────────────────────────────────────────────────────────

    def set_items(self, names: list[str]):
        """Replace the full list of available component names."""
        self._items = list(names)
        self._selected = [n for n in self._selected if n in self._items]
        self._refresh_tags()
        if self._list_widget:
            self._sync_list_icons()

    def set_selected(self, names: "list[str] | str"):
        """
        Pre-select items by name.
        Accepts either list[str] or a comma-separated string.
        """
        if isinstance(names, str):
            names = [n.strip() for n in names.split(",") if n.strip()]
        self._selected = [n for n in names if n in self._items]
        self._refresh_tags()
        if self._list_widget:
            self._sync_list_icons()

    def get_selected(self) -> list[str]:
        return list(self._selected)

    def clear_selection(self):
        self._selected = []
        self._refresh_tags()
        if self._list_widget:
            self._sync_list_icons()

    def setEnabled(self, enabled: bool):  # noqa: N802
        super().setEnabled(enabled)
        self._tag_frame.setEnabled(enabled)
        self._tag_frame.setStyleSheet("""
            QFrame {
                background: %s;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
            }
            QFrame:hover { border: 1px solid %s; }
        """ % (
            "#F8FAFC" if not enabled else "#FFFFFF",
            "#E2E8F0" if not enabled else "#6366F1",
        ))
        if not enabled and self._popup:
            self._close_popup()

    def set_placeholder(self, text: str):
        """Update the placeholder text shown when nothing is selected."""
        self._placeholder = text
        self._refresh_tags()

    # ── tag rendering ─────────────────────────────────────────────────────────

    def _refresh_tags(self):
        """Rebuild the pill-tags inside the tag frame."""
        while self._tag_layout.count():
            item = self._tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._selected:
            self._placeholder_lbl = QLabel(self._placeholder)
            self._placeholder_lbl.setStyleSheet(
                "color: #94A3B8; font-size: 9pt; background: transparent; border: none;"
            )
            self._tag_layout.addWidget(self._placeholder_lbl)
        else:
            for name in self._selected:
                tag = self._make_tag(name)
                self._tag_layout.addWidget(tag)

        self._tag_frame.updateGeometry()
        self._tag_frame.repaint()

    def _make_tag(self, name: str) -> QPushButton:
        """Create a single pill tag button for a selected component name."""
        btn = QPushButton(name + "  \u2715")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet("""
            QPushButton {
                background: #EEF2FF;
                color: #4338CA;
                padding: 1px 7px;
                border-radius: 5px;
                font-size: 9pt;
                font-weight: 600;
                border: none;
            }
            QPushButton:hover {
                background: #E0E7FF;
                color: #3730A3;
            }
        """)
        btn.clicked.connect(lambda: self._remove_tag(name))
        return btn

    def _remove_tag(self, name: str):
        """Deselect a component by clicking its x on the tag."""
        if name in self._selected:
            self._selected.remove(name)
        self._refresh_tags()
        if self._list_widget:
            self._sync_list_icons()
        self.selectionChanged.emit(list(self._selected))

    # ── popup ─────────────────────────────────────────────────────────────────

    def _open_popup(self):
        if not self._items:
            return

        popup = QFrame(self.window(), Qt.Popup | Qt.FramelessWindowHint)
        popup.setAttribute(Qt.WA_DeleteOnClose, True)
        popup.setStyleSheet("""
            QFrame {
                background: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 10px;
            }
            QListWidget {
                border: none;
                background: transparent;
                font-size: 9pt;
                outline: none;
            }
            QListWidget::item {
                padding: 5px 8px;
                border-radius: 6px;
                color: #0F172A;
            }
            QListWidget::item:hover  { background: #F1F5F9; }
            QListWidget::item:selected { background: #EAF2FF; color: #0F172A; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 2px 0;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1; min-height: 20px; border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover { background: #94A3B8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0; background: none;
            }
        """)

        drop_layout = QVBoxLayout(popup)
        drop_layout.setContentsMargins(6, 6, 6, 6)
        drop_layout.setSpacing(4)

        lw = QListWidget()
        lw.setSelectionMode(QAbstractItemView.MultiSelection)
        for name in self._items:
            li = QListWidgetItem(name)
            lw.addItem(li)
        self._list_widget = lw
        self._sync_list_icons()
        lw.itemSelectionChanged.connect(self._on_list_selection_changed)
        drop_layout.addWidget(lw)

        popup.setFixedWidth(max(200, self._tag_frame.width()))
        lw.setFixedHeight(min(len(self._items) * 30 + 8, 200))
        popup.adjustSize()

        from PySide6.QtCore import QPoint
        global_pos = self._tag_frame.mapToGlobal(
            QPoint(0, self._tag_frame.height() + 2)
        )
        popup.move(global_pos)
        popup.show()
        popup.installEventFilter(self)
        self._popup = popup

    def _close_popup(self):
        if self._popup:
            self._popup.close()
            self._popup = None
            self._list_widget = None

    # ── list sync ─────────────────────────────────────────────────────────────

    def _sync_list_icons(self):
        if not self._list_widget:
            return
        lw = self._list_widget
        lw.blockSignals(True)
        for i in range(lw.count()):
            li = lw.item(i)
            is_sel = li.text() in self._selected
            li.setSelected(is_sel)
            li.setIcon(self._check_icon if is_sel else QIcon())
        lw.blockSignals(False)

    def _on_list_selection_changed(self):
        lw = self._list_widget
        if lw is None:
            return
        newly_selected = [lw.item(i).text() for i in range(lw.count())
                          if lw.item(i).isSelected()]
        for i in range(lw.count()):
            li = lw.item(i)
            li.setIcon(self._check_icon if li.isSelected() else QIcon())

        self._selected = newly_selected
        self._refresh_tags()
        self.selectionChanged.emit(list(self._selected))

    # ── check-mark icon ───────────────────────────────────────────────────────

    @staticmethod
    def _build_check_icon() -> QIcon:
        pix = QPixmap(16, 16)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor("#6366F1"), 2))
        painter.drawLine(3, 8, 6, 11)
        painter.drawLine(6, 11, 12, 4)
        painter.end()
        return QIcon(pix)

    # ── event filter ──────────────────────────────────────────────────────────

    def eventFilter(self, obj, event):
        if obj is self._tag_frame and event.type() == QEvent.MouseButtonPress:
            if self.isEnabled():
                if self._popup and self._popup.isVisible():
                    self._close_popup()
                else:
                    self._open_popup()
            return True
        if obj is self._popup and event.type() == QEvent.Close:
            self._list_widget = None
            self._popup = None
        return super().eventFilter(obj, event)