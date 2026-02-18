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

        # Read-only audit field — shown greyed out with a forbidden cursor
        {"name": "added_by", "label": "Added By", "type": "readonly"},

        # Cascading combo — selecting the first populates the second
        {
            "name": "conn", "label": "Connection", "type": "cascade_combo",
            "options": {"Server A": ["Table1", "Table2"], "Server B": ["Orders"]},
            "child": "table_name",          # name of the dependent field
        },
        {"name": "table_name", "label": "Table Name", "type": "combo", "options": []},

        # Dual inch+px inputs that live-convert each other (DPI=96 by default)
        {"name": "height", "label": "Height", "type": "dimension_pair", "dpi": 96, "required": True},
    ]
    modal = GenericModal(
        title="Add Record",
        mode="add",          # or "edit"
        fields=schema,
        parent=self,
    )
    modal.formSubmitted.connect(lambda data: print(data))
    modal.exec()
    # dimension_pair emits:  data["height_in"]  and  data["height_px"]
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QDialogButtonBox,
    QScrollArea, QFrame, QPushButton, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QCursor

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
    "readonly_bg":    "#F3F4F6",
    "readonly_text":  "#9CA3AF",
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
            ``name``, ``label``, ``type`` (``"text"`` | ``"combo"`` | ``"text_with_unit"``
            | ``"readonly"`` | ``"cascade_combo"`` | ``"dimension_pair"``),
            ``required``, ``options``, ``placeholder``, ``units``, ``default_unit``,
            ``child`` (for cascade_combo → name of dependent combo field),
            ``dpi`` (for dimension_pair, default 96)
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

        # Internal map: cascade_combo parent name → child field name
        self._cascade_map: dict[str, str] = {}
        # Internal map: cascade_combo parent name → {parent_option: [child_options]}
        self._cascade_options: dict[str, dict] = {}

        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        self.setModal(False)

        if mode == "view":
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

    def exec(self):
        """Override exec() to use show() so the main window stays fully interactive."""
        self.show()

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
        from PySide6.QtWidgets import QAbstractScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(460)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.verticalScrollBar().setSingleStep(12)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: transparent; width: 6px; margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB; border-radius: 3px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::handle:vertical:pressed { background: #6B7280; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")

        form_layout = QFormLayout(scroll_content)
        form_layout.setSpacing(12)
        form_layout.setContentsMargins(0, 0, 12, 0)
        form_layout.setLabelAlignment(Qt.AlignRight)

        for field in self.fields_config:
            widget = self._create_form_widget(field)
            self.inputs[field["name"]] = widget

            label = field.get("label", field["name"])
            if field.get("required"):
                label += " *"

            if field.get("type") == "readonly":
                lbl = QLabel(label)
                lbl.setStyleSheet(f"color: {COLORS['readonly_text']}; font-size: 13px;")
                form_layout.addRow(lbl, widget)
            else:
                form_layout.addRow(label, widget)

        scroll.setWidget(scroll_content)
        root.addWidget(scroll)
        root.addSpacing(16)
        root.addStretch()

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

        # ── readonly ──────────────────────────────────────────────────
        if field_type == "readonly":
            w = QLineEdit()
            w.setReadOnly(True)
            w.setPlaceholderText("—")
            w.setCursor(QCursor(Qt.ForbiddenCursor))
            w.setStyleSheet(f"""
                QLineEdit {{
                    padding: 8px 12px;
                    border: 1px solid {COLORS['border_light']};
                    border-radius: 6px;
                    background-color: {COLORS['readonly_bg']};
                    color: {COLORS['readonly_text']};
                    font-size: 13px;
                    font-style: italic;
                }}
            """)
            w.setMinimumHeight(36)
            return w

        # ── text ──────────────────────────────────────────────────────
        if field_type == "text":
            w = QLineEdit()
            w.setPlaceholderText(field.get("placeholder", ""))
            self._style_input(w)
            return w

        # ── combo / select ────────────────────────────────────────────
        elif field_type in ("combo", "select"):
            w = QComboBox()
            w.addItems(field.get("options", []))
            self._style_input(w)
            return w

        # ── cascade_combo ─────────────────────────────────────────────
        elif field_type == "cascade_combo":
            options_map: dict = field.get("options", {})  # {parent_val: [child_vals]}
            child_name: str = field.get("child", "")

            w = QComboBox()
            w.addItems(list(options_map.keys()))
            self._style_input(w)

            # Store for wiring after all fields are created
            self._cascade_map[field["name"]] = child_name
            self._cascade_options[field["name"]] = options_map

            # Wire signal — must be done after child widget exists, so defer
            w.currentTextChanged.connect(
                lambda text, pname=field["name"]: self._on_cascade_changed(pname, text)
            )
            return w

        # ── text_with_unit ────────────────────────────────────────────
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

        # ── dimension_pair ────────────────────────────────────────────
        # Two side-by-side inputs (inch and px) that live-convert each other.
        # Emits: data["{name}_in"] and data["{name}_px"]
        elif field_type == "dimension_pair":
            from PySide6.QtGui import QDoubleValidator, QIntValidator
            from PySide6.QtCore import QLocale

            dpi = field.get("dpi", 96)
            container = QWidget()
            container.setStyleSheet("background: transparent;")
            outer = QHBoxLayout(container)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.setSpacing(10)

            def _labeled_input(label_text, placeholder):
                """Return (cell_widget, QLineEdit, error_label) with labels above and below."""
                cell = QWidget()
                cell.setStyleSheet("background: transparent;")
                vl = QVBoxLayout(cell)
                vl.setContentsMargins(0, 0, 0, 0)
                vl.setSpacing(3)

                header_lbl = QLabel(label_text)
                header_lbl.setStyleSheet(
                    f"font-size: 11px; font-weight: 600; color: {COLORS['text_muted']};"
                    " letter-spacing: 0.04em; background: transparent;"
                )

                inp = QLineEdit()
                inp.setPlaceholderText(placeholder)
                self._style_input(inp)

                err_lbl = QLabel("")
                err_lbl.setStyleSheet(
                    "font-size: 11px; color: #EF4444; background: transparent;"
                )
                err_lbl.setVisible(False)

                vl.addWidget(header_lbl)
                vl.addWidget(inp)
                vl.addWidget(err_lbl)
                return cell, inp, err_lbl

            inch_cell, inch_input, inch_err = _labeled_input("INCH", "e.g. 2.5")
            px_cell,   px_input,   px_err   = _labeled_input("PX",   "e.g. 240")

            outer.addWidget(inch_cell, stretch=1)
            outer.addWidget(px_cell,   stretch=1)

            # ── Validators: only allow positive decimals / positive integers ──
            inch_validator = QDoubleValidator(0.0001, 99999.0, 4)
            inch_validator.setLocale(QLocale(QLocale.English))
            inch_validator.setNotation(QDoubleValidator.StandardNotation)
            inch_input.setValidator(inch_validator)

            px_validator = QIntValidator(1, 999999)
            px_input.setValidator(px_validator)

            # ── Live conversion + live error feedback ──────────────────
            container._converting = False

            def _set_error(inp_widget, err_widget, msg: str):
                if msg:
                    inp_widget.setStyleSheet(
                        f"QLineEdit {{ padding: 8px 12px; border: 1.5px solid #EF4444;"
                        f" border-radius: 6px; background-color: #FEF2F2;"
                        f" color: {COLORS['text_primary']}; font-size: 13px; }}"
                    )
                    err_widget.setText(msg)
                    err_widget.setVisible(True)
                else:
                    self._style_input(inp_widget)
                    err_widget.setVisible(False)

            def _inch_changed(text, _dpi=dpi):
                if container._converting:
                    return
                container._converting = True
                try:
                    val = float(text)
                    if val <= 0:
                        raise ValueError("zero")
                    px_input.setText(str(int(round(val * _dpi))))
                    _set_error(inch_input, inch_err, "")
                    _set_error(px_input,   px_err,   "")
                except ValueError:
                    px_input.clear()
                    if text.strip():
                        _set_error(inch_input, inch_err, "Must be a positive number")
                    else:
                        _set_error(inch_input, inch_err, "")
                finally:
                    container._converting = False

            def _px_changed(text, _dpi=dpi):
                if container._converting:
                    return
                container._converting = True
                try:
                    val = int(text)
                    if val <= 0:
                        raise ValueError("zero")
                    inch_input.setText(f"{val / _dpi:.4f}")
                    _set_error(px_input,   px_err,   "")
                    _set_error(inch_input, inch_err, "")
                except ValueError:
                    inch_input.clear()
                    if text.strip():
                        _set_error(px_input, px_err, "Must be a positive whole number")
                    else:
                        _set_error(px_input, px_err, "")
                finally:
                    container._converting = False

            inch_input.textEdited.connect(_inch_changed)
            px_input.textEdited.connect(_px_changed)

            # Attach sub-widgets so populate/validate/collect can reach them
            container.inch_input = inch_input
            container.px_input   = px_input
            container.inch_err   = inch_err
            container.px_err     = px_err
            container._set_error = _set_error
            container._field_type = "dimension_pair"
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
    # Cascade logic
    # ------------------------------------------------------------------

    def _on_cascade_changed(self, parent_name: str, selected_text: str):
        """Repopulate the child combo when the parent selection changes."""
        child_name = self._cascade_map.get(parent_name)
        if not child_name or child_name not in self.inputs:
            return

        child_widget = self.inputs[child_name]
        if not isinstance(child_widget, QComboBox):
            return

        options_map = self._cascade_options.get(parent_name, {})
        child_options = options_map.get(selected_text, [])

        child_widget.blockSignals(True)
        child_widget.clear()
        child_widget.addItems(child_options)
        child_widget.blockSignals(False)

    # ------------------------------------------------------------------
    # Form helpers
    # ------------------------------------------------------------------

    def _populate_initial_data(self):
        for name, widget in self.inputs.items():
            if name not in self.initial_data and \
               f"{name}_in" not in self.initial_data and \
               f"{name}_px" not in self.initial_data:
                continue

            # dimension_pair: accepts {name}_in / {name}_px  OR  just {name} (treated as inch)
            if getattr(widget, "_field_type", None) == "dimension_pair":
                in_val = self.initial_data.get(f"{name}_in") or self.initial_data.get(name, "")
                px_val = self.initial_data.get(f"{name}_px", "")
                if in_val:
                    widget.inch_input.setText(str(in_val))
                    # derive px if not supplied
                    if not px_val:
                        try:
                            dpi = next(
                                (f.get("dpi", 96) for f in self.fields_config if f.get("name") == name), 96
                            )
                            px_val = str(int(round(float(in_val) * dpi)))
                        except ValueError:
                            pass
                if px_val:
                    widget.px_input.setText(str(px_val))
                continue

            value = self.initial_data.get(name)
            if value is None:
                continue

            if isinstance(widget, QLineEdit):
                widget.setText(str(value))
            elif isinstance(widget, QComboBox):
                if name in self._cascade_map:
                    self._on_cascade_changed(name, str(value))
                widget.setCurrentText(str(value))
                if name in self._cascade_map:
                    child_name = self._cascade_map[name]
                    child_val = self.initial_data.get(child_name, "")
                    child_widget = self.inputs.get(child_name)
                    if isinstance(child_widget, QComboBox) and child_val:
                        child_widget.setCurrentText(str(child_val))
            elif hasattr(widget, "text_input"):
                widget.text_input.setText(str(value))
                unit_key = f"{name}_unit"
                if unit_key in self.initial_data:
                    widget.unit_combo.setCurrentText(str(self.initial_data[unit_key]))

    def _validate(self) -> list[str]:
        errors = []
        for field in self.fields_config:
            if field.get("type") in ("readonly",):
                continue
            widget = self.inputs[field["name"]]
            label  = field.get("label", field["name"])
            is_required = field.get("required", False)

            if getattr(widget, "_field_type", None) == "dimension_pair":
                in_text = widget.inch_input.text().strip()
                px_text = widget.px_input.text().strip()

                # Required check
                if is_required and not in_text and not px_text:
                    errors.append(f"{label}: both Inch and PX are empty")
                    widget._set_error(widget.inch_input, widget.inch_err, "Required")
                    widget._set_error(widget.px_input,   widget.px_err,   "Required")
                    continue

                # Inch value check
                if in_text:
                    try:
                        v = float(in_text)
                        if v <= 0:
                            raise ValueError
                        widget._set_error(widget.inch_input, widget.inch_err, "")
                    except ValueError:
                        errors.append(f"{label} (Inch): must be a positive number")
                        widget._set_error(widget.inch_input, widget.inch_err,
                                          "Must be a positive number")

                # PX value check
                if px_text:
                    try:
                        v = int(px_text)
                        if v <= 0:
                            raise ValueError
                        widget._set_error(widget.px_input, widget.px_err, "")
                    except ValueError:
                        errors.append(f"{label} (PX): must be a positive whole number")
                        widget._set_error(widget.px_input, widget.px_err,
                                          "Must be a positive whole number")

            elif isinstance(widget, QLineEdit):
                if is_required and not widget.text().strip():
                    errors.append(f"{label} is required")
                    widget.setStyleSheet(
                        f"QLineEdit {{ padding: 8px 12px; border: 1.5px solid #EF4444;"
                        f" border-radius: 6px; background-color: #FEF2F2;"
                        f" color: {COLORS['text_primary']}; font-size: 13px; }}"
                    )
                else:
                    self._style_input(widget)

            elif isinstance(widget, QComboBox):
                if is_required and not widget.currentText():
                    errors.append(f"{label} is required")

            elif hasattr(widget, "text_input"):
                if is_required and not widget.text_input.text().strip():
                    errors.append(f"{label} is required")

        return errors

    def _collect_data(self) -> dict:
        data = {}
        for name, widget in self.inputs.items():
            if getattr(widget, "_field_type", None) == "dimension_pair":
                data[f"{name}_in"] = widget.inch_input.text().strip()
                data[f"{name}_px"] = widget.px_input.text().strip()
            elif isinstance(widget, QLineEdit):
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