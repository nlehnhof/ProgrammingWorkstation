from abc import ABC, abstractmethod
from typing import Any

from PyQt5.QtWidgets import QMainWindow, QSpacerItem, QSizePolicy, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtCore import pyqtSlot
from device_types.ssh_device import SSHDevice
from device_types import *
from manager import manager
import sys
from devices import *
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QSize


class AddDevice(QMainWindow):
    """
    To add any device, operator must input the name of the device and a folder path.
    Operator may also add arguments by adding text boxes, which can then be written to the JSON folder.
    """
    def __init__(self, stacked_widget):
        super().__init_()
        self.stacked_widget = stacked_widget
        self.rows = []  # store (title_field, info_field) 
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Add Device Page")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout
        self.main_layout = QVBoxLayout(self)
        
        # Navigation
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.main_layout.addWidget(self.home_button)

        # Container for dynamic rows
        self.rows_layout = QVBoxLayout()
        self.main_layout.addLayout(self.rows_layout)

        label = QLabel("Select Device Type:")
        self.device_dropdown = QComboBox()
        self.device_dropdown.addItems(all_classes)
        self.main_layout.addWidget(label)
        self.main_layout.addWidget(self.device_dropdown)

        # Add button at the bottom
        self.add_button = QPushButton("Add Entry")
        self.add_button.clicked.connect(self.add_row)
        self.main_layout.addWidget(self.add_button)

        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)
        
    def add_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        title_field = QLineEdit()
        info_field = QLineEdit()

        row_layout.addWidget(title_field)
        row_layout.addWidget(info_field)

        delete_button = QPushButton()
        delete_button.setIcon(QIcon.fromTheme("edit-delete"))
        delete_button.setFixedSize(30, 30)
        delete_button.clicked.connect(lambda: self.remove_row(row_widget, (title_field, info_field)))
        row_layout.addWidget(delete_button)

        self.rows_layout.addWidget(row_widget)

        # Keep track of the fields
        self.rows.append((title_field, info_field))

    def remove_row(self, row_widget, fields_tuple):
        self.rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        if fields_tuple in self.rows:
            self.rows.remove(fields_tuple)

    def on_submit(self):
        # Build dictionary from all dynamic rows
        data = {}
        for title_field, info_field in self.rows:
            key = title_field.text().strip()
            value = info_field.text().strip()
            if key:  # Only include non-empty keys
                data[key] = value
        try:
            name = data["Name"]
            path = data["Path"]
        except:
            print("Device must have 'Name' and 'Path' keys/values")
        data["type"] = self.device_dropdown.currentText().strip()

        print("Collected Data:", data, flush=True)

        # Example: pass dictionary to manager
        manager.create_device(data)
