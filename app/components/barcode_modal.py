from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QComboBox, QDialogButtonBox, QFormLayout,
    QWidget, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

COLORS = {
    "bg_main": "#F8FAFC",
    "text_primary": "#111827",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "link": "#6366F1",
}


class BarcodeFormModal(QDialog):
    """
    Reusable modal dialog for adding or editing barcode records.
    Can be used across different pages that manage barcode data.
    """
    
    # Signal emitted when form is successfully submitted
    # Emits a dict with all form data
    formSubmitted = Signal(dict)
    
    def __init__(self, parent=None, mode="add", initial_data=None):
        """
        Initialize the barcode form modal.
        
        :param parent: Parent widget
        :param mode: "add" for creating new records, "edit" for editing existing ones
        :param initial_data: Dict with initial values for edit mode
        """
        super().__init__(parent)
        self.mode = mode
        self.initial_data = initial_data or {}
        
        self.setup_ui()
        self.populate_form()
        
    def setup_ui(self):
        """Set up the dialog UI"""
        # Window properties
        title = "Add New Barcode" if self.mode == "add" else "Edit Barcode"
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(500)
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # Header
        header_label = QLabel(title)
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setStyleSheet(f"color: {COLORS['text_primary']};")
        main_layout.addWidget(header_label)
        
        # Subtitle
        subtitle = "Fill in the details below to create a new barcode record." if self.mode == "add" else "Update the barcode information below."
        subtitle_label = QLabel(subtitle)
        subtitle_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 13px;")
        subtitle_label.setWordWrap(True)
        main_layout.addWidget(subtitle_label)
        
        # Form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)
        
        # Name field
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter barcode name")
        self._style_input(self.name_input)
        form_layout.addRow("Name:*", self.name_input)
        
        # Sticker Size dropdown
        self.size_combo = QComboBox()
        self.size_combo.addItems([
            "4 X 2",
            "5 X 3 INCH",
            "7 X 2.5 INCH",
            "60 X 45 MM",
            "Custom"
        ])
        self._style_input(self.size_combo)
        form_layout.addRow("Sticker Size:*", self.size_combo)
        
        # Custom size field (hidden by default)
        self.custom_size_input = QLineEdit()
        self.custom_size_input.setPlaceholderText("Enter custom size (e.g., 10 X 5 CM)")
        self.custom_size_input.setVisible(False)
        self._style_input(self.custom_size_input)
        form_layout.addRow("", self.custom_size_input)
        
        # Status dropdown
        self.status_combo = QComboBox()
        self.status_combo.addItems(["DISPLAY", "NOT DISPLAY"])
        self._style_input(self.status_combo)
        form_layout.addRow("Status:*", self.status_combo)
        
        # Connect custom size visibility
        self.size_combo.currentTextChanged.connect(self._on_size_changed)
        
        main_layout.addLayout(form_layout)
        
        # Required field note
        required_note = QLabel("* Required fields")
        required_note.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: 11px; font-style: italic;")
        main_layout.addWidget(required_note)
        
        # Spacer
        main_layout.addStretch()
        
        # Dialog buttons
        button_box = QDialogButtonBox()
        
        if self.mode == "add":
            button_box.addButton("Create", QDialogButtonBox.AcceptRole)
        else:
            button_box.addButton("Save Changes", QDialogButtonBox.AcceptRole)
        
        button_box.addButton("Cancel", QDialogButtonBox.RejectRole)
        
        button_box.accepted.connect(self.on_submit)
        button_box.rejected.connect(self.reject)
        
        # Style the buttons
        button_box.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-width: 100px;
            }}
            QPushButton[text="Create"], QPushButton[text="Save Changes"] {{
                background-color: {COLORS['link']};
                color: white;
                border: none;
            }}
            QPushButton[text="Create"]:hover, QPushButton[text="Save Changes"]:hover {{
                background-color: #4F46E5;
            }}
            QPushButton[text="Cancel"] {{
                background-color: white;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
            }}
            QPushButton[text="Cancel"]:hover {{
                background-color: {COLORS['bg_main']};
            }}
        """)
        
        main_layout.addWidget(button_box)
    
    def _style_input(self, widget):
        """Apply consistent styling to input widgets"""
        widget.setMinimumHeight(36)
        widget.setStyleSheet(f"""
            QLineEdit, QComboBox {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                background-color: white;
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {COLORS['link']};
                outline: none;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iOCIgdmlld0JveD0iMCAwIDEyIDgiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxwYXRoIGQ9Ik0xIDFMNiA2TDExIDEiIHN0cm9rZT0iIzY0NzQ4QiIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
            }}
        """)
    
    def _on_size_changed(self, text):
        """Show/hide custom size input based on selection"""
        self.custom_size_input.setVisible(text == "Custom")
    
    def populate_form(self):
        """Populate form fields with initial data (for edit mode)"""
        if not self.initial_data:
            return
        
        self.name_input.setText(self.initial_data.get("name", ""))
        
        # Set sticker size
        size = self.initial_data.get("sticker_size", "")
        idx = self.size_combo.findText(size)
        if idx >= 0:
            self.size_combo.setCurrentIndex(idx)
        else:
            # Custom size
            self.size_combo.setCurrentText("Custom")
            self.custom_size_input.setText(size)
        
        # Set status
        status = self.initial_data.get("status", "DISPLAY")
        self.status_combo.setCurrentText(status)
    
    def validate_form(self):
        """Validate form inputs"""
        errors = []
        
        # Name is required
        if not self.name_input.text().strip():
            errors.append("Name is required")
        
        # Sticker size validation
        if self.size_combo.currentText() == "Custom":
            if not self.custom_size_input.text().strip():
                errors.append("Custom sticker size is required")
        
        return errors
    
    def get_form_data(self):
        """Collect all form data into a dictionary"""
        # Determine sticker size
        if self.size_combo.currentText() == "Custom":
            sticker_size = self.custom_size_input.text().strip()
        else:
            sticker_size = self.size_combo.currentText()
        
        return {
            "name": self.name_input.text().strip(),
            "sticker_size": sticker_size,
            "status": self.status_combo.currentText(),
        }
    
    def on_submit(self):
        """Handle form submission"""
        # Validate
        errors = self.validate_form()
        if errors:
            QMessageBox.warning(
                self,
                "Validation Error",
                "Please fix the following errors:\n\n" + "\n".join(f"• {e}" for e in errors)
            )
            return
        
        # Get form data
        form_data = self.get_form_data()
        
        # Emit signal with form data
        self.formSubmitted.emit(form_data)
        
        # Close dialog
        self.accept()