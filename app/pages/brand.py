from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QLabel, QHBoxLayout, QHeaderView
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
    "text_main": "#1E293B"
}

class BrandPage(QWidget):
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
        self.load_sample_data()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)
        enabled = ["Add", "Excel", "Refresh"]

        # 1. Header (standardized toolbar)
        self.header = StandardPageHeader(
            title="Brand",
            subtitle="Organize and monitor brand assets across your enterprise.",
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

        # 3. Table Configuration
        self.table_comp = StandardTable([
            "CODE", "NAME", "CASE", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table
        
        h_header = self.table.horizontalHeader()
        # Fixed widths so columns don't get squeezed; total can exceed viewport → horizontal scroll
        h_header.setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, 100)   # CODE
        self.table.setColumnWidth(1, 280)   # NAME (wide so "Vanguard Systems Enterprise Edition" etc. fit)
        self.table.setColumnWidth(2, 120)   # CASE
        self.table.setColumnWidth(3, 120)   # ADDED BY
        self.table.setColumnWidth(4, 110)   # ADDED ON
        self.table.setColumnWidth(5, 120)   # CHANGE BY
        self.table.setColumnWidth(6, 110)   # CHANGE ON
        self.table.setColumnWidth(7, 90)    # CHANGE NO
        
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
        
        # Initialize default sort AFTER pagination is set up
        self.sort_bar.initialize_default_sort()

        # Form schema for Add/Edit modal
        self.form_schema = [
            {
                "name": "code", 
                "label": "Brand Code", 
                "type": "text", 
                "placeholder": "Enter brand code (e.g., BR-001)", 
                "required": True
            },
            {
                "name": "name", 
                "label": "Brand Name", 
                "type": "text", 
                "placeholder": "Enter brand name", 
                "required": True
            },
            {
                "name": "case", 
                "label": "Case Status", 
                "type": "combo", 
                "options": ["AVAILABLE", "NOT AVAILABLE", "PENDING"], 
                "required": True
            },
        ]

        # Track table selection to enable Edit/Delete
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)

        # Initially disable edit/delete
        self._update_edit_delete_state(False)

    def _on_row_selection_changed(self):
        has_selection = bool(self.table.selectedItems())
        self._update_edit_delete_state(has_selection)

    def _update_edit_delete_state(self, enabled: bool):
        edit_btn = self.header.get_action_button("Edit")
        delete_btn = self.header.get_action_button("Delete")

        if edit_btn:
            edit_btn.setEnabled(enabled)
        if delete_btn:
            delete_btn.setEnabled(enabled)

    def _get_selected_global_index(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None

        table_row = selected_rows[0].row()
        global_index = (self.current_page * self.page_size) + table_row

        if global_index >= len(self.filtered_data):
            return None

        actual_row = self.filtered_data[global_index]
        return self.all_data.index(actual_row)


    def load_sample_data(self):
        raw_brands = [
            ("BR-001", "Lumina Tech International Solutions", "AVAILABLE", "Admin_User", "2026-02-01", "Systems", "2026-02-02", "102"),
            ("BR-042", "Apex Global", "NOT AVAILABLE", "Super_Admin", "2026-02-04", "User_A", "2026-02-05", "45"),
            ("BR-056", "Vanguard Systems Enterprise Edition", "AVAILABLE", "Admin_User", "2026-02-05", "-", "-", "0"),
            ("BR-098", "Nexus Brands", "PENDING", "Manager_X", "2026-02-06", "Admin_User", "2026-02-07", "12"),
        ]
        self.all_data = raw_brands * 4
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data if self.filtered_data is not None else []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
            self.table.setRowHeight(r, 28)

            # CODE
            code_item = QTableWidgetItem(row_data[0])
            code_item.setForeground(QColor(COLORS["link"]))
            font = code_item.font()
            font.setPointSize(9)
            code_item.setFont(font)
            code_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(r, 0, code_item)

            # NAME
            name_label = QLabel(row_data[1])
            name_label.setWordWrap(True)
            name_label.setStyleSheet(
                f"font-size: 9pt; color: {COLORS['text_main']}; background: transparent; border: none;"
            )
            name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            invisible_name_item = QTableWidgetItem()
            invisible_name_item.setBackground(QColor(0, 0, 0, 0))
            self.table.setItem(r, 1, invisible_name_item)
            self.table.setCellWidget(r, 1, name_label)

            # CASE (plain centered text, no badge)
            case_item = QTableWidgetItem(row_data[2])
            case_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 2, case_item)

            # METADATA
            # Indices adjusted since CASE no longer uses extra color fields
            cols = [
                (3, 3, Qt.AlignLeft),  # ADDED BY
                (4, 4, Qt.AlignLeft),  # ADDED AT
                (5, 5, Qt.AlignLeft),  # CHANGED BY
                (6, 6, Qt.AlignLeft),  # CHANGED AT
                (7, 7, Qt.AlignCenter) # CHANGED NO
            ]
            for col_idx, data_idx, align in cols:
                item = QTableWidgetItem(str(row_data[data_idx]))
                item.setTextAlignment(align | Qt.AlignVCenter)
                self.table.setItem(r, col_idx, item)

        # Global row numbers (1-based across all pages)
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
        header_to_index = {h: i for i, h in enumerate(headers)}

        col_index = header_to_index.get(self._last_filter_type, 1)

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
        """Apply multi-field sorting with individual directions to filtered_data."""
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

        numeric_cols = ["CHANGED NO"]  # only numeric columns
        if self.table_comp.headers()[idx] in numeric_cols:
            try:
                return float(str_val)
            except ValueError:
                return 0

        return str_val.lower()

    def _connect_header_actions(self):
        """Connect header action buttons to their handlers."""
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

    def handle_add_action(self):
        """Open the Add Brand modal."""
        modal = GenericFormModal(
            title="Add Brand",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime
        
        code = data.get("code", "").strip()
        name = data.get("name", "").strip()
        case_status = data.get("case", "AVAILABLE")
        
        if not code or not name:
            print("Brand Code and Name are required")
            return
        
        added_by = "Admin_User"
        added_at = datetime.date.today().strftime("%Y-%m-%d")
        changed_by = "-"
        changed_at = "-"
        changed_no = "0"
        
        new_row = (
            code,
            name,
            case_status,
            added_by,
            added_at,
            changed_by,
            changed_at,
            changed_no,
        )
        
        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()


    def handle_export_action(self):
        """Handle Excel export action."""
        print("Export to Excel clicked")

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        modal = GenericFormModal(
            title="Edit Brand",
            fields=self.form_schema,
            parent=self,
            mode="edit",
            initial_data={
                "code": row[0],
                "name": row[1],
                "case": row[2],
            }
        )

        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx, data):
        import datetime

        code = data.get("code", "").strip()
        name = data.get("name", "").strip()
        case_status = data.get("case", "AVAILABLE")

        if not code or not name:
            print("Brand Code and Name are required")
            return

        old_row = self.all_data[idx]

        today = datetime.date.today().strftime("%Y-%m-%d")

        updated_row = (
            code,
            name,
            case_status,
            old_row[3],   # added_by
            old_row[4],   # added_at
            "Admin_User", # changed_by
            today,        # changed_at
            str(int(old_row[7]) + 1 if old_row[7].isdigit() else 1),
        )

        self.all_data[idx] = updated_row
        self._apply_filter_and_reset_page()



    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        del self.all_data[idx]
        self._apply_filter_and_reset_page()