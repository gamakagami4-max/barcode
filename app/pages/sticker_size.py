from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal

DPI = 96

# Row tuple shape:
# (NAME, HEIGHT_IN, WIDTH_IN, HEIGHT_PX, WIDTH_PX, ADDED_BY, ADDED_AT, CHANGED_BY, CHANGED_AT, CHANGED_NO)
VIEW_DETAIL_FIELDS = [
    ("Name",           0),
    ("Height (inch)",  1),
    ("Width (inch)",   2),
    ("Height (pixel)", 3),
    ("Width (pixel)",  4),
    ("Added By",       5),
    ("Added At",       6),
    ("Changed By",     7),
    ("Changed At",     8),
    ("Changed No",     9),
]


def _build_form_schema(mode: str = "add") -> list[dict]:
    """
    Returns the form schema for add or edit mode.
    In edit mode the 5 audit fields are appended as readonly.
    dimension_pair renders inch + px side-by-side with live conversion.
    """
    schema = [
        {
            "name": "name",
            "label": "Sticker Name",
            "type": "text",
            "placeholder": "Enter sticker name",
            "required": True,
        },
        {
            "name": "height",
            "label": "Height",
            "type": "dimension_pair",
            "dpi": DPI,
            "required": True,
        },
        {
            "name": "width",
            "label": "Width",
            "type": "dimension_pair",
            "dpi": DPI,
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


class StickerSizePage(QWidget):
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
        self.init_ui()
        self.load_sample_data()

    def init_ui(self):
        self.setStyleSheet("background-color: #F8FAFC;")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        # 1. Header
        enabled = ["Add", "Excel", "Refresh", "View Detail"]
        self.header = StandardPageHeader(
            title="Sticker Size",
            subtitle="Define physical dimensions for barcode stickers.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        # 2. Search
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. Table
        self.table_comp = StandardTable([
            "NAME", "HEIGHT (INCH)", "WIDTH (INCH)",
            "HEIGHT (PIXEL)", "WIDTH (PIXEL)",
            "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table

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

        # Selection-dependent buttons
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)
        self._update_selection_dependent_state(False)

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
    # Data
    # ------------------------------------------------------------------

    def load_sample_data(self):
        self.all_data = [
            ("A - Small Square",     "1.0000", "1.0000", "96",  "96",  "Admin", "2024-01-15", "-", "-", "0"),
            ("B - Medium Rectangle", "2.0000", "3.0000", "192", "288", "John",  "2024-02-20", "-", "-", "1"),
            ("C - Large Label",      "3.5000", "5.0000", "336", "480", "Sarah", "2024-03-10", "-", "-", "2"),
            ("D - Tiny Sticker",     "0.5000", "0.5000", "48",  "48",  "Admin", "2024-01-05", "-", "-", "3"),
            ("E - Wide Banner",      "1.5000", "6.0000", "144", "576", "Mike",  "2024-04-12", "-", "-", "4"),
            ("F - Tall Label",       "4.0000", "2.0000", "384", "192", "John",  "2024-02-28", "-", "-", "5"),
            ("G - Standard",         "2.5000", "2.5000", "240", "240", "Sarah", "2024-03-15", "-", "-", "6"),
            ("H - Mini",             "0.7500", "1.2500", "72",  "120", "Admin", "2024-01-20", "-", "-", "7"),
            ("I - Jumbo",            "5.0000", "7.0000", "480", "672", "Mike",  "2024-04-05", "-", "-", "8"),
            ("J - Custom A",         "1.2500", "3.7500", "120", "360", "John",  "2024-02-10", "-", "-", "9"),
        ]
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data or []
        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for item in page_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 28)
            for col, val in enumerate(item):
                self.table.setItem(row, col, QTableWidgetItem(str(val)))

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
        col_index = header_to_index.get(self._last_filter_type, 0)

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
    # Sorting
    # ------------------------------------------------------------------

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
        if idx >= len(row):
            return (1, "")
        val = row[idx]
        str_val = "" if val is None else str(val).replace(',', '').strip()
        try:
            return (0, float(str_val))
        except (ValueError, AttributeError):
            return (1, str_val.lower())

    # ------------------------------------------------------------------
    # Header wiring
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
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_dimension(in_val, px_val):
        """
        Given inch string and px string from dimension_pair, return
        (h_in: float, h_px: int).  Derives whichever is missing.
        Raises ValueError if both are empty/invalid.
        """
        try:
            h_in = float(in_val)
            h_px = int(round(h_in * DPI)) if not px_val else int(px_val)
        except (ValueError, TypeError):
            try:
                h_px = int(px_val)
                h_in = h_px / DPI
            except (ValueError, TypeError):
                raise ValueError("Invalid dimension")
        return h_in, h_px

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Sticker Size",
            fields=_build_form_schema(mode="add"),
            parent=self,
            mode="add",
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        import datetime

        name = data.get("name", "").strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Sticker name is required.")
            return

        for row in self.all_data:
            if row[0].lower() == name.lower():
                QMessageBox.warning(self, "Duplicate Name", f'"{name}" already exists.')
                return

        try:
            h_in, h_px = self._parse_dimension(data.get("height_in"), data.get("height_px"))
            w_in, w_px = self._parse_dimension(data.get("width_in"),  data.get("width_px"))
            if h_in <= 0 or w_in <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Height and Width must be positive numbers.")
            return

        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.all_data.insert(0, (
            name,
            f"{h_in:.4f}", f"{w_in:.4f}",
            str(h_px), str(w_px),
            "Admin", now, "-", "-", "0",
        ))
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        import openpyxl
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel File", "sticker_size.xlsx", "Excel Files (*.xlsx)"
        )
        if not path:
            return

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sticker Size"
        ws.append(["NAME", "HEIGHT (INCH)", "WIDTH (INCH)", "HEIGHT (PIXEL)", "WIDTH (PIXEL)",
                   "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"])
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
            title="Sticker Size Detail",
            subtitle="Full details for the selected sticker size.",
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
            "name":       row[0],
            # dimension_pair reads {name}_in and {name}_px
            "height_in":  row[1],
            "height_px":  row[3],
            "width_in":   row[2],
            "width_px":   row[4],
            # audit (readonly)
            "added_by":   row[5],
            "added_at":   row[6],
            "changed_by": row[7],
            "changed_at": row[8],
            "changed_no": row[9],
        }

        modal = GenericFormModal(
            title="Edit Sticker Size",
            fields=_build_form_schema(mode="edit"),
            parent=self,
            mode="edit",
            initial_data=initial,
        )
        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()

    def _on_edit_submitted(self, idx, data):
        import datetime

        name = data.get("name", "").strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Sticker name is required.")
            return

        for i, row in enumerate(self.all_data):
            if i != idx and row[0].lower() == name.lower():
                QMessageBox.warning(self, "Duplicate Name", f'"{name}" already exists.')
                return

        try:
            h_in, h_px = self._parse_dimension(data.get("height_in"), data.get("height_px"))
            w_in, w_px = self._parse_dimension(data.get("width_in"),  data.get("width_px"))
            if h_in <= 0 or w_in <= 0:
                raise ValueError
        except ValueError:
            QMessageBox.warning(self, "Validation Error", "Height and Width must be positive numbers.")
            return

        old_row = self.all_data[idx]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        changed_no = str(int(old_row[9]) + 1) if str(old_row[9]).isdigit() else "1"

        self.all_data[idx] = (
            name,
            f"{h_in:.4f}", f"{w_in:.4f}",
            str(h_px), str(w_px),
            old_row[5], old_row[6],   # added_by, added_at unchanged
            "Admin", now, changed_no,
        )
        self._apply_filter_and_reset_page()

    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return
        name = self.all_data[idx][0]
        msg = QMessageBox(self)
        msg.setWindowTitle("Confirm Delete")
        msg.setText(f'Are you sure you want to delete "{name}"?')
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.Cancel)
        msg.setDefaultButton(QMessageBox.Cancel)
        msg.setIcon(QMessageBox.Warning)
        if msg.exec() == QMessageBox.Yes:
            del self.all_data[idx]
            self._apply_filter_and_reset_page()