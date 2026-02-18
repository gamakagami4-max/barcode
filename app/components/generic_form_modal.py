"""
generic_modal.py
----------------
Unified modal component that handles both read-only detail view and form submission.

Usage — View mode (replaces ViewDetailModal):
----------------------------------------------
    from components.generic_modal import GenericModal

    fields = [
        ("Connection",  row[1]),
        ("Table Name",  row[2]),
        ("Added By",    row[4]),
    ]
    modal = GenericModal(
        title="Row Detail",
        subtitle="Full details for the selected record.",
        mode="view",
        fields=fields,
        parent=self,
    )
    modal.exec()


Usage — Form mode (replaces GenericFormModal):
----------------------------------------------
    from components.generic_modal import GenericModal

    schema = [
        {"name": "name",  "label": "Name",  "type": "text",  "required": True},
        {"name": "role",  "label": "Role",  "type": "combo", "options": ["Admin", "User"], "required": True},
        {"name": "height","label": "Height","type": "text_with_unit",
         "units": ["inch", "px"], "default_unit": "inch", "required": True},
    ]
    modal = GenericModal(
        title="Add Record",
        mode="add",          # or "edit"
        fields=schema,
        parent=self,
    )
    modal.formSubmitted.connect(lambda data: print(data))
    modal.exec()
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDialogButtonBox,
    QScrollArea, QFrame, QPushButton, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

# ------------------------------------------------------------------
# Shared design tokens
# ------------------------------------------------------------------
COLORS = {
    "bg_main":        "#F8FAFC",
    "text_primary":   "#111827",
    "text_secondary": "#64748B",
    "text_muted":     "#6B7280",
    "border":         "#E2E8F0",
    "border_light":   "#E5E7EB",
    "link":           "#6366F1",
    "field_bg":       "#F9FAFB",
    "white":          "#FFFFFF",
}



class GenericFormModal(QDialog):
    """
    Single modal component for both read-only detail view and editable forms.

    Parameters
    ----------
    title : str
        Heading shown at the top.
    subtitle : str
        Smaller descriptive line beneath the title (optional).
    mode : str
        One of ``"view"``, ``"add"``, or ``"edit"``.
        - ``"view"``  → read-only detail layout (fields are (label, value) tuples)
        - ``"add"``   → form with a "Create" submit button
        - ``"edit"``  → form with a "Save Changes" submit button
    fields : list
        - In **view** mode: ``list[tuple[str, str]]`` → ``[(label, value), ...]``
        - In **add/edit** mode: ``list[dict]`` → form schema dicts with keys:
            ``name``, ``label``, ``type`` (``"text"`` | ``"combo"`` | ``"text_with_unit"``),
            ``required``, ``options``, ``placeholder``, ``units``, ``default_unit``
    initial_data : dict
        Pre-populated values for add/edit mode (keyed by field ``name``).
    parent : QWidget | None
        Optional parent widget.
    min_width : int
        Minimum dialog width in pixels (default 560).
    """

    # Emitted only in add/edit mode when the form is successfully submitted
    formSubmitted = Signal(dict)

    def __init__(
        self,
        title: str = "Detail",
        subtitle: str = "",
        mode: str = "view",
        fields=None,
        initial_data: dict | None = None,
        parent=None,
        min_width: int = 560,
    ):
        super().__init__(parent)

        if mode not in ("view", "add", "edit"):
            raise ValueError(f"mode must be 'view', 'add', or 'edit', got {mode!r}")

        self.mode = mode
        self.fields_config = fields or []
        self.initial_data = initial_data or {}
        self.inputs: dict[str, QWidget] = {}

        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setModal(True)

        if mode == "view":
            # Frameless card style for view modal
            self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
            self.setAttribute(Qt.WA_TranslucentBackground, False)
            self.setStyleSheet(f"""
                QDialog {{
                    background-color: {COLORS['white']};
                    border: 1px solid {COLORS['border_light']};
                    border-radius: 10px;
                }}
            """)
        else:
            self.setStyleSheet(f"background-color: {COLORS['bg_main']};")

        self._build_ui(title, subtitle)

        if mode in ("add", "edit"):
            self._populate_initial_data()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, subtitle: str):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        text_block = QVBoxLayout()
        text_block.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size: 18px; font-weight: 700; color: {COLORS['text_primary']}; background: transparent;"
        )
        text_block.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(
                f"font-size: 13px; color: {COLORS['text_muted']}; background: transparent;"
            )
            text_block.addWidget(sub_lbl)

        header_row.addLayout(text_block)
        header_row.addStretch()

        # Close button only in view mode (form mode uses the Cancel button)
        if self.mode == "view":
            close_btn = QPushButton("✕")
            close_btn.setFixedSize(32, 32)
            close_btn.setCursor(Qt.PointingHandCursor)
            close_btn.setToolTip("Close")
            close_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['text_muted']};
                    border: none;
                    border-radius: 6px;
                    font-size: 14px;
                    font-weight: 600;
                }}
                QPushButton:hover {{
                    background-color: #F3F4F6;
                    color: {COLORS['text_primary']};
                }}
                QPushButton:pressed {{ background-color: {COLORS['border_light']}; }}
            """)
            close_btn.clicked.connect(self.reject)
            header_row.addWidget(close_btn, alignment=Qt.AlignTop)

        root.addLayout(header_row)
        root.addSpacing(20)

        # ── Divider ────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet(
            f"color: {COLORS['border_light']}; background-color: {COLORS['border_light']}; max-height: 1px;"
        )
        root.addWidget(divider)
        root.addSpacing(20)

        # ── Body ───────────────────────────────────────────────────────
        if self.mode == "view":
            self._build_view_body(root)
        else:
            self._build_form_body(root)

    # ------------------------------------------------------------------
    # View mode body
    # ------------------------------------------------------------------

    def _build_view_body(self, root: QVBoxLayout):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(480)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; }
            QScrollBar:vertical {
                background: transparent; width: 8px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #E5E7EB; border-radius: 4px; min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { background: #D1D5DB; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        fields_layout = QVBoxLayout(container)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(16)

        for label_text, value in self.fields_config:
            fields_layout.addWidget(self._make_view_field(label_text, value))

        fields_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)
        root.addSpacing(8)

    @staticmethod
    def _make_view_field(label_text: str, value: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text.upper())
        lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};"
            " letter-spacing: 0.05em; background: transparent;"
        )
        layout.addWidget(lbl)

        val = QLabel(value if value and value.strip() else "—")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        val.setStyleSheet(
            f"font-size: 13px; color: {COLORS['text_primary']}; background: {COLORS['field_bg']};"
            f" border: 1px solid {COLORS['border_light']}; border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(val)
        return wrapper

    # ------------------------------------------------------------------
    # Form mode body
    # ------------------------------------------------------------------

    def _build_form_body(self, root: QVBoxLayout):
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight)

        for field in self.fields_config:
            widget = self._create_form_widget(field)
            self.inputs[field["name"]] = widget

            label = field.get("label", field["name"])
            if field.get("required"):
                label += " *"
            form_layout.addRow(label, widget)

        root.addLayout(form_layout)
        root.addStretch()

        # Buttons
        submit_text = "Create" if self.mode == "add" else "Save Changes"
        buttons = QDialogButtonBox()
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
                background-color: {COLORS['white']};
                color: {COLORS['text_secondary']};
                border: 1px solid {COLORS['border']};
            }}
        """)
        root.addWidget(buttons)

    def _create_form_widget(self, field: dict) -> QWidget:
        field_type = field.get("type", "text")

        if field_type == "text":
            w = QLineEdit()
            w.setPlaceholderText(field.get("placeholder", ""))
            self._style_input(w)
            return w

        elif field_type in ("combo", "select"):
            w = QComboBox()
            w.addItems(field.get("options", []))
            self._style_input(w)
            return w

        elif field_type == "text_with_unit":
            container = QWidget()
            h = QHBoxLayout(container)
            h.setContentsMargins(0, 0, 0, 0)
            h.setSpacing(8)

            text_input = QLineEdit()
            text_input.setPlaceholderText(field.get("placeholder", ""))
            self._style_input(text_input)

            unit_combo = QComboBox()
            units = field.get("units", ["unit"])
            unit_combo.addItems(units)
            default_unit = field.get("default_unit")
            if default_unit and default_unit in units:
                unit_combo.setCurrentText(default_unit)
            unit_combo.setFixedWidth(80)
            self._style_input(unit_combo)

            h.addWidget(text_input, stretch=1)
            h.addWidget(unit_combo)

            container.text_input = text_input
            container.unit_combo = unit_combo
            return container

        else:
            raise ValueError(f"Unsupported field type: {field_type!r}")

    def _style_input(self, widget):
        widget.setMinimumHeight(36)
        widget.setStyleSheet(f"""
            QLineEdit, QComboBox {{
                padding: 8px 12px;
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                background-color: {COLORS['white']};
                color: {COLORS['text_primary']};
                font-size: 13px;
            }}
            QLineEdit:focus, QComboBox:focus {{
                border-color: {COLORS['link']};
            }}
        """)

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _populate_initial_data(self):
        for name, widget in self.inputs.items():
            if name not in self.initial_data:
                continue
            value = self.initial_data[name]

            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(str(value))
            elif hasattr(widget, "text_input"):
                widget.text_input.setText(str(value))
                unit_key = f"{name}_unit"
                if unit_key in self.initial_data:
                    widget.unit_combo.setCurrentText(str(self.initial_data[unit_key]))

    def _validate(self) -> list[str]:
        errors = []
        for field in self.fields_config:
            if not field.get("required"):
                continue
            widget = self.inputs[field["name"]]
            label = field.get("label", field["name"])

            if isinstance(widget, QLineEdit):
                if not widget.text().strip():
                    errors.append(f"{label} is required")
            elif isinstance(widget, QComboBox):
                if not widget.currentText():
                    errors.append(f"{label} is required")
            elif hasattr(widget, "text_input"):
                if not widget.text_input.text().strip():
                    errors.append(f"{label} is required")
        return errors

    def _collect_data(self) -> dict:
        data = {}
        for name, widget in self.inputs.items():
            if isinstance(widget, QLineEdit):
                data[name] = widget.text().strip()
            elif isinstance(widget, QComboBox):
                data[name] = widget.currentText()
            elif hasattr(widget, "text_input"):
                data[name] = widget.text_input.text().strip()
                data[f"{name}_unit"] = widget.unit_combo.currentText()
        return data

    def _on_submit(self):
        errors = self._validate()
        if errors:
            QMessageBox.warning(self, "Validation Error", "\n".join(errors))
            return
        self.formSubmitted.emit(self._collect_data())
        self.accept()