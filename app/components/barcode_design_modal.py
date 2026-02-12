from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem
from PySide6.QtGui import QBrush, QColor, QFont, Qt

class BarcodeDesignModal(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Select Barcode Design")
        self.setFixedSize(400, 300)
        layout = QVBoxLayout(self)

        # --- ComboBox for barcode design ---
        self.design_combo = QComboBox()
        self.design_combo.addItems(["CODE128", "CODE39", "EAN13", "QR MOCK", "MINIMAL"])
        layout.addWidget(QLabel("Choose Design:"))
        layout.addWidget(self.design_combo)

        # --- Preview ---
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setFixedHeight(120)
        self.view.setStyleSheet("background:white; border:1px solid #CBD5E1; border-radius:4px;")
        layout.addWidget(QLabel("Preview:"))
        layout.addWidget(self.view)

        # Connect selection to preview
        self.design_combo.currentTextChanged.connect(self.update_preview)
        self.update_preview(self.design_combo.currentText())

        # --- OK / Cancel buttons ---
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Use Design")
        self.btn_cancel = QPushButton("Cancel")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

    def update_preview(self, design):
        self.scene.clear()
        x_offset = 15

        if design == "MINIMAL":
            pattern = [4,2,4,2,4,2,4]
        elif design == "EAN13":
            pattern = [2,2,3,2,2,4,3,2,3,2,2]
        elif design == "CODE39":
            pattern = [3,1,3,1,2,1,3,1,2,1,3]
        elif design == "QR MOCK":
            square = QGraphicsRectItem(40,15,50,50)
            square.setBrush(QBrush(Qt.black))
            square.setPen(Qt.NoPen)
            self.scene.addItem(square)
            pattern = []
        else:  # CODE128 default
            pattern = [3,2,3,2,2,3,2,3,3,2,2,3,2,3,2,2,3,2,3]

        for i, w in enumerate(pattern):
            if i % 2 == 0:
                bar = QGraphicsRectItem(x_offset, 15, w*2, 50)
                bar.setBrush(QBrush(Qt.black))
                bar.setPen(Qt.NoPen)
                self.scene.addItem(bar)
            x_offset += w*2

        # Label
        label = QGraphicsTextItem("*12345678*")
        label.setFont(QFont("Courier", 9, QFont.Bold))
        label.setPos(30, 70)
        self.scene.addItem(label)

    def get_value(self):
        return self.design_combo.currentText()
