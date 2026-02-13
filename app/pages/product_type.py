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

# --- Design Tokens ---
COLORS = {
    "bg_main": "#F8FAFC",
    "link": "#6366F1",  # Indigo link color
}

class ProductTypePage(QWidget):
    def __init__(self):
        super().__init__()
        self.all_data = []
        self.filtered_data = []
        self.current_page = 0
        self.page_size = 25
        self.available_page_sizes = [25, 50, 100]
        self._last_filter_type = "INGGRIS"
        self._last_search_text = ""
        self._sort_fields = []
        self._sort_directions = {}
        self.init_ui()
        self.load_translations()

    def init_ui(self):
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(40, 20, 40, 12)
        self.main_layout.setSpacing(0)
        enabled = ["Add", "Excel", "Refresh"]

        self.header = StandardPageHeader(
            title="Product Type",
            subtitle="Manage multilingual labels for your product catalog.",
            enabled_actions=enabled
        )
        self.main_layout.addWidget(self.header)
        self.main_layout.addSpacing(12)
        self._connect_header_actions()

        self.search_bar = StandardSearchBar()
        self.search_bar.searchChanged.connect(self.filter_table)
        self.main_layout.addWidget(self.search_bar)
        self.main_layout.addSpacing(5)

        self.table_comp = StandardTable([
            "INGGRIS", "SPANYOL", "PRANCIS", "JERMAN", "ADDED BY", "ADDED AT", "CHANGED BY", "CHANGED AT", "CHANGED NO"
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

        # Form schema for Add/Edit modal
        self.form_schema = [
            {
                "name": "inggris", 
                "label": "English (Inggris)", 
                "type": "text", 
                "placeholder": "Enter English translation", 
                "required": True
            },
            {
                "name": "spanyol", 
                "label": "Spanish (Spanyol)", 
                "type": "text", 
                "placeholder": "Enter Spanish translation", 
                "required": False
            },
            {
                "name": "prancis", 
                "label": "French (Prancis)", 
                "type": "text", 
                "placeholder": "Enter French translation", 
                "required": False
            },
            {
                "name": "jerman", 
                "label": "German (Jerman)", 
                "type": "text", 
                "placeholder": "Enter German translation", 
                "required": False
            },
        ]

    def load_translations(self):
        raw_data = [
            ("Adapter", "Adaptador", "Adaptateur", "Einbauteil", "Admin", "2024-01-15", "-", "-", "0"),
            ("Air Breather", "Respiradero", "Filtre air", "Be-Entlüftungsfilter", "Admin", "2024-01-20", "User_A", "2024-02-05", "1"),
            ("Air Cleaner", "Filtro de aire", "Filtre air", "Luftfilter", "Admin", "2024-02-01", "-", "-", "0"),
            ("Air Dryer", "Secador de aire", "Dessiccateur", "Trockenmittelbox", "Manager_X", "2024-02-10", "-", "-", "0"),
            ("Air Filter", "Filtro de aire", "Filtre air", "Luftfilter", "Admin", "2024-02-15", "Admin", "2024-02-20", "2"),
        ]
        self.all_data = raw_data * 6
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
            
            # Render all columns from the data
            for c in range(len(row_data)):
                val = row_data[c] if c < len(row_data) else "-"
                item = QTableWidgetItem(str(val))
                if c == 0:  # INGGRIS link color
                    item.setForeground(QColor(COLORS["link"]))
                    font = item.font()
                    item.setFont(font)
                self.table.setItem(r, c, item)

        # Row numbers
        for r in range(len(page_data)):
            self.table.setVerticalHeaderItem(r, QTableWidgetItem(str(start_idx + r + 1)))

        # No setSortingEnabled(True) here! Sorting is manual
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

    def _apply_filter_and_reset_page(self):
        query = (self._last_search_text or "").lower().strip()
        headers = self.table_comp.headers()
        header_to_index = {h: i for i, h in enumerate(headers)}
        col_index = header_to_index.get(self._last_filter_type, 0)

        if not query:
            self.filtered_data = list(self.all_data)
        else:
            out = []
            for row in self.all_data:
                val = "" if col_index >= len(row) or row[col_index] is None else str(row[col_index])
                if query in val.lower():
                    out.append(row)
            self.filtered_data = out

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
            direction = self._sort_directions.get(field, "asc")
            reverse = (direction == "desc")
            idx = header_to_index.get(field)
            if idx is None:
                continue
            self.filtered_data.sort(key=lambda row, i=idx: self._get_sort_value(row, i), reverse=reverse)

    def _get_sort_value(self, row, idx):
        val = row[idx] if idx < len(row) else ""
        str_val = "" if val is None else str(val)
        numeric_cols = ["CHANGED NO"]
        if self.table_comp.headers()[idx] in numeric_cols:
            try:
                return float(str_val)
            except ValueError:
                return 0
        return str_val.lower()

    def on_page_changed(self, page_action: int):
        total = len(self.filtered_data)
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

    def on_page_size_changed(self, new_size: int):
        self.page_size = new_size
        self.current_page = 0
        self.render_page()

    def _connect_header_actions(self):
        """Connect header action buttons to their handlers."""
        for action in ["Refresh", "Add", "Excel", "Edit", "Delete"]:
            btn = self.header.get_action_button(action)
            if btn:
                if action == "Refresh":
                    btn.clicked.connect(self.load_translations)
                elif action == "Add":
                    btn.clicked.connect(self.handle_add_action)
                elif action == "Excel":
                    btn.clicked.connect(self.handle_export_action)
                elif action == "Edit":
                    btn.clicked.connect(self.handle_edit_action)
                elif action == "Delete":
                    btn.clicked.connect(self.handle_delete_action)

    def handle_add_action(self):
        """Open the Add Product Type Translation modal."""
        modal = GenericFormModal(
            title="Add Product Type Translation",
            fields=self.form_schema,
            parent=self,
            mode="add"
        )
        modal.formSubmitted.connect(self._on_add_submitted)
        modal.exec()

    def _on_add_submitted(self, data: dict):
        """Handle form submission for adding a new product type translation."""
        import datetime
        
        inggris = data.get("inggris", "").strip()
        spanyol = data.get("spanyol", "").strip()
        prancis = data.get("prancis", "").strip()
        jerman = data.get("jerman", "").strip()
        
        if not inggris:
            print("English translation is required")
            return
        
        added_by = "Admin"
        added_at = datetime.date.today().strftime("%Y-%m-%d")
        changed_by = "-"
        changed_at = "-"
        changed_no = "0"
        
        new_row = (
            inggris,
            spanyol,
            prancis,
            jerman,
            added_by,
            added_at,
            changed_by,
            changed_at,
            changed_no,
        )
        
        self.all_data.insert(0, new_row)
        self._apply_filter_and_reset_page()

    def handle_export_action(self):
        """Handle Excel export action."""
        print("Export to Excel clicked")

    def handle_edit_action(self):
        """Handle Edit action."""
        print("Edit clicked")

    def handle_delete_action(self):
        """Handle Delete action."""
        print("Delete clicked")