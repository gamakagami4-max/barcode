from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt

from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal
from components.view_detail_modal import ViewDetailModal

ROW_STANDARD = "standard"
QUERY_COLUMN_INDEX = 2
QUERY_WRAP_LIMIT = 80

# Maps human-readable labels to their index inside a row tuple.
# Row tuple shape: (row_type, CONNECTION, TABLE NAME, QUERY, ADDED BY, ADDED AT, CHANGED BY, CHANGED AT, CHANGED NO)
VIEW_DETAIL_FIELDS = [
    ("Connection",            1),
    ("Table Name",            2),
    ("Query / Link Server",   3),
    ("Added By",              4),
    ("Added At",              5),
    ("Changed By",            6),
    ("Changed At",            7),
    ("Changed No",            8),
]


def _wrap_line(line: str, limit: int) -> list[str]:
    """Break a single line into chunks of at most *limit* chars, at spaces when possible."""
    if not line or len(line) <= limit:
        return [line] if line else []
    chunks = []
    rest = line
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        segment = rest[: limit + 1]
        last_space = segment.rfind(" ")
        break_at = last_space if last_space > limit // 2 else limit
        chunks.append(rest[:break_at].rstrip())
        rest = rest[break_at:].lstrip()
    return chunks


def wrap_query_text(text: str, limit: int = QUERY_WRAP_LIMIT) -> str:
    """Insert \\n so each line is at most *limit* chars; preserves existing newlines."""
    if not text:
        return text
    result = []
    for line in text.split("\n"):
        result.extend(_wrap_line(line, limit))
    return "\n".join(result)


class SourceDataPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data = []
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "CONNECTION"
        self._last_search_text = ""
        self._sort_fields = []
        self._sort_directions = {}
        self.init_ui()
        self.load_sample_data()

    def init_ui(self):
        self.setStyleSheet("background-color: #F8FAFC;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)
        enabled = ["Add", "Excel", "Refresh", "View Detail"]

        # 1. Header (standardized toolbar)
        self.header = StandardPageHeader(
            title="Source Data Group",
            subtitle="Manage and query your enterprise data sources from a single pane.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        self._connect_header_actions()
        self.main_layout.addSpacing(12)

        # 2. Search
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. REUSABLE TABLE COMPONENT (with standard audit columns)
        self.table_comp = StandardTable([
            "CONNECTION", "TABLE NAME", "QUERY LINK SERVER", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table
        self.table.setWordWrap(True)

        col_header = self.table.horizontalHeader()

        col_header.setSectionResizeMode(0, QHeaderView.Fixed)
        col_header.setSectionResizeMode(1, QHeaderView.Fixed)
        col_header.setSectionResizeMode(2, QHeaderView.Stretch)
        col_header.setSectionResizeMode(3, QHeaderView.Fixed)
        col_header.setSectionResizeMode(4, QHeaderView.Fixed)
        col_header.setSectionResizeMode(5, QHeaderView.Fixed)
        col_header.setSectionResizeMode(6, QHeaderView.Fixed)
        col_header.setSectionResizeMode(7, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(7, 100)

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
            {"name": "conn", "label": "Connection", "type": "text", "placeholder": "Enter connection name", "required": True},
            {"name": "table_name", "label": "Table Name", "type": "text", "placeholder": "Enter table name", "required": True},
            {"name": "query", "label": "Query", "type": "text", "placeholder": "Enter SQL query", "required": True},
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
    # Table rendering
    # ------------------------------------------------------------------

    def add_data_row(self, conn, table_name, query, added_by, added_at, changed_by, changed_at, changed_no):
        row = self.table.rowCount()
        self.table.insertRow(row)
        query_display = wrap_query_text(query)

        item_conn = QTableWidgetItem(conn)
        item_conn.setData(Qt.UserRole, ROW_STANDARD)
        item_conn.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 0, item_conn)

        item_table = QTableWidgetItem(table_name)
        item_table.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 1, item_table)

        item_query = QTableWidgetItem(query_display)
        item_query.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 2, item_query)

        item_added_by = QTableWidgetItem(added_by)
        item_added_by.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 3, item_added_by)

        item_added_at = QTableWidgetItem(added_at)
        item_added_at.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 4, item_added_at)

        item_changed_by = QTableWidgetItem(changed_by)
        item_changed_by.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 5, item_changed_by)

        item_changed_at = QTableWidgetItem(changed_at)
        item_changed_at.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 6, item_changed_at)

        item_changed_no = QTableWidgetItem(changed_no)
        item_changed_no.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.table.setItem(row, 7, item_changed_no)

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data if self.filtered_data is not None else []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for item in page_data:
            self.add_data_row(item[1], item[2], item[3], item[4], item[5], item[6], item[7], item[8])

        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        self.table.resizeRowsToContents()

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
    # Data
    # ------------------------------------------------------------------

    def load_sample_data(self):
        self.all_data = []
        for i in range(50):
            if i % 3 == 0:
                self.all_data.append((
                    "expandable",
                    f"SQL Server {i}",
                    "MITMAS",
                    f"SELECT * FROM [Inventory] WHERE ID = {i}\nORDER BY CreatedAt DESC",
                    "Admin",
                    "2024-01-15",
                    "User_A",
                    "2024-02-10",
                    "2"
                ))
            else:
                self.all_data.append((
                    "standard",
                    f"MySQL Connection {i}",
                    "PROD_DATA",
                    "Direct Link",
                    "Admin",
                    "2024-01-20",
                    "-",
                    "-",
                    "0"
                ))
        self._apply_filter_and_reset_page()

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        header_to_index = {h: i + 1 for i, h in enumerate(headers)}
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
    # Sorting
    # ------------------------------------------------------------------

    def on_sort_changed(self, fields: list[str], field_directions: dict):
        self._sort_fields = fields or []
        self._sort_directions = field_directions or {}
        self._apply_filter_and_reset_page()

    def _apply_sort(self):
        if not self._sort_fields or not self.filtered_data:
            return

        headers = self.table_comp.headers()
        header_to_index = {h: i + 1 for i, h in enumerate(headers)}

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
        if idx >= len(row):
            return ""
        val = row[idx]
        str_val = "" if val is None else str(val)
        try:
            return float(str_val.replace(',', ''))
        except (ValueError, AttributeError):
            return str_val.lower()

    # ------------------------------------------------------------------
    # Header action wiring
    # ------------------------------------------------------------------

    def _connect_header_actions(self):
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete", "View Detail"]:
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
                elif action == "View Detail":
                    btn.clicked.connect(self.handle_view_detail_action)

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Source Data",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime

        conn = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        query = data.get("query", "").strip()

        if not conn or not table_name or not query:
            print("All fields are required")
            return

        added_by = "Admin"
        added_at = datetime.date.today().strftime("%Y-%m-%d")
        changed_by = "-"
        changed_at = "-"
        changed_no = "0"

        new_row = ("standard", conn, table_name, query, added_by, added_at, changed_by, changed_at, changed_no)
        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        print("Export clicked")

    def handle_view_detail_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        # Build (label, value) pairs from the row tuple
        fields = [
            (label, str(row[i]) if i < len(row) and row[i] is not None else "")
            for label, i in VIEW_DETAIL_FIELDS
        ]

        modal = ViewDetailModal(
            title="Row Detail",
            subtitle="Full details for the selected record.",
            fields=fields,
            parent=self,
        )
        modal.exec()

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        modal = GenericFormModal(
            title="Edit Source Data",
            fields=self.form_schema,
            parent=self,
            mode="edit",
            initial_data={
                "conn": row[1],
                "table_name": row[2],
                "query": row[3],
            }
        )

        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx, data):
        conn = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        query = data.get("query", "").strip()

        if not conn or not table_name or not query:
            print("All fields required")
            return

        import datetime
        today = datetime.date.today().strftime("%Y-%m-%d")

        old_row = self.all_data[idx]

        updated_row = (
            old_row[0],
            conn,
            table_name,
            query,
            old_row[4],
            old_row[5],
            "Admin",
            today,
            str(int(old_row[8]) + 1 if old_row[8].isdigit() else 1)
        )

        self.all_data[idx] = updated_row
        self._apply_filter_and_reset_page()

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        del self.all_data[idx]
        self._apply_filter_and_reset_page()