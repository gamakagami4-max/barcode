from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QVBoxLayout,
    QAbstractItemView, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from components.pagination_widget import PaginationWidget


# ---------------------------------------------------------------------------
# Design tokens — change here to retheme the entire widget
# ---------------------------------------------------------------------------
class _Theme:
    text_main        = "#0F172A"
    text_header      = "#000000"
    border           = "#000000"
    header_bg        = "#E5E7EB"
    row_number_bg    = "#F3F4F6"
    selection_bg     = "#FEF9C3"
    scrollbar_handle = "#CBD5E1"
    scrollbar_hover  = "#94A3B8"
    bg               = "#FFFFFF"

    # Sizing
    header_height    = 26
    row_height       = 28
    row_number_width = 32
    font_size_body   = "10px"
    font_size_header = "9px"
    font_weight_header = "bold"


# ---------------------------------------------------------------------------
# Style sheets — built from tokens, kept separate from layout logic
# ---------------------------------------------------------------------------
def _container_style() -> str:
    t = _Theme
    return f"""
        StandardTable {{
            background-color: {t.bg};
            border: none;              /* Let pages decide surrounding borders; keeps pagination clean */
            border-radius: 0px;
        }}
        StandardTable QScrollBar:vertical {{
            background: transparent;
            width: 8px;
            margin: 0;
            border: none;
        }}
        StandardTable QScrollBar::handle:vertical {{
            background: {t.scrollbar_handle};
            min-height: 28px;
            border-radius: 4px;
        }}
        StandardTable QScrollBar::handle:vertical:hover {{
            background: {t.scrollbar_hover};
        }}
        StandardTable QScrollBar::add-line:vertical,
        StandardTable QScrollBar::sub-line:vertical {{
            height: 0;
            background: none;
        }}
        StandardTable QScrollBar:horizontal {{
            background: transparent;
            height: 8px;
            margin: 0;
            border: none;
        }}
        StandardTable QScrollBar::handle:horizontal {{
            background: {t.scrollbar_handle};
            min-width: 28px;
            border-radius: 4px;
        }}
        StandardTable QScrollBar::handle:horizontal:hover {{
            background: {t.scrollbar_hover};
        }}
        StandardTable QScrollBar::add-line:horizontal,
        StandardTable QScrollBar::sub-line:horizontal {{
            width: 0;
            background: none;
        }}
    """


def _table_style() -> str:
    t = _Theme
    return f"""
        QTableWidget {{
            background-color: {t.bg};
            gridline-color: {t.border};
        }}
        QTableWidget::item {{
            padding: 2px 6px;
            color: {t.text_main};
            font-size: {t.font_size_body};
            border: none;
        }}
        QTableWidget::item:selected {{
            background-color: {t.selection_bg};
            color: {t.text_main};
        }}
        QHeaderView::section {{
            background-color: {t.header_bg};
            color: {t.text_header};
            padding: 3px 6px;
            font-size: {t.font_size_header};
            font-weight: {t.font_weight_header};
            border: 1px solid {t.border};
        }}
        QHeaderView::down-arrow,
        QHeaderView::up-arrow {{
            width: 0px;
            height: 0px;
        }}
        QTableCornerButton::section {{
            background-color: {t.row_number_bg};
            border: 1px solid {t.border};
        }}
    """


def _row_number_style() -> str:
    t = _Theme
    return f"""
        QHeaderView::section {{
            background-color: {t.row_number_bg};
            color: {t.text_main};
            padding: 2px 4px;
            font-size: {t.font_size_header};
            font-weight: {t.font_weight_header};
            border: 1px solid {t.border};
        }}
    """


# ---------------------------------------------------------------------------
# Header configuration helpers
# ---------------------------------------------------------------------------
def _configure_horizontal_header(header: QHeaderView) -> None:
    """Compact, horizontally scrollable column headers."""
    header.setMinimumHeight(_Theme.header_height)
    header.setDefaultAlignment(Qt.AlignCenter | Qt.AlignVCenter)
    # Ensure columns are never ultra-cramped: sensible defaults that prefer
    # horizontal scrolling over squeezing.
    header.setDefaultSectionSize(140)
    header.setMinimumSectionSize(100)
    # Use Interactive so callers (pages) and end‑users can override widths.
    header.setSectionResizeMode(QHeaderView.Interactive)
    header.setSortIndicatorShown(False)
    header.setSectionsClickable(False)
    
    # Make header font bold programmatically
    header_font = QFont()
    header_font.setBold(True)
    header.setFont(header_font)


def _configure_vertical_header(header: QHeaderView) -> None:
    """Visible row-number gutter, compact and centred."""
    header.setVisible(True)
    header.setDefaultSectionSize(_Theme.row_height)
    header.setMinimumWidth(_Theme.row_number_width)
    header.setDefaultAlignment(Qt.AlignCenter | Qt.AlignVCenter)
    header.setStyleSheet(_row_number_style())
    
    # Make row number header font bold programmatically
    header_font = QFont()
    header_font.setBold(True)
    header.setFont(header_font)


