from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem, 
    QHeaderView, QFrame, QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from components.search_bar import StandardSearchBar
from components.standard_button import StandardButton
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "border": "#E2E8F0",
    "panel_bg": "#FFFFFF",
    "text_main": "#1E293B",
    "text_muted": "#64748B"
}

class MasterItemPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data = []
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "ITEM CODE"
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

        # 1. Page Header (standardized toolbar)
        header = StandardPageHeader(
            title="Master Item",
            subtitle="View and manage core product inventory and part mappings.",
        )
        self.main_layout.addWidget(header)
        self.main_layout.addSpacing(12)

        # 2. Search Bar
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. Content Area
        self.content_layout = QHBoxLayout()
        
        headers = ["ITEM CODE", "NAME", "BRAND", "WHS", "PART NO", "QTY", "UOM", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"]
        self.table_comp = StandardTable(headers)
        self.table = self.table_comp.table
        
        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 100)
        self.table.setColumnWidth(8, 100)
        self.table.setColumnWidth(9, 60)
        h_header.setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        
        self.content_layout.addWidget(self.table_comp, stretch=4)

        # 4. Detail Panel
        self.detail_panel = self._create_detail_panel()
        self.detail_panel.setVisible(False)
        self.content_layout.addWidget(self.detail_panel, stretch=1)

        self.main_layout.addLayout(self.content_layout)

        self.sort_bar = SortByWidget(self.table)

        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)

        # Shared pagination from StandardTable (25 per page)
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

    def _create_detail_panel(self):
        panel = QFrame()
        panel.setFixedWidth(380)
        panel.setStyleSheet(f"background: {COLORS['panel_bg']}; border-left: 1px solid {COLORS['border']};")
        
        layout = QVBoxLayout(panel)
        top_bar = QHBoxLayout()
        self.detail_title = QLabel("Item Details")
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        
        close_btn = StandardButton("", icon_name="fa5s.times", variant="ghost")
        close_btn.clicked.connect(lambda: panel.setVisible(False))
        
        top_bar.addWidget(self.detail_title)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.info_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return panel

    def load_data(self):
        self.all_data = []
        for i in range(50):
            qty_val = 25899 + i 
            self.all_data.append((
                f"EIF1-SFF1-FC-{1001+i}", f"FILTER CARTRIDGE MD {1000+i}", 
                "SFF", "EIF", f"FC-{1001+i}", "MB 220900", "5-13240032-0", 
                "31973-44100", "Z636", f"{qty_val:,}", "PCS"
            ))
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data or []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
            display_indices = [0, 1, 2, 3, 4, 9, 10]  # columns to display

            for c_idx, data_idx in enumerate(display_indices):
                val = str(row_data[data_idx])
                item = QTableWidgetItem(val)
                font = item.font()
                font.setPointSize(9)
                item.setFont(font)

                # Special styling for ITEM CODE (first column)
                if c_idx == 0:
                    item.setForeground(QColor(COLORS["link"]))

                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c_idx, item)

            # Dummy cells for ADDED BY / ADDED AT
            self.table.setItem(r, 7, QTableWidgetItem("-"))
            self.table.setItem(r, 8, QTableWidgetItem("-"))

        # Row numbers (vertical header)
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # Do NOT enable native sorting to avoid conflicts with manual sort
        self.table.setSortingEnabled(True)

        # Update pagination
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


    def show_details(self, data):
        self.detail_panel.setVisible(True)
        self.detail_title.setText(data[0])
        
        # Clear layout
        for i in reversed(range(self.info_layout.count())): 
            if self.info_layout.itemAt(i).widget():
                self.info_layout.itemAt(i).widget().setParent(None)

        fields = [
            ("Description", data[1]), ("Brand", data[2]), ("Warehouse", data[3]),
            ("Part No Print", data[4]), ("Interchange 1", data[5]), 
            ("Interchange 2", data[6]), ("Interchange 3", data[7]),
            ("Interchange 4", data[8]), ("Stock", f"{data[9]} {data[10]}")
        ]

        for label, val in fields:
            lbl = QLabel(f"<b>{label}</b><br><span style='color:{COLORS['text_muted']}'>{val}</span>")
            lbl.setWordWrap(True)
            self.info_layout.addWidget(lbl)
            self.info_layout.addSpacing(10)
        self.info_layout.addStretch()

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        # Map headers directly to their 0-based column indices in the data tuples
        header_to_index = {h: i for i, h in enumerate(headers)}

        col_index = header_to_index.get(self._last_filter_type, 0)

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
        header_to_index = {h: i for i, h in enumerate(headers)}  # <-- 0-based

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
        numeric_cols = ["CHANGED NO", "QTY"]
        if self.table_comp.headers()[idx] in numeric_cols:
            try:
                return float(str_val.replace(",", ""))
            except ValueError:
                return 0
        return str_val.lower()

