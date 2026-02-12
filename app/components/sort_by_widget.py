from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QComboBox, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QFrame,
    QVBoxLayout, QAbstractItemView
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QPixmap, QPainter, QPen
from PySide6.QtGui import QPixmap, QPainter, QPen, QIcon
from PySide6.QtWidgets import QSizePolicy

class SortByWidget(QWidget):

    sortChanged = Signal(list, object)

    def __init__(self, table, parent=None):
        super().__init__(parent)

        self._table = table
        self._fields = self._extract_headers()
        self._selected_fields = []
        self._updating_text = False
        # Track direction for each field independently
        self._field_directions = {}  # {field_name: "asc" or "desc"}

        # -------------------------------------------------
        # Layout
        # -------------------------------------------------
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        label = QLabel("Sort by")
        label.setStyleSheet("""
            QLabel {
                color:#475569;
                font-size:12px;
                font-weight:500;
            }
        """)

        # -------------------------------------------------
        # Input
        # -------------------------------------------------
        self._input = QFrame()
        self._input.setMinimumWidth(240)
        self._input.setFixedHeight(28)
        self._input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._input.setStyleSheet("""
            QFrame {
                background:#FFFFFF;
                border:1px solid #E2E8F0;
                border-radius:8px;
            }
            QFrame:hover {
                border:1px solid #CBD5E1;
            }
        """)

        self._tag_layout = QHBoxLayout(self._input)
        self._tag_layout.setContentsMargins(6, 4, 6, 4)
        self._tag_layout.setSpacing(4)
        self._tag_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)



        # -------------------------------------------------
        # Dropdown
        # -------------------------------------------------
        self._dropdown = QFrame(None)
        self._dropdown.setWindowFlags(Qt.Popup)
        self._dropdown.setStyleSheet("""
            QFrame {
                background:#FFFFFF;
                border:1px solid #E2E8F0;
                border-radius:10px;
            }

            QListWidget {
                border:none;
                background:transparent;
                font-size:12px;
                outline:none;
            }

            QListWidget::item {
                padding:6px 8px;
                border-radius:6px;
                color:#0F172A;
            }

            QListWidget::item:hover {
                background:#F1F5F9;
            }

            QListWidget::item:selected {
                background:#EAF2FF;
                color:#0F172A;
            }
        """)

        drop_layout = QVBoxLayout(self._dropdown)
        drop_layout.setContentsMargins(6, 6, 6, 6)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.MultiSelection)
        drop_layout.addWidget(self._list)

        # -------------------------------------------------
        # Check Icon
        # -------------------------------------------------
        self._check_icon = self._build_check_icon()

        for field in self._fields:
            item = QListWidgetItem(field)
            self._list.addItem(item)

        
        # -------------------------------------------------
        # Clear Button
        # -------------------------------------------------
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(70)
        clear_btn.setStyleSheet("""
            QPushButton {
                background:#F8FAFC;
                border:1px solid #E2E8F0;
                border-radius:8px;
                padding:4px 10px;
                font-size:12px;
                color:#475569;
            }
            QPushButton:hover {
                background:#F1F5F9;
                border:1px solid #CBD5E1;
            }
        """)

        layout.addWidget(label)
        layout.addWidget(self._input, 1)   # <-- THIS makes it expand
        layout.addWidget(clear_btn)


        # -------------------------------------------------
        # Events
        # -------------------------------------------------
        self._input.installEventFilter(self)

        self._list.itemSelectionChanged.connect(self._update_selection)
        clear_btn.clicked.connect(self._clear)

    def _create_tag(self, text):
        # Get direction for this specific field (default to ascending)
        direction = self._field_directions.get(text, "asc")
        arrow = "↑" if direction == "asc" else "↓"
        tag = QPushButton(f"{text} {arrow}")
        tag.setCursor(Qt.PointingHandCursor)
        tag.setStyleSheet("""
            QPushButton {
                background:#EAF2FF;
                color:#1E40AF;
                padding:2px 8px;
                border-radius:6px;
                font-size:11px;
                font-weight:500;
                border:none;
            }
            QPushButton:hover {
                background:#DBEAFE;
            }
        """)
        # Store the field name for identification
        tag.setProperty("field_name", text)
        tag.clicked.connect(lambda: self._toggle_tag_direction(text))
        return tag

    def _toggle_tag_direction(self, field_name):
        """Toggle between ascending and descending for a specific field."""
        current = self._field_directions.get(field_name, "asc")
        self._field_directions[field_name] = "desc" if current == "asc" else "asc"
        self._refresh_tags()
        self._emit_changed()

    # -------------------------------------------------
    def _build_check_icon(self):
        pix = QPixmap(16, 16)
        pix.fill(Qt.transparent)

        painter = QPainter(pix)
        painter.setRenderHint(QPainter.Antialiasing)

        pen = QPen(Qt.white, 2)
        painter.setPen(pen)

        painter.drawLine(4, 9, 7, 12)
        painter.drawLine(7, 12, 12, 4)

        painter.end()
        return QIcon(pix)

    # -------------------------------------------------
    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QEvent.MouseButtonPress:
            self._open_dropdown()
        return super().eventFilter(obj, event)

    # -------------------------------------------------
    def _extract_headers(self):
        headers = []

        if hasattr(self._table, "columnCount"):
            for col in range(self._table.columnCount()):
                item = self._table.horizontalHeaderItem(col)
                if item:
                    headers.append(item.text())

        elif hasattr(self._table, "model"):
            model = self._table.model()
            for col in range(model.columnCount()):
                headers.append(str(model.headerData(col, Qt.Horizontal)))

        return headers

    # -------------------------------------------------
    def _open_dropdown(self):
        if not self._fields:
            return

        pos = self._input.mapToGlobal(self._input.rect().bottomLeft())
        self._dropdown.setGeometry(pos.x(), pos.y(), 240, 220)
        self._dropdown.show()

    # -------------------------------------------------
    def _filter_items(self, text):
        if self._updating_text:
            return

        for i in range(self._list.count()):
            item = self._list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    # -------------------------------------------------
    def _refresh_tags(self):
        """Refresh tag display to update arrow indicators."""
        # clear tags
        while self._tag_layout.count():
            item = self._tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # add tags with current direction
        for field in self._selected_fields:
            tag = self._create_tag(field)
            self._tag_layout.addWidget(tag)

        self._input.updateGeometry()
        self._input.repaint()

    # -------------------------------------------------
    # -------------------------------------------------
    def _update_selection(self):

        # Get currently selected items
        selected_items = [item.text() for item in self._list.selectedItems()]

        # Enforce max 5 selection
        if len(selected_items) > 5:
            # Deselect items beyond the 5th
            for item in self._list.selectedItems()[5:]:
                item.setSelected(False)
            selected_items = [item.text() for item in self._list.selectedItems()]

        self._selected_fields = selected_items

        # Initialize direction for newly selected fields
        for field in self._selected_fields:
            if field not in self._field_directions:
                self._field_directions[field] = "asc"

        # update check icons
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.text() in self._selected_fields:
                item.setIcon(self._check_icon)
            else:
                item.setIcon(QIcon())

        # clear tags
        while self._tag_layout.count():
            item = self._tag_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # add tags
        for field in self._selected_fields:
            tag = self._create_tag(field)
            self._tag_layout.addWidget(tag)

        self._input.updateGeometry()
        self._input.repaint()
        self._emit_changed()



    # -------------------------------------------------
    def _emit_changed(self):
        # Emit list of fields with their individual directions
        fields_with_directions = [
            (field, self._field_directions.get(field, "asc"))
            for field in self._selected_fields
        ]
        # For backwards compatibility, emit fields list and directions dict
        self.sortChanged.emit(self._selected_fields, self._field_directions)

    def _clear(self):
        self._list.clearSelection()
        self._selected_fields = []
        self._field_directions = {}

        while self._tag_layout.count():
            w = self._tag_layout.takeAt(0).widget()
            if w:
                w.deleteLater()

        self._emit_changed()