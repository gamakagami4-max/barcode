# app/pages/master_source_group.py

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
from repositories.mmsdgr_repo import (
    create_sdgr,
    fetch_all_sdgr,
    fetch_sdgr_by_id,
    fetch_table_columns,
    soft_delete_sdgr,
    update_sdgr,
)
from repositories.mmtbnm_repo import fetch_connection_table_map, fetch_tbnm_id_map

ROW_STANDARD    = "standard"
QUERY_WRAP_LIMIT = 80
_BARCODE_SCHEMA  = "barcode"   # schema passed to information_schema lookup

VIEW_DETAIL_FIELDS = [
    ("Connection",          "conn_name"),
    ("Table Name",          "table_name"),
    ("Query / Link Server", "query"),
    ("Engine",              "engine"),
    ("Added By",            "added_by"),
    ("Added At",            "added_at"),
    ("Changed By",          "changed_by"),
    ("Changed At",          "changed_at"),
    ("Changed No",          "changed_no"),
]

_COL_HEADER_TO_TUPLE_IDX = {
    "CONNECTION":        1,
    "TABLE NAME":        2,
    "QUERY LINK SERVER": 3,
    "ENGINE":            4,
    "ADDED BY":          5,
    "ADDED AT":          6,
    "CHANGED BY":        7,
    "CHANGED AT":        8,
    "CHANGED NO":        9,
}


# ── Text helpers ──────────────────────────────────────────────────────────────

def _wrap_line(line: str, limit: int) -> list[str]:
    if not line or len(line) <= limit:
        return [line] if line else []
    chunks, rest = [], line
    while rest:
        if len(rest) <= limit:
            chunks.append(rest)
            break
        seg = rest[: limit + 1]
        bp  = seg.rfind(" ")
        bp  = bp if bp > limit // 2 else limit
        chunks.append(rest[:bp].rstrip())
        rest = rest[bp:].lstrip()
    return chunks


def wrap_query_text(text: str, limit: int = QUERY_WRAP_LIMIT) -> str:
    if not text:
        return text
    result = []
    for line in text.split("\n"):
        result.extend(_wrap_line(line, limit))
    return "\n".join(result)


# ── Data conversion ───────────────────────────────────────────────────────────

def _row_to_tuple(r: dict) -> tuple:
    """
    Index layout:
        0  key  (conn_name::table_name::pk)
        1  conn_name
        2  table_name
        3  query
        4  engine
        5  added_by
        6  added_at   (str)
        7  changed_by
        8  changed_at (str)
        9  changed_no (str)
        10 pk         (int)
    """
    pk   = r["pk"]
    conn = (r.get("conn_name") or "").strip()
    tbl  = (r.get("table_name") or "").strip()
    return (
        f"{conn}::{tbl}::{pk}",
        conn,
        tbl,
        (r.get("query") or "").strip(),
        (r.get("engine") or "").strip(),
        (r.get("added_by") or "").strip(),
        str(r["added_at"])[:19] if r.get("added_at") else "",
        (r.get("changed_by") or "").strip(),
        str(r["changed_at"])[:19] if r.get("changed_at") else "",
        str(r.get("changed_no", 0)),
        pk,
    )


# ── Form schema ───────────────────────────────────────────────────────────────

def _build_form_schema(
    connection_tables: dict,
    columns: list[str] | None = None,
    checked: list[str] | None = None,
) -> list[dict]:
    """
    columns — pre-loaded column names for the checkbox_list (None = empty / waiting for table pick)
    checked — which columns are pre-ticked (defaults to all when columns are provided)
    """
    return [
        {
            "name":     "engine",
            "label":    "Engine",
            "type":     "combo",
            "options":  ["postgresql", "sqlite"],
            "required": True,
        },
        {
            "name":     "conn",
            "label":    "Connection",
            "type":     "cascade_combo",
            "options":  connection_tables,
            "child":    "table_name",
            "required": True,
        },
        {
            "name":     "table_name",
            "label":    "Table Name",
            "type":     "combo",
            "options":  [],
            "required": True,
        },
        # ── Column picker — populated after table is selected ─────────
        {
            "name":            "columns",
            "label":           "Select Fields",
            "type":            "checkbox_list",
            "options":         columns or [],
            # tick all by default; caller may override via `checked`
            "initial_checked": {c: True for c in (checked if checked is not None else (columns or []))},
            "required":        False,
        },
        {
            "name":        "query",
            "label":       "Query Preview",
            "type":        "text",
            "placeholder": "Auto-filled when fields are selected, or enter manually",
            "required":    True,
        },
        {"name": "added_by",   "label": "Added By",   "type": "readonly"},
        {"name": "added_at",   "label": "Added At",   "type": "readonly"},
        {"name": "changed_by", "label": "Changed By", "type": "readonly"},
        {"name": "changed_at", "label": "Changed At", "type": "readonly"},
        {"name": "changed_no", "label": "Changed No", "type": "readonly"},
    ]


