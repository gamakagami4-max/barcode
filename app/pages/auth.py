import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QGraphicsDropShadowEffect,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Signal
from PySide6.QtGui import QFont, QColor, QPalette, QIcon, QPixmap, QPainter, QBrush, QPen
import qtawesome as qta

# Import authenticate from the user repo
from server.repositories.muser_repo import authenticate


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN WINDOW
# ─────────────────────────────────────────────────────────────────────────────

class LoginWindow(QWidget):
    login_success = Signal(dict)   # emits user dict on successful login

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barcode System — Login")
        self.setFixedSize(420, 540)
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self._drag_pos = None

        self._build_ui()
        self._center_on_screen()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)

        # Card frame
        self._card = QFrame()
        self._card.setObjectName("card")
        self._card.setStyleSheet("""
            #card {
                background: #FFFFFF;
                border-radius: 16px;
            }
        """)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 60))
        self._card.setGraphicsEffect(shadow)

        card_layout = QVBoxLayout(self._card)
        card_layout.setContentsMargins(40, 44, 40, 44)
        card_layout.setSpacing(0)

        # ── Close button ───────────────────────────────────────────────────
        close_row = QHBoxLayout()
        close_row.setContentsMargins(0, 0, 0, 0)
        close_row.addStretch()
        self._close_btn = QPushButton()
        self._close_btn.setIcon(qta.icon("fa5s.times", color="#9CA3AF"))
        self._close_btn.setIconSize(QSize(14, 14))
        self._close_btn.setFixedSize(28, 28)
        self._close_btn.setFlat(True)
        self._close_btn.setCursor(Qt.PointingHandCursor)
        self._close_btn.setFocusPolicy(Qt.NoFocus)
        self._close_btn.setStyleSheet("""
            QPushButton {
                background: transparent; border: none; border-radius: 14px;
            }
            QPushButton:hover { background: #F1F5F9; }
        """)
        self._close_btn.clicked.connect(QApplication.quit)
        close_row.addWidget(self._close_btn)
        card_layout.addLayout(close_row)

        # ── Logo / icon ────────────────────────────────────────────────────
        logo_container = QHBoxLayout()
        logo_container.setAlignment(Qt.AlignHCenter)
        logo_circle = QWidget()
        logo_circle.setFixedSize(64, 64)
        logo_circle.setStyleSheet("""
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #3B82F6, stop:1 #6366F1
            );
            border-radius: 32px;
        """)
        ic_layout = QHBoxLayout(logo_circle)
        ic_layout.setContentsMargins(0, 0, 0, 0)
        ic_layout.setAlignment(Qt.AlignCenter)
        ic_lbl = QLabel()
        ic_lbl.setPixmap(qta.icon("fa5s.barcode", color="white").pixmap(QSize(28, 28)))
        ic_lbl.setStyleSheet("background: transparent;")
        ic_layout.addWidget(ic_lbl)
        logo_container.addWidget(logo_circle)
        card_layout.addLayout(logo_container)

        card_layout.addSpacing(20)

        # ── Title ──────────────────────────────────────────────────────────
        title = QLabel("Barcode System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 22px;
            font-weight: 700;
            color: #0F172A;
        """)
        card_layout.addWidget(title)

        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("font-size: 13px; color: #94A3B8; margin-top: 4px;")
        card_layout.addWidget(subtitle)

        card_layout.addSpacing(32)

        # ── Username field ─────────────────────────────────────────────────
        card_layout.addWidget(self._make_label("Username"))
        self._username_field = self._make_input("fa5s.user", "Enter your username")
        card_layout.addWidget(self._username_field)

        card_layout.addSpacing(14)

        # ── Password field ─────────────────────────────────────────────────
        card_layout.addWidget(self._make_label("Password"))
        self._password_field = self._make_input("fa5s.lock", "Enter your password", is_password=True)
        card_layout.addWidget(self._password_field)

        card_layout.addSpacing(6)

        # ── Error label ────────────────────────────────────────────────────
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("""
            font-size: 12px;
            color: #EF4444;
            font-weight: 500;
            padding: 4px 0;
        """)
        self._error_label.setVisible(False)
        card_layout.addWidget(self._error_label)

        card_layout.addSpacing(8)

        # ── Login button ───────────────────────────────────────────────────
        self._login_btn = QPushButton("Sign In")
        self._login_btn.setFixedHeight(44)
        self._login_btn.setCursor(Qt.PointingHandCursor)
        self._login_btn.setFocusPolicy(Qt.NoFocus)
        self._login_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #6366F1
                );
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #4F46E5
                );
            }
            QPushButton:pressed {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #4338CA
                );
            }
        """)
        self._login_btn.clicked.connect(self._on_login)
        card_layout.addWidget(self._login_btn)

        # Allow Enter key to submit
        self._username_field.findChild(QLineEdit).returnPressed.connect(self._on_login)
        self._password_field.findChild(QLineEdit).returnPressed.connect(self._on_login)

        card_layout.addStretch()

        # ── Footer ─────────────────────────────────────────────────────────
        footer = QLabel("© Barcode System")
        footer.setAlignment(Qt.AlignCenter)
        footer.setStyleSheet("font-size: 11px; color: #CBD5E1;")
        card_layout.addWidget(footer)

        outer.addWidget(self._card)

    def _make_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 12px;
            font-weight: 600;
            color: #374151;
            margin-bottom: 4px;
        """)
        return lbl

    def _make_input(self, icon_name: str, placeholder: str, is_password=False) -> QWidget:
        """Returns a QWidget wrapping an icon + QLineEdit in a styled container."""
        wrapper = QWidget()
        wrapper.setFixedHeight(44)
        wrapper.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border: 1.5px solid #E2E8F0;
                border-radius: 10px;
            }
            QWidget:focus-within {
                border: 1.5px solid #3B82F6;
                background: #FFFFFF;
            }
        """)

        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color="#94A3B8").pixmap(QSize(14, 14)))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.setFixedWidth(16)
        layout.addWidget(icon_lbl)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if is_password:
            field.setEchoMode(QLineEdit.Password)
        field.setStyleSheet("""
            QLineEdit {
                background: transparent;
                border: none;
                font-size: 13px;
                color: #0F172A;
                outline: none;
            }
            QLineEdit::placeholder { color: #CBD5E1; }
        """)
        field.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(field)

        if is_password:
            self._toggle_btn = QPushButton()
            self._toggle_btn.setIcon(qta.icon("fa5s.eye-slash", color="#94A3B8"))
            self._toggle_btn.setIconSize(QSize(14, 14))
            self._toggle_btn.setFixedSize(24, 24)
            self._toggle_btn.setFlat(True)
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.setFocusPolicy(Qt.NoFocus)
            self._toggle_btn.setCheckable(True)
            self._toggle_btn.setStyleSheet("""
                QPushButton { background: transparent; border: none; }
            """)
            self._toggle_btn.toggled.connect(
                lambda checked, f=field: (
                    f.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),
                    self._toggle_btn.setIcon(
                        qta.icon("fa5s.eye" if checked else "fa5s.eye-slash", color="#94A3B8")
                    )
                )
            )
            layout.addWidget(self._toggle_btn)

        return wrapper

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_username(self) -> str:
        return self._username_field.findChild(QLineEdit).text().strip()

    def _get_password(self) -> str:
        return self._password_field.findChild(QLineEdit).text()

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.setVisible(True)
        self._shake_card()

    def _clear_error(self):
        self._error_label.setText("")
        self._error_label.setVisible(False)

    def _shake_card(self):
        """Brief horizontal shake animation on the card for bad login."""
        self._shake = QPropertyAnimation(self._card, b"pos")
        self._shake.setDuration(300)
        orig = self._card.pos()
        self._shake.setKeyValueAt(0.0, orig)
        self._shake.setKeyValueAt(0.15, orig.__class__(orig.x() - 8, orig.y()))
        self._shake.setKeyValueAt(0.35, orig.__class__(orig.x() + 8, orig.y()))
        self._shake.setKeyValueAt(0.55, orig.__class__(orig.x() - 5, orig.y()))
        self._shake.setKeyValueAt(0.75, orig.__class__(orig.x() + 5, orig.y()))
        self._shake.setKeyValueAt(1.0, orig)
        self._shake.setEasingCurve(QEasingCurve.OutElastic)
        self._shake.start()

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2,
        )

    # ── Login logic ───────────────────────────────────────────────────────────

    def _on_login(self):
        self._clear_error()
        username = self._get_username()
        password = self._get_password()

        if not username:
            self._show_error("Please enter your username.")
            return
        if not password:
            self._show_error("Please enter your password.")
            return

        try:
            user = authenticate(username, password)
        except Exception as e:
            self._show_error(f"Connection error: {e}")
            return

        if user is None:
            self._show_error("Invalid username or password.")
            return

        # Success — emit signal and close
        self.login_success.emit(user)
        self.close()

    # ── Frameless window drag ─────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT (standalone test)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    login = LoginWindow()

    def on_success(user: dict):
        print(f"Logged in as: {user}")
        # Import here to avoid circular issues during standalone test
        from layout.dashboard import Dashboard
        window = Dashboard(current_user=user)
        window.show()

    login.login_success.connect(on_success)
    login.show()

    sys.exit(app.exec())