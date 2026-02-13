import qtawesome as qta
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QTableWidgetItem, QHeaderView, 
    QHBoxLayout, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontMetrics
from datetime import datetime

# Local Imports 
from components.search_bar import StandardSearchBar
from components.standard_page_header import StandardPageHeader
from components.standard_table import StandardTable
from components.standard_button import StandardButton
from components.sort_by_widget import SortByWidget
from components.barcode_modal import BarcodeFormModal

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",
    "status_green_bg": "#DCFCE7",
    "status_green_text": "#166534",
    "status_gray_bg": "#F1F5F9",
    "status_gray_text": "#475569",
    "border": "#E2E8F0"
}

class BarcodeListPage(QWidget):
    # Signal to request navigation to editor page
    navigate_to_editor = Signal()
    
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
        self.selected_row_data = None  # Track selected row
        self.barcode_counter = 3120  # Counter for generating new barcode IDs
        self.current_user = "YOSAFAT.YACOB"  # Current logged-in user
        self.init_ui()
        self.load_data()

    # -----------------------
    # Text wrapping helpers
    # -----------------------
    def _wrap_text(self, text: str, max_chars: int) -> str:
        """
        Wrap text using \\n at word boundaries up to max_chars per line.
        This avoids Qt's visual eliding ("...") when columns are constrained.
        """
        s = "" if text is None else str(text)
        s = " ".join(s.split())  # normalize whitespace
        if max_chars <= 0 or len(s) <= max_chars:
            return s

        words = s.split(" ")
        lines: list[str] = []
        current = ""
        for w in words:
            if not current:
                current = w
                continue
            if len(current) + 1 + len(w) <= max_chars:
                current += " " + w
            else:
                lines.append(current)
                current = w
        if current:
            lines.append(current)
        return "\n".join(lines)

    def _row_line_count(self, row: int) -> int:
        max_lines = 1
        for c in range(self.table.columnCount()):
            it = self.table.item(row, c)
            if it is None:
                continue
            max_lines = max(max_lines, it.text().count("\n") + 1)
        return max_lines

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)

        # 1. Header - Initially only Edit and Delete are disabled
        enabled = ["Add", "Excel", "Refresh"]
        self.header = StandardPageHeader(
            title="Barcode Management",
            subtitle="Generate and manage enterprise-wide barcode assets.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        
        # --- Connect Header Buttons ---
        self.header.get_action_button("Refresh").clicked.connect(self.load_data)
        self.header.get_action_button("Add").clicked.connect(self.handle_add_action)
        self.header.get_action_button("Excel").clicked.connect(self.handle_export_action)
        self.header.get_action_button("Edit").clicked.connect(self.handle_edit_action)
        self.header.get_action_button("Delete").clicked.connect(self.handle_delete_action)
        # ------------------------------

        self.main_layout.addSpacing(12)

        # 2. Search Bar
        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        # 3. Standard Table Component (with standard audit columns)
        column_labels = ["CODE", "NAME", "STICKER SIZE", "STATUS", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"]
        self.table_comp = StandardTable(column_labels)
        self.table = self.table_comp.table
        
        # Connect row selection signal
        self.table.itemSelectionChanged.connect(self.on_row_selection_changed)
        
        header_obj = self.table.horizontalHeader()
        # Use interactive widths so we can cap columns (no infinite stretching)
        header_obj.setSectionResizeMode(QHeaderView.Interactive)
        header_obj.setSectionResizeMode(3, QHeaderView.Fixed)
        header_obj.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        header_obj.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header_obj.setSectionResizeMode(6, QHeaderView.Fixed)

        # Column width caps (pixels). Name is capped and wraps with \n.
        self.table.setColumnWidth(0, 140)  # CODE
        self.table.setColumnWidth(1, 360)  # NAME (max-ish; wraps)
        self.table.setColumnWidth(2, 140)  # STICKER SIZE
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(6, 120)
        
        # Sort bar — auto uses all current table columns
        self.sort_bar = SortByWidget(self.table)

        self.sort_bar.sortChanged.connect(self.on_sort_changed)
        self.main_layout.addWidget(self.sort_bar)
        self.main_layout.addSpacing(8)

        self.main_layout.addWidget(self.table_comp)
        self.main_layout.addSpacing(16)
        # 4. Hook into shared pagination from StandardTable (25 per page)
        self.pagination = self.table_comp.pagination
        self.pagination.pageChanged.connect(self.on_page_changed)
        self.pagination.pageSizeChanged.connect(self.on_page_size_changed)
        
        # Initialize default sort AFTER pagination is set up
        self.sort_bar.initialize_default_sort()

    def load_data(self):
        """Load initial data - in production this would fetch from a database"""
        # Start with some initial data
        initial_data = [
            ("ADR/BAR/3116", "SWI_NCC_424-16-111140SW_INNER_HYDRAULIC_60X45", "60 X 45 MM", "DISPLAY", "ACT", "02-Feb-2026", "ACT", "02-Feb-2026", "4", "ADS", "04-Feb-2026"),
            ("ADR/BAR/3116", "SWI_C_424-16-111140SW_INNER_HYDRAULIC_60X45", "60 X 45 MM", "DISPLAY", "ACT", "02-Feb-2026", "ACT", "02-Feb-2026", "4", "ADS", "04-Feb-2026"),
            ("ADR/BAR/3117", "[SAP] SAKURA INNER DIELECTRIC FLUIDS FILTER", "5 X 3 INCH", "DISPLAY", "JJH", "03-Feb-2026", "JJH", "03-Feb-2026", "9", "ADB", "10-Jul-2024"),
            ("ADR/BAR/3118", "P486182_HYDRAULIC_OUTER_(SAP)_ROTED", "7 X 2.5 INCH", "NOT DISPLAY", "ACT", "04-Feb-2026", "ACT", "05-Feb-2026", "17", "ACT", "04-Feb-2026"),
            ("ADR/BAR/3120", "TEST BARCODE", "4 X 2", "DISPLAY", "YOSAFAT.YACOB", "05-Feb-2026", "YOSAFAT.YACOB", "05-Feb-2026", "5", "-", "-"),
        ]
        
        # Only load initial data if all_data is empty
        if not self.all_data:
            self.all_data = list(initial_data) * 8
        
        self._apply_filter_and_reset_page()

    def render_page(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        data = self.filtered_data if self.filtered_data is not None else []

        total = len(data)
        start_idx = self.current_page * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_data = data[start_idx:end_idx]

        for r, row_data in enumerate(page_data):
            self.table.insertRow(r)
            # We'll set a dynamic row height after content is inserted.

            for c in range(3):
                raw = "" if row_data[c] is None else str(row_data[c])
                # Wrap long text using \n after a max length.
                if c == 1:  # NAME
                    txt = self._wrap_text(raw, max_chars=32)
                elif c == 0:  # CODE
                    txt = self._wrap_text(raw, max_chars=18)
                else:
                    txt = raw

                item = QTableWidgetItem(txt)
                if c == 0:
                    item.setForeground(QColor(COLORS["link"]))
                # Store the full row data in the first column item for easy retrieval
                if c == 0:
                    item.setData(Qt.UserRole, row_data)
                self.table.setItem(r, c, item)

            status_val = str(row_data[3])

            status_item = QTableWidgetItem(status_val)
            status_item.setTextAlignment(Qt.AlignCenter)

            # optional: keep colored text without badge
            if "NOT" in status_val:
                status_item.setForeground(QColor(COLORS["status_gray_text"]))
            else:
                status_item.setForeground(QColor(COLORS["status_green_text"]))

            self.table.setItem(r, 3, status_item)


            self.table.setItem(r, 4, QTableWidgetItem(str(row_data[4])))   # ADDED BY
            self.table.setItem(r, 5, QTableWidgetItem(str(row_data[5])))   # ADDED AT

            view_btn = QPushButton("View Detail")
            view_btn.setCursor(Qt.PointingHandCursor)
            view_btn.setFixedSize(95, 28)
            view_btn.setStyleSheet(f"""
                QPushButton {{
                    background: white; border: 1px solid {COLORS['border']};
                    border-radius: 6px; font-size: 11px; color: {COLORS['status_gray_text']};
                }}
                QPushButton:hover {{
                    background: {COLORS['bg_main']}; border-color: {COLORS['link']};
                    color: {COLORS['link']};
                }}
            """)
            view_btn.clicked.connect(lambda _, d=row_data: self.show_details(d))
            
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.addWidget(view_btn)
            btn_layout.setContentsMargins(0, 0, 0, 0)
            btn_layout.setAlignment(Qt.AlignCenter)
            self.table.setCellWidget(r, 6, btn_container)

            # Dynamic row height based on wrapped lines
            metrics = QFontMetrics(self.table.font())
            lines = self._row_line_count(r)
            base_padding = 12
            self.table.setRowHeight(r, max(28, lines * metrics.lineSpacing() + base_padding))

        # Global row numbers (1-based across all pages)
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # Keep native Qt header sorting disabled; all sorting is driven
        # by the SortByWidget and our manual _apply_sort implementation.
        self.table.setSortingEnabled(False)

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

    def on_row_selection_changed(self):
        """Handle row selection and update button states"""
        selected_rows = self.table.selectionModel().selectedRows()
        
        if selected_rows:
            # Get the row data from the first column's UserRole
            row = selected_rows[0].row()
            item = self.table.item(row, 0)
            if item:
                self.selected_row_data = item.data(Qt.UserRole)
                # Enable Edit and Delete buttons
                self.header.set_action_enabled("Edit", True)
                self.header.set_action_enabled("Delete", True)
        else:
            # No selection - disable Edit and Delete
            self.selected_row_data = None
            self.header.set_action_enabled("Edit", False)
            self.header.set_action_enabled("Delete", False)

    def show_details(self, data):
        details = f"""
        <div style='font-family: Segoe UI, sans-serif;'>
            <h3 style='color: {COLORS["link"]};'>Barcode Specifications</h3>
            <hr>
            <p><b>Code:</b> {data[0]}</p>
            <p><b>Name:</b> {data[1]}</p>
            <p><b>Sticker Size:</b> {data[2]}</p>
            <p><b>Status:</b> {data[3]}</p>
            <br>
            <p style='color: #64748B;'><b>Created:</b> {data[4]} on {data[5]}</p>
            <p style='color: #64748B;'><b>Modified:</b> {data[6]} on {data[7]} (Rev {data[8]})</p>
            <p style='color: #64748B;'><b>Last Print:</b> {data[9]} on {data[10]}</p>
        </div>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Item Details")
        msg.setTextFormat(Qt.RichText)
        msg.setText(details)
        msg.exec()

    def filter_table(self, filter_type, search_text):
        self._last_filter_type = filter_type
        self._last_search_text = search_text
        self._apply_filter_and_reset_page()

    def _apply_filter_and_reset_page(self) -> None:
        query = (self._last_search_text or "").lower().strip()

        headers = self.table_comp.headers()
        # Map headers directly to their 0-based column indices in the data tuples
        header_to_index = {h: i for i, h in enumerate(headers)}

        col_index = header_to_index.get(self._last_filter_type, 0)

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
        """
        PaginationWidget emits:
        -1 for Previous, 1 for Next, or a 0-based page index for direct jumps.
        """
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
            # direct page index
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
        # Map headers directly to their 0-based column indices in the data tuples
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
        """
        Normalize a value from the underlying data row for sorting.
        Handles numeric columns like CHANGED NO so that 10 > 2, not "10" < "2".
        """
        val = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val)

        numeric_cols = ["CHANGED NO"]
        header = self.table_comp.headers()[idx] if idx < len(self.table_comp.headers()) else ""

        if header in numeric_cols:
            try:
                return float(str_val.replace(",", ""))
            except ValueError:
                return 0

        return str_val.lower()

    # --- Header Action Handlers ---
    def handle_add_action(self):
        """Navigate to barcode editor page to create new barcode"""
        self.navigate_to_editor.emit()
    
    def on_barcode_added(self, form_data):
        """Handle the submission of a new barcode"""
        # Generate new barcode ID
        self.barcode_counter += 1
        new_code = f"ADR/BAR/{self.barcode_counter}"
        
        # Get current timestamp
        current_date = datetime.now().strftime("%d-%b-%Y")
        
        # Create new record tuple
        # (CODE, NAME, STICKER_SIZE, STATUS, ADDED_BY, ADDED_AT, CHANGED_BY, CHANGED_AT, CHANGED_NO, LAST_PRINT_BY, LAST_PRINT_AT)
        new_record = (
            new_code,
            form_data["name"],
            form_data["sticker_size"],
            form_data["status"],
            self.current_user,
            current_date,
            self.current_user,
            current_date,
            "1",  # Initial change number
            "-",  # No print yet
            "-"
        )
        
        # Add to beginning of data list
        self.all_data.insert(0, new_record)
        
        # Refresh the table
        self._apply_filter_and_reset_page()
        
        # Show success message
        QMessageBox.information(
            self,
            "Success",
            f"Barcode '{new_code}' has been created successfully!"
        )

    def handle_export_action(self):
        count = len(self.filtered_data)
        QMessageBox.information(self, "Export", f"Exporting {count} records to Excel...")

    def handle_edit_action(self):
        """Navigate to barcode editor page to edit the selected barcode"""
        if not self.selected_row_data:
            QMessageBox.warning(self, "Edit", "Please select a row to edit.")
            return
        
        # Emit signal to navigate to editor (editor will handle loading the barcode)
        self.navigate_to_editor.emit()
    
    def on_barcode_edited(self, form_data):
        """Handle the submission of edited barcode data"""
        if not self.selected_row_data:
            return
        
        # Find the record in all_data
        code_to_edit = self.selected_row_data[0]
        
        for i, record in enumerate(self.all_data):
            if record[0] == code_to_edit:
                # Get current timestamp
                current_date = datetime.now().strftime("%d-%b-%Y")
                
                # Increment change number
                try:
                    change_no = int(record[8]) + 1
                except (ValueError, IndexError):
                    change_no = 1
                
                # Create updated record
                # Keep original: CODE, ADDED_BY, ADDED_AT, LAST_PRINT_BY, LAST_PRINT_AT
                # Update: NAME, STICKER_SIZE, STATUS, CHANGED_BY, CHANGED_AT, CHANGED_NO
                updated_record = (
                    record[0],  # CODE (unchanged)
                    form_data["name"],  # NAME (updated)
                    form_data["sticker_size"],  # STICKER_SIZE (updated)
                    form_data["status"],  # STATUS (updated)
                    record[4],  # ADDED_BY (unchanged)
                    record[5],  # ADDED_AT (unchanged)
                    self.current_user,  # CHANGED_BY (updated)
                    current_date,  # CHANGED_AT (updated)
                    str(change_no),  # CHANGED_NO (incremented)
                    record[9],  # LAST_PRINT_BY (unchanged)
                    record[10]  # LAST_PRINT_AT (unchanged)
                )
                
                # Replace the record
                self.all_data[i] = updated_record
                
                # Update selected_row_data
                self.selected_row_data = updated_record
                
                break
        
        # Refresh the table
        self._apply_filter_and_reset_page()
        
        # Show success message
        QMessageBox.information(
            self,
            "Success",
            f"Barcode '{code_to_edit}' has been updated successfully!"
        )

    def handle_delete_action(self):
        """Delete the selected barcode after confirmation"""
        if not self.selected_row_data:
            QMessageBox.warning(self, "Delete", "Please select a row to delete.")
            return
        
        code_to_delete = self.selected_row_data[0]
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Delete Confirmation",
            f"Are you sure you want to delete barcode '{code_to_delete}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Find and remove the record
            self.all_data = [record for record in self.all_data if record[0] != code_to_delete]
            
            # Clear selection
            self.selected_row_data = None
            
            # Refresh the table
            self._apply_filter_and_reset_page()
            
            # Show success message
            QMessageBox.information(
                self,
                "Deleted",
                f"Barcode '{code_to_delete}' has been deleted successfully!"
            )