# add_device_page.py
import os
import sys
from PyQt5.QtWidgets import QMainWindow, QFrame, QListWidget, QStackedWidget, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QShowEvent, QPixmap
from device_types import *
from devices import *
from resources.utilities.fonts import header_font, subtitle_font

class ConnectionPage(QMainWindow):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Check Router Connections")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layouts
        layout = QVBoxLayout()
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        # Widgets
        welcome = QLabel("Please check the connections to the Router")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setFont(header_font)
        check = QLabel("The blue ethernet cable is connected to the WAN port on the router.")
        check.setAlignment(Qt.AlignmentFlag.AlignCenter)
        check.setFont(header_font)
        
        # Create QLabel and load image
        image = QLabel()
        try:
            pixmap = QPixmap("resources/images/router.jpg")  # Replace with your image path
            if pixmap.isNull():
                raise FileNotFoundError("Image not found or invalid format.")
            image.setPixmap(pixmap.scaled(600, 400, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        except Exception as e:
            image.setText(f"Error loading image: {e}")
            image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.confirm_button = QPushButton("YES")
        self.confirm_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        
        # Navigation
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        layout.addWidget(self.home_button)
        
        layout.addWidget(welcome)
        layout.addWidget(check)
        layout.addWidget(image)
        layout.addWidget(self.confirm_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)