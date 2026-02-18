import datetime

import openpyxl
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QHeaderView, QMessageBox, QTableWidgetItem, QVBoxLayout, QWidget,
)

from components.generic_form_modal import GenericFormModal
from components.search_bar import StandardSearchBar
from components.sort_by_widget import SortByWidget
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable

ROW_STANDARD = "standard"
QUERY_WRAP_LIMIT = 80

# (label, tuple index) for the View Detail modal
VIEW_DETAIL_FIELDS = [
    ("Connection",          1),
    ("Table Name",          2),
    ("Query / Link Server", 3),
    ("Added By",            4),
    ("Added At",            5),
    ("Changed By",          6),
    ("Changed At",          7),
    ("Changed No",          8),
]

# Row shape: (key, connection, table_name, query, added_by, added_at, changed_by, changed_at, changed_no)

CONNECTION_TABLES: dict[str, list[str]] = {
    "SQL Server A":  ["MITMAS", "ORDERS", "INVENTORY", "CUSTOMERS"],
    "SQL Server B":  ["PROD_DATA", "STAGING", "LOGS"],
    "MySQL Prod":    ["users", "transactions", "audit_log"],
    "MySQL Dev":     ["users_dev", "transactions_dev"],
    "PostgreSQL DW": ["fact_sales", "dim_product", "dim_date"],
}


# ── Text helpers ──────────────────────────────────────────────────────────────

def _wrap_line(line: str, limit: int) -> list[str]:
    """Break one line into ≤limit-char chunks, splitting at spaces when possible."""
    if not line or len(line) <= limit:
        return [line] if line else []
    chunks, rest = [], line
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        seg = rest[: limit + 1]
        bp = seg.rfind(" ")
        bp = bp if bp > limit // 2 else limit
        chunks.append(rest[:bp].rstrip())
        rest = rest[bp:].lstrip()
    return chunks


def wrap_query_text(text: str, limit: int = QUERY_WRAP_LIMIT) -> str:
    """Wrap query text so every line is ≤limit chars; preserves existing newlines."""
    if not text:
        return text
    result = []
    for line in text.split("\n"):
        result.extend(_wrap_line(line, limit))
    return "\n".join(result)


# ── Form schema ───────────────────────────────────────────────────────────────

def _build_form_schema(initial_data: dict | None = None, mode: str = "add") -> list[dict]:
    """Return field definitions for the add/edit modal."""
    schema = [
        {
            "name": "conn",
            "label": "Connection",
            "type": "cascade_combo",
            "options": CONNECTION_TABLES,
            "child": "table_name",
            "required": True,
        },
        {
            "name": "table_name",
            "label": "Table Name",
            "type": "combo",
            "options": [],
            "required": True,
        },
        {
            "name": "query",
            "label": "Query / Link Server",
            "type": "text",
            "placeholder": "Enter SQL query or link server path",
            "required": True,
        },
    ]

    if mode == "edit":
        # Audit fields shown read-only in edit mode
        schema += [
            {"name": "added_by",   "label": "Added By",   "type": "readonly"},
            {"name": "added_at",   "label": "Added At",   "type": "readonly"},
            {"name": "changed_by", "label": "Changed By", "type": "readonly"},
            {"name": "changed_at", "label": "Changed At", "type": "readonly"},
            {"name": "changed_no", "label": "Changed No", "type": "readonly"},
        ]

    return schema


# ── Page ──────────────────────────────────────────────────────────────────────

class SourceDataPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data: list[tuple] = []
        self.filtered_data: list[tuple] = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "CONNECTION"
        self._last_search_text = ""
        self._sort_fields: list[str] = []
        self._sort_directions: dict[str, str] = {}
        self._init_ui()
        self.load_sample_data()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet("background-color: #F8FAFC;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 12)
        layout.setSpacing(0)
        self.main_layout = layout

        enabled_actions = ["Add", "Excel", "Refresh", "View Detail"]

        # Header
        self.header = StandardPageHeader(
            title="Source Data Group",
            subtitle="Manage and query your enterprise data sources from a single pane.",
            enabled_actions=enabled_actions,
        )
        layout.addWidget(self.header)
        self._connect_header_actions()
        layout.addSpacing(12)

        # Search bar
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        layout.addWidget(self.search_bar)
        layout.addSpacing(5)

        # Table
        self.table_comp = StandardTable([
            "CONNECTION", "TABLE NAME", "QUERY LINK SERVER",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        self.table = self.table_comp.table
        self.table.setWordWrap(True)
        self._configure_table_columns()

        # Sort bar
        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        layout.addWidget(self.sort_bar)
        layout.addSpacing(8)

        layout.addWidget(self.table_comp)
        layout.addSpacing(16)

        # Pagination
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

        self.sort_bar.initialize_default_sort()
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

    def _configure_table_columns(self):
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        hdr.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(5, QHeaderView.Fixed)
        hdr.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QHeaderView.Fixed)

        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(7, 100)

    # ── Selection helpers ─────────────────────────────────────────────────────

    def _on_row_selection_changed(self):
        self._update_selection_dependent_state(bool(self.table.selectedItems()))

    def _update_selection_dependent_state(self, enabled: bool):
        for label in ("Edit", "Delete", "View Detail"):
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(enabled)

    def _get_selected_global_index(self) -> int | None:
        """Return the all_data index for the currently selected row, or None."""
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        global_idx = self.current_page * self.page_size + rows[0].row()
        if global_idx >= len(self.filtered_data):
            return None
        return self.all_data.index(self.filtered_data[global_idx])

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _make_item(self, text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        return it

    def _add_table_row(self, conn, table_name, query, added_by, added_at,
                       changed_by, changed_at, changed_no):
        row = self.table.rowCount()
        self.table.insertRow(row)
        item_conn = self._make_item(conn)
        item_conn.setData(Qt.UserRole, ROW_STANDARD)
        self.table.setItem(row, 0, item_conn)
        self.table.setItem(row, 1, self._make_item(table_name))
        self.table.setItem(row, 2, self._make_item(wrap_query_text(query)))
        self.table.setItem(row, 3, self._make_item(added_by))
        self.table.setItem(row, 4, self._make_item(added_at))
        self.table.setItem(row, 5, self._make_item(changed_by))
        self.table.setItem(row, 6, self._make_item(changed_at))
        self.table.setItem(row, 7, self._make_item(changed_no))

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        data = self.filtered_data or []
        total = len(data)
        start = self.current_page * self.page_size
        end = min(start + self.page_size, total)

        for item in data[start:end]:
            self._add_table_row(item[1], item[2], item[3], item[4], item[5],
                                 item[6], item[7], item[8])

        for r in range(end - start):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start + r + 1)))

        self.table.resizeRowsToContents()
        self.pagination.update(
            start=0 if total == 0 else start + 1,
            end=0 if total == 0 else end,
            total=total,
            has_prev=self.current_page > 0,
            has_next=end < total,
            current_page=self.current_page,
            page_size=self.page_size,
            available_page_sizes=self.available_page_sizes,
        )

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_sample_data(self):
        self.all_data = []
        conn_names = list(CONNECTION_TABLES.keys())
        for i in range(50):
            conn = conn_names[i % len(conn_names)]
            table_name = CONNECTION_TABLES[conn][i % len(CONNECTION_TABLES[conn])]
            if i % 3 == 0:
                row = (
                    "expandable", conn, table_name,
                    f"SELECT * FROM [{table_name}] WHERE ID = {i}\nORDER BY CreatedAt DESC",
                    "Admin", "2024-01-15", "User_A", "2024-02-10", "2",
                )
            else:
                row = (
                    "standard", conn, table_name, "Direct Link",
                    "Admin", "2024-01-20", "-", "-", "0",
                )
            self.all_data.append(row)
        self._apply_filter_and_reset_page()

    # ── Filtering & sorting ───────────────────────────────────────────────────

    def filter_table(self, filter_type: str, search_text: str):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query = (self._last_search_text or "").lower().strip()
        headers = self.table_comp.headers()
        col_index = {h: i + 1 for i, h in enumerate(headers)}.get(self._last_filter_type, 1)

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            self.filtered_data = [
                row for row in self.all_data
                if col_index < len(row) and query in str(row[col_index] or "").lower()
            ]

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
        header_to_index = {h: i + 1 for i, h in enumerate(self.table_comp.headers())}
        for field in reversed(self._sort_fields):
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._sort_key(row, i),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

    def _sort_key(self, row: tuple, idx: int):
        val = str(row[idx]) if idx < len(row) and row[idx] is not None else ""
        try:
            return float(val.replace(",", ""))
        except ValueError:
            return val.lower()

    # ── Pagination ────────────────────────────────────────────────────────────

    def on_page_changed(self, page_action: int):
        total = len(self.filtered_data or [])
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
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

    # ── Header button wiring ──────────────────────────────────────────────────

    def _connect_header_actions(self):
        mapping = {
            "Refresh":     self.load_sample_data,
            "Add":         self.handle_add_action,
            "Excel":       self.handle_export_action,
            "Edit":        self.handle_edit_action,
            "Delete":      self.handle_delete_action,
            "View Detail": self.handle_view_detail_action,
        }
        for label, slot in mapping.items():
            btn = self.header.get_action_button(label)
            if btn:
                btn.clicked.connect(slot)

    # ── Action handlers ───────────────────────────────────────────────────────

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Source Data",
            fields=_build_form_schema(mode="add"),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        conn       = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        query      = data.get("query", "").strip()

        if not all([conn, table_name, query]):
            print("All fields are required")
            return

        key = f"{conn}::{table_name}"
        if any(r[0] == key for r in self.all_data):
            QMessageBox.warning(self, "Duplicate Key",
                                f"A record for '{conn} / {table_name}' already exists.")
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.all_data.insert(0, (key, conn, table_name, query, "Admin", now, "-", "-", "0"))
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "source_data.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Source Data"
        ws.append(["CONNECTION", "TABLE NAME", "QUERY / LINK SERVER",
                   "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"])
        for row in self.filtered_data:
            ws.append([str(row[i]) if row[i] is not None else "" for i in range(1, 9)])
        wb.save(path)
        QMessageBox.information(self, "Export Complete",
                                f"Exported {len(self.filtered_data)} records to:\n{path}")

    def handle_view_detail_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]
        fields = [
            (label, str(row[i]) if i < len(row) and row[i] is not None else "")
            for label, i in VIEW_DETAIL_FIELDS
        ]
        GenericFormModal(
            title="Row Detail",
            subtitle="Full details for the selected record.",
            fields=fields,
            parent=self,
            mode="view",
        ).exec()

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]
        initial = {
            "conn":       row[1],
            "table_name": row[2],
            "query":      row[3],
            "added_by":   row[4],
            "added_at":   row[5],
            "changed_by": row[6],
            "changed_at": row[7],
            "changed_no": row[8],
        }
        modal = GenericFormModal(
            title="Edit Source Data",
            fields=_build_form_schema(initial_data=initial, mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx: int, data: dict):
        conn       = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        query      = data.get("query", "").strip()

        if not all([conn, table_name, query]):
            print("All fields required")
            return

        old_row = self.all_data[idx]
        new_key = f"{conn}::{table_name}"

        if any(r[0] == new_key and r != old_row for r in self.all_data):
            QMessageBox.warning(self, "Duplicate Key",
                                f"A record for '{conn} / {table_name}' already exists.")
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changed_no = str(int(old_row[8]) + 1) if old_row[8].isdigit() else "1"
        self.all_data[idx] = (
            new_key, conn, table_name, query,
            old_row[4], old_row[5],   # added_by / added_at unchanged
            "Admin", now, changed_no,
        )
        self._apply_filter_and_reset_page()

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText("Are you sure you want to delete this record?")
        msg.setInformativeText(f"Connection: {row[1]}\nTable Name: {row[2]}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)
        if msg.exec() == QMessageBox.Yes:
            del self.all_data[idx]
            self._apply_filter_and_reset_page()