from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget

# ======================
# Design Tokens
# ======================
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1"  # Using the Indigo accent for links
}

class FilterTypePage(QWidget):

    def __init__(self):
        super().__init__()
        self.all_data = []
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "NAME"
        self._last_search_text = ""
        self._sort_fields = []
        self._sort_directions = {}
        self.init_ui()
        self.load_data()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)
        enabled = ["Add", "Excel", "Refresh"]

        # 1. Header Component (standardized toolbar)
        header = StandardPageHeader(
            title="Filter Type",
            subtitle="Manage categories and audit logs for filter types.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(header)
        self.main_layout.addSpacing(12)

        # 2. Search
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. REUSABLE TABLE COMPONENT
        self.table_comp = StandardTable([
            "NAME", "DESCRIPTION", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        # Reference to the internal QTableWidget for data operations
        self.table = self.table_comp.table 
        self.sort_bar = SortByWidget(self.table)

        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)

        # Shared pagination from StandardTable
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

    def load_data(self):
        # Sample data
        raw_data = [
            ("ADAPTER", "ADAPTER", "ADMIN", "20-Jun-2023", "", "", "0"),
            ("AIR BREATHER", "", "ADMIN", "20-Jun-2023", "YOSAFAT.YACOB", "20-Jun-2023", "1"),
            ("AIR FILTER", "FILTER UDARA", "ADMIN", "20-Jun-2023", "", "", "0"),
        ]
        
        # Multiply data to demonstrate pagination
        self.all_data = raw_data * 5 
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)  # keep disabled
        self.table.setRowCount(0)
        data = self.filtered_data or []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
            self.table.setRowHeight(r, 28)
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                self.table.setItem(r, c, item)

        # Global row numbers
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # Update pagination UI
        has_prev = self.current_page > 0
        has_next = end_idx < total
        start_human = 0 if total == 0 else start_idx + 1
        end_human = 0 if total == 0 else end_idx
        self.pagination.update(
            start=start_human,
            end=end_human,
            total=total,
            has_prev=has_prev,
            has_next=has_next,
            current_page=self.current_page,
            page_size=self.page_size,
            available_page_sizes=self.available_page_sizes,
        )

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}  # <-- removed +1

        col_index = header_to_index.get(self._last_filter_type, 0)  # default to first column

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            out = []
            for row in self.all_data:
                if col_index >= len(row):
                    continue
                val = "" if row[col_index] is None else str(row[col_index])
                if query in val.lower():
                    out.append(row)
            self.filtered_data = out

        self._apply_sort()
        self.current_page = 0
        self.render_page()



    def on_sort_changed(self, fields: list[str], field_directions: dict):
        """
        Handle sort changes from SortByWidget.
        
        Parameters
        ----------
        fields : list[str]
            Ordered list of field names to sort by (priority order)
        field_directions : dict
            Mapping of field name to direction ("asc" or "desc")
        """
        self._sort_fields = fields or []
        self._sort_directions = field_directions or {}
        self._apply_filter_and_reset_page()



    def _apply_sort(self):
        if not self._sort_fields or not self.filtered_data:
            return

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}

        for field in reversed(self._sort_fields):
            direction = self._sort_directions.get(field, "asc")
            reverse = (direction == "desc")
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=reverse
            )

    def _get_sort_value(self, row, idx):
        val = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val)
        numeric_cols = ["CHANGED NO"]  # only numeric fields
        if self.table_comp.headers()[idx] in numeric_cols:
            try:
                return float(str_val)
            except ValueError:
                return 0
        return str_val.lower()



    def on_page_changed(self, page_action: int) -> None:
        total = len(self.filtered_data) if self.filtered_data is not None else 0
        total_pages = (total + self.page_size - 1) // self.page_size
        if total_pages <= 0:
            self.current_page = 0
            self.render_page()
            return

        if page_action == -1:
            self.current_page = max(0, self.current_page - 1)
        elif page_action == 1:
            self.current_page = min(total_pages - 1, self.current_page + 1)
        else:
            self.current_page = max(0, min(int(page_action), total_pages - 1))

        self.render_page()

    def on_page_size_changed(self, new_size: int) -> None:
        """Handle page size change from pagination component."""
        self.page_size = new_size
        self.current_page = 0  # Reset to first page when changing page size
        self.render_page()