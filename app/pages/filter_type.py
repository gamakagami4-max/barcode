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
from server.repositories.tyskra_repo import (
    fetch_all_tyskra,
    create_tyskra,
    update_tyskra,
    soft_delete_tyskra,
)

# ======================
# Design Tokens
# ======================
COLORS = {
    "bg_main": "#F8FAFC",
    "link":    "#6366F1",
}

# Row tuple indices
# 0: type_name  1: type_desc  2: added_by  3: added_at
# 4: changed_by 5: changed_at 6: changed_no
VIEW_DETAIL_FIELDS = [
    ("Type Name",   0),
    ("Description", 1),
    ("Added By",    2),
    ("Added At",    3),
    ("Changed By",  4),
    ("Changed At",  5),
    ("Changed No",  6),
]


def _build_form_schema() -> list[dict]:
    return [
        {
            "name":        "type_name",
            "label":       "Type Name",
            "type":        "text",
            "placeholder": "Enter type name",
            "required":    True,
        },
        {
            "name":        "type_desc",
            "label":       "Description",
            "type":        "text",
            "placeholder": "Enter description (optional)",
            "required":    False,
        },
        {"name": "added_by",   "label": "Added By",   "type": "readonly"},
        {"name": "added_at",   "label": "Added At",   "type": "readonly"},
        {"name": "changed_by", "label": "Changed By", "type": "readonly"},
        {"name": "changed_at", "label": "Changed At", "type": "readonly"},
        {"name": "changed_no", "label": "Changed No", "type": "readonly"},
    ]


