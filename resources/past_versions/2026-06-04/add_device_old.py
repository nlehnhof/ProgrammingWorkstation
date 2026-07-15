# gui.py
from PyQt5.QtWidgets import QMainWindow, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
from device_types.ssh_device import SSHDevice
from device_types.__init__ import *
from manager import DeviceManager
import sys

class AddDevicePage(QMainWindow):
    def __init__(self, devices_dict):
        super().__init__()
        self.device_dict = devices_dict
        self.device_instances = [mod.Device() for mod in devices_dict.values() if hasattr(mod, "Device")]
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Add Device Page")
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layouts
        layout = QVBoxLayout()

        # Host, username, password input
        self.name_input = QLineEdit()
        self.configs_folder = QLineEdit()
        self.host_input = QLineEdit()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        label = QLabel("Select Device Type:")
        self.device_dropdown = QComboBox()
        self.device_dropdown.addItems(all_classes)

        layout.addWidget(QLabel("Device Name"))
        layout.addWidget(self.name_input)
        layout.addWidget(QLabel("Host"))
        layout.addWidget(self.host_input)
        layout.addWidget(QLabel("Username"))
        layout.addWidget(self.username_input)
        layout.addWidget(QLabel("Password"))
        layout.addWidget(self.password_input)
        layout.addWidget(label)
        layout.addWidget(self.device_dropdown)
        layout.addWidget(QLabel("Configs Folder"))
        layout.addWidget(self.configs_folder)

        # Connect button
        self.create_button = QPushButton("Create Device")
        layout.addWidget(self.create_button)
        self.create_button.clicked.connect(self.on_submit)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

    def on_submit(self):
        # Get text values from QLineEdit widgets
        name = self.name_input.text().strip()
        device_type = self.device_dropdown.currentText().strip()
        host = self.host_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        path = self.configs_folder.text().strip()
        print(f"Config path: {path}", flush=True)
        manager = DeviceManager()
        manager.create_device(
            name, 
            device_type,
            path, 
            host, 
            username, 
            password
        )

        print(manager.devices, flush=True)
        print(manager.device_credentials, flush=True)