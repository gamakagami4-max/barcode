"""GeneralTab widget — sticker selection, code/name fields, print type."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QLineEdit, QGridLayout, QFormLayout, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from components.barcode_editor.utils import COLORS, MODERN_INPUT_STYLE, make_chevron_combo, CheckmarkCheckBox


def _fetch_sticker_data() -> dict:
    try:
        from server.db import get_connection
        conn = get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT msstnm, msheig, mswidt, mspixh, mspixw
                  FROM barcodesap.mstckr
                 WHERE msdlfg <> '1'
                 ORDER BY msstnm
                """
            )
            result = {}
            for msstnm, msheig, mswidt, mspixh, mspixw in cur.fetchall():
                result[str(msstnm).strip()] = {
                    "h_in": float(msheig) if msheig is not None else 0.0,
                    "w_in": float(mswidt) if mswidt is not None else 0.0,
                    "h_px": int(mspixh)   if mspixh is not None else 0,
                    "w_px": int(mspixw)   if mspixw is not None else 0,
                }
            return result
        finally:
            conn.close()
    except Exception as e:
        print(f"[_fetch_sticker_data] {e}")
        return {}


_LABEL_STYLE = (
    f"color: {COLORS['legacy_blue']}; font-size: 9px; font-weight: 700; "
    "text-transform: uppercase; letter-spacing: 0.4px; background: transparent; border: none;"
)

_READONLY_STYLE = """
    QLineEdit {
        background-color: #F8FAFC; border: 1px solid #E2E8F0;
        border-radius: 4px; padding: 4px 6px; font-size: 11px; color: #64748B;
    }
"""

_MUTED_STYLE = f"color:{COLORS['text_mute']}; font-size:10px; background:transparent; border:none;"


def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(_LABEL_STYLE)
    l.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
    l.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    l.setFixedHeight(32)
    return l


def _make_input(placeholder: str = "") -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setStyleSheet(MODERN_INPUT_STYLE)
    le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return le


def _make_readonly(placeholder: str = "—") -> QLineEdit:
    le = QLineEdit()
    le.setPlaceholderText(placeholder)
    le.setReadOnly(True)
    le.setStyleSheet(_READONLY_STYLE)
    le.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return le


def _vdiv() -> QFrame:
    d = QFrame()
    d.setFrameShape(QFrame.VLine)
    d.setStyleSheet(
        "background: #E2E8F0; border: none; min-width: 1px; max-width: 1px;"
    )
    return d