class FilterTypePage(QWidget):

    def __init__(self):
        super().__init__()
        self.all_data             = []
        self.filtered_data        = []
        self.current_page         = 0
        self.page_size            = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type    = "TYPE NAME"
        self._last_search_text    = ""
        self._sort_fields         = []
        self._sort_directions     = {}
        self._active_modal: GenericFormModal | None = None
        self.init_ui()
        self.load_data()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        self.header = StandardPageHeader(
            title="Source Type",
            subtitle="Manage source type records",
            enabled_actions=["Add", "Excel", "Refresh", "View Detail"],
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        self.table_comp = StandardTable([
            "TYPE NAME", "DESCRIPTION",
            "ADDED BY", "ADDED AT",
            "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        self.table = self.table_comp.table

        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)

        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

        self.sort_bar.initialize_default_sort()
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

    # ── Selection helpers ─────────────────────────────────────────────────────

    def _on_row_selection_changed(self):
        self._update_selection_dependent_state(bool(self.table.selectedItems()))

    def _update_selection_dependent_state(self, enabled: bool):
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
        table_row    = selected_rows[0].row()
        global_index = (self.current_page * self.page_size) + table_row
        if global_index >= len(self.filtered_data):
            return None
        actual_row = self.filtered_data[global_index]
        return self.all_data.index(actual_row)

    # ── Modal lock helpers ────────────────────────────────────────────────────

    _ALL_HEADER_ACTIONS = ["Add", "Excel", "Refresh", "Edit", "Delete", "View Detail"]

    def _lock_header(self):
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(False)

    def _unlock_header(self):
        has_selection = bool(self.table.selectedItems())
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(has_selection if label in ("Edit", "Delete", "View Detail") else True)

    def _clear_active_modal(self):
        self._active_modal = None

    def _open_modal(self, modal: GenericFormModal):
        modal.opened.connect(self._lock_header)
        modal.closed.connect(self._unlock_header)
        modal.closed.connect(self._clear_active_modal)
        self._active_modal = modal
        modal.exec()

    # ── Page visibility ───────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if self._active_modal is not None and not self._active_modal.isVisible():
            self._active_modal.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        if self._active_modal is not None and self._active_modal.isVisible():
            self._active_modal.hide()

    # ── Data loading ──────────────────────────────────────────────────────────

    def load_data(self):
        try:
            rows = fetch_all_tyskra()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load data:\n\n{exc}")
            rows = []

        self.all_data = [
            (
                str(r["type_name"]   or ""),
                str(r["type_desc"]   or ""),
                str(r["added_by"]    or ""),
                r["added_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("added_at") else "",
                str(r["changed_by"]  or ""),
                r["changed_at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("changed_at") else "",
                str(r["changed_no"]  or 0),
            )
            for r in rows
        ]
        self._apply_filter_and_reset_page()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        data  = self.filtered_data or []
        total = len(data)
        start = self.current_page * self.page_size
        end   = min(start + self.page_size, total)

        for r, row_data in enumerate(data[start:end]):
            self.table.insertRow(r)
            self.table.setRowHeight(r, 28)
            for c, value in enumerate(row_data):
                item = QTableWidgetItem(str(value))
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                self.table.setItem(r, c, item)

        for r in range(end - start):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start + r + 1)))

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

    # ── Filter / sort ─────────────────────────────────────────────────────────

    def filter_table(self, filter_type: str, search_text: str):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query   = (self._last_search_text or "").lower().strip()
        headers = self.table_comp.headers()
        col_idx = {h: i for i, h in enumerate(headers)}.get(self._last_filter_type, 0)

        self.filtered_data = (
            list(self.all_data)
            if not query
            else [
                row for row in self.all_data
                if col_idx < len(row) and query in str(row[col_idx]).lower()
            ]
        )
        self._apply_sort()
        self.current_page = 0
        self.render_page()

    def on_sort_changed(self, fields: list[str], field_directions: dict):
        self._sort_fields     = fields or []
        self._sort_directions = field_directions or {}
        self._apply_filter_and_reset_page()

    def _apply_sort(self):
        if not self._sort_fields or not self.filtered_data:
            return
        headers = self.table_comp.headers()
        h2i     = {h: i for i, h in enumerate(headers)}
        for field in reversed(self._sort_fields):
            idx = h2i.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._sort_key(row, i),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

    def _sort_key(self, row, idx):
        val = str(row[idx]).strip() if idx < len(row) and row[idx] is not None else ""
        try:
            return (0, float(val))
        except ValueError:
            return (1, val.lower())

    # ── Pagination ────────────────────────────────────────────────────────────

    def on_page_changed(self, page_action: int):
        total       = len(self.filtered_data or [])
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        if page_action == -1:
            self.current_page = max(0, self.current_page - 1)
        elif page_action == 1:
            self.current_page = min(total_pages - 1, self.current_page + 1)
        else:
            self.current_page = max(0, min(int(page_action), total_pages - 1))
        self.render_page()

    def on_page_size_changed(self, new_size: int):
        self.page_size    = new_size
        self.current_page = 0
        self.render_page()

    # ── Header button wiring ──────────────────────────────────────────────────

    def _connect_header_actions(self):
        for label, slot in {
            "Refresh":     self.load_data,
            "Add":         self.handle_add_action,
            "Excel":       self.handle_export_action,
            "Edit":        self.handle_edit_action,
            "Delete":      self.handle_delete_action,
            "View Detail": self.handle_view_detail_action,
        }.items():
            btn = self.header.get_action_button(label)
            if btn:
                btn.clicked.connect(slot)

    # ── Add ───────────────────────────────────────────────────────────────────

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Source Type",
            fields=_build_form_schema(),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        type_name = data.get("type_name", "").strip()
        type_desc = data.get("type_desc", "").strip() or None

        if not type_name:
            QMessageBox.warning(self, "Validation Error", "Type Name is required.")
            return

        try:
            create_tyskra(type_name=type_name, type_desc=type_desc)
            self.load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Insert failed:\n\n{exc}")

    # ── Export ────────────────────────────────────────────────────────────────

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "source_type.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Source Type"
        ws.append([
            "TYPE NAME", "DESCRIPTION",
            "ADDED BY", "ADDED AT",
            "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        for row in self.filtered_data:
            ws.append([str(v) if v is not None else "" for v in row])
        wb.save(path)
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(self.filtered_data)} records to:\n{path}",
        )

    # ── View Detail ───────────────────────────────────────────────────────────

    def handle_view_detail_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row    = self.all_data[idx]
        fields = [
            (label, str(row[i]) if i < len(row) and row[i] is not None else "")
            for label, i in VIEW_DETAIL_FIELDS
        ]
        modal = GenericFormModal(
            title="Source Type Detail",
            subtitle="Full details for the selected record.",
            fields=fields,
            parent=self,
            mode="view",
        )
        self._open_modal(modal)

    # ── Edit ──────────────────────────────────────────────────────────────────

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]

        initial = {
            "type_name":  row[0],
            "type_desc":  row[1],
            "added_by":   row[2],
            "added_at":   row[3],
            "changed_by": row[4],
            "changed_at": row[5],
            "changed_no": row[6],
        }
        modal = GenericFormModal(
            title="Edit Source Type",
            fields=_build_form_schema(),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, idx: int, data: dict):
        type_name = data.get("type_name", "").strip()
        type_desc = data.get("type_desc", "").strip() or None

        if not type_name:
            QMessageBox.warning(self, "Validation Error", "Type Name is required.")
            return

        row            = self.all_data[idx]
        old_changed_no = int(row[6]) if str(row[6]).isdigit() else 0

        try:
            update_tyskra(
                type_name=type_name,
                type_desc=type_desc,
                old_changed_no=old_changed_no,
            )
            self.load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Update failed:\n\n{exc}")

    # ── Delete ────────────────────────────────────────────────────────────────

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        type_name = self.all_data[idx][0]

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{type_name}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            try:
                soft_delete_tyskra(type_name=type_name)
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Delete failed:\n\n{exc}")