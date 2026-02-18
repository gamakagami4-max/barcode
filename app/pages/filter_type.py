from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal
from PySide6.QtWidgets import QMessageBox

# ======================
# Design Tokens
# ======================
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1"
}

# Maps human-readable labels to their index inside a row tuple.
# Row tuple shape: (NAME, DESCRIPTION, ADDED BY, ADDED AT, CHANGED BY, CHANGED AT, CHANGED NO)
VIEW_DETAIL_FIELDS = [
    ("Name",        0),
    ("Description", 1),
    ("Added By",    2),
    ("Added At",    3),
    ("Changed By",  4),
    ("Changed At",  5),
    ("Changed No",  6),
]


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
        enabled = ["Add", "Excel", "Refresh", "View Detail"]

        # 1. Header
        self.header = StandardPageHeader(
            title="Filter Type",
            subtitle="Manage categories and audit logs for filter types.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        # 2. Search
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. Table
        self.table_comp = StandardTable([
            "NAME", "DESCRIPTION", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
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

        # Initialize default sort AFTER pagination is set up
        self.sort_bar.initialize_default_sort()

        self.form_schema = [
            {
                "name": "name",
                "label": "Filter Type Name",
                "type": "text",
                "placeholder": "Enter filter type name",
                "required": True
            },
            {
                "name": "description",
                "label": "Description",
                "type": "text",
                "placeholder": "Enter description (optional)",
                "required": False
            },
        ]

        # Track table selection to enable Edit / Delete / View Detail
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)

        # Initially disable selection-dependent buttons
        self._update_selection_dependent_state(False)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _on_row_selection_changed(self):
        has_selection = bool(self.table.selectedItems())
        self._update_selection_dependent_state(has_selection)

    def _update_selection_dependent_state(self, enabled: bool):
        for label in ("Edit", "Delete", "View Detail"):
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(enabled)

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

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def load_data(self):
        raw_data = [
            ("ADAPTER",     "ADAPTER",      "ADMIN", "20-Jun-2023", "",               "",            "0"),
            ("AIR BREATHER","",             "ADMIN", "20-Jun-2023", "YOSAFAT.YACOB",  "20-Jun-2023", "1"),
            ("AIR FILTER",  "FILTER UDARA", "ADMIN", "20-Jun-2023", "",               "",            "0"),
        ]
        self.all_data = raw_data * 5
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
            self.table.setRowHeight(r, 28)
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                self.table.setItem(r, c, item)

        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

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

    # ------------------------------------------------------------------
    # Filter / sort
    # ------------------------------------------------------------------

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
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
        numeric_cols = ["CHANGED NO"]
        if self.table_comp.headers()[idx] in numeric_cols:
            try:
                return float(str_val)
            except ValueError:
                return 0
        return str_val.lower()

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

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
        self.page_size = new_size
        self.current_page = 0
        self.render_page()

    # ------------------------------------------------------------------
    # Header action wiring
    # ------------------------------------------------------------------

    def _connect_header_actions(self):
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete", "View Detail"]:
            btn = self.header.get_action_button(action)
            if btn:
                if action == "Refresh":
                    btn.clicked.connect(self.load_data)
                elif action == "Add":
                    btn.clicked.connect(self.handle_add_action)
                elif action == "Excel":
                    btn.clicked.connect(self.handle_export_action)
                elif action == "Edit":
                    btn.clicked.connect(self.handle_edit_action)
                elif action == "Delete":
                    btn.clicked.connect(self.handle_delete_action)
                elif action == "View Detail":
                    btn.clicked.connect(self.handle_view_detail_action)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Filter Type",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime

        name = data.get("name", "").strip()
        description = data.get("description", "").strip()

        if not name:
            print("Filter Type Name is required")
            return

        added_by = "ADMIN"
        added_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # date + time

        new_row = (name, description, added_by, added_at, "", "", "0")
        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "filter_type.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Filter Type"

        headers = ["NAME", "DESCRIPTION", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"]
        ws.append(headers)

        for row in self.filtered_data:
            ws.append([str(val) if val is not None else "" for val in row])

        wb.save(path)
        QMessageBox.information(self, "Export Complete", f"Exported {len(self.filtered_data)} records to:\n{path}")

    def handle_view_detail_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        fields = [
            (label, str(row[i]) if i < len(row) and row[i] is not None else "")
            for label, i in VIEW_DETAIL_FIELDS
        ]

        modal = GenericFormModal(
            title="Filter Type Detail",
            subtitle="Full details for the selected filter type.",
            fields=fields,
            parent=self,
            mode="view"
        )
        modal.exec()

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        modal = GenericFormModal(
            title="Edit Filter Type",
            fields=self.form_schema,
            parent=self,
            mode="edit",
            initial_data={
                "name": row[0],
                "description": row[1],
            }
        )

        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx, data):
        import datetime

        name = data.get("name", "").strip()
        description = data.get("description", "").strip()

        if not name:
            print("Filter Type Name is required")
            return

        old_row = self.all_data[idx]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        updated_row = (
            name,
            description,
            old_row[2],
            old_row[3],
            "ADMIN",
            now,
            str(int(old_row[6]) + 1 if old_row[6].isdigit() else 1),
        )

        self.all_data[idx] = updated_row
        self._apply_filter_and_reset_page()

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]
        name = row[0]

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f"Are you sure you want to delete \"{name}\"?")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            del self.all_data[idx]
            self._apply_filter_and_reset_page()