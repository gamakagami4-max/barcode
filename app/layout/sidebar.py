import qtawesome as qta
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QWidget, QScrollArea, QGraphicsDropShadowEffect, QGraphicsOpacityEffect
)
from PySide6.QtCore import Qt, QSize, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, Signal
from PySide6.QtGui import QColor

# --- Style Constants ---
STYLE_NORMAL = """
    QPushButton {
        text-align: left; 
        padding: 9px 14px; 
        border: none;
        color: #475569; 
        font-size: 13px; 
        background: transparent;
        outline: none;
        border-radius: 6px;
    }
    QPushButton:hover { 
        color: #1E293B; 
        background-color: #F1F5F9;
    }
"""

STYLE_ACTIVE = """
    QPushButton {
        text-align: left; 
        padding: 9px 14px; 
        border: none;
        color: #1E40AF; 
        font-size: 13px; 
        font-weight: 600;
        background-color: #EFF6FF;
        border-radius: 6px;
        outline: none;
    }
"""

class MenuItem(QWidget):
    def __init__(self, title, icon_name, on_click=None):
        super().__init__()
        self.on_click = on_click
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        
        icon_label = QLabel()
        icon_label.setPixmap(qta.icon(icon_name, color="#475569").pixmap(QSize(18, 18)))
        
        text_label = QLabel(title)
        text_label.setStyleSheet("font-size: 13px; font-weight: 500; color: #1E293B; border: none; background: transparent;")
        
        layout.addWidget(icon_label)
        layout.addSpacing(10)
        layout.addWidget(text_label)
        layout.addStretch()

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QWidget { background: transparent; border-radius: 6px; }
            QWidget:hover { background-color: #F1F5F9; }
        """)

    def mousePressEvent(self, event):
        if self.on_click: self.on_click()

class CollapsibleMenu(QWidget):
    def __init__(self, title, icon_name, sub_items_dict, sidebar_ref):
        super().__init__()
        self.sidebar_ref = sidebar_ref
        self.sub_buttons = [] 
        self.is_expanded = False
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # --- Header ---
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("background: transparent;")
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(14, 10, 14, 10)
        
        self.icon_label = QLabel()
        self.icon_label.setStyleSheet("background: transparent;")
        self.icon_label.setPixmap(qta.icon(icon_name, color="#475569").pixmap(QSize(18, 18)))
        
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-size: 13px; font-weight: 600; color: #1E293B; border: none; background: transparent;")
        
        self.chevron_label = QLabel()
        self.chevron_label.setStyleSheet("background: transparent; border: none;")
        self.update_chevron()

        self.header_layout.addWidget(self.icon_label)
        self.header_layout.addSpacing(10)
        self.header_layout.addWidget(self.title_label)
        self.header_layout.addStretch()
        self.header_layout.addWidget(self.chevron_label)

        self.header_widget.setCursor(Qt.PointingHandCursor)
        self.header_widget.mousePressEvent = self.toggle_expansion
        
        # Add hover stylesheet with transition
        self.header_widget.enterEvent = lambda event: self.animate_hover(True)
        self.header_widget.leaveEvent = lambda event: self.animate_hover(False)
        
        self.main_layout.addWidget(self.header_widget)

        # --- Sub-menu Container ---
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        self.container_layout.setContentsMargins(28, 4, 0, 4) 
        self.container_layout.setSpacing(1)
        
        for item_text, callback in sub_items_dict.items():
            sub_btn = QPushButton(item_text)
            sub_btn.setCursor(Qt.PointingHandCursor)
            sub_btn.setFocusPolicy(Qt.NoFocus) 
            sub_btn.setStyleSheet(STYLE_NORMAL)
            
            sub_btn.clicked.connect(lambda chk=False, b=sub_btn, c=callback: self.on_sub_clicked(b, c))
            
            self.sub_buttons.append(sub_btn)
            self.container_layout.addWidget(sub_btn)
        
        self.container.setVisible(False)
        self.container.setMaximumHeight(0)
        self.main_layout.addWidget(self.container)
        
        # Animation setup
        self.chevron_animation = None

    def animate_hover(self, is_entering):
        """Smooth hover animation"""
        if is_entering:
            self.header_widget.setStyleSheet("""
                QWidget { background-color: #F1F5F9; border-radius: 6px; }
            """)
        else:
            self.header_widget.setStyleSheet("""
                QWidget { background: transparent; border-radius: 6px; }
            """)

    def on_sub_clicked(self, button, callback):
        """Clears previous selections across the sidebar and highlights the clicked button."""
        self.sidebar_ref.clear_all_selections()
        button.setStyleSheet(STYLE_ACTIVE)
        callback()

    def update_chevron(self):
        """Update chevron icon with rotation animation"""
        icon_code = "fa5s.chevron-down" if self.is_expanded else "fa5s.chevron-right"
        self.chevron_label.setPixmap(qta.icon(icon_code, color="#94A3B8").pixmap(QSize(10, 10)))

    def toggle_expansion(self, event):
        """Toggle expansion with smooth animation"""
        self.is_expanded = not self.is_expanded
        
        # Update chevron
        self.update_chevron()
        
        # Animate container expansion
        if self.is_expanded:
            self.container.setVisible(True)
            # Calculate the target height
            target_height = self.container_layout.sizeHint().height()
            
            # Height animation
            self.height_anim = QPropertyAnimation(self.container, b"maximumHeight")
            self.height_anim.setDuration(250)
            self.height_anim.setStartValue(0)
            self.height_anim.setEndValue(target_height)
            self.height_anim.setEasingCurve(QEasingCurve.OutCubic)
            
            # Opacity animation
            self.opacity_effect = QGraphicsOpacityEffect()
            self.container.setGraphicsEffect(self.opacity_effect)
            
            self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.opacity_anim.setDuration(250)
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
            
            # Start animations
            self.height_anim.start()
            self.opacity_anim.start()
        else:
            # Height animation
            self.height_anim = QPropertyAnimation(self.container, b"maximumHeight")
            self.height_anim.setDuration(200)
            self.height_anim.setStartValue(self.container.height())
            self.height_anim.setEndValue(0)
            self.height_anim.setEasingCurve(QEasingCurve.InCubic)
            
            # Opacity animation
            if self.container.graphicsEffect():
                self.opacity_anim = QPropertyAnimation(self.container.graphicsEffect(), b"opacity")
                self.opacity_anim.setDuration(200)
                self.opacity_anim.setStartValue(1.0)
                self.opacity_anim.setEndValue(0.0)
                self.opacity_anim.setEasingCurve(QEasingCurve.InCubic)
                self.opacity_anim.start()
            
            # Hide after animation
            self.height_anim.finished.connect(lambda: self.container.setVisible(False))
            self.height_anim.start()

class Sidebar(QFrame):
    # Signal emitted when sidebar collapse state changes
    collapsed_changed = Signal(bool)
    
    def __init__(self, nav_callback):
        super().__init__()
        self.nav_callback = nav_callback
        self.menus = [] 
        self.is_collapsed = False
        
        self.expanded_width = 270
        self.collapsed_width = 60
        
        self.setFixedWidth(self.expanded_width)
        self.setStyleSheet("""
            QFrame { 
                background-color: #FAFAFA; 
                border-right: 1px solid #E5E7EB; 
            }
        """)
        
        self.main_sidebar_layout = QVBoxLayout(self)
        self.main_sidebar_layout.setContentsMargins(0, 0, 0, 0)
        self.main_sidebar_layout.setSpacing(0)

        # Toggle button container (always visible at top)
        self.toggle_container = QWidget()
        self.toggle_container.setStyleSheet("background: transparent;")
        toggle_layout = QHBoxLayout(self.toggle_container)
        toggle_layout.setContentsMargins(14, 14, 14, 14)
        
        self.toggle_btn = QPushButton()
        self.toggle_btn.setIcon(qta.icon("fa5s.bars", color="#475569"))
        self.toggle_btn.setIconSize(QSize(18, 18))
        self.toggle_btn.setFixedSize(36, 36)
        self.toggle_btn.setCursor(Qt.PointingHandCursor)
        self.toggle_btn.setFocusPolicy(Qt.NoFocus)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 8px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #F1F5F9;
            }
        """)
        self.toggle_btn.clicked.connect(self.toggle_sidebar)
        
        toggle_layout.addWidget(self.toggle_btn)
        toggle_layout.addStretch()
        
        self.main_sidebar_layout.addWidget(self.toggle_container)

        # Scroll Area
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setStyleSheet("""
            QScrollArea { 
                background: transparent; 
                border: none; 
            }
            QScrollBar:vertical { 
                background: transparent;
                width: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical { 
                background: #D1D5DB;
                border-radius: 3px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover { 
                background: #9CA3AF;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical,
            QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        self.content_container = QWidget()
        self.content_container.setObjectName("content_container")
        self.content_container.setStyleSheet("#content_container { background: #FAFAFA; }")
        
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(14, 10, 14, 20)
        self.content_layout.setSpacing(3)

        self.scroll.setWidget(self.content_container)
        self.main_sidebar_layout.addWidget(self.scroll)
        
        self.build_ui()

    def toggle_sidebar(self):
        """Toggle sidebar between expanded and collapsed states with smooth animation"""
        self.is_collapsed = not self.is_collapsed
        
        # Update toggle button icon
        if self.is_collapsed:
            self.toggle_btn.setIcon(qta.icon("fa5s.chevron-right", color="#475569"))
        else:
            self.toggle_btn.setIcon(qta.icon("fa5s.bars", color="#475569"))
        
        # Animate width change
        self.width_anim = QPropertyAnimation(self, b"minimumWidth")
        self.width_anim.setDuration(300)
        self.width_anim.setStartValue(self.width())
        self.width_anim.setEndValue(self.collapsed_width if self.is_collapsed else self.expanded_width)
        self.width_anim.setEasingCurve(QEasingCurve.InOutCubic)
        
        self.width_anim_max = QPropertyAnimation(self, b"maximumWidth")
        self.width_anim_max.setDuration(300)
        self.width_anim_max.setStartValue(self.width())
        self.width_anim_max.setEndValue(self.collapsed_width if self.is_collapsed else self.expanded_width)
        self.width_anim_max.setEasingCurve(QEasingCurve.InOutCubic)
        
        # Fade content in/out
        if self.is_collapsed:
            # Fade out content before collapsing
            self.opacity_effect = QGraphicsOpacityEffect()
            self.content_container.setGraphicsEffect(self.opacity_effect)
            
            self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.opacity_anim.setDuration(200)
            self.opacity_anim.setStartValue(1.0)
            self.opacity_anim.setEndValue(0.0)
            self.opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
            self.opacity_anim.finished.connect(lambda: self.content_container.setVisible(False))
            self.opacity_anim.start()
            
            # Hide user panel
            if hasattr(self, 'user_panel'):
                self.user_opacity_effect = QGraphicsOpacityEffect()
                self.user_panel.setGraphicsEffect(self.user_opacity_effect)
                
                self.user_opacity_anim = QPropertyAnimation(self.user_opacity_effect, b"opacity")
                self.user_opacity_anim.setDuration(200)
                self.user_opacity_anim.setStartValue(1.0)
                self.user_opacity_anim.setEndValue(0.0)
                self.user_opacity_anim.setEasingCurve(QEasingCurve.OutCubic)
                self.user_opacity_anim.finished.connect(lambda: self.user_panel.setVisible(False))
                self.user_opacity_anim.start()
        else:
            # Show content first, then fade in
            self.content_container.setVisible(True)
            if hasattr(self, 'user_panel'):
                self.user_panel.setVisible(True)
            
            self.opacity_effect = QGraphicsOpacityEffect()
            self.content_container.setGraphicsEffect(self.opacity_effect)
            
            self.opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
            self.opacity_anim.setDuration(300)
            self.opacity_anim.setStartValue(0.0)
            self.opacity_anim.setEndValue(1.0)
            self.opacity_anim.setEasingCurve(QEasingCurve.InCubic)
            self.opacity_anim.start()
            
            if hasattr(self, 'user_panel'):
                self.user_opacity_effect = QGraphicsOpacityEffect()
                self.user_panel.setGraphicsEffect(self.user_opacity_effect)
                
                self.user_opacity_anim = QPropertyAnimation(self.user_opacity_effect, b"opacity")
                self.user_opacity_anim.setDuration(300)
                self.user_opacity_anim.setStartValue(0.0)
                self.user_opacity_anim.setEndValue(1.0)
                self.user_opacity_anim.setEasingCurve(QEasingCurve.InCubic)
                self.user_opacity_anim.start()
        
        self.width_anim.start()
        self.width_anim_max.start()
        
        # Emit signal for parent widget to adjust layout
        self.collapsed_changed.emit(self.is_collapsed)

    def clear_all_selections(self):
        """Resets all sidebar sub-buttons to the normal style with fade animation."""
        for menu in self.menus:
            for btn in menu.sub_buttons:
                btn.setStyleSheet(STYLE_NORMAL)

    def build_ui(self):
        title_container = QWidget()
        title_container.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        t_layout = QVBoxLayout(title_container)
        t_layout.setContentsMargins(12, 8, 12, 20)
        
        title_label = QLabel("Barcode System")
        title_label.setStyleSheet("""
            font-size: 17px; 
            font-weight: 700; 
            color: #111827; 
            background: transparent;
        """)
        
        t_layout.addWidget(title_label)
        
        self.content_layout.addWidget(title_container)

        # Menus
        self.content_layout.addWidget(self.create_label("MENU"))
        self.content_layout.addSpacing(4)

        # File Menu
        file_items = {"Dashboard": lambda: self.nav_callback(0)}
        file_menu = CollapsibleMenu("File", "fa5s.folder", file_items, self)
        self.content_layout.addWidget(file_menu)
        self.menus.append(file_menu)
        
        self.content_layout.addSpacing(2)
        
        # Master Menu
        master_items = {
            "Source Data Group": lambda: self.nav_callback(2),
            "Master Sticker": lambda: self.nav_callback(3),
            "Master Filter Type": lambda: self.nav_callback(4),
            "Master Brand": lambda: self.nav_callback(5),
            "Master Product Type": lambda: self.nav_callback(6),
            "Master Item": lambda: self.nav_callback(7),
            "Master Brand Case": lambda: self.nav_callback(8)
        }
        master_menu = CollapsibleMenu("Master", "fa5s.database", master_items, self)
        self.content_layout.addWidget(master_menu)
        self.menus.append(master_menu)

        self.content_layout.addSpacing(2)

        # Barcode Menu
        barcode_items = {
            "Barcode Design": lambda: self.nav_callback(9),
            "Barcode Editor": lambda: self.nav_callback(10)}
        barcode_menu = CollapsibleMenu("Barcode", "fa5s.barcode", barcode_items, self)
        self.content_layout.addWidget(barcode_menu)
        self.menus.append(barcode_menu)
       
        self.content_layout.addStretch()

        # Professional User Panel
        self.user_panel = QWidget()
        self.user_panel.setStyleSheet("""
            QWidget {
                background-color: #FFFFFF;
                border-top: 1px solid #E5E7EB;
            }
        """)
        user_layout = QHBoxLayout(self.user_panel)
        user_layout.setContentsMargins(16, 14, 16, 14)
        
        # Professional Avatar
        avatar_container = QWidget()
        avatar_container.setFixedSize(36, 36)
        avatar_container.setStyleSheet("""
            background-color: #EFF6FF;
            border: 2px solid #DBEAFE;
            border-radius: 18px;
        """)
        avatar_layout = QHBoxLayout(avatar_container)
        avatar_layout.setContentsMargins(0, 0, 0, 0)
        avatar_layout.setAlignment(Qt.AlignCenter)
        
        avatar = QLabel()
        avatar.setStyleSheet("background: transparent; border: none;")
        avatar.setPixmap(qta.icon("fa5s.user", color="#2563EB").pixmap(QSize(16, 16)))
        avatar_layout.addWidget(avatar)
        
        user_info = QLabel("Administrator<br><span style='color:#6B7280; font-size: 10px;'>System User</span>")
        user_info.setTextFormat(Qt.RichText)
        user_info.setStyleSheet("""
            font-size: 12px; 
            font-weight: 600; 
            color: #111827;
            background: transparent;
        """)
        
        # Settings icon
        settings_btn = QPushButton()
        settings_btn.setIcon(qta.icon("fa5s.cog", color="#9CA3AF"))
        settings_btn.setIconSize(QSize(16, 16))
        settings_btn.setFixedSize(28, 28)
        settings_btn.setCursor(Qt.PointingHandCursor)
        settings_btn.setFocusPolicy(Qt.NoFocus)
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                border-radius: 6px;
                outline: none;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
        """)
        
        user_layout.addWidget(avatar_container)
        user_layout.addSpacing(10)
        user_layout.addWidget(user_info)
        user_layout.addStretch()
        user_layout.addWidget(settings_btn)
        
        self.main_sidebar_layout.addWidget(self.user_panel)

    def create_label(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet("""
            font-size: 10px; 
            color: #9CA3AF; 
            font-weight: 700; 
            letter-spacing: 0.8px;
            padding: 6px 12px 4px 12px; 
            background: transparent;
        """)
        return lbl