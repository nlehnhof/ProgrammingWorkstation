# program_page.py
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QScrollArea, QListWidget, QSizePolicy, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from device_types.ssh_device import SSHDevice
from PyQt5.QtGui import QShowEvent
from device_types import *
from core.manager import manager
import sys
from pathlib import Path
from devices import *
import os
from resources.utilities.excel_utils import get_dropdown, lookup_excel, get_excel_files
from PyQt5.QtCore import Qt
import importlib.util
import json
from resources.utilities.fonts import header_font, subtitle_font

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
        central_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.setCentralWidget(central_widget)
        print("Registred Devices: ", registered_devices)

        # Layouts
        outer_layout = QVBoxLayout(central_widget)

        first = QVBoxLayout()
        first.setContentsMargins(15,15,15,15)
        first.setSpacing(20)

        third = QHBoxLayout()
        third.setAlignment(Qt.AlignmentFlag.AlignCenter)
        third.setSpacing(10)
        third.setContentsMargins(0,0,0,0)

        fourth = QHBoxLayout()
        fourth.setSpacing(10)
        fourth.setContentsMargins(0,0,0,0)

        self.instructions = QVBoxLayout()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.instructions_layout = QVBoxLayout(self.container)

        self.scroll.setWidget(self.container)
        self.instructions.addWidget(self.scroll)

        # Drop Downs
        self.device_chosen = QComboBox()
        self.device_chosen.addItems(registered_devices)
        self.device_chosen.setFixedWidth(150)
        self.airport = QComboBox()
        self.airport.addItem("No data")
        self.airport.setFixedWidth(150)

        self.gate = QComboBox()
        self.gate.addItem("No data")
        self.gate.setFixedWidth(150)
        
        self.home_button = QPushButton("Home")
        self.home_button.clicked.connect(lambda: self.stacked_widget.setCurrentIndex(0))
        self.device_chosen.textActivated.connect(self.update_airports)
        self.airport.textActivated.connect(self.update_gates)

        # Labels
        title = QLabel("Program Device")
        title.setFont(header_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        l_instr = QLabel("Instructions: ")
        l_instr.setFont(subtitle_font)
        l_instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l_device = QLabel("Select Device, Airport, and Gate:")
        l_device.setFont(subtitle_font)
        l_device.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        l_device.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.router = QLineEdit()
        self.submit = QPushButton("Submit")
        self.submit.clicked.connect(self.on_submit)

        qr = QLabel("Scan the QR Code on the device, then hit submit followed by Program Device.")
        qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        qr.setWordWrap(True)
        qr.setFont(subtitle_font)

        # Add
        first.addWidget(self.home_button)
        first.addWidget(title)
        first.addWidget(l_device)

        third.addWidget(self.device_chosen)
        third.addWidget(self.airport)
        third.addWidget(self.gate)
        first.addLayout(third)
        first.addWidget(l_instr)
        first.addLayout(self.instructions)
        first.addStretch()
        first.addWidget(qr)
        fourth.addWidget(self.router)
        fourth.addWidget(self.submit)
        first.addLayout(fourth)
        

        # Program Button
        self.program_button = QPushButton("Program Device")
        self.program_button.clicked.connect(self.program_device)

        first.addWidget(self.program_button)

        form_widget = QWidget()
        form_widget.setLayout(first)

        outer_layout.addWidget(form_widget)
        self.load_instructions(self.device_chosen.currentText())
        self.refresh()

    def program_device(self):
        device = self.device_chosen.currentText().strip()
        program_file = os.path.join(current_dir, f"../devices/{device}/prog_dev.py")
        func_name = "run_main_script"
        with open(program_file, "r") as file:
            code = file.read()

        if code is None:
            print("Nothing found")
            
        namespace = {}
        exec(code, namespace)
        namespace[func_name](self.airport.currentText().strip(), self.gate.currentText().strip(), self.temp_pass)
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
        self.load_instructions(device)

    def load_instructions(self, device):
        while self.instructions_layout.count():
            item = self.instructions_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        file_path = os.path.join(f'C:\\Users\\u324754\\programming_workstation\\devices\\{device}', 'instructions.txt')
        with open(file_path, "r") as f:
            for line in f:
                text = line.strip()
                if text:
                    self.instructions_layout.addWidget(QCheckBox(text))

        self.instructions_layout.addStretch()

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
            with open("core/devices.json", "r", encoding="utf-8") as f:
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