# add_device_page.py
import os
import sys
from PyQt5.QtWidgets import QMainWindow, QFrame, QListWidget, QStackedWidget, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QShowEvent
from device_types import *
from devices import *
from utilities.fonts import header_font, subtitle_font

class HomePage(QMainWindow):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Programming Workstation")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layouts
        layout = QVBoxLayout()
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(20)

        # Widgets
        welcome = QLabel("Welcome to the Programming Workstation")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setFont(header_font)
        self.add_button = QPushButton("Add Device")
        self.program_button = QPushButton("Program Device")
        self.add_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(1))
        self.program_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(2))
        self.devices_list = QListWidget()
        self.stacked_widget.currentChanged.connect(self.on_page_changed)

        layout.addWidget(welcome)
        bottom_layout.addWidget(self.add_button)
        bottom_layout.addWidget(self.program_button)

        layout.addLayout(bottom_layout)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def showEvent(self, a0):
            """Refresh list every time the page is shown."""
            self.devices_list.clear()
            self.devices_list.addItems(registered_devices)
            super().showEvent(a0)
    
    def on_page_changed(self, index):
        page = self.stacked_widget.widget(index)  # Get the QWidget for this page
        if hasattr(page, "refresh") and callable(page.refresh):
            page.refresh()