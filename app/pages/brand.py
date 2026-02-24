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
from server.repositories.mmbran_repo import (
    fetch_all_mmbran,
    create_mmbran,
    update_mmbran,
    soft_delete_mmbran,
)

# --- Design Tokens ---
COLORS = {
    "bg_main":  "#F8FAFC",
    "link":     "#6366F1",
    "border":   "#E2E8F0",
    "text_main":"#1E293B"
}

# ── Column mapping ────────────────────────────────────────────────────────────
#
#   Tuple layout:
#       0   pk / nobr
#       1   name
#       2   flag
#       3   case_
#       4   added_by
#       5   added_at
#       6   changed_by
#       7   changed_at
#       8   changed_no


def _build_form_schema() -> list[dict]:
    return [
        {
            "name":        "nobr",
            "label":       "Brand Code",
            "type":        "text",
            "placeholder": "Enter brand code (max 10 chars)",
            "required":    True,
        },
        {
            "name":        "name",
            "label":       "Brand Name",
            "type":        "text",
            "placeholder": "Enter brand name",
            "required":    True,
        },
        {
            "name":        "flag",
            "label":       "Flag",
            "type":        "text",
            "placeholder": "Enter flag",
            "required":    False,
        },
        {
            "name":     "case_",
            "label":    "Case Status",
            "type":        "text",
            "placeholder": "Enter case status",
            "required":    False,
        },
        # Audit fields — always present, always readonly
        {"name": "added_by",   "label": "Added By",   "type": "readonly"},
        {"name": "added_at",   "label": "Added At",   "type": "readonly"},
        {"name": "changed_by", "label": "Changed By", "type": "readonly"},
        {"name": "changed_at", "label": "Changed At", "type": "readonly"},
        {"name": "changed_no", "label": "Changed No", "type": "readonly"},
    ]


def _row_to_tuple(r: dict) -> tuple:
    return (
        (r.get("pk") or "").strip(),                                    # 0  nobr/pk
        (r.get("name") or "").strip(),                                  # 1  name
        (r.get("flag") or "").strip(),                                  # 2  flag
        (r.get("case_") or "").strip(),                                 # 3  case_
        (r.get("added_by") or "").strip(),                              # 4  added_by
        str(r["added_at"])[:19] if r.get("added_at") else "",           # 5  added_at
        (r.get("changed_by") or "").strip(),                            # 6  changed_by
        str(r["changed_at"])[:19] if r.get("changed_at") else "",       # 7  changed_at
        str(r.get("changed_no") or 0),                                  # 8  changed_no
    )


def _row_to_modal_data(row: tuple) -> dict:
    return {
        "nobr":       row[0],
        "name":       row[1],
        "flag":       row[2],
        "case_":      row[3],
        "added_by":   row[4],
        "added_at":   row[5],
        "changed_by": row[6],
        "changed_at": row[7],
        "changed_no": row[8],
    }


class BrandPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data: list[tuple] = []
        self.filtered_data: list[tuple] = []
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

        # 1. Header
        self.header = StandardPageHeader(
            title="Brand",
            subtitle="Manage brand definitions.",
            enabled_actions=["Add", "Excel", "Refresh", "View Detail"],
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
            "CODE", "NAME", "FLAG", "CASE", "ADDED BY", "ADDED AT",
            "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Fixed)
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 280)
        self.table.setColumnWidth(2, 60)   # FLAG
        self.table.setColumnWidth(3, 120)  # CASE
        self.table.setColumnWidth(4, 120)  # ADDED BY
        h_header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # ADDED AT
        self.table.setColumnWidth(6, 120)  # CHANGED BY
        h_header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # CHANGED AT
        self.table.setColumnWidth(8, 90)   # CHANGED NO

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

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _on_row_selection_changed(self):
        self._update_selection_dependent_state(bool(self.table.selectedItems()))

    def _update_selection_dependent_state(self, enabled: bool):
        if self._active_modal is not None:
            return
        for label in ("Edit", "Delete", "View Detail"):
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(enabled)

    def _get_selected_row(self) -> tuple | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        global_idx = self.current_page * self.page_size + rows[0].row()
        if global_idx >= len(self.filtered_data):
            return None
        return self.filtered_data[global_idx]

    # ------------------------------------------------------------------
    # Modal lock helpers
    # ------------------------------------------------------------------

    _ALL_HEADER_ACTIONS = ["Add", "Excel", "Refresh", "Edit", "Delete", "View Detail"]

    def _lock_header(self):
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(False)

    def _unlock_header(self):
        has_sel = bool(self.table.selectedItems())
        for label in self._ALL_HEADER_ACTIONS:
            btn = self.header.get_action_button(label)
            if btn:
                btn.setEnabled(has_sel if label in ("Edit", "Delete", "View Detail") else True)

    def _clear_active_modal(self):
        self._active_modal = None

    def _open_modal(self, modal: GenericFormModal):
        modal.opened.connect(self._lock_header)
        modal.closed.connect(self._unlock_header)
        modal.closed.connect(self._clear_active_modal)
        self._active_modal = modal
        modal.exec()

    # ------------------------------------------------------------------
    # Page visibility
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
        try:
            self.all_data = [_row_to_tuple(r) for r in fetch_all_mmbran()]
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load data:\n\n{exc}")
            self.all_data = []
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
            case_item = QTableWidgetItem(row_data[3])
            case_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 3, case_item)

            # FLAG
            flag_item = QTableWidgetItem(row_data[2])
            flag_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
            self.table.setItem(r, 2, flag_item)

            # METADATA columns
            for col_idx, data_idx, align in [
                (4, 4, Qt.AlignLeft),
                (5, 5, Qt.AlignLeft),
                (6, 6, Qt.AlignLeft),
                (7, 7, Qt.AlignLeft),
                (8, 8, Qt.AlignCenter),
            ]:
                item = QTableWidgetItem(str(row_data[data_idx]))
                item.setTextAlignment(align | Qt.AlignVCenter)
                self.table.setItem(r, col_idx, item)

        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        self.pagination.update(
            start=0 if total == 0 else start_idx + 1,
            end=0 if total == 0 else end_idx,
            total=total,
            has_prev=self.current_page > 0,
            has_next=end_idx < total,
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

        self.filtered_data = (
            list(self.all_data) if not query
            else [
                row for row in self.all_data
                if col_index < len(row) and query in str(row[col_index]).lower()
            ]
        )
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
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

    def _get_sort_value(self, row, idx):
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
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
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

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Brand",
            fields=_build_form_schema(),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        nobr = data.get("nobr", "").strip()
        name = data.get("name", "").strip()

        if not nobr or not name:
            QMessageBox.warning(self, "Validation", "Brand Code and Name are required.")
            return
        if len(nobr) > 10:
            QMessageBox.warning(self, "Validation", "Brand Code must be 10 characters or fewer.")
            return

        try:
            create_mmbran(
                nobr=nobr,
                name=name,
                case_=data.get("case_", "").strip() or None,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Insert failed:\n\n{exc}")
            return
        self.load_data()

    def handle_edit_action(self):
        row = self._get_selected_row()
        if row is None:
            return
        modal = GenericFormModal(
            title="Edit Brand",
            fields=_build_form_schema(),
            parent=self,
            mode="edit",
            initial_data=_row_to_modal_data(row),
        )
        modal.formSubmitted.connect(lambda data, r=row: self._on_edit_submitted(r, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, row: tuple, data: dict):
        name = data.get("name", "").strip()
        if not name:
            QMessageBox.warning(self, "Validation", "Brand Name is required.")
            return

        old_changed_no = int(row[8]) if str(row[8]).isdigit() else 0
        try:
            update_mmbran(
                pk=row[0],
                name=name,
                flag=data.get("flag", "").strip() or None,
                case_=data.get("case_", "").strip() or None,
                old_changed_no=old_changed_no,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Update failed:\n\n{exc}")
            return
        self.load_data()

    def handle_view_detail_action(self):
        row = self._get_selected_row()
        if row is None:
            return
        modal = GenericFormModal(
            title="Brand Detail",
            subtitle="Full details for the selected brand.",
            fields=_build_form_schema(),
            parent=self,
            mode="view",
            initial_data=_row_to_modal_data(row),
        )
        self._open_modal(modal)

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
        ws.append(["CODE", "NAME", "FLAG", "CASE", "ADDED BY", "ADDED AT",
                   "CHANGED BY", "CHANGED AT", "CHANGED NO"])
        for row in self.filtered_data:
            ws.append([str(v) if v is not None else "" for v in row])
        wb.save(path)
        QMessageBox.information(self, "Export Complete",
                                f"Exported {len(self.filtered_data)} records to:\n{path}")

    def handle_delete_action(self):
        row = self._get_selected_row()
        if row is None:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{row[0]}"?')
        msg.setInformativeText(f"Name: {row[1]}")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)
        if msg.exec() == QMessageBox.Yes:
            try:
                soft_delete_mmbran(row[0])
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Delete failed:\n\n{exc}")
                return
            self.load_data()