from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem, QLabel, QHBoxLayout, QHeaderView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from PySide6.QtWidgets import QMessageBox
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal
from server.repositories.mmbrnd_repo import (
    fetch_all_brnd,
    create_brnd,
    update_brnd,
    soft_delete_brnd,
)

# --- Design Tokens ---
COLORS = {
    "bg_main":  "#F8FAFC",
    "link":     "#6366F1",
    "border":   "#E2E8F0",
    "text_main":"#1E293B"
}

# Row tuple shape: (CODE, NAME, CASE, ADDED_BY, ADDED_AT, CHANGED_BY, CHANGED_AT, CHANGED_NO)
VIEW_DETAIL_FIELDS = [
    ("Code",       0),
    ("Name",       1),
    ("Case",       2),
    ("Added By",   3),
    ("Added At",   4),
    ("Changed By", 5),
    ("Changed At", 6),
    ("Changed No", 7),
]


def _build_form_schema(mode: str = "add") -> list[dict]:
    """
    All modes show the same fields for consistency.
    Audit fields are always readonly — blank in add, populated in edit/view.
    """
    schema = [
        {
            "name": "code",
            "label": "Brand Code",
            "type": "text",
            "placeholder": "Enter brand code (e.g., BR-001)",
            "required": True,
        },
        {
            "name": "name",
            "label": "Brand Name",
            "type": "text",
            "placeholder": "Enter brand name",
            "required": True,
        },
        {
            "name": "case",
            "label": "Case Status",
            "type": "combo",
            "options": ["AVAILABLE", "NOT AVAILABLE", "PENDING"],
            "required": True,
        },
        # Audit fields — always present, always readonly
        {"name": "added_by",   "label": "Added By",   "type": "readonly"},
        {"name": "added_at",   "label": "Added At",   "type": "readonly"},
        {"name": "changed_by", "label": "Changed By", "type": "readonly"},
        {"name": "changed_at", "label": "Changed At", "type": "readonly"},
        {"name": "changed_no", "label": "Changed No", "type": "readonly"},
    ]
    return schema


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
        self._active_modal: GenericFormModal | None = None
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
            title="Brand",
            subtitle="Description",
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
            "CODE", "NAME", "CASE", "ADDED BY", "ADDED AT",
            "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 280)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 120)
        h_header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # ADDED AT
        self.table.setColumnWidth(5, 120)
        h_header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # CHANGED AT
        self.table.setColumnWidth(7, 90)

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

        self.sort_bar.initialize_default_sort()

        # Track table selection to enable Edit / Delete / View Detail
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _on_row_selection_changed(self):
        self._update_selection_dependent_state(bool(self.table.selectedItems()))

    def _update_selection_dependent_state(self, enabled: bool):
        # Don't re-enable selection buttons while a modal is open
        if self._active_modal is not None:
            return
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
    # Modal lock helpers
    # ------------------------------------------------------------------

    _ALL_HEADER_ACTIONS = ["Add", "Excel", "Refresh", "Edit", "Delete", "View Detail"]

    def _lock_header(self):
        """Disable every header button while a modal is open."""
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(False)

    def _unlock_header(self):
        """Re-enable header buttons when the modal closes."""
        has_selection = bool(self.table.selectedItems())
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                if label in ("Edit", "Delete", "View Detail"):
                    btn.setEnabled(has_selection)
                else:
                    btn.setEnabled(True)

    def _clear_active_modal(self):
        self._active_modal = None

    def _open_modal(self, modal: GenericFormModal):
        """Wire lock/unlock signals, track the active modal, and open it."""
        modal.opened.connect(self._lock_header)
        modal.closed.connect(self._unlock_header)
        modal.closed.connect(self._clear_active_modal)
        self._active_modal = modal
        modal.exec()

    # ------------------------------------------------------------------
    # Page visibility — hide/restore modal on page switch
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if self._active_modal is not None and not self._active_modal.isVisible():
            self._active_modal.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._active_modal is not None and self._active_modal.isVisible():
            self._active_modal.hide()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------

    def load_data(self):
        rows = fetch_all_brnd()

        formatted = []
        for r in rows:
            formatted.append((
                r["code"],
                r["name"],
                r["case_name"] or "",
                r["added_by"] or "",
                r["added_at"].strftime("%Y-%m-%d %H:%M:%S") if r["added_at"] else "",
                r["changed_by"] or "",
                r["changed_at"].strftime("%Y-%m-%d %H:%M:%S") if r["changed_at"] else "",
                str(r["changed_no"] or 0),
            ))

        self.all_data = formatted
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

            # CODE
            code_item = QTableWidgetItem(row_data[0])
            code_item.setForeground(QColor(COLORS["link"]))
            font = code_item.font()
            font.setPointSize(9)
            code_item.setFont(font)
            code_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.table.setItem(r, 0, code_item)

            # NAME (cell widget for word-wrap)
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

            # CASE
            case_item = QTableWidgetItem(row_data[2])
            case_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 2, case_item)

            # METADATA columns
            for col_idx, data_idx, align in [
                (3, 3, Qt.AlignLeft),
                (4, 4, Qt.AlignLeft),
                (5, 5, Qt.AlignLeft),
                (6, 6, Qt.AlignLeft),
                (7, 7, Qt.AlignCenter),
            ]:
                item = QTableWidgetItem(str(row_data[data_idx]))
                item.setTextAlignment(align | Qt.AlignVCenter)
                self.table.setItem(r, col_idx, item)

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

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()
        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}
        col_index = header_to_index.get(self._last_filter_type, 1)

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
                mapping = {
                    "Refresh":     self.load_data,
                    "Add":         self.handle_add_action,
                    "Excel":       self.handle_export_action,
                    "Edit":        self.handle_edit_action,
                    "Delete":      self.handle_delete_action,
                    "View Detail": self.handle_view_detail_action,
                }
                if action in mapping:
                    btn.clicked.connect(mapping[action])

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Brand",
            fields=_build_form_schema(mode="add"),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        code = data.get("code", "").strip()
        name = data.get("name", "").strip()
        case_status = data.get("case", "AVAILABLE")

        if not code or not name:
            QMessageBox.warning(self, "Validation Error", "Brand Code and Name are required.")
            return

        try:
            create_brnd(
                code=code,
                name=name,
                case_name=case_status,
                user="ADMIN",
            )
            self.load_data()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "brand.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Brand"
        ws.append(["CODE", "NAME", "CASE", "ADDED BY", "ADDED AT",
                   "CHANGED BY", "CHANGED AT", "CHANGED NO"])
        for row in self.filtered_data:
            ws.append([str(v) if v is not None else "" for v in row])
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
            title="Brand Detail",
            subtitle="Full details for the selected brand.",
            fields=fields,
            parent=self,
            mode="view",
        )
        self._open_modal(modal)

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]

        initial = {
            "code":       row[0],
            "name":       row[1],
            "case":       row[2],
            "added_by":   row[3],
            "added_at":   row[4],
            "changed_by": row[5],
            "changed_at": row[6],
            "changed_no": row[7],
        }

        modal = GenericFormModal(
            title="Edit Brand",
            fields=_build_form_schema(mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, idx, data):
        code = data.get("code", "").strip()
        name = data.get("name", "").strip()
        case_status = data.get("case", "AVAILABLE")

        if not code or not name:
            QMessageBox.warning(self, "Validation Error", "Brand Code and Name are required.")
            return

        try:
            rows = fetch_all_brnd()
            db_row = rows[idx]

            update_brnd(
                pk=db_row["pk"],
                code=code,
                name=name,
                case_name=case_status,
                display_flag="1",
                disable_flag="0",
                protect_flag="0",
                old_changed_no=db_row["changed_no"],
                user="ADMIN",
            )

            self.load_data()

        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

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
            try:
                rows = fetch_all_brnd()
                db_row = rows[idx]

                soft_delete_brnd(
                    pk=db_row["pk"],
                    user="ADMIN",
                )

                self.load_data()

            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))