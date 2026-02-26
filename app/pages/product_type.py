from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QTableWidgetItem
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal
from server.repositories.tyfltr_repo import (
    fetch_all_tyfltr,
    fetch_tyfltr_by_pk,
    create_tyfltr,
    update_tyfltr,
    soft_delete_tyfltr,
)

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link":    "#6366F1",
}

# Header → repo dict key
_HEADER_MAP = {
    "ENGLISH":    "pk",
    "SPANISH":    "span",
    "FRENCH":     "fren",
    "GERMAN":     "germ",
    "ADDED BY":   "added_by",
    "ADDED AT":   "added_at",
    "CHANGED BY": "changed_by",
    "CHANGED AT": "ch_dt",
    "CHANGED NO": "changed_no",
}

VIEW_DETAIL_FIELDS = [
    ("English", "pk"),
    ("Spanish", "span"),
    ("French",  "fren"),
    ("German",  "germ"),
    ("Added By",    "added_by"),
    ("Added At",    "added_at"),
    ("Changed By",  "changed_by"),
    ("Changed At",  "ch_dt"),
    ("Changed No",  "changed_no"),
]


def _build_form_schema() -> list[dict]:
    return [
        {
            "name":        "engl",
            "label":       "English",
            "type":        "text",
            "placeholder": "Enter English value",
            "required":    True,
        },
        {
            "name":        "span",
            "label":       "Spanish",
            "type":        "text",
            "placeholder": "Enter Spanish translation",
            "required":    False,
        },
        {
            "name":        "fren",
            "label":       "French",
            "type":        "text",
            "placeholder": "Enter French translation",
            "required":    False,
        },
        {
            "name":        "germ",
            "label":       "German",
            "type":        "text",
            "placeholder": "Enter German translation",
            "required":    False,
        },
        {"name": "added_by",   "label": "Added By",   "type": "readonly"},
        {"name": "added_at",   "label": "Added At",   "type": "readonly"},
        {"name": "changed_by", "label": "Changed By", "type": "readonly"},
        {"name": "changed_at", "label": "Changed At", "type": "readonly"},
        {"name": "changed_no", "label": "Changed No", "type": "readonly"},
    ]


def _fmt_dt(val) -> str:
    if val is None:
        return ""
    try:
        return val.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(val)


