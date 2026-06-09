from abc import ABC, abstractmethod
from typing import Any

from PyQt5.QtWidgets import QMainWindow, QStyleFactory, QSpacerItem, QSizePolicy, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtCore import pyqtSlot
from device_types.ssh_device import SSHDevice
from device_types import *
from manager import manager
import sys
from devices import *
from PyQt5.QtGui import QIcon, QBrush, QColor, QStandardItemModel
from PyQt5.QtCore import QSize, Qt
import json

class AddDevice(QMainWindow):
    """
    To add any device, operator must input the name of the device and a folder path.
    Operator may also add arguments by adding text boxes, which can then be written to the JSON folder.
    """
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.rows = []  # store (title_field, info_field) 
        self.__init_ui()

    def __init_ui(self):
        self.setWindowTitle("Add Device Page")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main vertical layout
        main_layout = QVBoxLayout()
        top_layout = QVBoxLayout()
        bottom_layout = QVBoxLayout()
        top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # Navigation
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        top_layout.addWidget(self.home_button)
        main_layout.addLayout(top_layout)

        # Container for dynamic rows
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        top_layout.addLayout(self.rows_layout)

        self.device_dropdown = QComboBox()
        model = QStandardItemModel()
        self.device_dropdown.setModel(model)
        self.device_dropdown.addItem("Select Device Type...")

        # Disable selecting the hint as a valid choice
        self.device_dropdown.addItems(all_classes)
        bottom_layout.addWidget(self.device_dropdown)

        # Add button at the bottom
        self.add_button = QPushButton("Add Entry")
        self.add_button.clicked.connect(self.add_row)
        bottom_layout.addWidget(self.add_button)

        # Connect button
        self.create_button = QPushButton("Create Device")
        bottom_layout.addWidget(self.create_button)
        self.create_button.clicked.connect(self.on_submit)

        main_layout.addLayout(bottom_layout)
        central_widget.setLayout(main_layout)
        self.setCentralWidget(central_widget)
        self.refresh()
        
    def add_row(self):
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        title_field = QLineEdit()
        title_field.setPlaceholderText("Enter Title...")
        title_field.setClearButtonEnabled(False)
        info_field = QLineEdit()
        info_field.setPlaceholderText("Enter Info...")
        info_field.setClearButtonEnabled(False)

        row_layout.addWidget(title_field)
        row_layout.addWidget(info_field)

        delete_button = QPushButton()
        delete_button.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
            }
        """)
        trash = QIcon("utilities\\trash.jpg")
        delete_button.setIcon(trash)
        delete_button.setFixedSize(30, 30)
        delete_button.clicked.connect(lambda: self.remove_row(row_widget))
        row_layout.addWidget(delete_button)

        self.rows_layout.addWidget(row_widget)

        # Keep track of the fields
        self.rows.append(row_widget)

    def remove_row(self, row_widget):
        """Remove a row widget from the layout and tracking list."""
        self.rows_layout.removeWidget(row_widget)
        row_widget.deleteLater()
        if row_widget in self.rows:
            self.rows.remove(row_widget)

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

    def refresh(self):
        """Clear all rows and reset dropdown to default."""
        # Remove all existing rows
        for row_widget in list(self.rows):
            self.remove_row(row_widget)

        # Reset dropdown
        self.device_dropdown.setCurrentIndex(0)

        # Optionally add one empty row
        self.add_row()