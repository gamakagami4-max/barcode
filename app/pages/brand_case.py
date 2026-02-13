from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, 
    QTableWidgetItem, QHBoxLayout, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "border": "#E2E8F0",
    "text_muted": "#94A3B8"
}

class BrandCasePage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data = []
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "CODE"
        self._last_search_text = ""
        self._sort_fields = []
        self._sort_directions = {}
        self.form_schema = [
            {
                "name": "code",
                "label": "Code",
                "type": "text",
                "required": True,
                "placeholder": "Enter brand code"
            },
            {
                "name": "type_case",
                "label": "Type Case",
                "type": "combo",  # Fixed from "select" to "combo"
                "options": ["TITLE", "UPPER"],
                "required": True
            }
        ]
        self.init_ui()
        self.load_sample_data()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        # 1. Header
        enabled = ["Add", "Excel", "Refresh"]
        self.header = StandardPageHeader(
            title="Brand Case",
            subtitle="Configure casing rules for brand codes (TITLE vs UPPER).",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        # 2. Search Bar
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. Table
        self.table_comp = StandardTable(["CODE", "TYPE CASE", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"])
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 250)  # CODE
        h_header.setSectionResizeMode(1, QHeaderView.Stretch)
        h_header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h_header.setSectionResizeMode(3, QHeaderView.ResizeToContents)

        # 4. Sort bar
        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)

        # 5. Pagination
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

    def _connect_header_actions(self):
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete"]:
            btn = self.header.get_action_button(action)
            if btn:
                if action == "Refresh":
                    btn.clicked.connect(self.load_sample_data)
                elif action == "Add":
                    btn.clicked.connect(self.handle_add_action)
                elif action == "Excel":
                    btn.clicked.connect(self.handle_export_action)
                elif action == "Edit":
                    btn.clicked.connect(self.handle_edit_action)
                elif action == "Delete":
                    btn.clicked.connect(self.handle_delete_action)

    def load_sample_data(self):
        case_data = [
            ("CAR", "TITLE", "Admin", "2024-01-01", "Admin", "2024-01-02", "1", "#DCFCE7", "#166534", "-"),
            ("FVP", "UPPER", "User1", "2024-01-05", "-", "-", "0", "#FFEDD5", "#9A3412", "-"),
        ]
        self.all_data = case_data * 20
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
            display_indices = [0, 1, 2, 3, 4, 5, 6]  # Table columns to display

            for c_idx, data_idx in enumerate(display_indices):
                val = str(row_data[data_idx]) if data_idx < len(row_data) else "-"
                item = QTableWidgetItem(val)
                font = item.font()
                font.setPointSize(9)
                item.setFont(font)

                if c_idx == 0:
                    item.setForeground(QColor(COLORS["link"]))

                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c_idx, item)

            # Fill missing columns if necessary
            for col in range(len(display_indices), self.table.columnCount()):
                self.table.setItem(r, col, QTableWidgetItem("-"))

        # Row numbers
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # Keep sorting disabled to avoid conflicts
        # self.table.setSortingEnabled(True)

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

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query = (self._last_search_text or "").lower().strip()
        headers = self.table_comp.headers()

        try:
            col_index = headers.index(self._last_filter_type)
        except ValueError:
            col_index = 0

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            self.filtered_data = [
                row for row in self.all_data
                if col_index < len(row) and query in str(row[col_index]).lower()
            ]

        self._apply_sort()
        self.current_page = 0
        self.render_page()

    def on_page_changed(self, page_action: int):
        total = len(self.filtered_data) if self.filtered_data else 0
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

    def on_page_size_changed(self, new_size: int):
        self.page_size = new_size
        self.current_page = 0
        self.render_page()

    def on_sort_changed(self, fields: list[str], field_directions: dict):
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
            reverse = direction == "desc"
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
                return float(str_val)
            except ValueError:
                return 0
        return str_val.lower()

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Brand Case",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime
        
        code = data.get("code", "").strip()
        type_case = data.get("type_case", "TITLE")
        
        if not code:
            print("Code is required")
            return
        
        if type_case == "TITLE":
            bg, fg = "#DCFCE7", "#166534"
        else:
            bg, fg = "#FFEDD5", "#9A3412"

        added_by = "Admin"
        added_at = datetime.date.today().strftime("%Y-%m-%d")
        changed_by = "-"
        changed_at = "-"
        changed_no = "0"

        new_row = (
            code,
            type_case,
            added_by,
            added_at,
            changed_by,
            changed_at,
            changed_no,
            bg,
            fg,
            "-"
        )
        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()

    def handle_edit_action(self):
        row = self.table.currentRow()
        if row < 0:
            return

        global_index = (self.current_page * self.page_size) + row
        if global_index >= len(self.filtered_data):
            return

        item = self.filtered_data[global_index]
        initial_data = {"code": item[0], "type_case": item[1]}

        modal = GenericFormModal(
            title="Edit Brand Case",
            fields=self.form_schema,
            initial_data=initial_data,
            parent=self,
            mode="edit"
        )
        modal.formSubmitted.connect(
            lambda data, idx=global_index: self._on_edit_submitted(idx, data)
        )
        modal.exec()

    def _on_edit_submitted(self, index: int, data: dict):
        import datetime
        
        code = data.get("code", "").strip()
        type_case = data.get("type_case", "TITLE")
        
        if not code:
            print("Code is required")
            return
        
        if type_case == "TITLE":
            bg, fg = "#DCFCE7", "#166534"
        else:
            bg, fg = "#FFEDD5", "#9A3412"

        # Get original item to preserve original ADDED BY/AT
        old_item = self.filtered_data[index]
        added_by = old_item[2] if len(old_item) > 2 else "Admin"
        added_at = old_item[3] if len(old_item) > 3 else "2024-01-01"
        
        changed_by = "Admin"
        changed_at = datetime.date.today().strftime("%Y-%m-%d")
        
        # Increment change number
        try:
            old_change_no = int(old_item[6]) if len(old_item) > 6 else 0
            changed_no = str(old_change_no + 1)
        except (ValueError, TypeError):
            changed_no = "1"

        updated_row = (
            code,
            type_case,
            added_by,
            added_at,
            changed_by,
            changed_at,
            changed_no,
            bg,
            fg,
            "-"
        )

        original_index = self.all_data.index(old_item)
        self.all_data[original_index] = updated_row
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        print("Export clicked")

    def handle_delete_action(self):
        print("Delete clicked")