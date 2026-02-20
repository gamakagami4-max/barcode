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
from server.repositories.mmbrcs_repo import (
    fetch_all_mmbrcs,
    create_mmbrcs,
    update_mmbrcs,
    delete_mmbrcs,
)

# --- Design Tokens ---
COLORS = {
    "bg_main":   "#F8FAFC",
    "link":      "#6366F1",
    "border":    "#E2E8F0",
    "text_muted":"#94A3B8"
}

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
    All modes show the same fields for consistency.
    Audit fields are always readonly — blank in add, populated in edit/view.
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
        # Audit fields — always present, always readonly
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
        self._active_modal: GenericFormModal | None = None
        self.init_ui()

        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

        self.load_data()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        # 1. Header
        enabled = ["Add", "Excel", "Refresh", "View Detail"]
        self.header = StandardPageHeader(
            title="Brand Case",
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
        # Don't re-enable selection buttons while a modal is open
        if self._active_modal is not None:
            return
        for label in ("Edit", "Delete", "View Detail"):
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(enabled)

    def _get_selected_pk(self):
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row_index = selected[0].row()
        item = self.table.item(row_index, 0)
        if not item:
            return None
        return item.data(Qt.UserRole)

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
    # Data
    # ------------------------------------------------------------------

    def load_data(self):
        rows = fetch_all_mmbrcs()
        self.all_data = rows
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data or []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row in enumerate(page_data):
            self.table.insertRow(r)

            values = [
                row["mmcode"],
                "TITLE" if row["mmtyca"] else "UPPER",
                row["mmrgid"],
                row["mmrgdt"].strftime("%Y-%m-%d %H:%M:%S") if row["mmrgdt"] else "",
                row["mmchid"],
                row["mmchdt"].strftime("%Y-%m-%d %H:%M:%S") if row["mmchdt"] else "",
                str(row["mmchno"]),
            ]

            for c, val in enumerate(values):
                item = QTableWidgetItem(str(val or ""))
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                    item.setData(Qt.UserRole, row["mmbrcsiy"])
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c, item)

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

        self.table.clearSelection()
        self._update_selection_dependent_state(False)

    # ------------------------------------------------------------------
    # Filter / sort
    # ------------------------------------------------------------------

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query = (self._last_search_text or "").lower().strip()

        header_map = {
            "CODE":       "mmcode",
            "TYPE CASE":  "mmtyca",
            "ADDED BY":   "mmrgid",
            "ADDED AT":   "mmrgdt",
            "CHANGED BY": "mmchid",
            "CHANGED AT": "mmchdt",
            "CHANGED NO": "mmchno",
        }

        key = header_map.get(self._last_filter_type, "mmcode")

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            self.filtered_data = [
                row for row in self.all_data
                if query in str(row.get(key, "")).lower()
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

        header_map = {
            "CODE":       "mmcode",
            "TYPE CASE":  "mmtyca",
            "ADDED BY":   "mmrgid",
            "ADDED AT":   "mmrgdt",
            "CHANGED BY": "mmchid",
            "CHANGED AT": "mmchdt",
            "CHANGED NO": "mmchno",
        }

        for field in reversed(self._sort_fields):
            direction = self._sort_directions.get(field, "asc")
            key = header_map.get(field)
            if not key:
                continue
            self.filtered_data.sort(
                key=lambda row: row.get(key) if row.get(key) is not None else "",
                reverse=(direction == "desc")
            )

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
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        code = data.get("code", "").strip()
        type_case = data.get("type_case", "TITLE")

        if not code:
            QMessageBox.warning(self, "Validation Error", "Code is required.")
            return

        for row in self.all_data:
            if row["mmcode"].strip().lower() == code.lower():
                QMessageBox.warning(self, "Duplicate Code",
                                    f'Code "{code}" already exists.')
                return

        create_mmbrcs(
            code=code,
            type_case=(type_case == "TITLE"),
            user="Admin",
        )

        self.load_data()

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
            ws.append([
                row["mmcode"],
                "TITLE" if row["mmtyca"] else "UPPER",
                row["mmrgid"],
                row["mmrgdt"],
                row["mmchid"],
                row["mmchdt"],
                row["mmchno"],
            ])

        wb.save(path)
        QMessageBox.information(self, "Export Complete",
                                f"Exported {len(self.filtered_data)} records to:\n{path}")

    def handle_view_detail_action(self):
        pk = self._get_selected_pk()
        if pk is None:
            return

        row = next((r for r in self.all_data if r["mmbrcsiy"] == pk), None)
        if not row:
            return

        fields = [
            ("Code",       row["mmcode"]),
            ("Type Case",  "TITLE" if row["mmtyca"] else "UPPER"),
            ("Added By",   row["mmrgid"]),
            ("Added At",   row["mmrgdt"]),
            ("Changed By", row["mmchid"]),
            ("Changed At", row["mmchdt"]),
            ("Changed No", row["mmchno"]),
        ]

        modal = GenericFormModal(
            title="Brand Case Detail",
            subtitle="Full details for the selected brand case.",
            fields=fields,
            parent=self,
            mode="view",
        )
        self._open_modal(modal)

    def handle_edit_action(self):
        pk = self._get_selected_pk()
        if pk is None:
            return

        row = next((r for r in self.all_data if r["mmbrcsiy"] == pk), None)
        if not row:
            return

        initial = {
            "code":       row["mmcode"],
            "type_case":  "TITLE" if row["mmtyca"] else "UPPER",
            "added_by":   row["mmrgid"],
            "added_at":   row["mmrgdt"],
            "changed_by": row["mmchid"],
            "changed_at": row["mmchdt"],
            "changed_no": row["mmchno"],
        }

        modal = GenericFormModal(
            title="Edit Brand Case",
            fields=_build_form_schema(mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data: self._on_edit_submitted(pk, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, pk, data):
        code = data.get("code", "").strip()
        type_case = data.get("type_case", "TITLE")

        if not code:
            QMessageBox.warning(self, "Validation Error", "Code is required.")
            return

        update_mmbrcs(
            mmbrcs_id=pk,
            code=code,
            type_case=(type_case == "TITLE"),
            user="Admin",
        )

        self.load_data()

    def handle_delete_action(self):
        pk = self._get_selected_pk()
        if pk is None:
            return

        row = next((r for r in self.all_data if r["mmbrcsiy"] == pk), None)
        if not row:
            return

        code = row["mmcode"]
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{code}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            delete_mmbrcs(pk, user="Admin")
            self.load_data()