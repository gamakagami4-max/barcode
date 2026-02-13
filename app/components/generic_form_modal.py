from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit,
    QComboBox, QDialogButtonBox, QFormLayout,
    QMessageBox, QHBoxLayout, QWidget
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# --------------------------------------------------
# Theme Colors
# --------------------------------------------------
COLORS = {
    "bg_main": "#F8FAFC",
    "text_primary": "#111827",
    "text_secondary": "#64748B",
    "border": "#E2E8F0",
    "link": "#6366F1",
}

# --------------------------------------------------
# Generic Modal
# --------------------------------------------------
class GenericFormModal(QDialog):
    """
    A fully generic modal dialog.
    
    Usage:
        fields = [
            {"name": "username", "label": "Username", "type": "text", "required": True},
            {"name": "role", "label": "Role", "type": "combo", "options": ["Admin", "User"], "required": True},
            {"name": "height", "label": "Height", "type": "text_with_unit", "units": ["inch", "px"], "default_unit": "inch", "required": True},
        ]
        modal = GenericFormModal("Create User", fields)
        modal.formSubmitted.connect(lambda data: print(data))
        modal.exec()
    """
    formSubmitted = Signal(dict)

    def __init__(self, title: str, fields: list, parent=None, mode="add", initial_data=None):
        super().__init__(parent)

        self.mode = mode
        self.fields_config = fields
        self.initial_data = initial_data or {}
        self.inputs = {}

        self.setWindowTitle(title)
        self.setMinimumWidth(500)
        self.setModal(True)
        self.setStyleSheet(f"background-color: {COLORS['bg_main']};")

        self._build_ui(title)
        self._populate_initial_data()

    # ------------------------------
    # Build UI
    # ------------------------------
    def _build_ui(self, title: str):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # Header
        header = QLabel(title)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        header.setFont(font)
        header.setStyleSheet(f"color: {COLORS['text_primary']};")
        main_layout.addWidget(header)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        for field in self.fields_config:
            widget = self._create_widget(field)
            self.inputs[field["name"]] = widget

            label = field.get("label", field["name"])
            if field.get("required"):
                label += " *"
            form_layout.addRow(label, widget)

        main_layout.addLayout(form_layout)
        main_layout.addStretch()

        # Buttons
        buttons = QDialogButtonBox()
        submit_text = "Create" if self.mode == "add" else "Save Changes"
        buttons.addButton(submit_text, QDialogButtonBox.AcceptRole)
        buttons.addButton("Cancel", QDialogButtonBox.RejectRole)

        buttons.accepted.connect(self._on_submit)
        buttons.rejected.connect(self.reject)

        buttons.setStyleSheet(f"""
            QPushButton {{
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 600;
                font-size: 13px;
                min-width: 100px;
            }}
            QPushButton[text="{submit_text}"] {{
                background-color: {COLORS['link']};
                color: white;
                border: none;
            }}
            QPushButton[text="Cancel"] {{
                background-color: white;
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
            }}
        """)

        main_layout.addWidget(buttons)

    # ------------------------------
    # Widget Factory
    # ------------------------------
    def _create_widget(self, field: dict):
        field_type = field.get("type", "text")
        widget = None

        if field_type == "text":
            widget = QLineEdit()
            widget.setPlaceholderText(field.get("placeholder", ""))
            self._style_input(widget)
            
        elif field_type in ("combo", "select"):
            widget = QComboBox()
            widget.addItems(field.get("options", []))
            self._style_input(widget)
            
        elif field_type == "text_with_unit":
            # Create a container widget with horizontal layout
            container = QWidget()
            h_layout = QHBoxLayout(container)
            h_layout.setContentsMargins(0, 0, 0, 0)
            h_layout.setSpacing(8)
            
            # Text input for the value
            text_input = QLineEdit()
            text_input.setPlaceholderText(field.get("placeholder", ""))
            self._style_input(text_input)
            
            # Dropdown for unit selection
            unit_combo = QComboBox()
            units = field.get("units", ["unit"])
            unit_combo.addItems(units)
            default_unit = field.get("default_unit")
            if default_unit and default_unit in units:
                unit_combo.setCurrentText(default_unit)
            unit_combo.setFixedWidth(80)
            self._style_input(unit_combo)
            
            # Add to layout
            h_layout.addWidget(text_input, stretch=1)
            h_layout.addWidget(unit_combo)
            
            # Store references to both widgets
            container.text_input = text_input
            container.unit_combo = unit_combo
            
            widget = container
            
        else:
            raise ValueError(f"Unsupported field type: {field_type}")

        return widget

    # ------------------------------
    # Styling
    # ------------------------------
    def _style_input(self, widget):
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
            }}
        """)

    # ------------------------------
    # Populate initial data
    # ------------------------------
    def _populate_initial_data(self):
        for name, widget in self.inputs.items():
            if name not in self.initial_data:
                continue
            value = self.initial_data[name]
            
            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif hasattr(widget, 'text_input'):  # text_with_unit type
                widget.text_input.setText(str(value))
                # Check if there's a corresponding unit value
                unit_key = f"{name}_unit"
                if unit_key in self.initial_data:
                    widget.unit_combo.setCurrentText(str(self.initial_data[unit_key]))

    # ------------------------------
    # Validation
    # ------------------------------
    def _validate(self):
        errors = []
        for field in self.fields_config:
            if not field.get("required"):
                continue
            
            widget = self.inputs[field["name"]]
            field_label = field.get('label', field['name'])
            
            if isinstance(widget, QLineEdit):
                if not widget.text().strip():
                    errors.append(f"{field_label} is required")
            elif isinstance(widget, QComboBox):
                if not widget.currentText():
                    errors.append(f"{field_label} is required")
            elif hasattr(widget, 'text_input'):  # text_with_unit type
                if not widget.text_input.text().strip():
                    errors.append(f"{field_label} is required")
                    
        return errors

    # ------------------------------
    # Collect Data
    # ------------------------------
    def _collect_data(self):
        data = {}
        for name, widget in self.inputs.items():
            if isinstance(widget, QLineEdit):
                data[name] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                data[name] = widget.currentText()
            elif hasattr(widget, 'text_input'):  # text_with_unit type
                data[name] = widget.text_input.text().strip()
                data[f"{name}_unit"] = widget.unit_combo.currentText()
                
        return data

    # ------------------------------
    # Submit Handler
    # ------------------------------
    def _on_submit(self):
        errors = self._validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        data = self._collect_data()
        self.formSubmitted.emit(data)
        self.accept()