# ---------------------------------------------------------------------------
# Main widget
# ---------------------------------------------------------------------------
class StandardTable(QFrame):
    """
    Excel-style table widget with sorting capability.

    Features
    --------
    - Compact grid with row numbers, non-sortable headers, yellow row selection
    - Modern slim scrollbars (vertical + horizontal)
    - Columns auto-size to content; table scrolls horizontally when needed
    - Word-wrap enabled: \\n in cell text wraps instead of truncating with ...
    - Multi-field sorting with ascending/descending per field
    - Fully themeable via the ``_Theme`` class above

    Parameters
    ----------
    headers : list[str]
        Column labels for the horizontal header.
    """

    def __init__(self, headers: list[str], parent=None) -> None:
        super().__init__(parent)
        self._headers = headers
        self._original_data = []  # Store original row data for sorting
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(_container_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.table = self._create_table()
        layout.addWidget(self.table)

        # Integrated pagination bar (25 rows/page by default for callers).
        # Pages can listen to `self.pagination.pageChanged` and call their own
        # render/refresh logic, then feed back stats via `update(...)`.
        self.pagination = PaginationWidget(colors={
            "text_table": _Theme.text_main,
            "text_secondary": "#64748B",
            "border": _Theme.border,
            "accent": "#6366F1",
            "hover": "#F9FAFB",
        })
        layout.addWidget(self.pagination)

    def _create_table(self) -> QTableWidget:
        table = QTableWidget(0, len(self._headers))
        table.setHorizontalHeaderLabels(self._headers)
        table.setSortingEnabled(False)

        # Excel-like look
        table.setShowGrid(True)
        table.setFrameShape(QFrame.StyledPanel)
        table.setStyleSheet(_table_style())

        # Word wrap: honour \n in cell text; avoid visual "..." truncation
        table.setWordWrap(True)
        table.setTextElideMode(Qt.ElideNone)

        # Selection: single full-row highlight
        table.setSelectionMode(QTableWidget.SingleSelection)
        table.setSelectionBehavior(QAbstractItemView.SelectRows)
        table.setFocusPolicy(Qt.StrongFocus)

        # Smooth scrolling: by pixel instead of by row/item
        table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        table.verticalScrollBar().setSingleStep(12)
        table.horizontalScrollBar().setSingleStep(12)

        _configure_horizontal_header(table.horizontalHeader())
        _configure_vertical_header(table.verticalHeader())

        return table

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _fill_empty_cells(self, row: int) -> None:
        """
        Ensure every cell in *row* has a QTableWidgetItem.

        Qt only draws gridlines around cells that have an item; without
        this, rows whose data is partially or fully absent look broken —
        the grid lines simply vanish for the empty columns.  Inserting a
        blank, non-editable item costs nothing visually but guarantees
        consistent borders across every row.
        """
        for col in range(self.table.columnCount()):
            if self.table.item(row, col) is None:
                placeholder = QTableWidgetItem("")
                placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row, col, placeholder)

    def _get_cell_sort_value(self, row: int, col: int):
        """Extract sortable value from a cell (handles widgets and items)."""
        widget = self.table.cellWidget(row, col)
        if widget:
            # If it's a widget, try to get its text or value
            if hasattr(widget, 'text'):
                return widget.text()
            elif hasattr(widget, 'value'):
                return widget.value()
            return ""
        
        item = self.table.item(row, col)
        if item:
            text = item.text()
            # Try to convert to number if possible for better numeric sorting
            try:
                return float(text.replace(',', ''))
            except (ValueError, AttributeError):
                return text.lower() if text else ""
        return ""

    def sort_by_fields(self, fields: list[str], field_directions: dict) -> None:
        """
        Sort table by multiple fields with individual directions.
        
        Parameters
        ----------
        fields : list[str]
            Ordered list of field names to sort by (priority order).
        field_directions : dict
            Mapping of field name to direction ("asc" or "desc").
        """
        if not fields:
            # If no sort fields, restore original order
            self._restore_original_order()
            return
        
        # Get column indices for each field
        header_map = {self._headers[i]: i for i in range(len(self._headers))}
        sort_columns = []
        for field in fields:
            if field in header_map:
                col_idx = header_map[field]
                reverse = field_directions.get(field, "asc") == "desc"
                sort_columns.append((col_idx, reverse))
        
        if not sort_columns:
            return
        
        # Collect all row data
        row_count = self.table.rowCount()
        rows_data = []
        
        for row in range(row_count):
            row_items = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                widget = self.table.cellWidget(row, col)
                
                if widget:
                    # Store widget reference and its data
                    row_items.append(('widget', widget, self._get_cell_sort_value(row, col)))
                elif item:
                    # Clone the item
                    new_item = QTableWidgetItem(item)
                    row_items.append(('item', new_item, self._get_cell_sort_value(row, col)))
                else:
                    row_items.append(('empty', None, ""))
            
            rows_data.append(row_items)
        
        # Sort using multiple keys
        def sort_key(row_data):
            keys = []
            for col_idx, _ in sort_columns:
                keys.append(row_data[col_idx][2])  # The sort value
            return keys
        
        # Apply sorting with proper direction for each field
        for col_idx, reverse in reversed(sort_columns):  # Reverse to apply in priority order
            rows_data.sort(key=lambda r: r[col_idx][2], reverse=reverse)
        
        # Clear table and repopulate
        self.table.setRowCount(0)
        
        for row_items in rows_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            for col, (item_type, item_data, _) in enumerate(row_items):
                if item_type == 'widget':
                    self.table.setCellWidget(row, col, item_data)
                elif item_type == 'item':
                    self.table.setItem(row, col, item_data)
                else:
                    placeholder = QTableWidgetItem("")
                    placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, col, placeholder)

    def _restore_original_order(self) -> None:
        """Restore the table to its original unsorted order."""
        if not self._original_data:
            return
        
        self.table.setRowCount(0)
        for row_items in self._original_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            for col, (item_type, item_data) in enumerate(row_items):
                if item_type == 'widget':
                    # Create a new instance or clone if possible
                    self.table.setCellWidget(row, col, item_data)
                elif item_type == 'item':
                    self.table.setItem(row, col, QTableWidgetItem(item_data))
                else:
                    placeholder = QTableWidgetItem("")
                    placeholder.setFlags(placeholder.flags() & ~Qt.ItemIsEditable)
                    self.table.setItem(row, col, placeholder)

    def _store_original_data(self) -> None:
        """Store current table data for later restoration."""
        self._original_data = []
        for row in range(self.table.rowCount()):
            row_items = []
            for col in range(self.table.columnCount()):
                widget = self.table.cellWidget(row, col)
                item = self.table.item(row, col)
                
                if widget:
                    row_items.append(('widget', widget))
                elif item:
                    row_items.append(('item', QTableWidgetItem(item)))
                else:
                    row_items.append(('empty', None))
            
            self._original_data.append(row_items)

    # ------------------------------------------------------------------
    # Public API — thin delegation to the inner QTableWidget
    # ------------------------------------------------------------------
    def row_count(self) -> int:
        return self.table.rowCount()

    def set_row_count(self, count: int) -> None:
        """Set total row count, filling any new rows with blank items."""
        self.table.setRowCount(count)
        for row in range(count):
            self._fill_empty_cells(row)
        self._store_original_data()

    def insert_row(self, row: int) -> None:
        """Insert a blank row at *row*, pre-filled so grid lines appear."""
        self.table.insertRow(row)
        self._fill_empty_cells(row)

    def set_item(self, row: int, col: int, item) -> None:
        self.table.setItem(row, col, item)

    def set_cell_widget(self, row: int, col: int, widget) -> None:
        self.table.setCellWidget(row, col, widget)

    def set_row_height(self, row: int, height: int) -> None:
        self.table.setRowHeight(row, height)

    def clear(self) -> None:
        """Remove all rows (keeps headers)."""
        self.table.setRowCount(0)
        self._original_data = []

    def headers(self) -> list[str]:
        """Return the logical column headers used by this table."""
        return list(self._headers)

    def append_row(self, items: list) -> int:
        """
        Convenience: append one row and return its index.

        Parameters
        ----------
        items : list[QTableWidgetItem | QWidget | str | None]
            - ``QTableWidgetItem`` -> set directly
            - ``QWidget``          -> embedded via setCellWidget
            - ``str``              -> wrapped in a QTableWidgetItem
            - ``None`` / missing   -> blank placeholder (grid lines preserved)

        Any columns beyond ``len(items)`` are also filled with blank
        placeholders so grid lines remain consistent.
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        for col, item in enumerate(items):
            if isinstance(item, QWidget):
                self.table.setCellWidget(row, col, item)
            elif isinstance(item, QTableWidgetItem):
                self.table.setItem(row, col, item)
            else:
                # str, int, float, None — coerce to a plain text item
                cell = QTableWidgetItem("" if item is None else str(item))
                self.table.setItem(row, col, cell)

        # Fill any trailing columns not covered by `items`
        self._fill_empty_cells(row)
        return row

    # Backwards-compatible camelCase aliases
    def rowCount(self) -> int:
        return self.row_count()

    def setRowCount(self, count: int) -> None:
        self.set_row_count(count)

    def insertRow(self, row: int) -> None:
        self.insert_row(row)

    def setItem(self, row: int, col: int, item) -> None:
        self.set_item(row, col, item)

    def setCellWidget(self, row: int, col: int, widget) -> None:
        self.set_cell_widget(row, col, widget)

    def setRowHeight(self, row: int, height: int) -> None:
        self.set_row_height(row, height)

    def clearContents(self) -> None:
        self.clear()