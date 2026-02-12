import qtawesome as qta
from PySide6.QtWidgets import QPushButton
from PySide6.QtCore import Qt, QSize

class StandardButton(QPushButton):
    """
    A custom button component with pre-defined styles for 
    Primary, Secondary, and Danger variants.
    """
    def __init__(self, text, icon_name=None, variant="primary", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(38)
        
        # Variants and their color schemes (Background, Hover, Text)
        self.variants = {
            "primary":   ("#3B82F6", "#2563EB", "#FFFFFF"),
            "secondary": ("#FFFFFF", "#F9FAFB", "#374151"),
            "danger":    ("#EF4444", "#DC2626", "#FFFFFF"),
            "success":   ("#10B981", "#059669", "#FFFFFF"),
        }
        
        bg, hover, text_color = self.variants.get(variant, self.variants["primary"])
        
        # Border only for secondary
        border_style = "border: 1px solid #E5E7EB;" if variant == "secondary" else "border: none;"
        
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {text_color};
                border-radius: 6px;
                padding: 0px 16px;
                font-weight: 600;
                font-size: 13px;
                {border_style}
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
            QPushButton:pressed {{
                background-color: {bg};
            }}
            QPushButton:disabled {{
                background-color: #D1D5DB;
                color: #9CA3AF;
            }}
        """)

        if icon_name:
            self.setIcon(qta.icon(icon_name, color=text_color))
            self.setIconSize(QSize(16, 16))