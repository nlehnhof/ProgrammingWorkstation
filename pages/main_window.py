import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QVBoxLayout,
    QLabel, QStackedWidget, QMainWindow
)
from PyQt5.QtCore import Qt
from pages.home_page import HomePage
from pages.add_device_page import AddDevice
from pages.program_page import ProgramPage
from pages.connection_page import ConnectionPage

# ------------------ Main Window ------------------
class MainPage(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Workstation")

        # Create stacked widget
        self.stacked_widget = QStackedWidget()

        # Create pages
        self.home_page = HomePage(self.stacked_widget)
        self.add_page = AddDevice(self.stacked_widget)
        self.prog_page = ProgramPage(self.stacked_widget)
        self.connection_page = ConnectionPage(self.stacked_widget)

        # Add pages to stacked widget
        self.stacked_widget.addWidget(self.home_page)  # index 0
        self.stacked_widget.addWidget(self.add_page)   # index 1
        self.stacked_widget.addWidget(self.prog_page)  # index 2
        self.stacked_widget.addWidget(self.connection_page) # index 3

        # Set stacked widget as central widget
        self.setCentralWidget(self.stacked_widget)