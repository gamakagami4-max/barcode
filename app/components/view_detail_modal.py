"""
view_detail_modal.py
--------------------
Reusable read-only detail modal.

Usage
-----
    from components.view_detail_modal import ViewDetailModal

    # field_map: list of (label, value) string pairs — build it however you like
    fields = [
        ("Connection",          row[1]),
        ("Table Name",          row[2]),
        ("Query / Link Server", row[3]),
        ("Added By",            row[4]),
        ("Added At",            row[5]),
        ("Changed By",          row[6]),
        ("Changed At",          row[7]),
        ("Changed No",          row[8]),
    ]

    modal = ViewDetailModal(
        title="Row Detail",
        subtitle="Full details for the selected record.",
        fields=fields,
        parent=self,
    )
    modal.exec()
"""

from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QScrollArea, QFrame, QPushButton, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont


class ViewDetailModal(QDialog):
    """
    Generic read-only detail modal.

    Parameters
    ----------
    title : str
        Bold heading shown at the top of the modal.
    subtitle : str
        Smaller descriptive line beneath the title.
    fields : list[tuple[str, str]]
        Ordered list of ``(label, value)`` pairs to display.
    parent : QWidget | None
        Optional parent widget.
    min_width : int
        Minimum dialog width in pixels (default 560).
    """

    def __init__(
        self,
        title: str = "Detail",
        subtitle: str = "",
        fields: list[tuple[str, str]] | None = None,
        parent=None,
        min_width: int = 560,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(min_width)
        # Remove the native title bar (we draw our own close button)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
            }
            """
        )
        self._build_ui(title, subtitle, fields or [])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self, title: str, subtitle: str, fields: list[tuple[str, str]]):
        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 24)
        root.setSpacing(0)

        # ── Header row (title block + X button) ───────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        text_block = QVBoxLayout()
        text_block.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: #111827; background: transparent;"
        )
        text_block.addWidget(title_lbl)

        if subtitle:
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setStyleSheet(
                "font-size: 13px; color: #6B7280; background: transparent;"
            )
            text_block.addWidget(subtitle_lbl)

        header_row.addLayout(text_block)
        header_row.addStretch()

        close_x_btn = QPushButton("✕")
        close_x_btn.setFixedSize(32, 32)
        close_x_btn.setCursor(Qt.PointingHandCursor)
        close_x_btn.setToolTip("Close")
        close_x_btn.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                color: #9CA3AF;
                border: none;
                border-radius: 6px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                color: #111827;
            }
            QPushButton:pressed {
                background-color: #E5E7EB;
            }
            """
        )
        close_x_btn.clicked.connect(self.reject)
        header_row.addWidget(close_x_btn, alignment=Qt.AlignTop)

        root.addLayout(header_row)
        root.addSpacing(20)

        # ── Divider ────────────────────────────────────────────────────
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #E5E7EB; background-color: #E5E7EB; max-height: 1px;")
        root.addWidget(divider)
        root.addSpacing(20)

        # ── Scrollable fields ──────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMaximumHeight(480)

        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 0px;
            }

            QScrollBar::handle:vertical {
                background: #E5E7EB;
                border-radius: 4px;
                min-height: 30px;
            }

            QScrollBar::handle:vertical:hover {
                background: #D1D5DB;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }

            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        fields_layout = QVBoxLayout(container)
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setSpacing(16)

        for label_text, value in fields:
            fields_layout.addWidget(self._make_field(label_text, value))

        fields_layout.addStretch()
        scroll.setWidget(container)
        root.addWidget(scroll)
        root.addSpacing(8)

    # ------------------------------------------------------------------
    # Field widget helper
    # ------------------------------------------------------------------

    @staticmethod
    def _make_field(label_text: str, value: str) -> QWidget:
        wrapper = QWidget()
        wrapper.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(wrapper)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        lbl = QLabel(label_text.upper())
        lbl.setStyleSheet(
            "font-size: 11px; font-weight: 600; color: #6B7280;"
            " letter-spacing: 0.05em; background: transparent;"
        )
        layout.addWidget(lbl)

        val = QLabel(value if value and value.strip() else "—")
        val.setWordWrap(True)
        val.setTextInteractionFlags(Qt.TextSelectableByMouse)
        val.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        val.setStyleSheet(
            "font-size: 13px; color: #111827; background: #F9FAFB;"
            " border: 1px solid #E5E7EB; border-radius: 6px; padding: 8px 10px;"
        )
        layout.addWidget(val)
        return wrapper