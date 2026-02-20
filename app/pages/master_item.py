from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidgetItem,
    QHeaderView, QFrame, QScrollArea, QAbstractItemView
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QMessageBox
from components.search_bar import StandardSearchBar
from components.standard_button import StandardButton
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal

from server.repositories.mmitem_repo import (
    fetch_all_item,
    create_item,
    update_item,
    delete_item,
)

# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────
CURRENT_USER = "Admin"   # ← swap with session.user when auth is ready

# --- Design Tokens ---
COLORS = {
    "bg_main":    "#F8FAFC",
    "link":       "#6366F1",
    "border":     "#E2E8F0",
    "panel_bg":   "#FFFFFF",
    "text_main":  "#1E293B",
    "text_muted": "#64748B",
}

# Mapping: (display label, index into the row tuple used in the table)
VIEW_DETAIL_FIELDS = [
    ("Item Code",     0),
    ("Name",          1),
    ("Brand",         2),
    ("Warehouse",     3),
    ("Part No",       4),
    ("Interchange 1", 5),
    ("Interchange 2", 6),
    ("Interchange 3", 7),
    ("Interchange 4", 8),
    ("Quantity",      9),
    ("UOM",          10),
    ("Added By",     11),
    ("Added At",     12),
    ("Changed By",   13),
    ("Changed At",   14),
    ("Changed No",   15),
]


