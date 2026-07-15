from abc import ABC, abstractmethod
from typing import Any

from PyQt5.QtWidgets import QMainWindow, QSizePolicy, QFrame, QStyleFactory, QSpacerItem, QSizePolicy, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from PyQt5.QtCore import pyqtSlot
from device_types.ssh_device import SSHDevice
from device_types import *
from core.manager import manager
import sys
from devices import *
from PyQt5.QtGui import QIcon, QBrush, QColor, QStandardItemModel, QFont
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
        main_layout.setSpacing(20)
        top_layout = QVBoxLayout()
        bottom_layout = QVBoxLayout()
        top_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        bottom_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # Navigation
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        top_layout.addWidget(self.home_button)
        main_layout.addLayout(top_layout)

        # Example Device
        main_title = QLabel("Add Device")
        main_title.setStyleSheet("font-size: 16px; font-weight: bold;")
        main_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        top_layout.addWidget(main_title)

        instr = QLabel("Add device information. Use the example as a template. Every device must include the keys 'Name' and 'Path'. Keys should begin with a capital letter.")
        instr.setWordWrap(True)
        instr.setFont(QFont("Arial", 10))
        top_layout.addWidget(instr)

        # Container for dynamic rows
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        top_layout.addLayout(self.rows_layout)

        self.device_dropdown = QComboBox()
        model = QStandardItemModel()
        self.device_dropdown.setModel(model)
        self.device_dropdown.addItem("Select Device Type...")
        self.device_dropdown.setFixedWidth(500)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        line.setStyleSheet("color: gray; background-color: gray; height: 3px;")

        names = QHBoxLayout()
        key = QLabel("Keys")
        key.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
        value = QLabel("Values")
        value.setStyleSheet("color: green; font-size: 14px; font-weight: bold;")
        names.addWidget(key)
        names.addWidget(value)
        names.setContentsMargins(0,0,0,0)
        names.setAlignment(Qt.AlignmentFlag.AlignCenter)
        names.setSpacing(350)

        # Disable selecting the hint as a valid choice
        # self.device_dropdown.addItems(all_classes)
        # bottom_layout.addWidget(self.device_dropdown, alignment=Qt.AlignmentFlag.AlignCenter)
        # bottom_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # bottom_layout.addWidget(line)

        # Example Device
        example = QLabel("Example Device")
        example.setStyleSheet("font-size: 16px; font-weight: bold;")
        example.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom_layout.addWidget(example)
        bottom_layout.addLayout(names)
        bottom_layout.setSpacing(15)

        rows_example = QVBoxLayout()
        rows_example.setAlignment(Qt.AlignmentFlag.AlignCenter)

        row_w = QWidget()
        row = QHBoxLayout(row_w)
        row.setContentsMargins(0, 0, 0, 0)

        title = QLineEdit("Name")
        title.setReadOnly(True)

        self.setStyleSheet("""
            QLineEdit {
                font-size: 14px;
                color: black;
                background-color: #000;
                border: 1px solid #888;
                border-radius: 5px;
                padding: 5px;
            }
            QLineEidt:placeholder {
                color: #888;
                font-style: italic;
            }
        """)

        info = QLineEdit("Teltonika")
        info.setReadOnly(True)
        row.addWidget(title)
        row.addWidget(info)

        row_2 = QWidget()
        row2 = QHBoxLayout(row_2)
        row2.setContentsMargins(0,0,0,0)
        field_2 = QLineEdit("Path")
        field_2.setReadOnly(True)
        info_2 = QLineEdit("path/to/teltonika/folder")
        info_2.setReadOnly(True)
        row2.addWidget(field_2)
        row2.addWidget(info_2)

        # row_3 = QWidget()
        # row3 = QHBoxLayout(row_3)
        # row3.setContentsMargins(0,0,0,0)
        # field_3 = QLineEdit("Username")
        # field_3.setReadOnly(True)
        # info_3 = QLineEdit("admin")
        # info_3.setReadOnly(True)
        # row3.addWidget(field_3)
        # row3.addWidget(info_3)

        # row_4 = QWidget()
        # row4 = QHBoxLayout(row_4)
        # row4.setContentsMargins(0,0,0,0)
        # field_4 = QLineEdit("Password")
        # field_4.setReadOnly(True)
        # info_4 = QLineEdit("pswd123")
        # info_4.setReadOnly(True)
        # row4.addWidget(field_4)
        # row4.addWidget(info_4)

        row_5 = QWidget()
        row5 = QHBoxLayout(row_5)
        row5.setContentsMargins(0,0,0,0)
        field_5 = QLineEdit("IP Address")
        field_5.setReadOnly(True)
        info_5 = QLineEdit("123.456.78")
        info_5.setReadOnly(True)
        row5.addWidget(field_5)
        row5.addWidget(info_5)

        rows_example.addWidget(row_w)
        rows_example.addWidget(row_2)
        # rows_example.addWidget(row_3)
        # rows_example.addWidget(row_4)
        rows_example.addWidget(row_5)
        bottom_layout.addLayout(rows_example)

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
        data = {}
        for row_widget in self.rows:
            edits = row_widget.findChildren(QLineEdit)
            if len(edits) >= 2:
                title_field, info_field = edits[0], edits[1]
                key = title_field.text().strip()
                value = info_field.text().strip()
                if key:
                    data[key] = value
        try:
            name = data["Name"]
            path = data["Path"]
        except KeyError:
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