# ── Page ──────────────────────────────────────────────────────────────────────

class SourceDataPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data:       list[tuple] = []
        self.filtered_data:  list[tuple] = []
        self.current_page    = 0
        self.page_size       = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type  = "CONNECTION"
        self._last_search_text  = ""
        self._sort_fields:       list[str]       = []
        self._sort_directions:   dict[str, str]  = {}
        self._connection_tables: dict[str, list] = {}
        self._tbnm_id_map:       dict[str, int]  = {}   # "conn::table" → motbnmiy
        self._conc_id_map:       dict[str, int]  = {}   # conn_name    → mnconciy
        self._active_modal: GenericFormModal | None = None
        self._init_ui()
        self.load_data()

    # ── UI setup ──────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setStyleSheet("background-color: #F8FAFC;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 20, 40, 12)
        layout.setSpacing(0)
        self.main_layout = layout

        self.header = StandardPageHeader(
            title="Master Source Group",
            subtitle="Manage source data group records",
            enabled_actions=["Add", "Excel", "Refresh", "View Detail"],
        )
        layout.addWidget(self.header)
        self._connect_header_actions()
        layout.addSpacing(12)

        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        layout.addWidget(self.search_bar)
        layout.addSpacing(5)

        self.table_comp = StandardTable([
            "CONNECTION", "TABLE NAME", "QUERY LINK SERVER",
            "ENGINE", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        self.table = self.table_comp.table
        self.table.setWordWrap(True)
        self._configure_table_columns()

        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        layout.addWidget(self.sort_bar)
        layout.addSpacing(8)

        layout.addWidget(self.table_comp)
        layout.addSpacing(16)

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
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)
        hdr.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(6, QHeaderView.Fixed)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(8, QHeaderView.Fixed)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnWidth(3, 120)
        self.table.setColumnWidth(4, 100)
        self.table.setColumnWidth(6, 110)
        self.table.setColumnWidth(8, 100)

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

    def _get_selected_row(self) -> tuple | None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        global_idx = self.current_page * self.page_size + rows[0].row()
        if global_idx >= len(self.filtered_data):
            return None
        return self.filtered_data[global_idx]

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
                if label in ("Edit", "Delete", "View Detail"):
                    btn.setEnabled(has_selection)
                else:
                    btn.setEnabled(True)

    def _open_modal(self, modal: GenericFormModal):
        modal.opened.connect(self._lock_header)
        modal.closed.connect(self._unlock_header)
        modal.closed.connect(self._clear_active_modal)
        self._active_modal = modal
        modal.exec()

    def _clear_active_modal(self):
        self._active_modal = None

    # ── Page visibility ───────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_active_modal", None) and not self._active_modal.isVisible():
            self._active_modal.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        if getattr(self, "_active_modal", None) and self._active_modal.isVisible():
            self._active_modal.hide()

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _make_item(self, text: str) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        it.setTextAlignment(Qt.AlignTop | Qt.AlignLeft)
        return it

    def _add_table_row(self, row: tuple):
        r = self.table.rowCount()
        self.table.insertRow(r)
        item_conn = self._make_item(row[1])
        item_conn.setData(Qt.UserRole, ROW_STANDARD)
        self.table.setItem(r, 0, item_conn)
        self.table.setItem(r, 1, self._make_item(row[2]))
        self.table.setItem(r, 2, self._make_item(wrap_query_text(row[3])))
        self.table.setItem(r, 3, self._make_item(row[4]))
        self.table.setItem(r, 4, self._make_item(row[5]))
        self.table.setItem(r, 5, self._make_item(row[6]))
        self.table.setItem(r, 6, self._make_item(row[7]))
        self.table.setItem(r, 7, self._make_item(row[8]))
        self.table.setItem(r, 8, self._make_item(row[9]))

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        data  = self.filtered_data or []
        total = len(data)
        start = self.current_page * self.page_size
        end   = min(start + self.page_size, total)

        for item in data[start:end]:
            self._add_table_row(item)

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

    def load_data(self):
        try:
            self.all_data            = [_row_to_tuple(r) for r in fetch_all_sdgr()]
            self._connection_tables  = fetch_connection_table_map()
            self._tbnm_id_map, self._conc_id_map = fetch_tbnm_id_map()
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load data:\n\n{exc}")
            self.all_data           = []
            self._connection_tables = {}
            self._tbnm_id_map       = {}
            self._conc_id_map       = {}
        self._apply_filter_and_reset_page()

    # ── Filtering & sorting ───────────────────────────────────────────────────

    def filter_table(self, filter_type: str, search_text: str):
        self._last_filter_type  = filter_type
        self._last_search_text  = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query   = (self._last_search_text or "").lower().strip()
        col_idx = _COL_HEADER_TO_TUPLE_IDX.get(self._last_filter_type, 1)
        self.filtered_data = (
            list(self.all_data)
            if not query
            else [row for row in self.all_data if query in str(row[col_idx] or "").lower()]
        )
        self._apply_sort()
        self.current_page = 0
        self.render_page()

    def on_sort_changed(self, fields: list[str], field_directions: dict):
        self._sort_fields      = fields or []
        self._sort_directions  = field_directions or {}
        self._apply_filter_and_reset_page()

    def _apply_sort(self):
        if not self._sort_fields or not self.filtered_data:
            return
        for field in reversed(self._sort_fields):
            idx = _COL_HEADER_TO_TUPLE_IDX.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._sort_key(row, i),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

    def _sort_key(self, row: tuple, idx: int):
        val = str(row[idx]) if row[idx] is not None else ""
        try:
            return float(val.replace(",", ""))
        except ValueError:
            return val.lower()

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

    # ── Column / query helpers ────────────────────────────────────────────────

    def _fetch_columns_for(self, conn_name: str, table_name: str) -> list[str]:
        if not conn_name or not table_name:
            return []
        try:
            return fetch_table_columns(_BARCODE_SCHEMA, table_name)
        except Exception:
            return []

    def _build_query_from_columns(self, table_name: str, columns: list[str]) -> str:
        if not columns or not table_name:
            return ""
        return f"SELECT {', '.join(columns)} FROM {table_name}"

    def _parse_columns_from_query(self, query: str, all_columns: list[str]) -> list[str]:
        """
        Try to extract previously selected columns from a stored SELECT query.
        Falls back to returning all columns if parsing fails.
        """
        try:
            upper = query.strip().upper()
            if upper.startswith("SELECT") and "FROM" in upper:
                col_part = query[6 : query.upper().index("FROM")].strip()
                if col_part == "*":
                    return all_columns
                parsed = [c.strip() for c in col_part.split(",") if c.strip() in all_columns]
                return parsed if parsed else all_columns
        except Exception:
            pass
        return all_columns

    # ── Action handlers ───────────────────────────────────────────────────────

    def _resolve_fk_ids(self, conn_name: str, table_name: str) -> tuple[int, int] | None:
        conciy = self._conc_id_map.get(conn_name)
        tbnmiy = self._tbnm_id_map.get(f"{conn_name}::{table_name}")
        if conciy is None or tbnmiy is None:
            QMessageBox.warning(
                self, "Lookup Error",
                f"Could not resolve IDs for:\n  Connection: {conn_name}\n  Table: {table_name}\n\n"
                "Please refresh and try again.",
            )
            return None
        return conciy, tbnmiy

    def _on_table_selected(self, modal: GenericFormModal, field_name: str, value: str):
        """
        Fired by modal.fieldChanged. When table_name changes, fetch its columns,
        rebuild the checkbox_list, and auto-fill the query preview.
        """
        if field_name != "table_name" or not value:
            return
        conn_name = modal.get_field_value("conn")
        columns   = self._fetch_columns_for(conn_name, value)
        query     = self._build_query_from_columns(value, columns)

        modal.update_field_options("columns", columns, checked=columns)  # tick all by default
        modal.set_field_value("query", query)

    # ── Add ───────────────────────────────────────────────────────────────────

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Source Group",
            fields=_build_form_schema(self._connection_tables),
            parent=self,
            mode="add",
        )
        modal.fieldChanged.connect(
            lambda name, val, m=modal: self._on_table_selected(m, name, val)
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        conn_name  = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        engine     = data.get("engine", "").strip()
        selected   = data.get("columns", [])   # list[str] from checkbox_list

        # Build query from ticked columns; fall back to whatever is in the text field
        query = (
            self._build_query_from_columns(table_name, selected)
            if selected
            else data.get("query", "").strip()
        )

        if not all([conn_name, table_name, query, engine]):
            QMessageBox.warning(self, "Validation", "All fields are required.")
            return
        ids = self._resolve_fk_ids(conn_name, table_name)
        if ids is None:
            return
        conciy, tbnmiy = ids
        try:
            create_sdgr(conciy, tbnmiy, query, engine)
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Insert failed:\n\n{exc}")
            return
        self.load_data()

    # ── Export ────────────────────────────────────────────────────────────────

    def handle_export_action(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "master_source_group.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Master Source Group"
        ws.append([
            "CONNECTION", "TABLE NAME", "QUERY / LINK SERVER",
            "ENGINE", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        for row in self.filtered_data:
            ws.append([str(row[i]) if row[i] is not None else "" for i in range(1, 10)])
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
        try:
            detail = fetch_sdgr_by_id(row[10])
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Could not load detail:\n\n{exc}")
            return
        if detail is None:
            return
        fields = [(label, str(detail.get(key, "") or "")) for label, key in VIEW_DETAIL_FIELDS]
        modal  = GenericFormModal(
            title="Row Detail",
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

        # Pre-load columns for the already-selected table so checkboxes are visible immediately
        existing_columns   = self._fetch_columns_for(row[1], row[2])
        previously_checked = self._parse_columns_from_query(row[3], existing_columns)

        initial = {
            "conn":       row[1],
            "table_name": row[2],
            "query":      row[3],
            "engine":     row[4],
            "added_by":   row[5],
            "added_at":   row[6],
            "changed_by": row[7],
            "changed_at": row[8],
            "changed_no": row[9],
        }
        modal = GenericFormModal(
            title="Edit Source Group",
            fields=_build_form_schema(
                self._connection_tables,
                columns=existing_columns,
                checked=previously_checked,
            ),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.fieldChanged.connect(
            lambda name, val, m=modal: self._on_table_selected(m, name, val)
        )
        modal.formSubmitted.connect(lambda data, r=row: self._on_edit_submitted(r, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, row: tuple, data: dict):
        conn_name  = data.get("conn", "").strip()
        table_name = data.get("table_name", "").strip()
        engine     = data.get("engine", "").strip()
        selected   = data.get("columns", [])

        query = (
            self._build_query_from_columns(table_name, selected)
            if selected
            else data.get("query", "").strip()
        )

        if not all([conn_name, table_name, query, engine]):
            QMessageBox.warning(self, "Validation", "All fields are required.")
            return
        ids = self._resolve_fk_ids(conn_name, table_name)
        if ids is None:
            return
        conciy, tbnmiy = ids
        pk             = row[10]
        old_changed_no = int(row[9]) if str(row[9]).isdigit() else 0
        try:
            update_sdgr(pk, conciy, tbnmiy, query, engine, old_changed_no)
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Update failed:\n\n{exc}")
            return
        self.load_data()

    # ── Delete ────────────────────────────────────────────────────────────────

    def handle_delete_action(self):
        row = self._get_selected_row()
        if row is None:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText("Are you sure you want to delete this record?")
        msg.setInformativeText(
            f"Connection: {row[1]}\nTable Name: {row[2]}\nEngine: {row[4]}"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)
        if msg.exec() == QMessageBox.Yes:
            try:
                soft_delete_sdgr(row[10])
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Delete failed:\n\n{exc}")
                return
            self.load_data()