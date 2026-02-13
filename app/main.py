import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
    QTabWidget, QTabBar, QWidget, QLabel, QPushButton,
    QSizePolicy, QToolTip, QMenu, QFrame, QAbstractButton,
    QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QSize, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QIcon, QAction, QFont, QColor, QPalette, QCursor, QPainter, QPen, QBrush

# ── Importing your custom components ─────────────────────────────────────────
from layout.sidebar import Sidebar
from pages.master_item import MasterItemPage
from pages.source_data_group import SourceDataPage
from pages.sticker_size import StickerSizePage
from pages.filter_type import FilterTypePage
from pages.brand import BrandPage
from pages.product_type import ProductTypePage
from pages.brand_case import BrandCasePage
from pages.barcode_list import BarcodeListPage
from pages.barcode_editor import BarcodeEditorPage


# ─────────────────────────────────────────────────────────────────────────────
# PAGE REGISTRY  — single source of truth for all navigable pages
# ─────────────────────────────────────────────────────────────────────────────
PAGE_REGISTRY: dict[int, dict] = {
    0:  {"title": "Dashboard",      "class": None,              "icon": "🏠"},
    1:  {"title": "Master Item",    "class": MasterItemPage,    "icon": "📦"},
    2:  {"title": "Source Data",    "class": SourceDataPage,    "icon": "🗄️"},
    3:  {"title": "Sticker Size",   "class": StickerSizePage,   "icon": "🏷️"},
    4:  {"title": "Filter Type",    "class": FilterTypePage,    "icon": "🔽"},
    5:  {"title": "Brand",          "class": BrandPage,         "icon": "🏢"},
    6:  {"title": "Product Type",   "class": ProductTypePage,   "icon": "🗂️"},
    7:  {"title": "Item Master",    "class": MasterItemPage,    "icon": "📋"},
    8:  {"title": "Brand Case",     "class": BrandCasePage,     "icon": "🗃️"},
    9:  {"title": "Barcode Design",   "class": BarcodeListPage,   "icon": "📊"},
    10: {"title": "Barcode Editor", "class": BarcodeEditorPage, "icon": "✏️"},
}


# ─────────────────────────────────────────────────────────────────────────────
# CHROME-STYLE CLOSE BUTTON — fully painted, no image file required
# ─────────────────────────────────────────────────────────────────────────────
class ChromeCloseButton(QAbstractButton):
    """
    Paints its own close button:
      - Idle:   faint × (discoverable but quiet)
      - Hover:  grey circle + dark ×  (Chrome / Edge style)
      - Press:  darker circle + ×
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.ArrowCursor)
        self.setToolTip("Close tab")
        self._hovered = False
        self._pressed = False

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._pressed = False
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._pressed = True
            self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2.0, h / 2.0

        # Background circle (hover / press only)
        if self._pressed:
            p.setBrush(QBrush(QColor("#B0B5BE")))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRect(1, 1, w - 2, h - 2))
        elif self._hovered:
            p.setBrush(QBrush(QColor("#DADDE3")))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QRect(1, 1, w - 2, h - 2))

        # × glyph — subtle when idle, solid dark on hover/press
        cross_color = QColor("#3C4048") if (self._hovered or self._pressed) else QColor("#9CA3AF")
        pen = QPen(cross_color, 1.6, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        offset = 3.8
        p.drawLine(
            QPoint(int(cx - offset), int(cy - offset)),
            QPoint(int(cx + offset), int(cy + offset)),
        )
        p.drawLine(
            QPoint(int(cx + offset), int(cy - offset)),
            QPoint(int(cx - offset), int(cy + offset)),
        )
        p.end()

    def sizeHint(self):
        return QSize(16, 16)


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM TAB BAR — handles pinned tabs, overflow, context menu, tooltips
# ─────────────────────────────────────────────────────────────────────────────
class AppTabBar(QTabBar):
    """
    Production-grade tab bar:
    - Pinned tabs cannot be closed or moved
    - Right-click context menu: Close / Close Others / Close All to the Right
    - Tooltip with full page title on hover
    - Scrollable when tabs overflow
    - Chrome-style close buttons (painted, no image file)
    """

    close_others_requested = Signal(int)
    close_right_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMovable(True)
        self.setTabsClosable(True)
        self.setUsesScrollButtons(True)
        self.setElideMode(Qt.ElideRight)
        self.setExpanding(False)  # don't stretch tabs to fill bar

    # ── Inject ChromeCloseButton on every new tab ──────────────────────────
    def tabInserted(self, index: int):
        super().tabInserted(index)
        self.setTabToolTip(index, self.tabText(index))
        self._install_close_button(index)

    def _install_close_button(self, index: int):
        btn = ChromeCloseButton(self)
        # Use a default-arg capture so the lambda doesn't close over a mutable index
        btn.clicked.connect(lambda _=False, b=btn: self.tabCloseRequested.emit(self._index_of_button(b)))
        self.setTabButton(index, QTabBar.ButtonPosition.RightSide, btn)

    def _index_of_button(self, btn: ChromeCloseButton) -> int:
        for i in range(self.count()):
            if self.tabButton(i, QTabBar.ButtonPosition.RightSide) is btn:
                return i
        return -1

    # ── Right-click context menu ───────────────────────────────────────────
    def contextMenuEvent(self, event):
        index = self.tabAt(event.pos())
        if index < 0:
            return

        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1E293B;
                color: #E2E8F0;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 7px 20px 7px 12px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background: #3B82F6;
                color: white;
            }
            QMenu::item:disabled {
                color: #475569;
            }
            QMenu::separator {
                height: 1px;
                background: #334155;
                margin: 4px 8px;
            }
        """)

        is_pinned = self.tabData(index) == "pinned"

        act_close = QAction("Close Tab", self)
        act_close.setEnabled(not is_pinned)
        act_close.triggered.connect(lambda: self.tabCloseRequested.emit(index))

        act_close_others = QAction("Close Other Tabs", self)
        act_close_others.triggered.connect(lambda: self.close_others_requested.emit(index))

        act_close_right = QAction("Close Tabs to the Right", self)
        act_close_right.triggered.connect(lambda: self.close_right_requested.emit(index))

        menu.addAction(act_close)
        menu.addSeparator()
        menu.addAction(act_close_others)
        menu.addAction(act_close_right)
        menu.exec(event.globalPos())

    # ── Prevent moving pinned tabs ─────────────────────────────────────────
    def mouseMoveEvent(self, event):
        current = self.currentIndex()
        if self.tabData(current) == "pinned":
            return
        super().mouseMoveEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# CUSTOM TAB WIDGET — wraps AppTabBar with close-other/close-right logic