class GeneralTab(QWidget):
    stickerChanged = Signal(int, int)   # (w_px, h_px)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self._sticker_data: dict = _fetch_sticker_data()
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 20, 40, 20)
        root.setSpacing(0)

        card = QFrame()
        card.setStyleSheet(
            "QFrame { background: white; border: 1px solid #E2E8F0; border-radius: 10px; }"
        )

        # ── Card body: left | divider | middle | divider | right ──────────────
        card_h = QHBoxLayout(card)
        card_h.setContentsMargins(28, 22, 28, 22)
        card_h.setSpacing(0)

        # ── Left block ────────────────────────────────────────────────────────
        left_block = QWidget()
        left_block.setStyleSheet("background: transparent; border: none;")
        left_form = QFormLayout(left_block)
        left_form.setContentsMargins(0, 0, 32, 0)
        left_form.setVerticalSpacing(18)
        left_form.setHorizontalSpacing(14)
        left_form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        left_form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        left_form.setFormAlignment(Qt.AlignLeft | Qt.AlignTop)

        self.code_input = _make_input("")
        self.code_input.setReadOnly(True)
        self.code_input.setStyleSheet("""
            QLineEdit {
                background-color: #F8FAFC; border: 1px solid #E2E8F0;
                border-radius: 4px; padding: 5px; font-size: 11px; color: #64748B;
            }
        """)

        self.name_input = _make_input("e.g. Member Label A4")
        self.status_combo = make_chevron_combo(["DISPLAY", "NOT DISPLAY"])
        self.status_combo._current = "DISPLAY"
        self.status_combo._label.setText("DISPLAY")

        left_form.addRow(_lbl("CODE :"),           self.code_input)
        left_form.addRow(_lbl("NAME :"),           self.name_input)
        left_form.addRow(_lbl("DISPLAY STATUS :"), self.status_combo)

        # Horizontal separator inside left block
        hsep = QFrame()
        hsep.setFrameShape(QFrame.HLine)
        hsep.setStyleSheet(
            "background: #E2E8F0; border: none; min-height: 1px; max-height: 1px;"
        )
        left_form.addRow(hsep)

        # Sticker
        sticker_keys = list(self._sticker_data.keys())
        self.sticker_combo = make_chevron_combo(sticker_keys)
        self.sticker_combo.setPlaceholderText("— Please select a sticker —")
        self.sticker_combo.setCurrentIndex(-1)
        left_form.addRow(_lbl("STICKER :"), self.sticker_combo)

        # Height row
        h_row_w = QWidget(); h_row_w.setStyleSheet("background: transparent; border: none;")
        h_hl = QHBoxLayout(h_row_w); h_hl.setContentsMargins(0, 0, 0, 0); h_hl.setSpacing(4)
        self.height_inch = _make_readonly(); self.height_inch.setFixedWidth(70)
        h_hl.addWidget(self.height_inch)
        h_hl.addWidget(QLabel("INCH /", styleSheet=_MUTED_STYLE))
        self.height_px = _make_readonly(); self.height_px.setFixedWidth(70)
        h_hl.addWidget(self.height_px)
        h_hl.addWidget(QLabel("PIXEL", styleSheet=_MUTED_STYLE))
        h_hl.addStretch()
        left_form.addRow(_lbl("HEIGHT :"), h_row_w)

        # Width row
        w_row_w = QWidget(); w_row_w.setStyleSheet("background: transparent; border: none;")
        w_hl = QHBoxLayout(w_row_w); w_hl.setContentsMargins(0, 0, 0, 0); w_hl.setSpacing(4)
        self.width_inch = _make_readonly(); self.width_inch.setFixedWidth(70)
        w_hl.addWidget(self.width_inch)
        w_hl.addWidget(QLabel("INCH /", styleSheet=_MUTED_STYLE))
        self.width_px = _make_readonly(); self.width_px.setFixedWidth(70)
        w_hl.addWidget(self.width_px)
        w_hl.addWidget(QLabel("PIXEL", styleSheet=_MUTED_STYLE))
        w_hl.addStretch()
        left_form.addRow(_lbl("WIDTH :"), w_row_w)

        card_h.addWidget(left_block, stretch=1)
        card_h.addWidget(_vdiv())

        # ── Middle block: placeholder ─────────────────────────────────────────
        middle_block = QWidget()
        middle_block.setStyleSheet("background: transparent; border: none;")
        middle_layout = QVBoxLayout(middle_block)
        middle_layout.setContentsMargins(24, 0, 24, 0)
        middle_layout.setSpacing(8)
        middle_layout.setAlignment(Qt.AlignTop)

        middle_lbl = QLabel("SECTION 2 :")
        middle_lbl.setStyleSheet(_LABEL_STYLE)
        middle_layout.addWidget(middle_lbl)

        placeholder_lbl = QLabel("— coming soon —")
        placeholder_lbl.setStyleSheet(
            f"color: {COLORS['text_mute']}; font-size: 10px; "
            "background: transparent; border: none;"
        )
        middle_layout.addWidget(placeholder_lbl)
        middle_layout.addStretch()

        card_h.addWidget(middle_block, stretch=1)
        card_h.addWidget(_vdiv())

        # ── Right block: JENIS CETAK ──────────────────────────────────────────
        right_block = QWidget()
        right_block.setStyleSheet("background: transparent; border: none;")
        right_layout = QVBoxLayout(right_block)
        right_layout.setContentsMargins(24, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.setAlignment(Qt.AlignTop)

        jenis_lbl = QLabel("JENIS CETAK :")
        jenis_lbl.setStyleSheet(_LABEL_STYLE)
        right_layout.addWidget(jenis_lbl)

        self.chk_barcode_printer = CheckmarkCheckBox("KE BARCODE PRINTER")
        self.chk_report          = CheckmarkCheckBox("KE REPORT")
        right_layout.addWidget(self.chk_barcode_printer)
        right_layout.addWidget(self.chk_report)
        right_layout.addStretch()

        card_h.addWidget(right_block, stretch=1)

        root.addWidget(card)
        root.addStretch()

        self.sticker_combo.currentTextChanged.connect(self._on_sticker_changed)

    # ── Slots ──────────────────────────────────────────────────────────────────

    def _on_sticker_changed(self, key: str):
        d = self._sticker_data.get(key)
        if d:
            self.height_inch.setText(f"{d['h_in']:.2f}")
            self.height_px.setText(str(d["h_px"]))
            self.width_inch.setText(f"{d['w_in']:.2f}")
            self.width_px.setText(str(d["w_px"]))
            self.stickerChanged.emit(d["w_px"], d["h_px"])
        else:
            self.height_inch.clear()
            self.height_px.clear()
            self.width_inch.clear()
            self.width_px.clear()

    # ── Public API ─────────────────────────────────────────────────────────────

    def sync_from_design(
        self, code: str, name: str, sticker_name: str = "",
        h_in: float = 0.0, w_in: float = 0.0,
        h_px: int = 0, w_px: int = 0, dp_fg: int = 0,
    ):
        self.code_input.setText(code)
        self.name_input.setText(name)
        status_text = "DISPLAY" if dp_fg == 1 else "NOT DISPLAY"
        self.status_combo._current = status_text
        self.status_combo._label.setText(status_text)

        self.sticker_combo.blockSignals(True)
        if sticker_name and sticker_name in self._sticker_data:
            idx = self.sticker_combo.findText(sticker_name)
            if idx >= 0:
                self.sticker_combo.setCurrentIndex(idx)
            d = self._sticker_data[sticker_name]
            self.height_inch.setText(f"{d['h_in']:.2f}")
            self.height_px.setText(str(d["h_px"]))
            self.width_inch.setText(f"{d['w_in']:.2f}")
            self.width_px.setText(str(d["w_px"]))
        else:
            self.sticker_combo.setCurrentIndex(-1)
            self.height_inch.setText(f"{h_in:.2f}" if h_in else "")
            self.height_px.setText(str(h_px) if h_px else "")
            self.width_inch.setText(f"{w_in:.2f}" if w_in else "")
            self.width_px.setText(str(w_px) if w_px else "")
        self.sticker_combo.blockSignals(False)

    def get_canvas_size(self) -> tuple[int, int]:
        try:    w = int(self.width_px.text())
        except (ValueError, AttributeError): w = 600
        try:    h = int(self.height_px.text())
        except (ValueError, AttributeError): h = 400
        return w, h

    def get_dp_fg(self) -> int:
        return 1 if self.status_combo.currentText() == "DISPLAY" else 0