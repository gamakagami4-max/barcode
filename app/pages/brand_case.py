from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel,
    QTableWidgetItem, QHBoxLayout, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal

# --- Design Tokens ---
COLORS = {
    "bg_main":   "#F8FAFC",
    "link":      "#6366F1",
    "border":    "#E2E8F0",
    "text_muted":"#94A3B8"
}

# Row tuple shape:
# (CODE, TYPE_CASE, ADDED_BY, ADDED_AT, CHANGED_BY, CHANGED_AT, CHANGED_NO, bg, fg, misc)
VIEW_DETAIL_FIELDS = [
    ("Code",       0),
    ("Type Case",  1),
    ("Added By",   2),
    ("Added At",   3),
    ("Changed By", 4),
    ("Changed At", 5),
    ("Changed No", 6),
]


def _build_form_schema(mode: str = "add") -> list[dict]:
    """
    Add mode  → editable Code + Type Case only.
    Edit mode → same editable fields + 5 readonly audit fields below.
    """
    schema = [
        {
            "name": "code",
            "label": "Code",
            "type": "text",
            "required": True,
            "placeholder": "Enter brand code",
        },
        {
            "name": "type_case",
            "label": "Type Case",
            "type": "combo",
            "options": ["TITLE", "UPPER"],
            "required": True,
        },
    ]

    if mode == "edit":
        schema += [
            {"name": "added_by",   "label": "Added By",   "type": "readonly"},
            {"name": "added_at",   "label": "Added At",   "type": "readonly"},
            {"name": "changed_by", "label": "Changed By", "type": "readonly"},
            {"name": "changed_at", "label": "Changed At", "type": "readonly"},
            {"name": "changed_no", "label": "Changed No", "type": "readonly"},
        ]

    return schema


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
        self.init_ui()

        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

        self.load_sample_data()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        # 1. Header
        enabled = ["Add", "Excel", "Refresh", "View Detail"]
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
        self.table_comp = StandardTable([
            "CODE", "TYPE CASE", "ADDED BY", "ADDED AT",
            "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(0, QHeaderView.Fixed)
        h_header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
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

        self.sort_bar.initialize_default_sort()

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _on_row_selection_changed(self):
        self._update_selection_dependent_state(bool(self.table.selectedItems()))

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
    # Header action wiring
    # ------------------------------------------------------------------

    def _connect_header_actions(self):
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete", "View Detail"]:
            btn = self.header.get_action_button(action)
            if btn:
                mapping = {
                    "Refresh":     self.load_sample_data,
                    "Add":         self.handle_add_action,
                    "Excel":       self.handle_export_action,
                    "Edit":        self.handle_edit_action,
                    "Delete":      self.handle_delete_action,
                    "View Detail": self.handle_view_detail_action,
                }
                if action in mapping:
                    btn.clicked.connect(mapping[action])

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def load_sample_data(self):
        case_data = [
            ("CAR", "TITLE", "Admin", "2024-01-01", "Admin", "2024-01-02", "1", "#DCFCE7", "#166534", "-"),
            ("FVP", "UPPER", "User1", "2024-01-05", "-",     "-",          "0", "#FFEDD5", "#9A3412", "-"),
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

        display_indices = [0, 1, 2, 3, 4, 5, 6]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
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

            for col in range(len(display_indices), self.table.columnCount()):
                self.table.setItem(r, col, QTableWidgetItem("-"))

        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        has_prev = self.current_page > 0
        has_next = end_idx < total
        self.pagination.update(
            start=0 if total == 0 else start_idx + 1,
            end=0 if total == 0 else end_idx,
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
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=(direction == "desc")
            )

    def _get_sort_value(self, row, idx):
        """Always returns a (type_tag, value) tuple so mixed types never crash sort."""
        val = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val).strip()
        try:
            return (0, float(str_val))
        except (ValueError, AttributeError):
            return (1, str_val.lower())

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Brand Case",
            fields=_build_form_schema(mode="add"),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime

        code      = data.get("code",      "").strip()
        type_case = data.get("type_case", "TITLE")

        if not code:
            QMessageBox.warning(self, "Validation Error", "Code is required.")
            return

        for row in self.all_data:
            if row[0].strip().lower() == code.lower():
                QMessageBox.warning(self, "Duplicate Code",
                                    f'Code "{code}" already exists.')
                return

        bg, fg = ("#DCFCE7", "#166534") if type_case == "TITLE" else ("#FFEDD5", "#9A3412")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        self.all_data.insert(0, (code, type_case, "Admin", now, "-", "-", "0", bg, fg, "-"))
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "brand_case.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Brand Case"
        ws.append(["CODE", "TYPE CASE", "ADDED BY", "ADDED AT",
                   "CHANGED BY", "CHANGED AT", "CHANGED NO"])
        for row in self.filtered_data:
            ws.append([str(row[i]) if row[i] is not None else "" for i in range(7)])
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
        modal = GenericFormModal(
            title="Brand Case Detail",
            subtitle="Full details for the selected brand case.",
            fields=fields,
            parent=self,
            mode="view",
        )
        modal.exec()

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]

        initial = {
            "code":      row[0],
            "type_case": row[1],
            # audit (readonly)
            "added_by":   row[2],
            "added_at":   row[3],
            "changed_by": row[4],
            "changed_at": row[5],
            "changed_no": row[6],
        }

        modal = GenericFormModal(
            title="Edit Brand Case",
            fields=_build_form_schema(mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx, data):
        import datetime

        code      = data.get("code",      "").strip()
        type_case = data.get("type_case", "TITLE")

        if not code:
            QMessageBox.warning(self, "Validation Error", "Code is required.")
            return

        for i, row in enumerate(self.all_data):
            if i != idx and row[0].strip().lower() == code.lower():
                QMessageBox.warning(self, "Duplicate Code",
                                    f'Code "{code}" already exists.')
                return

        bg, fg = ("#DCFCE7", "#166534") if type_case == "TITLE" else ("#FFEDD5", "#9A3412")
        old_row    = self.all_data[idx]
        now        = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changed_no = str(int(old_row[6]) + 1) if str(old_row[6]).isdigit() else "1"

        self.all_data[idx] = (
            code, type_case,
            old_row[2], old_row[3],   # added_by, added_at unchanged
            "Admin", now, changed_no,
            bg, fg, old_row[9],
        )
        self._apply_filter_and_reset_page()

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        code = self.all_data[idx][0]
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{code}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)
        if msg.exec() == QMessageBox.Yes:
            del self.all_data[idx]
            self._apply_filter_and_reset_page()