# ─────────────────────────────────────────────────────────────────────────────
class AppTabWidget(QTabWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Swap in our custom tab bar
        self._tab_bar = AppTabBar()
        self.setTabBar(self._tab_bar)

        self.setTabsClosable(True)
        self.setMovable(True)
        self.setDocumentMode(False)

        self._tab_bar.close_others_requested.connect(self._close_others)
        self._tab_bar.close_right_requested.connect(self._close_right)

        self.setStyleSheet(self._stylesheet())

    # ── Stylesheet ─────────────────────────────────────────────────────────
    def _stylesheet(self):
        return """
            QTabWidget::pane {
                border: none;
                border-top: 1px solid #E2E8F0;
                background: #F8FAFC;
            }

            QTabWidget::tab-bar {
                alignment: left;
            }

            QTabBar {
                background: #F1F5F9;
                border-bottom: 1px solid #E2E8F0;
            }

            QTabBar::tab {
                background: transparent;
                color: #64748B;
                padding: 9px 36px 9px 14px;
                border: none;
                border-right: 1px solid #E2E8F0;
                min-width: 110px;
                max-width: 200px;
                font-size: 13px;
                font-weight: 500;
            }

            QTabBar::tab:first {
                border-left: 1px solid #E2E8F0;
            }

            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #1E293B;
                font-weight: 600;
                border-bottom: 2px solid #3B82F6;
            }

            QTabBar::tab:hover:!selected {
                background: #E9EEF5;
                color: #334155;
            }

            /*
             * ChromeCloseButton is injected as a real QWidget via setTabButton().
             * This rule just reserves the correct space — no image needed.
             */
            QTabBar::close-button {
                subcontrol-position: right center;
                subcontrol-origin: padding;
                width: 16px;
                height: 16px;
                margin-right: 4px;
            }

            /* Scroll buttons when tabs overflow */
            QTabBar::scroller {
                width: 28px;
            }

            QTabBar QToolButton {
                background: #E2E8F0;
                border: 1px solid #CBD5E1;
                border-radius: 4px;
                padding: 2px;
            }

            QTabBar QToolButton:hover {
                background: #CBD5E1;
            }
        """

    # ── Tab management helpers ─────────────────────────────────────────────
    def add_pinned_tab(self, widget: QWidget, title: str) -> int:
        """Add a tab that cannot be closed or repositioned."""
        index = self.addTab(widget, title)
        self.tabBar().setTabData(index, "pinned")
        # Hide the close button on pinned tabs
        btn = self.tabBar().tabButton(index, QTabBar.ButtonPosition.RightSide)
        if btn:
            btn.hide()
        return index

    def _close_others(self, keep_index: int):
        """Close all tabs except the one at keep_index and pinned tabs."""
        indices_to_remove = [
            i for i in range(self.count())
            if i != keep_index and self.tabBar().tabData(i) != "pinned"
        ]
        for i in reversed(indices_to_remove):
            self.removeTab(i)

    def _close_right(self, from_index: int):
        """Close all tabs to the right of from_index (excluding pinned)."""
        indices_to_remove = [
            i for i in range(from_index + 1, self.count())
            if self.tabBar().tabData(i) != "pinned"
        ]
        for i in reversed(indices_to_remove):
            self.removeTab(i)

    def find_tab_by_title(self, title: str) -> int | None:
        for i in range(self.count()):
            if self.tabText(i) == title:
                return i
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PAGE FACTORY — isolates widget construction from navigation logic
# ─────────────────────────────────────────────────────────────────────────────
def build_page(page_id: int) -> QWidget:
    """Construct and return the widget for a given page_id."""
    entry = PAGE_REGISTRY.get(page_id)
    if entry is None:
        return _placeholder_page(f"Unknown page (id={page_id})")

    PageClass = entry.get("class")
    if PageClass is None:
        return _placeholder_page(entry["title"])

    try:
        return PageClass()
    except Exception as exc:  # pragma: no cover
        return _placeholder_page(f"Failed to load '{entry['title']}'\n\n{exc}", error=True)


def _placeholder_page(title: str, error: bool = False) -> QLabel:
    label = QLabel(f"{'⚠ ' if error else ''}  {title}")
    label.setAlignment(Qt.AlignCenter)
    color = "#EF4444" if error else "#94A3B8"
    label.setStyleSheet(
        f"font-size: 20px; color: {color}; background: #F8FAFC; font-weight: 500;"
    )
    return label


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD — main window
# ─────────────────────────────────────────────────────────────────────────────
class Dashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Barcode System")
        self.resize(1280, 820)
        self.setMinimumSize(900, 600)

        # ── Central layout ─────────────────────────────────────────────────
        self._central = QWidget()
        self.setCentralWidget(self._central)
        root = QHBoxLayout(self._central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────────
        self._sidebar = Sidebar(nav_callback=self.navigate_to)

        # ── Content: dashboard when no tabs, tab widget when tabs exist ─────
        self._dashboard_widget = build_page(0)
        self._tabs = AppTabWidget()
        self._tabs.tabCloseRequested.connect(self._on_tab_close_requested)
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._dashboard_widget)   # index 0: dashboard
        self._stack.addWidget(self._tabs)              # index 1: tabs
        self._stack.setCurrentIndex(0)                 # start with dashboard, tabs empty

        # ── Assemble ───────────────────────────────────────────────────────
        root.addWidget(self._sidebar)
        root.addWidget(self._stack, stretch=1)

    # ── Navigation ─────────────────────────────────────────────────────────
    def navigate_to(self, page_id: int):
        entry = PAGE_REGISTRY.get(page_id)
        if entry is None:
            return

        title = entry["title"]

        if page_id == 0:
            self._stack.setCurrentWidget(self._dashboard_widget)
            self._sidebar.set_active(0)  # sync sidebar
            return

        existing = self._tabs.find_tab_by_title(title)
        if existing is not None:
            self._stack.setCurrentWidget(self._tabs)
            self._tabs.setCurrentIndex(existing)
            self._sidebar.set_active(page_id)  # sync sidebar
            return

        page_widget = build_page(page_id)

        if page_id == 9 and hasattr(page_widget, "navigate_to_editor"):
            page_widget.navigate_to_editor.connect(
                lambda: self.navigate_to(10)
            )

        idx = self._tabs.addTab(page_widget, title)
        self._stack.setCurrentWidget(self._tabs)
        self._tabs.setCurrentIndex(idx)
        self._sidebar.set_active(page_id)

    def _on_tab_changed(self, index: int):
        if self._tabs.count() == 0:
            self._stack.setCurrentWidget(self._dashboard_widget)
            self._sidebar.set_active(0)  # reset to Dashboard
        else:
            title = self._tabs.tabText(index)
            for pid, entry in PAGE_REGISTRY.items():
                if entry["title"] == title:
                    self._sidebar.set_active(pid)  # sync sidebar
                    break


    # ── Tab close handling ─────────────────────────────────────────────────
    def _on_tab_close_requested(self, index: int):
        """Close the tab; if no tabs remain, show dashboard."""
        self._tabs.removeTab(index)
        if self._tabs.count() == 0:
            self._stack.setCurrentWidget(self._dashboard_widget)

    # ── Keyboard shortcuts ─────────────────────────────────────────────────
    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        # Ctrl+W → close current tab (only when showing tabs and have tabs)
        if modifiers == Qt.ControlModifier and key == Qt.Key_W:
            if self._stack.currentWidget() is self._tabs and self._tabs.count() > 0:
                self._on_tab_close_requested(self._tabs.currentIndex())

        # Ctrl+Tab / Ctrl+Shift+Tab → cycle tabs (only when showing tabs)
        elif self._stack.currentWidget() is self._tabs and self._tabs.count() > 0:
            if modifiers == Qt.ControlModifier and key == Qt.Key_Tab:
                count = self._tabs.count()
                self._tabs.setCurrentIndex((self._tabs.currentIndex() + 1) % count)
            elif modifiers == (Qt.ControlModifier | Qt.ShiftModifier) and key == Qt.Key_Tab:
                count = self._tabs.count()
                self._tabs.setCurrentIndex((self._tabs.currentIndex() - 1) % count)
            elif modifiers == Qt.ControlModifier and Qt.Key_1 <= key <= Qt.Key_9:
                target = key - Qt.Key_1
                if target < self._tabs.count():
                    self._tabs.setCurrentIndex(target)

        else:
            super().keyPressEvent(event)


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Crisp base font
    font = QFont("Segoe UI", 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)

    window = Dashboard()
    window.show()
    sys.exit(app.exec())