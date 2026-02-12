from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSizePolicy, QComboBox, QStyle, QStyleOptionComboBox
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QPixmap, QPainter, QPen, QColor


# --- Modern SaaS Palette ---
DEFAULT_COLORS = {
    "text_table": "#0F172A",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "accent": "#6366F1",
    "hover": "#F8FAFC"
}


class ChevronComboBox(QComboBox):
    """Custom QComboBox with a chevron down arrow."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
    def paintEvent(self, event):
        # Call the default paint event first
        super().paintEvent(event)
        
        # Draw custom chevron
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get the drop-down button area
        opt = QStyleOptionComboBox()
        self.initStyleOption(opt)
        
        # Calculate chevron position (right side of the combo box)
        rect = self.rect()
        chevron_x = rect.width() - 18
        chevron_y = rect.height() // 2
        
        # Draw chevron (V shape pointing down)
        pen = QPen(QColor("#64748B"), 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        
        # Left line of chevron
        painter.drawLine(chevron_x, chevron_y - 2, chevron_x + 4, chevron_y + 2)
        # Right line of chevron
        painter.drawLine(chevron_x + 4, chevron_y + 2, chevron_x + 8, chevron_y - 2)
        
        painter.end()


class PaginationWidget(QWidget):
    pageChanged = Signal(int)
    pageSizeChanged = Signal(int)

    def __init__(self, colors=None):
        super().__init__()

        self.COLORS = colors or DEFAULT_COLORS

        # ========================
        # Main Layout
        # ========================
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 15, 0, 0)
        layout.setSpacing(10)

        # Info Label
        self.lbl_info = QLabel("Showing 0 to 0 of 0 entries")
        self.lbl_info.setStyleSheet(
            f"color:{self.COLORS['text_secondary']}; font-size:13px;"
        )

        # Page Size Selector
        self.page_size_combo = ChevronComboBox()
        self.page_size_combo.setFixedHeight(28)
        self.page_size_combo.setMinimumWidth(70)
        self.page_size_combo.currentTextChanged.connect(self._on_page_size_changed)
        
        combo_style = f"""
            QComboBox {{
                background: white;
                border: 1px solid {self.COLORS['border']};
                border-radius: 8px;
                font-size: 12px;
                color: {self.COLORS['text_table']};
                padding: 4px 10px;
                padding-right: 30px;
            }}
            QComboBox:hover {{
                background: white;
                border: 1px solid #CBD5E1;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 0px;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
            QComboBox QAbstractItemView {{
                background: white;
                border: 1px solid {self.COLORS['border']};
                border-radius: 10px;
                padding: 6px;
                selection-background-color: transparent;
                outline: none;
            }}
            QComboBox QAbstractItemView::item {{
                padding: 8px 12px;
                border-radius: 6px;
                color: {self.COLORS['text_table']};
                background: transparent;
                min-height: 24px;
            }}
            QComboBox QAbstractItemView::item:hover {{
                background: #F1F5F9;
            }}
            QComboBox QAbstractItemView::item:selected {{
                background: #EAF2FF;
                color: #2563EB;
                font-weight: 500;
            }}
        """
        self.page_size_combo.setStyleSheet(combo_style)

        # Nav Buttons
        self.btn_prev = QPushButton("Previous")
        self.btn_next = QPushButton("Next")

        self.btn_prev.setFixedSize(80, 32)
        self.btn_next.setFixedSize(80, 32)

        self.btn_prev.clicked.connect(lambda: self.pageChanged.emit(-1))
        self.btn_next.clicked.connect(lambda: self.pageChanged.emit(1))

        nav_style = f"""
            QPushButton {{
                background: white;
                border: 1px solid {self.COLORS['border']};
                border-radius: 6px;
                font-size: 12px;
                color: {self.COLORS['text_table']};
                padding:0px;
                margin:0px;
            }}
            QPushButton:hover:!disabled {{
                background: {self.COLORS['hover']};
                border: 1px solid #CBD5E1;
            }}
            QPushButton:disabled {{
                color: #CBD5E1;
                background: #F8FAFC;
                border: 1px solid {self.COLORS['border']};
            }}
        """

        self.btn_prev.setStyleSheet(nav_style)
        self.btn_next.setStyleSheet(nav_style)

        # ========================
        # Page Buttons Container
        # ========================
        self.page_buttons_layout = QHBoxLayout()
        self.page_buttons_layout.setSpacing(4)
        self.page_buttons_layout.setContentsMargins(0, 0, 0, 0)

        pages_container = QWidget()
        pages_container.setLayout(self.page_buttons_layout)
        pages_container.setSizePolicy(
            QSizePolicy.Minimum,
            QSizePolicy.Fixed
        )

        # Layout assembly
        layout.addWidget(self.lbl_info)
        layout.addStretch()
        layout.addWidget(self.page_size_combo)
        layout.addWidget(self.btn_prev)
        layout.addWidget(pages_container)
        layout.addWidget(self.btn_next)

    # ========================
    # PUBLIC API
    # ========================
    def update(self, start, end, total, has_prev, has_next, current_page, page_size, available_page_sizes=None):
        self.lbl_info.setText(
            f"Showing <b>{start}</b> to <b>{end}</b> of <b>{total}</b> entries"
        )

        self.btn_prev.setEnabled(has_prev)
        self.btn_next.setEnabled(has_next)

        # Update page size combo if available_page_sizes is provided
        if available_page_sizes is not None:
            self._update_page_size_options(available_page_sizes, page_size)

        total_pages = (total + page_size - 1) // page_size
        self._build_buttons(current_page, total_pages)

    # ========================
    # INTERNALS
    # ========================
    def _update_page_size_options(self, available_sizes, current_size):
        """Update the page size combo box with available options."""
        # Block signals to prevent triggering pageSizeChanged during update
        self.page_size_combo.blockSignals(True)
        
        current_text = str(current_size)
        needs_update = False
        
        # Check if we need to update the combo box items
        if self.page_size_combo.count() != len(available_sizes):
            needs_update = True
        else:
            for i, size in enumerate(available_sizes):
                if self.page_size_combo.itemText(i) != str(size):
                    needs_update = True
                    break
        
        if needs_update:
            self.page_size_combo.clear()
            for size in available_sizes:
                self.page_size_combo.addItem(str(size))
        
        # Set the current selection
        index = self.page_size_combo.findText(current_text)
        if index >= 0:
            self.page_size_combo.setCurrentIndex(index)
        
        self.page_size_combo.blockSignals(False)

    def _on_page_size_changed(self, text):
        """Handle page size selection change."""
        if text:
            try:
                new_size = int(text)
                self.pageSizeChanged.emit(new_size)
            except ValueError:
                pass

    def _build_buttons(self, current_page, total_pages, max_buttons=3):

        while self.page_buttons_layout.count():
            item = self.page_buttons_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if total_pages <= 0:
            return

        half = max_buttons // 2
        start = max(0, current_page - half)
        end = min(total_pages, start + max_buttons)

        if end - start < max_buttons:
            start = max(0, end - max_buttons)

        if start > 0:
            self._add_page_input()

        for i in range(start, end):
            self._add_page_button(i, current_page)

        if end < total_pages:
            self._add_page_input()

    # ------------------------
    def _add_page_button(self, page_index, current_page):

        btn = QPushButton(str(page_index + 1))
        btn.setFixedSize(28, 28)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        is_active = (page_index == current_page)

        if is_active:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {self.COLORS['accent']};
                    color: white;
                    border: 1px solid {self.COLORS['accent']};
                    border-radius: 6px;
                    font-weight: bold;
                    font-size: 11px;
                    padding:0px;
                    margin:0px;
                }}
            """)
        else:
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: white;
                    border: 1px solid {self.COLORS['border']};
                    border-radius: 6px;
                    color: {self.COLORS['text_table']};
                    font-size: 11px;
                    padding:0px;
                    margin:0px;
                }}
                QPushButton:hover {{
                    background: {self.COLORS['hover']};
                    border: 1px solid #CBD5E1;
                }}
            """)

        btn.clicked.connect(lambda _, p=page_index: self.pageChanged.emit(p))
        self.page_buttons_layout.addWidget(btn)

    # ------------------------
    def _add_page_input(self):

        edit = QLineEdit()
        edit.setPlaceholderText("…")
        edit.setAlignment(Qt.AlignCenter)
        edit.setFixedSize(28, 28)

        edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        edit.setTextMargins(0, 0, 0, 0)

        edit.setStyleSheet(f"""
            QLineEdit {{
                border: 1px solid {self.COLORS['border']};
                border-radius: 6px;
                font-size: 11px;
                background: white;
                color: {self.COLORS['text_secondary']};
                padding:0px;
                margin:0px;
            }}
            QLineEdit:focus {{
                border: 1px solid {self.COLORS['accent']};
                color: {self.COLORS['text_table']};
            }}
        """)

        def go_to_page():
            try:
                page = int(edit.text()) - 1
                if page >= 0:
                    self.pageChanged.emit(page)
                edit.clear()
                edit.clearFocus()
            except ValueError:
                edit.clear()

        edit.returnPressed.connect(go_to_page)
        self.page_buttons_layout.addWidget(edit)