class ProductTypePage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data:            list[dict]       = []
        self.filtered_data:       list[dict]       = []
        self.current_page         = 0
        self.page_size            = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type    = "ENGLISH"
        self._last_search_text    = ""
        self._sort_fields:        list[str]        = []
        self._sort_directions:    dict[str, str]   = {}
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
            title="Product Type",
            subtitle="Manage product type translations",
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
            "ENGLISH", "SPANISH", "FRENCH", "GERMAN",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
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

    def _get_selected_pk(self) -> str | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 0)
        return item.data(Qt.UserRole) if item else None

    def _get_selected_row(self) -> dict | None:
        pk = self._get_selected_pk()
        if pk is None:
            return None
        return next((r for r in self.filtered_data if r["pk"] == pk), None)

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
            self.all_data = fetch_all_tyfltr()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load data:\n\n{exc}")
            self.all_data = []
        self._apply_filter_and_reset_page()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        data  = self.filtered_data or []
        total = len(data)
        start = self.current_page * self.page_size
        end   = min(start + self.page_size, total)

        for r, row in enumerate(data[start:end]):
            self.table.insertRow(r)
            self.table.setRowHeight(r, 28)

            values = [
                str(row.get("pk")         or ""),
                str(row.get("span")       or ""),
                str(row.get("fren")       or ""),
                str(row.get("germ")       or ""),
                str(row.get("added_by")   or ""),
                _fmt_dt(row.get("added_at")),
                str(row.get("changed_by") or ""),
                _fmt_dt(row.get("ch_dt")),
                str(row.get("changed_no") or 0),
            ]

            for c, val in enumerate(values):
                item = QTableWidgetItem(val)
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                    item.setData(Qt.UserRole, row["pk"])
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
        query = (self._last_search_text or "").lower().strip()
        key   = _HEADER_MAP.get(self._last_filter_type, "pk")

        self.filtered_data = (
            list(self.all_data)
            if not query
            else [r for r in self.all_data if query in str(r.get(key) or "").lower()]
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
        for field in reversed(self._sort_fields):
            key = _HEADER_MAP.get(field)
            if not key:
                continue
            self.filtered_data.sort(
                key=lambda row, k=key: str(row.get(k) or "").lower(),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

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
            title="Add Product Type",
            fields=_build_form_schema(),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        engl = data.get("engl", "").strip()
        span = data.get("span", "").strip()
        fren = data.get("fren", "").strip()
        germ = data.get("germ", "").strip()

        if not engl:
            QMessageBox.warning(self, "Validation Error", "English value is required.")
            return

        # Duplicate check
        if any(r["pk"].strip().lower() == engl.lower() for r in self.all_data):
            QMessageBox.warning(self, "Duplicate Entry",
                                f'English value "{engl}" already exists.')
            return

        try:
            create_tyfltr(
                engl=engl,
                span=span or engl,
                fren=fren or engl,
                germ=germ or engl,
            )
            self.load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Insert failed:\n\n{exc}")

    # ── Export ────────────────────────────────────────────────────────────────

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "product_type.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Product Type"
        ws.append([
            "ENGLISH", "SPANISH", "FRENCH", "GERMAN",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        for row in self.filtered_data:
            ws.append([
                str(row.get("pk")         or ""),
                str(row.get("span")       or ""),
                str(row.get("fren")       or ""),
                str(row.get("germ")       or ""),
                str(row.get("added_by")   or ""),
                _fmt_dt(row.get("added_at")),
                str(row.get("changed_by") or ""),
                _fmt_dt(row.get("ch_dt")),
                str(row.get("changed_no") or 0),
            ])
        wb.save(path)
        QMessageBox.information(
            self, "Export Complete",
            f"Exported {len(self.filtered_data)} records to:\n{path}",
        )

    # ── View Detail ───────────────────────────────────────────────────────────

    def handle_view_detail_action(self):
        row = self._get_selected_row()
        if row is None:
            return
        fields = [
            (label, _fmt_dt(row.get(key)) if "at" in key else str(row.get(key) or ""))
            for label, key in VIEW_DETAIL_FIELDS
        ]
        modal = GenericFormModal(
            title="Product Type Detail",
            subtitle="Full details for the selected record.",
            fields=fields,
            parent=self,
            mode="view",
        )
        self._open_modal(modal)

    # ── Edit ──────────────────────────────────────────────────────────────────

    def handle_edit_action(self):
        row = self._get_selected_row()
        if row is None:
            return

        # Build schema and make PK readonly
        fields = _build_form_schema()

        initial = {
            "engl":       row.get("pk",         ""),
            "span":       row.get("span",        ""),
            "fren":       row.get("fren",        ""),
            "germ":       row.get("germ",        ""),
            "added_by":   row.get("added_by",    ""),
            "added_at":   _fmt_dt(row.get("added_at")),
            "changed_by": row.get("changed_by",  ""),
            "changed_at": _fmt_dt(row.get("ch_dt")),
            "changed_no": str(row.get("changed_no") or 0),
        }

        modal = GenericFormModal(
            title="Edit Product Type",
            fields=fields,
            parent=self,
            mode="edit",
            initial_data=initial,
        )

        modal.formSubmitted.connect(
            lambda data, r=row: self._on_edit_submitted(r, data)
        )

        self._open_modal(modal)

    def _on_edit_submitted(self, row: dict, data: dict):
        old_pk = row["pk"]
        new_pk = data.get("engl", "").strip()
        span   = data.get("span", "").strip()
        fren   = data.get("fren", "").strip()
        germ   = data.get("germ", "").strip()

        if not new_pk:
            QMessageBox.warning(self, "Validation Error", "English value is required.")
            return

        # Duplicate check if PK changed
        if new_pk.lower() != old_pk.lower():
            if any(r["pk"].strip().lower() == new_pk.lower() for r in self.all_data):
                QMessageBox.warning(self, "Duplicate Entry",
                                    f'English value "{new_pk}" already exists.')
                return

        old_changed_no = int(row.get("changed_no") or 0)

        try:
            update_tyfltr(
                old_pk=old_pk,
                new_pk=new_pk,
                span=span or new_pk,
                fren=fren or new_pk,
                germ=germ or new_pk,
                old_changed_no=old_changed_no,
            )
            self.load_data()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Update failed:\n\n{exc}")

    # ── Delete ────────────────────────────────────────────────────────────────

    def handle_delete_action(self):
        row = self._get_selected_row()
        if row is None:
            return

        pk = row["pk"]
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{pk}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            try:
                soft_delete_tyfltr(pk=pk)
                self.load_data()
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Delete failed:\n\n{exc}")