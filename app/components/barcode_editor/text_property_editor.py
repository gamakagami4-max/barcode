"""TextPropertyEditor — orchestrates all type-specific mixins."""

from PySide6.QtWidgets import (
    QWidget, QFormLayout, QLabel, QLineEdit, QSizePolicy, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor, QTextBlockFormat

from components.barcode_editor.utils import (
    COLORS, MODERN_INPUT_STYLE, _LINE_DISABLED,
    make_spin, make_chevron_combo,
)
from components.barcode_editor.same_with_mixin import SameWithMixin, SameWithRegistry
from components.barcode_editor.lookup_mixin import LookupMixin
from components.barcode_editor.link_mixin import LinkMixin
from components.barcode_editor.system_mixin import SystemMixin
from components.barcode_editor.merge_konversi_mixin import MergeKonversiMixin

LABEL_W = 70

_DISABLED_COMBO_STYLE = """
    QComboBox, QSpinBox {
        background-color: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 4px; padding: 5px; font-size: 11px; color: #94A3B8;
    }
    QComboBox::drop-down, QSpinBox::up-button, QSpinBox::down-button {
        background: transparent; border: none;
    }
"""


def _lbl(text: str) -> QLabel:
    label_style = (
        f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; "
        "background: transparent; border: none;"
    )
    l = QLabel(text)
    l.setStyleSheet(label_style)
    l.setFixedWidth(LABEL_W)
    l.setAlignment(Qt.AlignLeft | Qt.AlignBottom)
    return l


class TextPropertyEditor(
    SameWithMixin,
    LookupMixin,
    LinkMixin,
    SystemMixin,
    MergeKonversiMixin,
    QWidget,
):
    def __init__(self, target_item, update_callback):
        QWidget.__init__(self)
        self.item = target_item
        self.update_callback = update_callback
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        # LookupMixin state
        self.init_lookup_state()

        layout = QFormLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setVerticalSpacing(8)
        layout.setHorizontalSpacing(4)
        layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        layout.setLabelAlignment(Qt.AlignLeft)

        # ── ALIGNMENT ────────────────────────────────────────────────────────
        self.align_combo = make_chevron_combo(["LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"])
        stored_align = getattr(self.item, "_design_alignment", None)
        if stored_align in ("LEFT JUSTIFY", "CENTER", "RIGHT JUSTIFY"):
            self.align_combo._current = stored_align
            self.align_combo._label.setText(stored_align)
        else:
            doc = self.item.document()
            if doc.blockCount() > 0:
                block_align = doc.begin().blockFormat().alignment()
                if block_align == Qt.AlignCenter:
                    self.align_combo._current = "CENTER"
                    self.align_combo._label.setText("CENTER")
                elif block_align == Qt.AlignRight:
                    self.align_combo._current = "RIGHT JUSTIFY"
                    self.align_combo._label.setText("RIGHT JUSTIFY")
        layout.addRow(_lbl("ALIGNMENT :"), self.align_combo)

        # ── FONT ─────────────────────────────────────────────────────────────
        self.font_combo = make_chevron_combo([
            "STANDARD", "ARIAL", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
            "ARIAL BOLD", "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD",
            "FUTURA-CONDENSED-BOL", "FUTURA-NORMAL", "GLORIOLA STD BOLD",
            "GLORIOLA STD LIGHT", "HELVETICANEUE", "MONTSERRAT BOLD",
            "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD", "MYRIAD PRO",
            "NEO SANS", "NEO SANS BOLD", "OCR-B", "SWIS721", "TAHOMA",
            "UNIVERS CONDENSED",
        ])
        layout.addRow(_lbl("FONT NAME :"), self.font_combo)

        # ── SIZE / POSITION ───────────────────────────────────────────────────
        self.size_spin  = make_spin(1, 100, int(self.item.font().pointSize()))
        self.top_spin   = make_spin(0, 5000, int(self.item.pos().y()))
        self.left_spin  = make_spin(0, 5000, int(self.item.pos().x()))
        self.size_spin.valueChanged.connect(self.apply_font_changes)
        self.top_spin.valueChanged.connect(lambda v: self.item.setY(v))
        self.left_spin.valueChanged.connect(lambda v: self.item.setX(v))
        layout.addRow(_lbl("FONT SIZE :"), self.size_spin)
        layout.addRow(_lbl("TOP :"),       self.top_spin)
        layout.addRow(_lbl("LEFT :"),      self.left_spin)

        # ── ANGLE ─────────────────────────────────────────────────────────────
        self.angle_combo = make_chevron_combo(["0", "90", "180", "270"])
        _angle_map = {"0": 0, "90": 270, "180": 180, "270": 90}
        self.angle_combo.currentTextChanged.connect(
            lambda v: self.item.setRotation(_angle_map.get(v, 0))
        )
        layout.addRow(_lbl("ANGLE :"), self.angle_combo)

        # ── INVERSE ───────────────────────────────────────────────────────────
        self.inverse_combo = make_chevron_combo(["NO", "YES"])
        self.inverse_combo.setCurrentText(
            "YES" if getattr(self.item, "design_inverse", False) else "NO"
        )
        self.inverse_combo.currentTextChanged.connect(self._apply_inverse)
        layout.addRow(_lbl("INVERSE :"), self.inverse_combo)

        # ── TYPE ──────────────────────────────────────────────────────────────
        self.type_combo = make_chevron_combo([
            "FIX", "INPUT", "LOOKUP", "SAME WITH", "LINK", "SYSTEM",
            "BATCH NO", "MERGE", "TIMBANGAN", "DUPLIKASI", "RUNNING NO",
            "KONVERSI TIMBANGAN",
        ])
        self.type_combo.setCurrentText(getattr(self.item, "design_type", "FIX"))
        layout.addRow(_lbl("TYPE :"), self.type_combo)

        # ── EDITOR ────────────────────────────────────────────────────────────
        self.editor_combo = make_chevron_combo(["ENABLED", "DISABLED", "INVISIBLE"])
        layout.addRow(_lbl("EDITOR :"), self.editor_combo)

        # ── SYSTEM fields ─────────────────────────────────────────────────────
        self.system_value_combo = make_chevron_combo(["USER ID", "DATETIME", "LOT NO", "OTHERS"])
        self.system_extra_combo = make_chevron_combo([""])
        layout.addRow(_lbl("SYSTEM VALUE :"), self.system_value_combo)
        layout.addRow(_lbl("EXTRA :"),        self.system_extra_combo)
        self.system_value_combo.currentTextChanged.connect(self._on_system_value_changed)
        self.system_extra_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_system_extra", v)
        )
        self.restore_system_values(
            getattr(self.item, "design_system_value", ""),
            getattr(self.item, "design_system_extra", ""),
        )

        # ── INPUT fields ──────────────────────────────────────────────────────
        self.data_type_combo  = make_chevron_combo(["STRING", "INTEGER", "DECIMAL"])
        self.max_length_spin  = make_spin(0, 9999, 1)
        self.max_length_spin.setSpecialValueText("")
        layout.addRow(_lbl("DATA TYPE :"),   self.data_type_combo)
        layout.addRow(_lbl("MAX LENGTH :"),  self.max_length_spin)

        # ── SAME WITH combo ───────────────────────────────────────────────────
        self.same_with_combo = self._build_scene_name_combo(exclude_same_with=True)
        stored_same_with = getattr(self.item, "design_same_with", "")
        if stored_same_with and stored_same_with in self.same_with_combo._items:
            self.same_with_combo.setCurrentText(stored_same_with)
        self.same_with_combo.currentTextChanged.connect(self._on_same_with_changed)
        layout.addRow(_lbl("SAME WITH :"), self.same_with_combo)

        # ── LINK combo ────────────────────────────────────────────────────────
        self.link_combo = self._build_scene_name_combo(only_lookup=True)
        stored_link = getattr(self.item, "design_link", "")
        if stored_link and stored_link in self.link_combo._items:
            self.link_combo.setCurrentText(stored_link)
        self.link_combo.currentTextChanged.connect(self._on_link_changed)
        layout.addRow(_lbl("LINK TO :"), self.link_combo)

        # ── MERGE combo ───────────────────────────────────────────────────────
        self.merge_combo = self._build_scene_name_combo()
        stored_merge = getattr(self.item, "design_merge", "")
        if stored_merge and stored_merge in self.merge_combo._items:
            self.merge_combo.setCurrentText(stored_merge)
        self.merge_combo.currentTextChanged.connect(self._on_merge_changed)
        layout.addRow(_lbl("MERGE WITH :"), self.merge_combo)

        # ── KONVERSI TIMBANGAN combos ─────────────────────────────────────────
        self.timbangan_combo = self._build_scene_name_combo()
        self.weight_combo    = self._build_scene_name_combo()
        self.um_combo        = self._build_scene_name_combo()
        for stored_attr, combo in (
            ("design_timbangan", self.timbangan_combo),
            ("design_weight",    self.weight_combo),
            ("design_um",        self.um_combo),
        ):
            sv = getattr(self.item, stored_attr, "")
            if sv and sv in combo._items:
                combo.setCurrentText(sv)
        self.timbangan_combo.currentTextChanged.connect(self._on_timbangan_changed)
        self.weight_combo.currentTextChanged.connect(self._on_weight_changed)
        self.um_combo.currentTextChanged.connect(self._on_um_changed)
        layout.addRow(_lbl("TIMBANGAN :"), self.timbangan_combo)
        layout.addRow(_lbl("WEIGHT :"),    self.weight_combo)
        layout.addRow(_lbl("U/M :"),       self.um_combo)

        # ── LOOKUP cascade ────────────────────────────────────────────────────
        self.group_combo  = make_chevron_combo([""])
        self.table_combo  = make_chevron_combo([""])
        self.table_extra  = QLineEdit()
        self.field_edit   = make_chevron_combo([""])
        self.result_combo = make_chevron_combo([""])

        self.table_extra.setStyleSheet(MODERN_INPUT_STYLE)
        self.table_extra.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        for combo, ph in (
            (self.group_combo,  "— select connection —"),
            (self.table_combo,  "— select table —"),
            (self.field_edit,   "— select field —"),
            (self.result_combo, "— select result field —"),
        ):
            combo.setPlaceholderText(ph)
            combo.setCurrentIndex(-1)
            combo.setEnabled(False)

        layout.addRow(_lbl("GROUP :"),  self.group_combo)
        layout.addRow(_lbl("TABLE :"),  self.table_combo)
        layout.addRow(_lbl("QUERY :"),  self.table_extra)
        layout.addRow(_lbl("FIELD :"),  self.field_edit)
        layout.addRow(_lbl("RESULT :"), self.result_combo)

        # Wire up LOOKUP cascade
        self.build_connection_combo()
        self.group_combo.currentTextChanged.connect(self._on_group_changed)
        self.table_combo.currentTextChanged.connect(self._on_table_changed)
        self.field_edit.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_field",  v if v not in ("", "—") else "")
        )
        self.result_combo.currentTextChanged.connect(
            lambda v: setattr(self.item, "design_result", v if v not in ("", "—") else "")
        )
        self.table_extra.textChanged.connect(
            lambda v: setattr(self.item, "design_query", v)
        )
        self.restore_lookup_values(
            getattr(self.item, "design_group",  ""),
            getattr(self.item, "design_table",  ""),
            getattr(self.item, "design_field",  ""),
            getattr(self.item, "design_result", ""),
            getattr(self.item, "design_query",  ""),
        )

        # ── Text / display fields ─────────────────────────────────────────────
        self.text_input = QLineEdit(self.item.toPlainText())
        self.text_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.text_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.text_input.textChanged.connect(self.apply_text_changes)
        layout.addRow(_lbl("TEXT :"), self.text_input)

        self.caption_input = QLineEdit("LABEL 1")
        self.caption_input.setStyleSheet(MODERN_INPUT_STYLE)
        self.caption_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(_lbl("CAPTION :"), self.caption_input)

        self.wrap_combo      = make_chevron_combo(["NO", "YES"])
        self.wrap_width_spin = make_spin(0, 5000, 1)
        layout.addRow(_lbl("WRAP TEXT :"),  self.wrap_combo)
        layout.addRow(_lbl("WRAP WIDTH :"), self.wrap_width_spin)

        # Trim checkbox row
        self._trim_checked = False
        trim_row = QWidget()
        trim_row.setStyleSheet("background: transparent; border: none;")
        trim_layout = QHBoxLayout(trim_row)
        trim_layout.setContentsMargins(0, 0, 0, 0)
        trim_layout.setSpacing(6)
        self.trim_box = QLabel()
        self.trim_box.setFixedSize(14, 14)
        self.trim_box.setCursor(Qt.PointingHandCursor)
        self._set_trim_style(False)
        self.trim_box.mousePressEvent = self._toggle_trim
        trim_layout.addWidget(self.trim_box)
        trim_lbl = QLabel("TRIM")
        label_style = (
            f"color: {COLORS['legacy_blue']}; font-size: 9px; text-transform: uppercase; "
            "background: transparent; border: none;"
        )
        trim_lbl.setStyleSheet(label_style)
        trim_layout.addWidget(trim_lbl)
        trim_layout.addStretch()
        layout.addRow(_lbl(""), trim_row)

        self.format_edit = QLineEdit()
        self.format_edit.setStyleSheet(MODERN_INPUT_STYLE)
        self.format_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addRow(_lbl("FORMAT :"), self.format_edit)

        # ── VISIBLE ───────────────────────────────────────────────────────────
        self.visible_combo = make_chevron_combo(["TRUE", "FALSE"])
        current_visible = getattr(self.item, "design_visible", None)
        self.visible_combo.setCurrentText("TRUE" if current_visible in (True, None) else "FALSE")
        self.visible_combo.currentTextChanged.connect(self._apply_visible)
        layout.addRow(_lbl("VISIBLE :"), self.visible_combo)

        # ── Remaining fields ──────────────────────────────────────────────────
        self.save_field_combo = make_chevron_combo(["-- NOT SAVE --", "SAVE"])
        self.column_spin      = make_spin(1, 999, 1)
        self.mandatory_combo  = make_chevron_combo(["FALSE", "TRUE"])
        self.batch_no_combo   = make_chevron_combo([""])
        self.wh_combo         = make_chevron_combo([""])
        layout.addRow(_lbl("SAVE FIELD :"), self.save_field_combo)
        layout.addRow(_lbl("COLUMN :"),     self.column_spin)
        layout.addRow(_lbl("MANDATORY :"),  self.mandatory_combo)
        layout.addRow(_lbl("BATCH NO :"),   self.batch_no_combo)
        layout.addRow(_lbl("WH :"),         self.wh_combo)

        # ── Wire remaining signals ────────────────────────────────────────────
        self.align_combo.currentTextChanged.connect(self._apply_alignment)
        self.font_combo.currentTextChanged.connect(self._apply_font_family)
        self.type_combo.currentTextChanged.connect(self._on_type_changed)

        # Trigger initial enable/disable state
        self._on_type_changed(getattr(self.item, "design_type", "FIX"))

        # Restore SAME WITH link if previously set
        stored_same_with = getattr(self.item, "design_same_with", "")
        if (stored_same_with
                and stored_same_with in self.same_with_combo._items
                and getattr(self.item, "design_type", "") == "SAME WITH"):
            self._apply_same_with_link(stored_same_with)

    # ── Helper: build a name combo from scene items ───────────────────────────

    def _build_scene_name_combo(self, exclude_same_with=False, only_lookup=False):
        from components.barcode_editor.scene_items import SelectableTextItem
        names = []
        try:
            scene = self.item.scene()
            if scene:
                for si in scene.items():
                    if si.group() or si is self.item:
                        continue
                    if not isinstance(si, SelectableTextItem):
                        continue
                    if exclude_same_with and getattr(si, "design_same_with", "") == getattr(self.item, "component_name", ""):
                        continue
                    if only_lookup and getattr(si, "design_type", "") != "LOOKUP":
                        continue
                    name = getattr(si, "component_name", "") or "Text"
                    names.append(name)
        except Exception:
            pass

        combo = make_chevron_combo([""] + names if names else ["—"])
        combo.setPlaceholderText("—")
        combo.setCurrentIndex(-1)
        return combo

    # ── _on_type_changed: thin orchestrator ──────────────────────────────────

    def _on_type_changed(self, val: str):
        is_input    = val == "INPUT"
        is_lookup   = val == "LOOKUP"
        is_same_with = val == "SAME WITH"
        is_link     = val == "LINK"
        is_system   = val == "SYSTEM"
        is_batch_no = val == "BATCH NO"
        is_merge    = val == "MERGE"
        is_konversi = val == "KONVERSI TIMBANGAN"

        setattr(self.item, "design_type", val)

        # SAME WITH (locks everything else)
        self.enable_for_same_with(is_same_with)
        if is_same_with:
            return  # remaining enables are irrelevant while locked

        # INPUT
        self.data_type_combo.setEnabled(is_input)
        self.max_length_spin.setEnabled(is_input)
        if is_input:
            self.data_type_combo.blockSignals(False)
            if self.data_type_combo.currentIndex() == -1:
                self.data_type_combo.setCurrentIndex(0)
            self.max_length_spin.setStyleSheet(MODERN_INPUT_STYLE)
            if self.max_length_spin.value() == 0:
                self.max_length_spin.setValue(1)
        else:
            self.data_type_combo.blockSignals(True)
            self.data_type_combo.setCurrentIndex(-1)
            self.data_type_combo.blockSignals(False)
            self.max_length_spin.setValue(0)
            self.max_length_spin.setStyleSheet(_DISABLED_COMBO_STYLE)

        # Delegate to mixins
        self.enable_for_lookup(is_lookup)
        self.enable_for_link(is_link)
        self.enable_for_system(is_system)
        self.enable_for_merge(is_merge)
        self.enable_for_konversi(is_konversi)

        # BATCH NO
        self.batch_no_combo.setEnabled(is_batch_no)
        self.wh_combo.setEnabled(is_batch_no)
        if not is_batch_no:
            self.batch_no_combo.setCurrentIndex(-1)
            self.wh_combo.setCurrentIndex(-1)

        # SAME WITH combo is only active when type == SAME WITH
        self.same_with_combo.setEnabled(is_same_with)

    # ── Standard property-apply methods ──────────────────────────────────────

    def _apply_alignment(self, value: str):
        align_map = {
            "LEFT JUSTIFY":  Qt.AlignLeft,
            "CENTER":        Qt.AlignCenter,
            "RIGHT JUSTIFY": Qt.AlignRight,
        }
        alignment = align_map.get(value, Qt.AlignLeft)
        if value == "LEFT JUSTIFY":
            self.item.setTextWidth(-1)
        else:
            w = self.item.boundingRect().width()
            self.item.setTextWidth(w if w > 0 else 200)
        doc = self.item.document()
        doc_cursor = QTextCursor(doc)
        doc_cursor.select(QTextCursor.SelectionType.Document)
        fmt = QTextBlockFormat()
        fmt.setAlignment(alignment)
        doc_cursor.mergeBlockFormat(fmt)
        self.item._design_alignment = value
        self.update_callback()

    def _apply_font_family(self, value: str):
        font_map = {
            "STANDARD":              "Arial",
            "ARIAL":                 "Arial",
            "ARIAL BLACK":           "Arial Black",
            "ARIAL BLACK (GT)":      "Arial Black",
            "ARIAL BLACK NEW":       "Arial Black",
            "ARIAL BOLD":            "Arial",
            "ARIAL NARROW BOLD":     "Arial Narrow",
            "EUROSTILE BOLD OLD":    "Eurostile",
            "FUTURA-CONDENSED-BOL":  "Futura",
            "FUTURA-NORMAL":         "Futura",
            "GLORIOLA STD BOLD":     "Arial",
            "GLORIOLA STD LIGHT":    "Arial",
            "HELVETICANEUE":         "Helvetica Neue",
            "MONTSERRAT BOLD":       "Montserrat",
            "MONTSERRAT SBOLD-CAE":  "Montserrat",
            "MONTSERRAT SEMI BOLD":  "Montserrat",
            "MYRIAD PRO":            "Myriad Pro",
            "NEO SANS":              "Neo Sans",
            "NEO SANS BOLD":         "Neo Sans",
            "OCR-B":                 "OCR B",
            "SWIS721":               "Swiss 721",
            "TAHOMA":                "Tahoma",
            "UNIVERS CONDENSED":     "Univers Condensed",
        }
        bold_fonts = {
            "ARIAL BOLD", "ARIAL BLACK", "ARIAL BLACK (GT)", "ARIAL BLACK NEW",
            "ARIAL NARROW BOLD", "EUROSTILE BOLD OLD", "FUTURA-CONDENSED-BOL",
            "GLORIOLA STD BOLD", "HELVETICANEUE", "MONTSERRAT BOLD",
            "MONTSERRAT SBOLD-CAE", "MONTSERRAT SEMI BOLD", "NEO SANS BOLD",
        }
        font = self.item.font()
        font.setFamily(font_map.get(value, "Arial"))
        font.setBold(value in bold_fonts)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_inverse(self, value: str):
        self.item.design_inverse = (value == "YES")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _apply_visible(self, value: str):
        self.item.design_visible = (value == "TRUE")
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def _set_trim_style(self, checked: bool):
        if checked:
            self.trim_box.setText("✓")
            self.trim_box.setAlignment(Qt.AlignCenter)
            self.trim_box.setStyleSheet(
                "QLabel{border:1.5px solid #6366F1;border-radius:3px;"
                "background:#6366F1;color:white;font-size:9px;font-weight:bold;}"
            )
        else:
            self.trim_box.setText("")
            self.trim_box.setStyleSheet(
                "QLabel{border:1.5px solid #CBD5E1;border-radius:3px;background:white;}"
            )

    def _toggle_trim(self, event):
        self._trim_checked = not self._trim_checked
        self._set_trim_style(self._trim_checked)

    def apply_text_changes(self, text: str):
        self.item.setPlainText(text)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def apply_font_changes(self, size: int):
        font = self.item.font()
        font.setPointSize(size)
        self.item.setFont(font)
        if SameWithRegistry.is_source(self.item):
            self._sync_same_with_targets()
        self.update_callback()

    def update_position_fields(self, pos):
        self.top_spin.blockSignals(True)
        self.left_spin.blockSignals(True)
        self.top_spin.setValue(int(pos.y()))
        self.left_spin.setValue(int(pos.x()))
        self.top_spin.blockSignals(False)
        self.left_spin.blockSignals(False)