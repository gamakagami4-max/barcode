# app/pages/master_source_group.py

import threading
import openpyxl
from PySide6.QtCore import Qt, QObject, Signal, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QHeaderView, QMessageBox, QTableWidgetItem, QVBoxLayout, QWidget,
)
from PySide6.QtCore import QMetaObject, Qt
from components.generic_form_modal import GenericFormModal
from components.search_bar import StandardSearchBar
from components.sort_by_widget import SortByWidget
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from repositories.mmsdgr_repo import (
    create_sdgr,
    fetch_all_sdgr,
    fetch_sdgr_by_id,
    soft_delete_sdgr,
    update_sdgr,
)
from repositories.mengin_repo import fetch_all_engines
from repositories.mconnc_repo import fetch_connections_by_engine
from repositories.mtable_repo import fetch_tables_by_connection
from repositories.field_repo import fetch_fields

ROW_STANDARD          = "standard"
QUERY_COL_FIXED_WIDTH = 370
_QUERY_PADDING_PX     = 12
_WRAP_PIXEL_LIMIT     = QUERY_COL_FIXED_WIDTH - _QUERY_PADDING_PX

# Source-type toggle options
SOURCE_TYPE_TABLE = "Table + Fields"
SOURCE_TYPE_QUERY = "Query / Link Server"

VIEW_DETAIL_FIELDS = [
    ("Engine",              "engine"),
    ("Connection",          "conn_name"),
    ("Table Name",          "table_name"),
    ("Query / Link Server", "query"),
    ("Fields",              "fields"),
    ("Added By",            "added_by"),
    ("Added At",            "added_at"),
    ("Changed By",          "changed_by"),
    ("Changed At",          "changed_at"),
    ("Changed No",          "changed_no"),
]

_COL_HEADER_TO_TUPLE_IDX = {
    "ENGINE":            1,
    "CONNECTION":        2,
    "TABLE NAME":        3,
    "FIELDS":            12,
    "QUERY LINK SERVER": 4,
    "ADDED BY":          5,
    "ADDED AT":          6,
    "CHANGED BY":        7,
    "CHANGED AT":        8,
    "CHANGED NO":        9,
}


# ── Background column fetcher ─────────────────────────────────────────────────
# Runs fetch_table_columns on a daemon thread and emits `done` back on the
# Qt main thread via a queued signal — zero UI blocking.

class _ColsFetcher(QObject):
    done = Signal(list)

    def start(self, table_name: str):
        def _run():
            try:
                from repositories.mmsdgr_repo import fetch_table_columns
                cols = fetch_table_columns("barcode", table_name)
            except Exception:
                cols = []
            self.done.emit(cols)

        threading.Thread(target=_run, daemon=True).start()


# ── Text helpers ──────────────────────────────────────────────────────────────

def _get_fm() -> QFontMetrics:
    return QFontMetrics(QApplication.font())


def _wrap_line_px(line: str, fm: QFontMetrics, limit_px: int) -> list[str]:
    if not line:
        return []
    if fm.horizontalAdvance(line) <= limit_px:
        return [line]
    chunks = []
    rest = line
    while rest:
        if fm.horizontalAdvance(rest) <= limit_px:
            chunks.append(rest)
            break
        lo, hi = 1, len(rest)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if fm.horizontalAdvance(rest[:mid]) <= limit_px:
                lo = mid
            else:
                hi = mid - 1
        seg = rest[:lo]
        sp  = seg.rfind(" ")
        bp  = sp if sp > lo // 2 else lo
        chunks.append(rest[:bp].rstrip())
        rest = rest[bp:].lstrip()
    return chunks


def wrap_query_text(text: str, limit_px: int = _WRAP_PIXEL_LIMIT) -> str:
    if not text:
        return text
    fm = _get_fm()
    result = []
    for line in text.split("\n"):
        result.extend(_wrap_line_px(line, fm, limit_px))
    return "\n".join(result)


# ── Name splitting ────────────────────────────────────────────────────────────

