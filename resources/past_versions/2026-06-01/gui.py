from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTextEdit
from PyQt5 import QtCore
import sys
import os

# Ensure parent directory is in sys.path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from device_implementation import SSHDevice, SerialProtocol
from device_manager import DeviceManager

class MainWindow(QWidget):
    def __init__(self, device_manager):
        super().__init__()
        self.device_manager = device_manager
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.ip_addr = QTextEdit()
        self.user = QTextEdit()
        self.pswd = QTextEdit()

        lay = QHBoxLayout()
        btn_connect = QPushButton("Connect to Device")
        btn_connect.clicked.connect(self.connect_device)

        layout.addWidget(self.log, alignment=QtCore.Qt.AlignCenter)
        layout.addWidget(self.ip_addr)
        layout.addWidget(self.user)
        layout.addWidget(self.pswd)
        layout.addWidget(btn_connect)
        self.setLayout(layout)

    def connect_device(self):
        protocol = SerialProtocol("COM3")
        device = self.device_manager.create_device("SSHDevice", protocol)
        device.connect(ipaddr, user, pswd)
        info = device.get_device_info()
        self.log.append(f"Connected: {info}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = DeviceManager()
    ipaddr = sys.argv[1]
    user = sys.argv[2]
    pswd = sys.argv[3]
    manager.register_device("SSHDevice", SSHDevice)
    manager.create_device("SSHDevice", SerialProtocol)
    window = MainWindow(manager)
    window.show()
    sys.exit(app.exec_())
