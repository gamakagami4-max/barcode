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

from server.repositories.mtitms_repo import (
    fetch_all_mtitms,
    create_mtitms,
    update_mtitms,
    soft_delete_mtitms,
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

# ─────────────────────────────────────────────
# Row tuple layout (index → field)
# ─────────────────────────────────────────────
# 0  pk
# 1  description
# 2  brand
# 3  warehouse
# 4  po_no  (Part No)
# 5  itc1
# 6  itc2
# 7  itc3
# 8  itc4
# 9  itc5
# 10 itc6
# 11 itc7
# 12 itc8
# 13 qty
# 14 uom
# 15 added_by
# 16 added_at
# 17 changed_by
# 18 changed_at
# 19 changed_no
# 20 pk  (hidden — used as a stable PK reference for DB ops)

# Mapping: (display label, index into the row tuple)
VIEW_DETAIL_FIELDS = [
    ("Item Code",     0),
    ("Name",          1),
    ("Brand",         2),
    ("Warehouse",     3),
    ("Part No Print",  4),
    ("Interchange 1", 5),
    ("Interchange 2", 6),
    ("Interchange 3", 7),
    ("Interchange 4", 8),
    ("Interchange 5", 9),
    ("Interchange 6", 10),
    ("Interchange 7", 11),
    ("Interchange 8", 12),
    ("Quantity",      13),
    ("UOM",          14),
    ("Added By",     15),
    ("Added At",     16),
    ("Changed By",   17),
    ("Changed At",   18),
    ("Changed No",   19),
]


def _build_form_schema(mode: str = "add") -> list[dict]:
    schema = [
        {
            "name": "item_code",
            "label": "Item Code",
            "type": "readonly" if mode == "edit" else "text",
            "placeholder": "e.g., EIF1-SFF1-FC-1001",
            "required": True,
            "max_length": 50,
        },
        {"name": "name",          "label": "Item Name",       "type": "text",  "placeholder": "Enter item description",  "required": True,  "max_length": 50},
        {"name": "warehouse",     "label": "Warehouse",       "type": "text",  "placeholder": "e.g., EIF",              "required": False, "max_length": 10},
        {"name": "part_no",       "label": "Part No Print",   "type": "text",  "placeholder": "Enter part number",       "required": False, "max_length": 15},
        {"name": "itc1",          "label": "Interchange 1",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc2",          "label": "Interchange 2",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc3",          "label": "Interchange 3",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc4",          "label": "Interchange 4",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc5",          "label": "Interchange 5",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc6",          "label": "Interchange 6",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc7",          "label": "Interchange 7",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
        {"name": "itc8",          "label": "Interchange 8",   "type": "text",  "placeholder": "Optional",               "required": False, "max_length": 50},
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
    def _fmt_dt(val):
        if val is None:
            return "-"
        return str(val)[:19]

    return (
        r.get("pk", ""),                # 0
        r.get("description", ""),       # 1
        r.get("brand", ""),             # 2
        r.get("warehouse", ""),         # 3
        r.get("po_no", ""),             # 4
        r.get("itc1", "") or "",        # 5
        r.get("itc2", "") or "",        # 6
        r.get("itc3", "") or "",        # 7
        r.get("itc4", "") or "",        # 8
        r.get("itc5", "") or "",        # 9
        r.get("itc6", "") or "",        # 10
        r.get("itc7", "") or "",        # 11
        r.get("itc8", "") or "",        # 12
        str(r.get("qty", 0)),           # 13
        r.get("uom", ""),               # 14
        r.get("added_by", "-"),         # 15
        _fmt_dt(r.get("added_at")),     # 16
        r.get("changed_by") or "-",     # 17
        _fmt_dt(r.get("changed_at")),   # 18
        str(r.get("changed_no", 0)),    # 19
        r.get("pk"),                    # 20  ← hidden PK
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
            "ITEM CODE", "NAME", "BRAND", "WHS", "PART NO PRINT",
            "INTERCHANGE 1", "INTERCHANGE 2", "INTERCHANGE 3", "INTERCHANGE 4",
            "INTERCHANGE 5", "INTERCHANGE 6", "INTERCHANGE 7", "INTERCHANGE 8",
            "QTY", "UOM",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ]
        self.table_comp = StandardTable(headers)
        self.table = self.table_comp.table

        h_header = self.table.horizontalHeader()
        h_header.setSectionResizeMode(QHeaderView.Interactive)
        self.table.setColumnWidth(0,  160)   # ITEM CODE
        h_header.setSectionResizeMode(1, QHeaderView.Stretch)  # NAME
        self.table.setColumnWidth(2,  90)    # BRAND
        self.table.setColumnWidth(3,  80)    # WHS
        self.table.setColumnWidth(4,  130)   # PART NO
        for itc_col in range(5, 13):         # ITC 1–8
            self.table.setColumnWidth(itc_col, 120)
        self.table.setColumnWidth(13, 60)    # QTY
        self.table.setColumnWidth(14, 60)    # UOM
        self.table.setColumnWidth(15, 100)   # ADDED BY
        h_header.setSectionResizeMode(16, QHeaderView.ResizeToContents)  # ADDED AT
        self.table.setColumnWidth(17, 100)   # CHANGED BY
        h_header.setSectionResizeMode(18, QHeaderView.ResizeToContents)  # CHANGED AT
        self.table.setColumnWidth(19, 80)    # CHANGED NO
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
            ("Interchange 5", data[9]),
            ("Interchange 6", data[10]),
            ("Interchange 7", data[11]),
            ("Interchange 8", data[12]),
            ("Stock",         f"{data[13]} {data[14]}"),
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
    # Data loading
    # ──────────────────────────────────────────

    def load_data(self):
        try:
            rows = fetch_all_mtitms()
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

        # Visible table columns:
        # ITEM CODE(0), NAME(1), BRAND(2), WHS(3), PART NO(4),
        # ITC1(5)–ITC8(12), QTY(13), UOM(14),
        # ADDED BY(15), ADDED AT(16), CHANGED BY(17), CHANGED AT(18), CHANGED NO(19)
        display_indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19]

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
        item_code = data.get("item_code", "").strip()
        name      = data.get("name",      "").strip()
        warehouse = data.get("warehouse", "").strip()
        part_no   = data.get("part_no",   "").strip()
        itc1      = data.get("itc1", "").strip() or None
        itc2      = data.get("itc2", "").strip() or None
        itc3      = data.get("itc3", "").strip() or None
        itc4      = data.get("itc4", "").strip() or None
        itc5      = data.get("itc5", "").strip() or None
        itc6      = data.get("itc6", "").strip() or None
        itc7      = data.get("itc7", "").strip() or None
        itc8      = data.get("itc8", "").strip() or None
        qty_str   = data.get("qty", "0").strip()
        uom       = data.get("uom", "PCS")

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
            create_mtitms(
                item_no=item_code,
                description=name,
                sap_code=None,
                warehouse=warehouse,
                part_no=part_no,
                itc1=itc1, itc2=itc2, itc3=itc3, itc4=itc4,
                itc5=itc5, itc6=itc6, itc7=itc7, itc8=itc8,
                qty=qty,
                uom=uom,
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
            "ITEM CODE", "NAME", "BRAND", "WAREHOUSE", "PART NO PRINT",
            "INTERCHANGE 1", "INTERCHANGE 2", "INTERCHANGE 3", "INTERCHANGE 4",
            "INTERCHANGE 5", "INTERCHANGE 6", "INTERCHANGE 7", "INTERCHANGE 8",
            "QTY", "UOM",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO",
        ])
        for row in self.filtered_data:
            ws.append([str(v) if v is not None else "" for v in row[:20]])
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
            "item_code":  row[0],
            "name":       row[1],
            "warehouse":  row[3],
            "part_no":    row[4],
            "itc1":       row[5],
            "itc2":       row[6],
            "itc3":       row[7],
            "itc4":       row[8],
            "itc5":       row[9],
            "itc6":       row[10],
            "itc7":       row[11],
            "itc8":       row[12],
            "qty":        row[13],
            "uom":        row[14],
            "added_by":   row[15],
            "added_at":   row[16],
            "changed_by": row[17],
            "changed_at": row[18],
            "changed_no": row[19],
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
        item_code = data.get("item_code", "").strip()
        name      = data.get("name",      "").strip()
        warehouse = data.get("warehouse", "").strip()
        part_no   = data.get("part_no",   "").strip()
        itc1      = data.get("itc1", "").strip() or None
        itc2      = data.get("itc2", "").strip() or None
        itc3      = data.get("itc3", "").strip() or None
        itc4      = data.get("itc4", "").strip() or None
        itc5      = data.get("itc5", "").strip() or None
        itc6      = data.get("itc6", "").strip() or None
        itc7      = data.get("itc7", "").strip() or None
        itc8      = data.get("itc8", "").strip() or None
        qty_str   = data.get("qty", "0").strip()
        uom       = data.get("uom", "PCS")

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

        pk = self.all_data[idx][20]   # hidden PK at index 20

        try:
            update_mtitms(
                pk=pk,
                description=name,
                warehouse=warehouse,
                part_no=part_no,
                itc1=itc1, itc2=itc2, itc3=itc3, itc4=itc4,
                itc5=itc5, itc6=itc6, itc7=itc7, itc8=itc8,
                qty=qty,
                uom=uom,
                old_changed_no=int(self.all_data[idx][19]),
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
        pk        = self.all_data[idx][20]   # hidden PK at index 20

        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete\n"{item_code} – {name}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)

        if msg.exec() == QMessageBox.Yes:
            try:
                soft_delete_mtitms(pk, user=CURRENT_USER)
            except Exception as exc:
                QMessageBox.critical(self, "Database Error", f"Failed to delete item:\n{exc}")
                return
            self.load_data()