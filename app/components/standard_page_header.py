from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel

from components.standard_button import StandardButton

COLORS = {
    "text_primary": "#111827",
    "text_secondary": "#BDBDBD",
}

STANDARD_ACTIONS = [
    # label, icon_name, variant
    ("Add", "fa5s.plus", "primary"),
    ("Edit", "fa5s.edit", "primary"),
    ("Delete", "fa5s.trash", "primary"),
    ("View Detail", "fa5s.info-circle", "primary"),
    ("Print", "fa5s.print", "primary"),
    ("Excel", "fa5s.file-excel", "primary"),
    ("Refresh", "fa5s.sync", "primary"),
]

class StandardPageHeader(QWidget):

    def __init__(self, title, subtitle: str = "", enabled_actions=None):
        """
        Reusable page header with a fixed set of toolbar buttons.

        Buttons that are not meant to be clickable on a given page can be
        disabled so they appear in a soft gray state.

        :param title: Main header title
        :param subtitle: Optional subtitle text
        :param enabled_actions: Optional iterable with labels from STANDARD_ACTIONS
                                that should start enabled. If None, all start enabled.
        """
        super().__init__()

        self.setStyleSheet("background: transparent; border: none;")

        if enabled_actions is not None:
            enabled_actions = set(enabled_actions)

        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(8)

        # Always create actions row
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(6)

        # Create and add standard toolbar buttons
        self.action_buttons = {}
        for label, icon_name, variant in STANDARD_ACTIONS:
            btn = StandardButton(label, icon_name=icon_name, variant=variant)
            if enabled_actions is not None and label not in enabled_actions:
                btn.setEnabled(False)
            self.action_buttons[label] = btn
            actions_layout.addWidget(btn)

        # Add a stretch to push them to the right
        actions_layout.addStretch()
        main_layout.addLayout(actions_layout)

        # Text block (title + subtitle)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            f"font-size:24px; font-weight:700; color:{COLORS['text_primary']}; background: transparent;"
        )
        text_layout.addWidget(title_lbl)

        if subtitle:
            subtitle_lbl = QLabel(subtitle)
            subtitle_lbl.setStyleSheet(
                f"font-size:13px; color:{COLORS['text_secondary']}; background: transparent;"
            )
            text_layout.addWidget(subtitle_lbl)

        main_layout.addLayout(text_layout)

    # --- Public helpers -------------------------------------------------
    def get_action_button(self, label: str):
        """Return the underlying button instance for a given action label."""
        return self.action_buttons.get(label)

    def set_action_enabled(self, label: str, enabled: bool):
        """Enable/disable a specific action button and let styles handle the gray state."""
        btn = self.action_buttons.get(label)
        if btn is not None:
            btn.setEnabled(enabled)