def _split_tables_and_fields(mixed: list[str]) -> tuple[list[str], list[str]]:
    tables = sorted(name[2:] for name in mixed if name.startswith("t."))
    fields = sorted(name for name in mixed if not name.startswith("t."))
    return tables, fields


# ── Data conversion ───────────────────────────────────────────────────────────

def _row_to_tuple(r: dict) -> tuple:
    pk      = r["pk"]
    eng     = (r.get("engine")     or "").strip()
    conn    = (r.get("conn_name")  or "").strip()
    tbl     = (r.get("table_name") or "").strip()
    fields_raw = r.get("fields") or []
    if isinstance(fields_raw, str):
        fields_list = [f.strip() for f in fields_raw.split(",") if f.strip()]
    else:
        fields_list = [str(f).strip() for f in fields_raw if f]
    fields_display = ", ".join(fields_list)

    return (
        f"{eng}::{conn}::{tbl}::{pk}",   # 0  composite key
        eng,                               # 1  engine
        conn,                              # 2  connection
        tbl,                               # 3  table_name
        (r.get("query") or "").strip(),    # 4  query
        (r.get("added_by") or "").strip(), # 5  added_by
        str(r["added_at"])[:19] if r.get("added_at") else "",    # 6
        (r.get("changed_by") or "").strip(),                     # 7
        str(r["changed_at"])[:19] if r.get("changed_at") else "", # 8
        str(r.get("changed_no", 0)),       # 9  changed_no
        pk,                                # 10 pk
        eng,                               # 11 (dup engine, kept for legacy)
        fields_display,                    # 12 fields (comma-separated display)
    )


# ── Form schema ───────────────────────────────────────────────────────────────

