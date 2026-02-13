from PySide6.QtWidgets import QWidget, QVBoxLayout, QTableWidgetItem
from PySide6.QtCore import Qt

from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.sort_by_widget import SortByWidget
from components.generic_form_modal import GenericFormModal

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
        enabled = ["Add", "Excel", "Refresh"]
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

        # 3. Table declared first so sort_bar can read its headers
        self.table_comp = StandardTable([
            "NAME", "HEIGHT (INCH)", "WIDTH (INCH)",
            "HEIGHT (PIXEL)", "WIDTH (PIXEL)", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
        ])
        self.table = self.table_comp.table

        # 4. Sort bar — sits above the table
        self.sort_bar = SortByWidget(self.table)

        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)

        # 5. Shared pagination from StandardTable
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)

        DPI = 96  # 1 inch = 96 pixels

        self.form_schema = [
            {"name": "name", "label": "Sticker Name", "type": "text", "placeholder": "Enter sticker name", "required": True},
            {
                "name": "height", 
                "label": "Height", 
                "type": "text_with_unit", 
                "placeholder": "Enter height", 
                "required": True,
                "units": ["inch", "px"],
                "default_unit": "inch"
            },
            {
                "name": "width", 
                "label": "Width", 
                "type": "text_with_unit", 
                "placeholder": "Enter width", 
                "required": True,
                "units": ["inch", "px"],
                "default_unit": "inch"
            },
        ]

        # Track table selection to enable Edit/Delete
        self.table.itemSelectionChanged.connect(self._on_row_selection_changed)

        # Initially disable edit/delete
        self._update_edit_delete_state(False)




    def _on_row_selection_changed(self):
        has_selection = bool(self.table.selectedItems())
        self._update_edit_delete_state(has_selection)

    def _update_edit_delete_state(self, enabled: bool):
        edit_btn = self.header.get_action_button("Edit")
        delete_btn = self.header.get_action_button("Delete")

        if edit_btn:
            edit_btn.setEnabled(enabled)
        if delete_btn:
            delete_btn.setEnabled(enabled)

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

    def load_sample_data(self):
        # Diverse test data to see sorting work
        raw_data = [
            ("A - Small Square", "1.0000", "1.0000", "96", "96", "Admin", "2024-01-15", "-", "-", "0"),
            ("B - Medium Rectangle", "2.0000", "3.0000", "192", "288", "John", "2024-02-20", "-", "-", "1"),
            ("C - Large Label", "3.5000", "5.0000", "336", "480", "Sarah", "2024-03-10", "-", "-", "2"),
            ("D - Tiny Sticker", "0.5000", "0.5000", "48", "48", "Admin", "2024-01-05", "-", "-", "3"),
            ("E - Wide Banner", "1.5000", "6.0000", "144", "576", "Mike", "2024-04-12", "-", "-", "4"),
            ("F - Tall Label", "4.0000", "2.0000", "384", "192", "John", "2024-02-28", "-", "-", "5"),
            ("G - Standard", "2.5000", "2.5000", "240", "240", "Sarah", "2024-03-15", "-", "-", "6"),
            ("H - Mini", "0.7500", "1.2500", "72", "120", "Admin", "2024-01-20", "-", "-", "7"),
            ("I - Jumbo", "5.0000", "7.0000", "480", "672", "Mike", "2024-04-05", "-", "-", "8"),
            ("J - Custom A", "1.2500", "3.7500", "120", "360", "John", "2024-02-10", "-", "-", "9"),
        ]
        self.all_data = raw_data
        self._apply_filter_and_reset_page()

    def render_page(self):
        # IMPORTANT: Keep sorting disabled - we handle sorting ourselves!
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data if self.filtered_data is not None else []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for item in page_data:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 28)

            # Now we can iterate through all columns since data matches headers
            for col in range(len(item)):
                self.table.setItem(row, col, QTableWidgetItem(item[col]))

        # Global row numbers (1-based across all pages)
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # DON'T re-enable sorting here - it will override our sort!
        # self.table.setSortingEnabled(True)  # ← REMOVED THIS LINE

        # Update pagination UI
        has_prev = self.current_page > 0
        has_next = end_idx < total
        start_human = 0 if total == 0 else start_idx + 1
        end_human = 0 if total == 0 else end_idx
        self.pagination.update(
            start=start_human,
            end=end_human,
            total=total,
            has_prev=has_prev,
            has_next=has_next,
            current_page=self.current_page,
            page_size=self.page_size,
            available_page_sizes=self.available_page_sizes,
        )

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}

        col_index = header_to_index.get(self._last_filter_type, 0)  # Default to 0 (NAME)

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            out = []
            for row in self.all_data:
                if col_index >= len(row):
                    continue

                val = "" if row[col_index] is None else str(row[col_index])

                if query in val.lower():
                    out.append(row)

            self.filtered_data = out

        self._apply_sort()
        self.current_page = 0
        self.render_page()


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
        """Handle page size change from pagination component."""
        self.page_size = new_size
        self.current_page = 0  # Reset to first page when changing page size
        self.render_page()

    def on_sort_changed(self, fields: list[str], field_directions: dict):
        """
        Handle sort changes from SortByWidget.
        
        Parameters
        ----------
        fields : list[str]
            Ordered list of field names to sort by (priority order)
        field_directions : dict
            Mapping of field name to direction ("asc" or "desc")
        """
        self._sort_fields = fields or []
        self._sort_directions = field_directions or {}
        self._apply_filter_and_reset_page()


    def _apply_sort(self):
        """Apply multi-field sorting with individual directions to filtered_data."""
        if not self._sort_fields or not self.filtered_data:
            return

        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}

        # Sort by each field in reverse priority order
        # This way the first field in _sort_fields has the highest priority
        for field in reversed(self._sort_fields):
            # Get the direction for THIS specific field
            direction = self._sort_directions.get(field, "asc")
            reverse = (direction == "desc")
            
            idx = header_to_index.get(field)
            if idx is None:
                continue
            
            # Important: capture idx in the lambda's default argument
            # to avoid late binding issues in the loop
            self.filtered_data.sort(
                key=lambda row, i=idx: self._get_sort_value(row, i),
                reverse=reverse
            )
    
    def _get_sort_value(self, row, idx):
        """Extract and normalize a sort value from a row at the given index."""
        if idx >= len(row):
            return ""
        
        val = row[idx]
        str_val = "" if val is None else str(val)
        
        # Try numeric conversion for better sorting
        try:
            return float(str_val.replace(',', '').replace('×', '').replace('INCH', '').strip())
        except (ValueError, AttributeError):
            return str_val.lower()
        
    def _connect_header_actions(self):
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete"]:
            btn = self.header.get_action_button(action)
            if btn:
                if action == "Refresh":
                    btn.clicked.connect(self.load_sample_data)
                elif action == "Add":
                    btn.clicked.connect(self.handle_add_action)
                elif action == "Excel":
                    btn.clicked.connect(self.handle_export_action)
                elif action == "Edit":
                    btn.clicked.connect(self.handle_edit_action)
                elif action == "Delete":
                    btn.clicked.connect(self.handle_delete_action)

    def handle_add_action(self):
        modal = GenericFormModal(
            title="Add Sticker Size",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()


    def _on_add_submitted(self, data: dict):
        DPI = 96  # 1 inch = 96 pixels
        
        name = data.get("name", "").strip()
        
        # Get height value and unit
        height_value = data.get("height", 0)
        height_unit = data.get("height_unit", "inch")
        
        # Get width value and unit
        width_value = data.get("width", 0)
        width_unit = data.get("width_unit", "inch")
        
        try:
            h_val = float(height_value)
            w_val = float(width_value)
            if h_val <= 0 or w_val <= 0:
                raise ValueError
        except ValueError:
            print("Height and Width must be positive numbers")
            return

        # Convert to inches if needed
        if height_unit == "px":
            h_in = h_val / DPI
            h_px = int(round(h_val))
        else:  # inch
            h_in = h_val
            h_px = int(round(h_val * DPI))
        
        if width_unit == "px":
            w_in = w_val / DPI
            w_px = int(round(w_val))
        else:  # inch
            w_in = w_val
            w_px = int(round(w_val * DPI))

        import datetime
        added_by = "Admin"
        added_at = datetime.date.today().isoformat()
        changed_by = "-"
        changed_at = "-"
        changed_no = "0"

        new_row = (
            name,
            f"{h_in:.4f}",  # Height in inches
            f"{w_in:.4f}",  # Width in inches
            str(h_px),      # Height in pixels
            str(w_px),      # Width in pixels
            added_by,
            added_at,
            changed_by,
            changed_at,
            changed_no,
        )

        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()





    def handle_export_action(self):
        print("Export clicked")

    def handle_edit_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        row = self.all_data[idx]

        modal = GenericFormModal(
            title="Edit Sticker Size",
            fields=self.form_schema,
            parent=self,
            mode="edit",
            initial_data={
                "name": row[0],
                "height": row[1],
                "height_unit": "inch",
                "width": row[2],
                "width_unit": "inch",
            }
        )

        modal.formSubmitted.connect(lambda data, i=idx: self._on_edit_submitted(i, data))
        modal.exec()


    def _on_edit_submitted(self, idx, data):
        DPI = 96

        name = data.get("name", "").strip()

        height_value = data.get("height", 0)
        height_unit = data.get("height_unit", "inch")

        width_value = data.get("width", 0)
        width_unit = data.get("width_unit", "inch")

        try:
            h_val = float(height_value)
            w_val = float(width_value)
            if h_val <= 0 or w_val <= 0:
                raise ValueError
        except ValueError:
            print("Height and Width must be positive numbers")
            return

        if height_unit == "px":
            h_in = h_val / DPI
            h_px = int(round(h_val))
        else:
            h_in = h_val
            h_px = int(round(h_val * DPI))

        if width_unit == "px":
            w_in = w_val / DPI
            w_px = int(round(w_val))
        else:
            w_in = w_val
            w_px = int(round(w_val * DPI))

        import datetime
        today = datetime.date.today().isoformat()

        old_row = self.all_data[idx]

        updated_row = (
            name,
            f"{h_in:.4f}",
            f"{w_in:.4f}",
            str(h_px),
            str(w_px),
            old_row[5],   # added_by
            old_row[6],   # added_at
            "Admin",      # changed_by
            today,        # changed_at
            str(int(old_row[9]) + 1 if old_row[9].isdigit() else 1),
        )

        self.all_data[idx] = updated_row
        self._apply_filter_and_reset_page()



    def handle_delete_action(self):
        idx = self._get_selected_global_index()
        if idx is None:
            return

        del self.all_data[idx]
        self._apply_filter_and_reset_page()