def _build_form_schema(mode: str = "add") -> list[dict]:
    schema = [
        {"name": "item_code",     "label": "Item Code",      "type": "text",  "placeholder": "e.g., EIF1-SFF1-FC-1001", "required": True},
        {"name": "name",          "label": "Item Name",       "type": "text",  "placeholder": "Enter item description",  "required": True},
        {"name": "warehouse",     "label": "Warehouse",       "type": "text",  "placeholder": "e.g., EIF",              "required": False},
        {"name": "part_no",       "label": "Part Number",     "type": "text",  "placeholder": "Enter part number",       "required": False},
        {"name": "interchange_1", "label": "Interchange 1",   "type": "text",  "placeholder": "Optional",               "required": False},
        {"name": "interchange_2", "label": "Interchange 2",   "type": "text",  "placeholder": "Optional",               "required": False},
        {"name": "interchange_3", "label": "Interchange 3",   "type": "text",  "placeholder": "Optional",               "required": False},
        {"name": "interchange_4", "label": "Interchange 4",   "type": "text",  "placeholder": "Optional",               "required": False},
        {"name": "qty",           "label": "Quantity",        "type": "text",  "placeholder": "Enter quantity",          "required": True},
        {"name": "uom",           "label": "Unit of Measure", "type": "combo", "options": ["PCS", "SET", "BOX", "KG", "LTR"], "required": True},
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


# ─────────────────────────────────────────────
# Helper: DB row dict → display tuple
# ─────────────────────────────────────────────
def _row_to_tuple(r: dict) -> tuple:
    """Convert a DB dict from fetch_all_item() into the display tuple."""
    def _fmt_dt(val):
        if val is None:
            return "-"
        # val may already be a string or a datetime object
        return str(val)[:19] if str(val) else "-"

    return (
        r.get("mlcode",  "") or "",           # 0  item code
        r.get("mlname",  "") or "",           # 1  name
        r.get("mlbrndiy", "") or "",          # 2  brand (FK id for now)
        r.get("mlwhse",  "") or "",           # 3  warehouse
        r.get("mlpnpr",  "") or "",           # 4  part no
        r.get("mlinc1",  "") or "",           # 5  interchange 1
        r.get("mlinc2",  "") or "",           # 6  interchange 2
        r.get("mlinc3",  "") or "",           # 7  interchange 3
        r.get("mlinc4",  "") or "",           # 8  interchange 4
        str(r.get("mlqtyn", 0) or 0),        # 9  quantity
        r.get("mlumit",  "") or "",           # 10 UOM
        r.get("mlrgid",  "-") or "-",        # 11 added by
        _fmt_dt(r.get("mlrgdt")),            # 12 added at
        r.get("mlchid",  "-") or "-",        # 13 changed by
        _fmt_dt(r.get("mlchdt")),            # 14 changed at
        str(r.get("mlchno", 0) or 0),       # 15 changed no
        r.get("mlitemiy"),                   # 16 PK (hidden, for updates/deletes)
    )


class MasterItemPage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data:      list[tuple] = []
        self.filtered_data: list[tuple] = []
        self.current_page   = 0
        self.page_size      = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "ITEM CODE"
        self._last_search_text = ""
        self._sort_fields:      list[str] = []
        self._sort_directions:  dict      = {}
        self._active_modal: GenericFormModal | None = None
        self.init_ui()
        self.load_data()

    # ──────────────────────────────────────────
    # UI setup
    # ──────────────────────────────────────────

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        enabled = ["Add", "Excel", "Refresh", "View Detail"]
        self.header = StandardPageHeader(
            title="Master Item",
            subtitle="Description",
            enabled_actions=enabled,
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        self.content_layout = QHBoxLayout()

        headers = [
            "ITEM CODE", "NAME", "BRAND", "WHS", "PART NO", "QTY", "UOM",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ]
        self.table_comp = StandardTable(headers)
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0, 160)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 80)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 110)
        self.table.setColumnWidth(6, 80)
        self.table.setColumnWidth(7, 100)
        h_header.setSectionResizeMode(8,  QHeaderView.ResizeToContents)
        self.table.setColumnWidth(9, 60)
        h_header.setSectionResizeMode(10, QHeaderView.ResizeToContents)
        h_header.setSectionResizeMode(1,  QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)

        self.content_layout.addWidget(self.table_comp, stretch=4)

        self.detail_panel = self._create_detail_panel()
        self.detail_panel.setVisible(False)
        self.content_layout.addWidget(self.detail_panel, stretch=1)

        self.main_layout.addLayout(self.content_layout)

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

    # ──────────────────────────────────────────
    # Selection helpers
    # ──────────────────────────────────────────

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

    # ──────────────────────────────────────────
    # Modal lock helpers
    # ──────────────────────────────────────────

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

    # ──────────────────────────────────────────
    # Page visibility
    # ──────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, "_active_modal", None) and not self._active_modal.isVisible():
            self._active_modal.show()

    def hideEvent(self, event):
        super().hideEvent(event)
        if getattr(self, "_active_modal", None) and self._active_modal.isVisible():
            self._active_modal.hide()

    # ──────────────────────────────────────────
    # Detail panel
    # ──────────────────────────────────────────

    def _create_detail_panel(self):
        panel = QFrame()
        panel.setFixedWidth(380)
        panel.setStyleSheet(
            f"background: {COLORS['panel_bg']}; border-left: 1px solid {COLORS['border']};"
        )
        layout  = QVBoxLayout(panel)
        top_bar = QHBoxLayout()

        self.detail_title = QLabel("Item Details")
        self.detail_title.setStyleSheet("font-size: 16px; font-weight: 700;")

        close_btn = StandardButton("", icon_name="fa5s.times", variant="ghost")
        close_btn.clicked.connect(lambda: panel.setVisible(False))

        top_bar.addWidget(self.detail_title)
        top_bar.addStretch()
        top_bar.addWidget(close_btn)
        layout.addLayout(top_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll_content = QWidget()
        self.info_layout = QVBoxLayout(scroll_content)
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll)

        return panel

    def show_details(self, data: tuple):
        self.detail_panel.setVisible(True)
        self.detail_title.setText(data[0])

        for i in reversed(range(self.info_layout.count())):
            w = self.info_layout.itemAt(i).widget()
            if w:
                w.setParent(None)

        fields = [
            ("Description",   data[1]),
            ("Warehouse",     data[3]),
            ("Part No Print", data[4]),
            ("Interchange 1", data[5]),
            ("Interchange 2", data[6]),
            ("Interchange 3", data[7]),
            ("Interchange 4", data[8]),
            ("Stock",         f"{data[9]} {data[10]}"),
        ]
        for label, val in fields:
            lbl = QLabel(
                f"<b>{label}</b><br>"
                f"<span style='color:{COLORS['text_muted']}'>{val or '—'}</span>"
            )
            lbl.setWordWrap(True)
            self.info_layout.addWidget(lbl)
            self.info_layout.addSpacing(10)
        self.info_layout.addStretch()

    # ──────────────────────────────────────────
    # Data loading  ← hits the real DB
    # ──────────────────────────────────────────

    def load_data(self):
        try:
            rows = fetch_all_item()
            self.all_data = [_row_to_tuple(r) for r in rows]
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to load items:\n{exc}")
            self.all_data = []
        self._apply_filter_and_reset_page()

    # ──────────────────────────────────────────
    # Render
    # ──────────────────────────────────────────

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data or []

        total     = len(data)
        start_idx = self.current_page * self.page_size
        end_idx   = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        # Indices into the display tuple that map to visible columns
        # (index 16 is the hidden PK — never shown)
        display_indices = [0, 1, 2, 3, 4, 9, 10, 11, 12, 13, 14, 15]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
            for c_idx, data_idx in enumerate(display_indices):
                val  = str(row_data[data_idx]) if data_idx < len(row_data) else "-"
                item = QTableWidgetItem(val)
                font = item.font()
                font.setPointSize(9)
                item.setFont(font)
                if c_idx == 0:
                    item.setForeground(QColor(COLORS["link"]))
                item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(r, c_idx, item)

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

    # ──────────────────────────────────────────
    # Filter / sort
    # ──────────────────────────────────────────

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query         = (self._last_search_text or "").lower().strip()
        headers       = self.table_comp.headers()
        header_to_idx = {h: i for i, h in enumerate(headers)}
        col_index     = header_to_idx.get(self._last_filter_type, 0)

        self.filtered_data = (
            list(self.all_data)
            if not query
            else [
                row for row in self.all_data
                if col_index < len(row) and query in str(row[col_index] or "").lower()
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
        headers       = self.table_comp.headers()
        header_to_idx = {h: i for i, h in enumerate(headers)}
        for field in reversed(self._sort_fields):
            idx = header_to_idx.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=(self._sort_directions.get(field, "asc") == "desc"),
            )

    def _get_sort_value(self, row, idx):
        val     = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val).replace(",", "").strip()
        try:
            return (0, float(str_val))
        except (ValueError, AttributeError):
            return (1, str_val.lower())

    # ──────────────────────────────────────────
    # Pagination
    # ──────────────────────────────────────────

    def on_page_changed(self, page_action: int) -> None:
        total       = len(self.filtered_data) if self.filtered_data else 0
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
        self.page_size    = new_size
        self.current_page = 0
        self.render_page()

    # ──────────────────────────────────────────
    # Header wiring
    # ──────────────────────────────────────────

    def _connect_header_actions(self):
        mapping = {
            "Refresh":     self.load_data,
            "Add":         self.handle_add_action,
            "Excel":       self.handle_export_action,
            "Edit":        self.handle_edit_action,
            "Delete":      self.handle_delete_action,
            "View Detail": self.handle_view_detail_action,
        }
        for action, slot in mapping.items():
            btn = self.header.get_action_button(action)
            if btn:
                btn.clicked.connect(slot)

    # ──────────────────────────────────────────
    # Action handlers
    # ──────────────────────────────────────────

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Master Item",
            fields=_build_form_schema(mode="add"),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        self._open_modal(modal)

    def _on_add_submitted(self, data: dict):
        item_code     = data.get("item_code",     "").strip()
        name          = data.get("name",          "").strip()
        warehouse     = data.get("warehouse",     "").strip()
        part_no       = data.get("part_no",       "").strip()
        interchange_1 = data.get("interchange_1", "").strip() or None
        interchange_2 = data.get("interchange_2", "").strip() or None
        interchange_3 = data.get("interchange_3", "").strip() or None
        interchange_4 = data.get("interchange_4", "").strip() or None
        qty_str       = data.get("qty",           "0").strip()
        uom           = data.get("uom",           "PCS")

        if not all([item_code, name, qty_str]):
            QMessageBox.warning(self, "Validation Error", "Item Code, Name, and Quantity are required.")
            return

        try:
            qty = int(qty_str)
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Quantity must be a whole number.")
            return

        # Duplicate code check (local cache)
        for row in self.all_data:
            if row[0].strip().lower() == item_code.lower():
                QMessageBox.warning(self, "Duplicate Item Code",
                                    f'Item Code "{item_code}" already exists.')
                return

        try:
            create_item(
                code=item_code,
                name=name,
                brand_id=None,       # ← wire to dropdown later
                filter_id=None,
                prty_id=None,
                stkr_id=None,
                sgdr_id=None,
                warehouse=warehouse or None,
                pnpr=part_no or None,
                inc1=interchange_1,
                inc2=interchange_2,
                inc3=interchange_3,
                inc4=interchange_4,
                inc5=None, inc6=None, inc7=None, inc8=None,
                quantity=qty,
                unit=uom,
                user=CURRENT_USER,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to create item:\n{exc}")
            return

        self.load_data()

    # ──────────────────────────────────────────

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "master_item.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Master Item"
        ws.append([
            "ITEM CODE", "NAME", "BRAND", "WAREHOUSE", "PART NO",
            "INTERCHANGE 1", "INTERCHANGE 2", "INTERCHANGE 3", "INTERCHANGE 4",
            "QTY", "UOM", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        for row in self.filtered_data:
            ws.append([str(v) if v is not None else "" for v in row[:16]])
        wb.save(path)
        QMessageBox.information(self, "Export Complete",
                                f"Exported {len(self.filtered_data)} records to:\n{path}")

    # ──────────────────────────────────────────

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
            title="Master Item Detail",
            subtitle="Full details for the selected item.",
            fields=fields,
            parent=self,
            mode="view",
        )
        self._open_modal(modal)

    # ──────────────────────────────────────────

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        row = self.all_data[idx]

        initial = {
            "item_code":     row[0],
            "name":          row[1],
            "warehouse":     row[3],
            "part_no":       row[4],
            "interchange_1": row[5],
            "interchange_2": row[6],
            "interchange_3": row[7],
            "interchange_4": row[8],
            "qty":           row[9],
            "uom":           row[10],
            "added_by":      row[11],
            "added_at":      row[12],
            "changed_by":    row[13],
            "changed_at":    row[14],
            "changed_no":    row[15],
        }
        modal = GenericFormModal(
            title="Edit Master Item",
            fields=_build_form_schema(mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        self._open_modal(modal)

    def _on_edit_submitted(self, idx: int, data: dict):
        item_code     = data.get("item_code",     "").strip()
        name          = data.get("name",          "").strip()
        warehouse     = data.get("warehouse",     "").strip()
        part_no       = data.get("part_no",       "").strip()
        interchange_1 = data.get("interchange_1", "").strip() or None
        interchange_2 = data.get("interchange_2", "").strip() or None
        interchange_3 = data.get("interchange_3", "").strip() or None
        interchange_4 = data.get("interchange_4", "").strip() or None
        qty_str       = data.get("qty",           "0").strip()
        uom           = data.get("uom",           "PCS")

        if not all([item_code, name, qty_str]):
            QMessageBox.warning(self, "Validation Error", "Item Code, Name, and Quantity are required.")
            return

        try:
            qty = int(qty_str)
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Quantity must be a whole number.")
            return

        # Duplicate check (exclude the row being edited)
        for i, row in enumerate(self.all_data):
            if i != idx and row[0].strip().lower() == item_code.lower():
                QMessageBox.warning(self, "Duplicate Item Code",
                                    f'Item Code "{item_code}" already exists.')
                return

        pk = self.all_data[idx][16]   # hidden PK stored at index 16

        try:
            update_item(
                item_id=pk,
                code=item_code,
                name=name,
                brand_id=None,       # ← wire to dropdown later
                filter_id=None,
                prty_id=None,
                stkr_id=None,
                sgdr_id=None,
                warehouse=warehouse or None,
                pnpr=part_no or None,
                inc1=interchange_1,
                inc2=interchange_2,
                inc3=interchange_3,
                inc4=interchange_4,
                inc5=None, inc6=None, inc7=None, inc8=None,
                quantity=qty,
                unit=uom,
                user=CURRENT_USER,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Database Error", f"Failed to update item:\n{exc}")
            return

        self.load_data()

    # ──────────────────────────────────────────

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        item_code = self.all_data[idx][0]
        name      = self.all_data[idx][1]
        pk        = self.all_data[idx][16]

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete\n"{item_code} – {name}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            try:
                delete_item(pk, user=CURRENT_USER)
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Failed to delete item:\n{exc}")
                return
            self.load_data()