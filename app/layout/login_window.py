import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFrame, QSizePolicy,
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Signal, QPoint
from PySide6.QtGui import QFont, QColor, QPalette
import qtawesome as qta

from server.repositories.muser_repo import authenticate


# ─────────────────────────────────────────────────────────────────────────────
# LOGIN WINDOW  —  standard OS window, same as Dashboard ("Barcode System")
# ─────────────────────────────────────────────────────────────────────────────

class LoginWindow(QWidget):
    login_success = Signal(dict)

    def __init__(self):
        super().__init__()
        # ── Standard OS window — matches the Dashboard title bar exactly ──
        self.setWindowTitle("Barcode System")
        self.setFixedSize(380, 440)
        # No FramelessWindowHint — let the OS draw the native title bar
        self.setStyleSheet("QWidget { background-color: #E2E8F0; }")

        self._build_ui()
        self._center_on_screen()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(40, 36, 40, 36)
        root.setSpacing(0)

        # ── Avatar ────────────────────────────────────────────────────────
        logo_row = QHBoxLayout()
        logo_row.setAlignment(Qt.AlignHCenter)

        avatar = QWidget()
        avatar.setFixedSize(52, 52)
        avatar.setStyleSheet("""
            background-color: #EFF6FF;
            border: 2px solid #DBEAFE;
            border-radius: 26px;
        """)
        av_layout = QHBoxLayout(avatar)
        av_layout.setContentsMargins(0, 0, 0, 0)
        av_layout.setAlignment(Qt.AlignCenter)
        av_icon = QLabel()
        av_icon.setStyleSheet("background: transparent; border: none;")
        av_icon.setPixmap(qta.icon("fa5s.barcode", color="#2563EB").pixmap(QSize(22, 22)))
        av_layout.addWidget(av_icon)

        logo_row.addWidget(avatar)
        root.addLayout(logo_row)

        root.addSpacing(16)

        # ── Title ──────────────────────────────────────────────────────────
        title = QLabel("Barcode System")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("""
            font-size: 20px; font-weight: 700;
            color: #111827; background: transparent;
        """)
        root.addWidget(title)

        subtitle = QLabel("Sign in to your account")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("""
            font-size: 12px; color: #94A3B8;
            margin-top: 3px; background: transparent;
        """)
        root.addWidget(subtitle)

        root.addSpacing(28)

        # ── Divider ────────────────────────────────────────────────────────
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CBD5E1; background: #CBD5E1; border: none; max-height: 1px;")
        root.addWidget(line)

        root.addSpacing(20)

        # ── Username ───────────────────────────────────────────────────────
        root.addWidget(self._field_label("Username"))
        self._username_field = self._make_input("fa5s.user", "Enter your username")
        root.addWidget(self._username_field)

        root.addSpacing(12)

        # ── Password ───────────────────────────────────────────────────────
        root.addWidget(self._field_label("Password"))
        self._password_field = self._make_input(
            "fa5s.lock", "Enter your password", is_password=True
        )
        root.addWidget(self._password_field)

        root.addSpacing(6)

        # ── Error label ────────────────────────────────────────────────────
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignCenter)
        self._error_label.setStyleSheet("""
            font-size: 11px; color: #EF4444;
            font-weight: 500; background: transparent; padding: 3px 0;
        """)
        self._error_label.setVisible(False)
        root.addWidget(self._error_label)

        root.addSpacing(10)

        # ── Sign In button ─────────────────────────────────────────────────
        self._login_btn = QPushButton("Sign In")
        self._login_btn.setFixedHeight(40)
        self._login_btn.setCursor(Qt.PointingHandCursor)
        self._login_btn.setFocusPolicy(Qt.NoFocus)
        self._login_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover   { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E40AF; }
        """)
        self._login_btn.clicked.connect(self._on_login)
        root.addWidget(self._login_btn)

        # Enter key support
        self._username_field.findChild(QLineEdit).returnPressed.connect(self._on_login)
        self._password_field.findChild(QLineEdit).returnPressed.connect(self._on_login)

        root.addStretch()

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _field_label(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 11px; font-weight: 600;
            color: #475569; margin-bottom: 4px; background: transparent;
        """)
        return lbl

    def _make_input(self, icon_name: str, placeholder: str, is_password=False) -> QWidget:
        wrapper = QWidget()
        wrapper.setFixedHeight(40)
        wrapper.setStyleSheet("""
            QWidget {
                background-color: #F1F5F9;
                border: 1px solid #CBD5E1;
                border-radius: 8px;
            }
            QWidget:focus-within {
                border: 1.5px solid #3B82F6;
                background-color: #FFFFFF;
            }
        """)

        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(8)

        icon_lbl = QLabel()
        icon_lbl.setPixmap(qta.icon(icon_name, color="#94A3B8").pixmap(QSize(13, 13)))
        icon_lbl.setStyleSheet("background: transparent; border: none;")
        icon_lbl.setFixedWidth(16)
        layout.addWidget(icon_lbl)

        field = QLineEdit()
        field.setPlaceholderText(placeholder)
        if is_password:
            field.setEchoMode(QLineEdit.Password)
        field.setStyleSheet("""
            QLineEdit {
                background: transparent; border: none;
                font-size: 13px; color: #0F172A;
            }
            QLineEdit::placeholder { color: #CBD5E1; }
        """)
        field.setFocusPolicy(Qt.StrongFocus)
        layout.addWidget(field)

        if is_password:
            self._toggle_btn = QPushButton()
            self._toggle_btn.setIcon(qta.icon("fa5s.eye-slash", color="#94A3B8"))
            self._toggle_btn.setIconSize(QSize(13, 13))
            self._toggle_btn.setFixedSize(22, 22)
            self._toggle_btn.setFlat(True)
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.setFocusPolicy(Qt.NoFocus)
            self._toggle_btn.setCheckable(True)
            self._toggle_btn.setStyleSheet(
                "QPushButton { background: transparent; border: none; }"
            )
            self._toggle_btn.toggled.connect(
                lambda checked, f=field: (
                    f.setEchoMode(QLineEdit.Normal if checked else QLineEdit.Password),
                    self._toggle_btn.setIcon(
                        qta.icon("fa5s.eye" if checked else "fa5s.eye-slash", color="#94A3B8")
                    ),
                )
            )
            layout.addWidget(self._toggle_btn)

        return wrapper

    # ── Login logic ───────────────────────────────────────────────────────────

    def _get_username(self) -> str:
        return self._username_field.findChild(QLineEdit).text().strip()

    def _get_password(self) -> str:
        return self._password_field.findChild(QLineEdit).text()

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.setVisible(True)
        self._shake()

    def _clear_error(self):
        self._error_label.setText("")
        self._error_label.setVisible(False)

    def _shake(self):
        """Shake the whole window on bad login."""
        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(300)
        orig = self.pos()
        anim.setKeyValueAt(0.0,  orig)
        anim.setKeyValueAt(0.15, QPoint(orig.x() - 7, orig.y()))
        anim.setKeyValueAt(0.35, QPoint(orig.x() + 7, orig.y()))
        anim.setKeyValueAt(0.55, QPoint(orig.x() - 4, orig.y()))
        anim.setKeyValueAt(0.75, QPoint(orig.x() + 4, orig.y()))
        anim.setKeyValueAt(1.0,  orig)
        anim.setEasingCurve(QEasingCurve.OutElastic)
        anim.start()
        self._shake_anim = anim  # keep reference

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(
            (screen.width()  - self.width())  // 2,
            (screen.height() - self.height()) // 2,
        )

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

        self.login_success.emit(user)
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    login = LoginWindow()
    login.login_success.connect(lambda u: print("Logged in:", u))
    login.show()
    sys.exit(app.exec())