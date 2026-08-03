# program_page.py
from PyQt5.QtWidgets import QMainWindow, QCheckBox, QScrollArea, QListWidget, QSizePolicy, QApplication, QWidget, QLabel, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QHBoxLayout, QMessageBox, QComboBox
# from device_types.ssh_device import SSHDevice
from PyQt5.QtGui import QShowEvent
# from device_types import *
from core.manager import manager
import sys
from pathlib import Path
from devices import *
import os
from resources.utilities.excel_utils import get_dropdown, lookup_excel, get_excel_files
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import importlib.util
import json
import traceback
from resources.utilities.fonts import header_font, subtitle_font
from resources.utilities.app_paths import app_root, device_dir
from pages.status_panel import StatusPanel, load_checklist

current_dir = Path(__file__).parent


class ProgramWorker(QThread):
    """Runs a device's prog_dev.py off the GUI thread.

    The programming run takes several minutes; doing it inline froze the window
    for the whole time, which made a live checklist impossible. Progress from
    the device script arrives on `progress` and is applied on the GUI thread.
    """

    progress = pyqtSignal(str, str, str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, program_file, airport, gate, temp_pass, device, parent=None):
        super().__init__(parent)
        self.program_file = program_file
        self.airport = airport
        self.gate = gate
        self.temp_pass = temp_pass
        self.device = device

    def _emit_progress(self, step_id, state, detail=""):
        self.progress.emit(str(step_id), str(state), str(detail))

    def run(self):
        try:
            with open(self.program_file, "r") as file:
                code = file.read()

            namespace = {"progress_callback": self._emit_progress}
            exec(code, namespace)
            namespace["run_main_script"](self.airport, self.gate, self.temp_pass, self.device)
        except SystemExit:
            # A device script calling sys.exit() must not take the app down.
            self.finished_ok.emit()
            return
        except BaseException:
            self.failed.emit(traceback.format_exc())
            return
        self.finished_ok.emit()


class ProgramPage(QMainWindow):
    def __init__(self, stacked_widget):
        super().__init__()
        self.stacked_widget = stacked_widget
        self.devices_list = QListWidget()
        self.temp_pass = None
        self.worker = None
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Program Device Page")
        central_widget = QWidget()
        central_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
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
        self.router.setPlaceholderText("Enter device password / info here...")
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
        self.program_button.setEnabled(False)
        self.program_button.clicked.connect(self.program_device)

        first.addWidget(self.program_button)

        form_widget = QWidget()
        form_widget.setLayout(first)
        # Capped so the word-wrapped labels below can't squeeze the Status
        # column past its minimum and clip the PASS/FAIL text.
        form_widget.setMaximumWidth(560)

        # Left: the existing form. Right: the live Status checklist.
        columns = QHBoxLayout()
        columns.setSpacing(15)
        columns.addWidget(form_widget, 3)

        self.status_panel = StatusPanel()
        self.status_panel.setMinimumWidth(300)
        columns.addWidget(self.status_panel, 2)

        outer_layout.addLayout(columns)
        self.load_instructions(self.device_chosen.currentText())
        self.load_checklist(self.device_chosen.currentText())
        self.refresh()

    def program_device(self):
        device = self.device_chosen.currentText().strip()
        airport = self.airport.currentText().strip()
        gate = self.gate.currentText().strip()

        if not device or not airport or not gate or not self.temp_pass:
            QMessageBox.critical(
                self,
                "Missing Information",
                "Please fill out Device, Airport, Gate, and Password before proceeding."
            )
            return  # Stop execution

        program_file = os.path.join(device_dir(device), "prog_dev.py")
        if not os.path.isfile(program_file):
            QMessageBox.critical(
                self,
                "Device Script Missing",
                f"No prog_dev.py found for '{device}'."
            )
            return

        self.status_panel.reset()
        self.program_button.setEnabled(False)

        self.worker = ProgramWorker(program_file, airport, gate, self.temp_pass, device, self)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished_ok.connect(self.on_program_finished)
        self.worker.failed.connect(self.on_program_failed)
        self.worker.start()

    def on_progress(self, step_id, state, detail):
        self.status_panel.update_step(step_id, state, detail)

    def on_program_finished(self):
        self.program_button.setEnabled(True)
        while self.instructions_layout.count():
            item = self.instructions_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        complete = QLabel("Router Configuration Complete")
        complete.setFont(header_font)
        complete.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instructions_layout.addWidget(complete)

    def on_program_failed(self, tb_text):
        self.status_panel.fail_running("see the error log")
        self.program_button.setEnabled(True)
        # Written from the GUI thread on purpose: error_log_page's stdout/stderr
        # interceptor opens a modal QDialog on any stderr write, which is only
        # safe on the Qt thread. This is what puts Digi failures in the error
        # log the same way TR's failures land there.
        sys.stderr.write(tb_text)

    def load_checklist(self, device):
        """Show the automated milestone list for the selected device."""
        steps, image_path = load_checklist(device_dir(device))
        self.status_panel.set_steps(steps, image_path)

    def update_airports(self):
        """Update airport dropdown based on device chosen."""
        self.airport.clear()

        device = self.device_chosen.currentText().strip()
        device_info = manager.get_credentials(device)
        if device_info is None:
            print("Device Info not found")
            return
        path = device_dir(device)
        airport_options = get_excel_files(path)
        self.airport.addItems(airport_options)
        self.load_instructions(device)
        self.load_checklist(device)

    def load_instructions(self, device):
        while self.instructions_layout.count():
            item = self.instructions_layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget:
                    widget.deleteLater()

        self.instruction_checkboxes = []

        file_path = os.path.join(device_dir(device), "instructions.txt")
        try:
            with open(file_path, "r") as f:
                for line in f:
                    text = line.strip()
                    if text:
                        checkbox = QCheckBox(text)
                        self.instructions_layout.addWidget(checkbox)
                        self.instruction_checkboxes.append(checkbox)

                        checkbox.stateChanged.connect(self.update_button_state)
        except FileNotFoundError:
            print(f"Instructions file not found: {file_path}")

        self.instructions_layout.addStretch()
        self.program_button.setEnabled(False)
        
        
    def update_button_state(self):
        """Enable button only if all dynamically created checkboxes are checked."""
        all_checked = all(cb.isChecked() for cb in self.instruction_checkboxes)
        self.program_button.setEnabled(all_checked)

    def update_gates(self):
        """Update Gate dropdown based on airport chosen."""
        self.gate.clear()

        airport = self.airport.currentText().strip()
        print(airport)
        device = self.device_chosen.currentText().strip()
        device_info = manager.get_credentials(device)
        if device_info is None:
            return
        path = device_dir(device)
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
            devices_json = os.path.join(app_root(), "core", "devices.json")
            with open(devices_json, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Get all top-level keys from JSON
            keys = list(data.keys())

            # Update QListWidget
            self.devices_list.clear()
            self.devices_list.addItems(keys)

            # Update QComboBox
            self.device_chosen.clear()
            self.device_chosen.addItems(keys)

            # Keep the checklist matched to whatever device is now selected.
            if hasattr(self, "status_panel"):
                self.load_checklist(self.device_chosen.currentText().strip())

        except FileNotFoundError:
            print("Error: devices.json not found.")
        except json.JSONDecodeError:
            print("Error: devices.json is not valid JSON.")

    def on_submit(self):
        user_text=self.router.text().strip()
        print("User Submitted: ", user_text)
        try:
            self.temp_pass = user_text.split("PW:")[1].split(";")[0]
        except:
            self.temp_pass = user_text
        print("Temp_pass: ", self.temp_pass, flush=True)