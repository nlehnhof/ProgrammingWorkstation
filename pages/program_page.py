# program_page.py
from PyQt5.QtWidgets import QMainWindow, QListWidget, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from device_types.ssh_device import SSHDevice
from PyQt5.QtGui import QShowEvent
from device_types import *
from manager import manager
import sys
from pathlib import Path
from devices import *
import os
from utilities.excel_utils import get_dropdown, lookup_excel, get_excel_files
from PyQt5.QtCore import Qt
import importlib.util
import json
from utilities.fonts import header_font, subtitle_font

current_dir = Path(__file__).parent

class ProgramPage(QMainWindow):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.devices_list = QListWidget()
        self.temp_pass = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Program Device Page")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        print("Registred Devices: ", registered_devices)

        # Layouts
        first = QVBoxLayout()
        second = QHBoxLayout()
        second.setAlignment(Qt.AlignmentFlag.AlignCenter)
        second.setSpacing(20)
        third = QHBoxLayout()
        third.setAlignment(Qt.AlignmentFlag.AlignCenter)
        third.setSpacing(20)
        fourth = QHBoxLayout()
        fourth.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fourth.setSpacing(20)

        # Drop Downs
        self.device_chosen = QComboBox()
        self.device_chosen.addItems(registered_devices)
        self.airport = QComboBox()
        self.airport.addItem("No data")
        self.gate = QComboBox()
        self.gate.addItem("No data")
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))

        self.device_chosen.textActivated.connect(self.update_airports)
        self.airport.textActivated.connect(self.update_gates)

        # Labels
        title = QLabel("Program Device")
        title.setFont(header_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_device = QLabel("Select Device")
        l_device.setFont(subtitle_font)
        l_airport = QLabel("Select Airport")
        l_airport.setFont(subtitle_font)
        l_gate = QLabel("Select Gate")
        l_gate.setFont(subtitle_font)
        self.router = QLineEdit()
        self.submit = QPushButton("Submit")

        # Add
        first.addWidget(self.home_button)
        first.addWidget(title)
        second.addWidget(l_device)
        third.addWidget(self.device_chosen)
        second.addWidget(l_airport)
        third.addWidget(self.airport)
        second.addWidget(l_gate)
        third.addWidget(self.gate)
        fourth.addWidget(self.router)
        fourth.addWidget(self.submit)
        self.submit.clicked.connect(self.on_submit)

        # Program Button
        self.program_button = QPushButton("Program Device")
        self.program_button.clicked.connect(self.program_device)

        first.addLayout(second)
        first.setContentsMargins(15, 15, 15, 15)
        first.addLayout(third)
        first.addLayout(fourth)
        first.addWidget(self.program_button)
        central_widget.setLayout(first)
        self.setCentralWidget(central_widget)

        self.refresh()

    def program_device(self):
        device = self.device_chosen.currentText().strip()
        device_info = manager.get_credentials(device)
        if device_info is None:
            print("Device Info not found")
            return
        program_file = os.path.join(current_dir, f"../devices/{device}/prog_dev.py")
        func_name = "run_main_script"
        with open(program_file, "r") as file:
            code = file.read()

        if code is None:
            print("Nothing found")
            
        namespace = {}
        exec(code, namespace)
        namespace[func_name](self.airport.currentText().strip(), self.gate.currentText().strip(), self.temp_pass, device)
        # print("Connected...", flush=True)
        
    def update_airports(self):
        """Update airport dropdown based on device chosen."""
        self.airport.clear()

        device = self.device_chosen.currentText().strip()
        device_info = manager.get_credentials(device)
        if device_info is None:
            print("Device Info not found")
            return
        path = os.path.join(current_dir, f"../devices/{device}")
        airport_options = get_excel_files(path)
        self.airport.addItems(airport_options)

    def update_gates(self):
        """Update Gate dropdown based on airport chosen."""
        self.gate.clear()

        airport = self.airport.currentText().strip()
        print(airport)
        device = self.device_chosen.currentText().strip()
        device_info = manager.get_credentials(device)
        if device_info is None:
            return
        path = os.path.join(current_dir, f"../devices/{device}")
        if device_info is None:
            print("device info not found")
            return
        
        file = os.path.join(path, airport)
        gate_options = get_dropdown(file)
        print(gate_options)
        if gate_options:
            self.gate.addItems(gate_options)

    def showEvent(self, a0):
            """Refresh list every time the page is shown."""
            self.devices_list.clear()  # Clear the widget
            self.devices_list.addItems(registered_devices)  # Load from global list
            self.refresh()
            super().showEvent(a0)

    def refresh(self):
        """Load devices from JSON and update both widgets."""
        try:
            with open("devices.json", "r", encoding="utf-8") as f:
                data = json.load(f)

            # Get all top-level keys from JSON
            keys = list(data.keys())

            # Update QListWidget
            self.devices_list.clear()
            self.devices_list.addItems(keys)

            # Update QComboBox
            self.device_chosen.clear()
            self.device_chosen.addItems(keys)

        except FileNotFoundError:
            print("Error: devices.json not found.")
        except json.JSONDecodeError:
            print("Error: devices.json is not valid JSON.")

    def on_submit(self):
        user_text=self.router.text().strip()
        print("User Submitted: ", user_text)
        self.temp_pass = user_text.split("PW:")[1].split(";")[0]
        print("Temp_pass: ", self.temp_pass, flush=True)