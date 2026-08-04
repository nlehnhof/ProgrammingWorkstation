# home_page.py
"""The landing page: pick "Add Device" or "Program Device"."""

from PyQt5.QtWidgets import QMainWindow, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout
from PyQt5.QtCore import Qt

from resources.utilities.fonts import header_font

ADD_DEVICE_PAGE = 1
PROGRAM_PAGE = 2


class HomePage(QMainWindow):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Programming Workstation")
        central_widget = QWidget()

        layout = QVBoxLayout()
        buttons = QHBoxLayout()
        buttons.setSpacing(20)

        welcome = QLabel("Welcome to the Programming Workstation")
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome.setFont(header_font)

        self.add_button = QPushButton("Add Device")
        self.add_button.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(ADD_DEVICE_PAGE)
        )
        self.program_button = QPushButton("Program Device")
        self.program_button.clicked.connect(
            lambda: self.stacked_widget.setCurrentIndex(PROGRAM_PAGE)
        )

        layout.addWidget(welcome)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.program_button)
        layout.addLayout(buttons)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Every page gets a chance to re-read the registry as it comes into
        # view, so a device added on one page shows up on the others without
        # restarting the app.
        self.stacked_widget.currentChanged.connect(self.on_page_changed)

    def on_page_changed(self, index):
        page = self.stacked_widget.widget(index)
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            refresh()