def _build_form_schema(
    connection_tables: dict,
    initial_engine: str = "",
    initial_conn: str = "",
    initial_table: str = "",
    initial_fields: list[str] | None = None,
    initial_source_type: str = SOURCE_TYPE_TABLE,
) -> list[dict]:
    engine_options = sorted(connection_tables.keys())

    if initial_engine:
        mixed              = connection_tables.get(initial_engine, {}).get(initial_conn, [])
        initial_tables, all_fields_for_conn = _split_tables_and_fields(mixed)
        initial_conns      = sorted(connection_tables.get(initial_engine, {}).keys())
        initial_field_opts = all_fields_for_conn
    else:
        all_conns: set[str] = set()
        for conns in connection_tables.values():
            all_conns.update(conns.keys())
        initial_conns = sorted(all_conns)

        all_mixed: list[str] = []
        for conns in connection_tables.values():
            for names in conns.values():
                all_mixed.extend(names)
        initial_tables, _ = _split_tables_and_fields(all_mixed)
        initial_field_opts = []

    checked = initial_fields if initial_fields is not None else initial_field_opts

    return [
        {
            "name":        "engine",
            "label":       "Engine",
            "type":        "combo",
            "options":     engine_options,
            "placeholder": "Please select an engine...",
            "required":    True,
        },
        {
            "name":        "conn",
            "label":       "Connection",
            "type":        "combo",
            "options":     initial_conns,
            "placeholder": "Please select a connection...",
            "required":    True,
        },
        {
            "name":    "source_type",
            "label":   "Source Type",
            "type":    "tab_select",
            "options": [SOURCE_TYPE_TABLE, SOURCE_TYPE_QUERY],
        },
        {
            "name":        "table_name",
            "label":       "Table Name",
            "type":        "combo",
            "options":     initial_tables,
            "placeholder": "Please select a table...",
        },
        {
            "name":            "fields",
            "label":           "Fields",
            "type":            "checkbox_list",
            "options":         initial_field_opts,
            "initial_checked": {f: (f in checked) for f in initial_field_opts},
        },
        {
            "name":        "query",
            "label":       "Query / Link Server",
            "type":        "textarea",
            "placeholder": "Enter query or link server manually",
            "height":      150,
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
        self._engine_map = {}        # code -> id
        self._conn_map   = {}        # engine_code -> [conn_names]
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
            "ENGINE",
            "CONNECTION",
            "TABLE NAME",
            "FIELDS",
            "QUERY LINK SERVER",
            "ADDED BY",
            "ADDED AT",
            "CHANGED BY",
            "CHANGED AT",
            "CHANGED NO",
        ])
        self.table = self.table_comp.table
        self.table.setWordWrap(True)
        self.table.setStyleSheet(
            self.table.styleSheet() + "\nQTableWidget::item { padding: 4px 6px; }"
        )

        self.sort_bar = SortByWidget(self.table)
        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        layout.addWidget(self.sort_bar)
        layout.addSpacing(8)

        layout.addWidget(self.table_comp)
        self._configure_table_columns()
        layout.addSpacing(16)

        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

        self.sort_bar.initialize_default_sort()
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

    def _configure_table_columns(self):
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ENGINE
        hdr.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # CONNECTION
        hdr.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # TABLE NAME
        hdr.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # FIELDS
        hdr.setSectionResizeMode(4, QHeaderView.Fixed)             # QUERY
        hdr.resizeSection(4, QUERY_COL_FIXED_WIDTH)

        for i in range(5, 10):
            hdr.setSectionResizeMode(i, QHeaderView.ResizeToContents)

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

        # ENGINE
        self.table.setItem(r, 0, self._make_item(row[1]))

        # CONNECTION
        item_conn = self._make_item(row[2])
        item_conn.setData(Qt.UserRole, ROW_STANDARD)
        self.table.setItem(r, 1, item_conn)

        # TABLE NAME
        self.table.setItem(r, 2, self._make_item(row[3]))

        # FIELDS
        fields_text = row[12] if len(row) > 12 else ""
        if fields_text and len(fields_text) > 60:
            _flds = [f.strip() for f in fields_text.split(",") if f.strip()]
            _per_line = 4
            fields_display = "\n".join(
                ", ".join(_flds[i:i + _per_line])
                for i in range(0, len(_flds), _per_line)
            )
        else:
            fields_display = fields_text
        self.table.setItem(r, 3, self._make_item(fields_display))

        # QUERY
        self.table.setItem(r, 4, self._make_item(wrap_query_text(row[4])))

        # META
        self.table.setItem(r, 5, self._make_item(row[5]))
        self.table.setItem(r, 6, self._make_item(row[6]))
        self.table.setItem(r, 7, self._make_item(row[7]))
        self.table.setItem(r, 8, self._make_item(row[8]))
        self.table.setItem(r, 9, self._make_item(row[9]))
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
            self.all_data = [_row_to_tuple(r) for r in fetch_all_sdgr()]

            # Load engines
            engines = fetch_all_engines()

            self._engine_map = {}
            self._conn_map = {}

            for e in engines:
                engine_code = e["code"]
                engine_id   = e["pk"]

                self._engine_map[engine_code] = engine_id

                conns = fetch_connections_by_engine(engine_id)
                self._conn_map[engine_code] = [c["name"] for c in conns]

        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load data:\n\n{exc}")
            self.all_data = []
            self._engine_map = {}
            self._conn_map = {}

        self._apply_filter_and_reset_page()

    # ── Filtering & sorting ───────────────────────────────────────────────────

    def filter_table(self, filter_type: str, search_text: str):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self):
        query   = (self._last_search_text or "").lower().strip()
        col_idx = _COL_HEADER_TO_TUPLE_IDX.get(self._last_filter_type, 2)
        self.filtered_data = (
            list(self.all_data)
            if not query
            else [row for row in self.all_data if query in str(row[col_idx] or "").lower()]
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

    
    # ── Source-type mutual-exclusion ──────────────────────────────────────────

    def _apply_source_type_state(self, modal: GenericFormModal, source_type: str):
        use_table = (source_type == SOURCE_TYPE_TABLE)

        modal.set_field_disabled("table_name", not use_table)
        modal.set_field_disabled("fields",     not use_table)
        modal.set_field_disabled("query", use_table)

        fields_widget = modal.inputs.get("fields")
        if fields_widget:
            table_selected = bool(modal.get_field_value("table_name")) if use_table else False
            if use_table and table_selected:
                fields_widget.setMinimumHeight(155)
                fields_widget.setMaximumHeight(230)
            else:
                fields_widget.setMinimumHeight(0)
                fields_widget.setMaximumHeight(0)
            cbw = getattr(fields_widget, "_checkbox_widget", None)
            if cbw and hasattr(cbw, "_scroll"):
                if use_table and table_selected:
                    cbw._scroll.setFixedHeight(125)
                else:
                    cbw._scroll.setFixedHeight(0)

    # ── Cascade field handler ─────────────────────────────────────────────────

    def _on_field_changed(self, modal: "GenericFormModal", field_name: str, value: str):
        if field_name == "source_type":
            self._apply_source_type_state(modal, value)

            if value == SOURCE_TYPE_QUERY:
                modal.update_field_options("table_name", [])
                modal.update_field_options("fields", [])
                fields_widget = modal.inputs.get("fields")
                if fields_widget and hasattr(fields_widget, "set_actions_visible"):
                    fields_widget.set_actions_visible(False)

            elif value == SOURCE_TYPE_TABLE:
                query_widget = modal.inputs.get("query")
                if query_widget:
                    from PySide6.QtWidgets import QTextEdit as _QTE
                    if isinstance(query_widget, _QTE):
                        query_widget.setPlainText("")

                engine = modal.get_field_value("engine")
                conn   = modal.get_field_value("conn")

                if engine and conn:
                    try:
                        tables = [t["name"] for t in fetch_tables_by_connection(conn)]
                    except Exception:
                        tables = []

                    modal.update_field_options("table_name", tables)

            return

        if field_name == "engine" and value:
            conns = self._conn_map.get(value, [])
            modal.update_field_options("conn", conns)
            modal.update_field_options("table_name", [])
            modal.update_field_options("fields", [])
            fields_widget = modal.inputs.get("fields")
            if fields_widget and hasattr(fields_widget, "set_actions_visible"):
                fields_widget.set_actions_visible(False)

        elif field_name == "conn" and value:
            try:
                tables = [t["name"] for t in fetch_tables_by_connection(value)]
            except Exception:
                tables = []

            modal.update_field_options("table_name", tables)
            modal.update_field_options("fields", [])

            fields_widget = modal.inputs.get("fields")
            if fields_widget and hasattr(fields_widget, "set_actions_visible"):
                fields_widget.set_actions_visible(False)

        elif field_name == "table_name" and value:
            # Always async — modal stays fully interactive while columns load
            self._fetch_and_populate_fields(modal, value)

        elif field_name == "table_name" and not value:
            fields_widget = modal.inputs.get("fields")
            if fields_widget:
                fields_widget.setMinimumHeight(0)
                fields_widget.setMaximumHeight(0)
                cbw = getattr(fields_widget, "_checkbox_widget", None)
                if cbw and hasattr(cbw, "_scroll"):
                    cbw._scroll.setFixedHeight(0)
                if hasattr(fields_widget, "set_actions_visible"):
                    fields_widget.set_actions_visible(False)

    # ── Async field population ────────────────────────────────────────────────

    def _fetch_and_populate_fields(self, modal, table_name):
        print(">>> _fetch_and_populate_fields CALLED")

        engine = modal.get_field_value("engine")
        conn   = modal.get_field_value("conn")

        if not engine or not conn or not table_name:
            print(">>> Missing required values")
            return

        try:
            cols = fetch_fields(conn, table_name)
            print(">>> GOT COLS:", cols)
        except Exception as e:
            print(">>> ERROR:", e)
            cols = []

        # Direct UI update (no thread)
        self._update_fields_ui(modal, cols)


    def _update_fields_ui(self, modal, cols):
        print(">>> _update_fields_ui CALLED")
        print(">>> COLS RECEIVED:", cols)

        if not cols:
            modal.update_field_options("fields", [])
            return

        saved = getattr(modal, "_saved_fields", None)
        checked = saved if saved else [col["name"] for col in cols]

        # IMPORTANT: must be dict format
        options = []
        for col in cols:
            value = col["name"]
            label = col.get("comment") or value
            options.append({
                "value": value,
                "label": label
            })

        modal.update_field_options("fields", options, checked=checked)

        fields_widget = modal.inputs.get("fields")
        if fields_widget:
            fields_widget.setMinimumHeight(155)
            fields_widget.setMaximumHeight(155)

            cbw = getattr(fields_widget, "_checkbox_widget", None)
            if cbw and hasattr(cbw, "_scroll"):
                cbw._scroll.setFixedHeight(125)

            if hasattr(fields_widget, "set_actions_visible"):
                fields_widget.set_actions_visible(True)

        modal._saved_fields = None

        print(">>> DONE updating UI")
    # ── Add ───────────────────────────────────────────────────────────────────

    def handle_add_action(self):
        default_engine = "postgresql"
        default_conn   = "barcode db"

        schema = _build_form_schema(
            self._build_connection_tables_structure(),
            initial_engine=default_engine,
            initial_conn=default_conn,
            initial_source_type=SOURCE_TYPE_TABLE,
        )

        modal = GenericFormModal(
            title="Add Source Group",
            fields=schema,
            parent=self,
            mode="add",
            initial_data={
                "engine": default_engine,
                "conn": default_conn,
                "source_type": SOURCE_TYPE_TABLE,
            },
        )
        modal.fieldChanged.connect(
            lambda name, val, m=modal: self._on_field_changed(m, name, val)
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        # Trigger engine + connection cascade immediately
        self._on_field_changed(modal, "engine", default_engine)
        self._on_field_changed(modal, "conn", default_conn)

        # 🔥 Disable Query initially (since default is TABLE mode)
        self._apply_source_type_state(modal, SOURCE_TYPE_TABLE)

        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        engine      = data.get("engine", "").strip()
        conn_name   = data.get("conn", "").strip()
        table_name  = data.get("table_name", "").strip()
        query       = data.get("query", "").strip()
        source_type = data.get("source_type", SOURCE_TYPE_TABLE)

        if not engine or not conn_name:
            QMessageBox.warning(self, "Validation", "Engine and Connection are required.")
            return

        if source_type == SOURCE_TYPE_TABLE and not table_name:
            QMessageBox.warning(self, "Validation", "Table Name is required.")
            return

        if source_type == SOURCE_TYPE_QUERY and not query:
            QMessageBox.warning(self, "Validation", "Query / Link Server is required.")
            return

        selected_fields = data.get("fields", [])
        if isinstance(selected_fields, str):
            selected_fields = [f.strip() for f in selected_fields.split(",") if f.strip()]

        try:
            create_sdgr(
                engine=engine,
                conn_name=conn_name,
                table_name=table_name if source_type == SOURCE_TYPE_TABLE else "",
                query=query,
                fields=selected_fields
            )
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
            "ENGINE",
            "CONNECTION",
            "TABLE NAME",
            "FIELDS",
            "QUERY / LINK SERVER",
            "ADDED BY",
            "ADDED AT",
            "CHANGED BY",
            "CHANGED AT",
            "CHANGED NO",
        ])
        for row in self.filtered_data:
            fields_val = row[12] if len(row) > 12 else ""
            ws.append([
                str(row[1]) if row[1] else "",
                str(row[2]) if row[2] else "",
                str(row[3]) if row[3] else "",
                fields_val,
                str(row[4]) if row[4] else "",
                str(row[5]) if row[5] else "",
                str(row[6]) if row[6] else "",
                str(row[7]) if row[7] else "",
                str(row[8]) if row[8] else "",
                str(row[9]) if row[9] else "",
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
        try:
            detail = fetch_sdgr_by_id(row[10])
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Could not load detail:\n\n{exc}")
            return
        if detail is None:
            return

        fields_raw = detail.get("fields") or []
        if isinstance(fields_raw, list):
            fields_str = ", ".join(str(f) for f in fields_raw)
        else:
            fields_str = str(fields_raw)
        detail_copy = dict(detail)
        detail_copy["fields"] = fields_str

        fields = [(label, str(detail_copy.get(key, "") or "")) for label, key in VIEW_DETAIL_FIELDS]
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

        engine     = row[1]
        conn_name  = row[2]
        table_name = row[3]
        query      = row[4]

        try:
            detail = fetch_sdgr_by_id(row[10])
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Could not load detail:\n\n{exc}")
            return

        saved_fields: list[str] = detail.get("fields", []) if detail else []
        initial_source_type = SOURCE_TYPE_TABLE if table_name else SOURCE_TYPE_QUERY

        initial = {
            "engine":      engine,
            "conn":        conn_name,
            "source_type": initial_source_type,
            "table_name":  table_name,
            "query":       query,
            "added_by":    row[5],
            "added_at":    row[6],
            "changed_by":  row[7],
            "changed_at":  row[8],
            "changed_no":  row[9],
        }

        # Build schema and guarantee the saved table_name is always a valid
        # combo option (prevents "Please select a table..." showing on open).
        schema = _build_form_schema(
            self._build_connection_tables_structure(),
            initial_engine=engine,
            initial_conn=conn_name,
            initial_table=table_name,
            initial_fields=saved_fields,
            initial_source_type=initial_source_type,
        )
        for field_def in schema:
            if field_def.get("name") == "table_name" and table_name:
                if table_name not in field_def.get("options", []):
                    field_def["options"] = sorted(set(field_def["options"]) | {table_name})
                break

        # ── Open modal immediately — no blocking DB calls here ───────────────
        modal = GenericFormModal(
            title="Edit Source Group",
            fields=schema,
            parent=self,
            mode="edit",
            initial_data=initial,
        )

        # Store saved fields so _fetch_and_populate_fields can pre-check them
        modal._saved_fields = saved_fields

        modal.fieldChanged.connect(
            lambda name, val, m=modal: self._on_field_changed(m, name, val)
        )
        modal.formSubmitted.connect(lambda data, r=row: self._on_edit_submitted(r, data))

        self._apply_source_type_state(modal, initial_source_type)

        # Set the table combo to the saved value (guaranteed to be in options)
        if table_name and initial_source_type == SOURCE_TYPE_TABLE:
            table_widget = modal.inputs.get("table_name")
            if table_widget:
                table_widget.setCurrentText(table_name)

            # Kick off background column fetch — modal is already open and
            # interactive while this runs; fields populate when ready.
            self._fetch_and_populate_fields(modal, table_name)

        self._open_modal(modal)

    def _on_edit_submitted(self, row: tuple, data: dict):
        engine      = data.get("engine", "").strip()
        conn_name   = data.get("conn", "").strip()
        table_name  = data.get("table_name", "").strip()
        query       = data.get("query", "").strip()
        source_type = data.get("source_type", SOURCE_TYPE_TABLE)

        if not engine or not conn_name:
            QMessageBox.warning(self, "Validation", "Engine and Connection are required.")
            return

        if source_type == SOURCE_TYPE_TABLE and not table_name:
            QMessageBox.warning(self, "Validation", "Table Name is required.")
            return

        if source_type == SOURCE_TYPE_QUERY and not query:
            QMessageBox.warning(self, "Validation", "Query / Link Server is required.")
            return

        pk             = row[10]
        old_changed_no = int(row[9]) if str(row[9]).isdigit() else 0

        selected_fields = data.get("fields", [])
        if isinstance(selected_fields, str):
            selected_fields = [f.strip() for f in selected_fields.split(",") if f.strip()]

        try:
            update_sdgr(
                pk=pk,
                engine=engine,
                conn_name=conn_name,
                table_name=table_name if source_type == SOURCE_TYPE_TABLE else "",
                query=query,
                old_changed_no=old_changed_no,
                fields=selected_fields
            )
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
            f"Engine:     {row[1]}\nConnection: {row[2]}\nTable Name: {row[3]}"
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

    def _build_connection_tables_structure(self) -> dict:
        result = {}

        for engine_code, conn_list in self._conn_map.items():
            result[engine_code] = {}
            for conn_name in conn_list:
                try:
                    tables = fetch_tables_by_connection(conn_name)
                    result[engine_code][conn_name] = [
                        t["name"] for t in tables
                    ]
                except Exception:
                    result[engine_code][conn_name] = []

        return result