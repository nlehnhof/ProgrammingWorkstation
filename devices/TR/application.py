#GUI
import threading
import time
import openpyxl
from openpyxl.styles import Font
from openpyxl.worksheet.hyperlink import Hyperlink
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QStackedWidget, QFrame,
    QTextEdit, QComboBox, QLineEdit
)
from PyQt5.QtCore import Qt

#SSH
import subprocess
import paramiko
from ping3 import ping

#Python
import sys
import subprocess
import os
from datetime import datetime
from collections import deque
import ipaddress

import shutil
import argparse
import socket
import select

########## ARCHITECTURE ##############
# HOME PAGE: 
#  - Welcome Title
#  - HOME MENU
#    - Start Programming Button 
#    - Set Up Instructions Button
#    - FAQ Button
#  - NAV BAR ON EVERY PAGE
# PROGRAMMING PAGE
#  - Title
#  - Airport Drop Down
#  - Gate Drop Down
#  - Text Box for Inputting Router information
#  - Submit Button to submit the Router information
#  - Airport and Gate information boxes
#  - Router information box
#  - Checklist box
#  - Start Button (includes testing and printing)
#  - Returns Error or Success Messages in pop up!
# SET UP INSTRUCTIONS PAGE
#  - Drop down instructions for physical set up of station
#  - Drop down instructions for how to program the routers
# FAQ PAGE
#  - Who to contact
#  - Debugging Frequent Problems
#####################################

app = QApplication(sys.argv)
# Home Page
class HomePage(QWidget):
    """The first screen users see."""
    def __init__(self, navigation_stack):
        super().__init__()
        self.stack = navigation_stack
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("Router Programming Station")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        
        # Button to trigger navigation to Programming Screen
        prog_button = QPushButton("Start Programming")
        prog_button.setFixedWidth(200)
        prog_button.clicked.connect(self.go_to_programming)

        # Button to trigger navigation to Programming Screen
        inst_button = QPushButton("Set Up Instructions")
        inst_button.setFixedWidth(200)
        inst_button.clicked.connect(self.go_to_instructions)

        # Button to trigger navigation to Programming Screen
        faq_button = QPushButton("FAQs")
        faq_button.setFixedWidth(200)
        faq_button.clicked.connect(self.go_to_faq)

        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(prog_button, alignment=Qt.AlignCenter)
        layout.addWidget(inst_button, alignment=Qt.AlignCenter)
        layout.addWidget(faq_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

    def go_to_programming(self):
        # Index 1 corresponds to the Programming Screen
        self.stack.setCurrentIndex(1)

    def go_to_instructions(self):
        # Index 2 corresponds to the Instructions Screen
        self.stack.setCurrentIndex(2)
        
    def go_to_faq(self):
        # Index 3 corresponds to the FAQ Screen
        self.stack.setCurrentIndex(3)

class ProgrammingScreen(QWidget):
    """The second screen users can navigate to."""
    def __init__(self, navigation_stack):
        super().__init__()
        self.stack = navigation_stack
        self.init_ui()
        
        # State variables
        self.ssh_bbb = None
        self.sftp_bbb = None
        self.valid_ip = True
        self.s_pause = 1  # Define your pause time here
        self.gate = None
        self.airport = None
        self.excel = None

        # Load Excel Files
        self.load_excel_files()

    def init_ui(self):
        # Main vertical layout for the entire screen
        main_layout = QVBoxLayout()
        main_layout.setAlignment(Qt.AlignCenter)
        main_layout.setSpacing(10)  # Adds clean spacing between rows
        main_layout.addStretch()

        # --- TITLE ---
        title = QLabel("Programming Panel")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        main_layout.addWidget(title, alignment=Qt.AlignCenter)

        # --- CENTERED DROPDOWN COLUMNS ---
        # Horizontal container to hold the left (Airport) and right (Gate) columns
        columns_layout = QHBoxLayout()
        columns_layout.setAlignment(Qt.AlignCenter)
        columns_layout.setSpacing(40)  # Generous gap between Airport and Gate sections

        # --- Left Column: Airport ---
        airport_layout = QVBoxLayout()
        airport_layout.setAlignment(Qt.AlignCenter) # Aligns the entire column
        airport_layout.setSpacing(10)

        self.label = QLabel("Airport")
        self.label.setStyleSheet("font-size: 24px; margin-bottom: 10px;")

        self.dropdown1 = QComboBox()
        self.dropdown1.currentIndexChanged.connect(self.on_airport_selected)
        self.dropdown1.setFixedWidth(250)

        self.drop_output1 = QTextEdit()
        self.drop_output1.setDisabled(True)

        # Add widgets and explicitly center them
        airport_layout.addWidget(self.label, alignment=Qt.AlignCenter)
        airport_layout.addWidget(self.dropdown1, alignment=Qt.AlignCenter)
        airport_layout.addWidget(self.drop_output1, alignment=Qt.AlignCenter)


        # --- Right Column: Gate ---
        gate_layout = QVBoxLayout()
        gate_layout.setAlignment(Qt.AlignCenter)
        gate_layout.setSpacing(10)

        self.label2 = QLabel("Gate")
        self.label2.setStyleSheet("font-size: 24px; margin-bottom: 10px;")

        self.dropdown2 = QComboBox()
        self.dropdown2.currentIndexChanged.connect(self.on_gate_selected)
        self.dropdown2.setFixedWidth(250)

        self.drop_output2 = QTextEdit()
        self.drop_output2.setDisabled(True)

        # Add widgets and explicitly center them
        gate_layout.addWidget(self.label2, alignment=Qt.AlignCenter)
        gate_layout.addWidget(self.dropdown2, alignment=Qt.AlignCenter)
        gate_layout.addWidget(self.drop_output2, alignment=Qt.AlignCenter)


        # Add both columns to the side-by-side layout
        columns_layout = QHBoxLayout()
        columns_layout.addLayout(airport_layout)
        columns_layout.addLayout(gate_layout)
        main_layout.addLayout(columns_layout)


        # --- ROUTER INFO SUBMIT ROW ---
        router_layout = QHBoxLayout()
        router_layout.setAlignment(Qt.AlignCenter)

        self.router_input = QLineEdit()
        self.router_input.setPlaceholderText("Router Information...") # Adds hint text
        self.router_input.setFixedWidth(280)

        submit_button = QPushButton("Submit")
        submit_button.setFixedWidth(100)
        submit_button.clicked.connect(self.user_submit)

        router_layout.addWidget(self.router_input)
        router_layout.addWidget(submit_button)
        main_layout.addLayout(router_layout)

        # --- NAVIGATION BUTTON ---
        home_button = QPushButton("Back to Home")
        home_button.setFixedWidth(200)
        home_button.clicked.connect(self.go_to_home)
        main_layout.addWidget(home_button, alignment=Qt.AlignCenter)

        main_layout.addStretch()
        self.setLayout(main_layout)

    # --- CLASS METHODS ---

    def go_to_home(self):
        """Navigates back to the home screen index (usually 0)."""
        self.stack.setCurrentIndex(0)

    def program_router(self):
        pass

    def load_excel_files(self):
        folder_path = r"C:/Users/u324754/Documents/teltonika"
        
        if os.path.exists(folder_path):
            # FIXED: String quotes added around ".xlsx" and "oshkosh_log.xlsx"
            files = [f for f in os.listdir(folder_path) if f.endswith(".xlsx") and f != "oshkosh_log.xlsx"]
            self.dropdown1.clear()
            
            if files:
                self.dropdown1.addItems(files)
                # No need to manually call drop_change1; 
                # adding items will trigger on_airport_selected which handles it
            else:
                self.dropdown1.addItem("No Data")
                self.drop_output1.clear()
                self.drop_output2.clear()
        else:
            self.dropdown1.addItem("No Data")

    def on_airport_selected(self):
        """Triggered whenever a new airport is selected from dropdown1."""
        self.airport = self.dropdown1.currentText()
        
        if self.airport and self.airport != "No Data":
            # self.show_drop1(f"Selected: {self.airport}")
            self.drop_change1() # Update the gate when a new airport is selected
        else:
            self.drop_output1.clear()
            self.dropdown2.clear()
            self.drop_output2.clear()

    def drop_change1(self):
        """Updates dropdown2 (gate options) based on the selected Excel file."""
        self.excel = self.dropdown1.currentText()
        
        if not self.excel or self.excel == "No Data":
            return
            
        # Update dropdown2
        self.dropdown2.clear()
        gate_options = self.get_dropdown(str(self.excel))
        
        if gate_options:
            self.dropdown2.addItems(gate_options)
        else:
            self.dropdown2.addItem("No Data")

    def on_gate_selected(self):
        """Triggered whenever a new gate is selected from dropdown2."""
        gate = self.dropdown2.currentText()
        # if self.gate and self.gate != "No Data":
            # self.show_drop2(f"Selected: {self.gate}")

    def get_dropdown(self, filepath):
        gate_options = []
        
        # 1. Prevent crashes if the dropdown sends invalid/empty paths
        if not os.path.exists(filepath):
            return gate_options

        try:
            # Load the workbook with data_only=True to get values, not formulas
            wb = openpyxl.load_workbook(filepath, data_only=True, read_only=True)
            sheet = wb.active
            
            seen_gates = set() # To keep track of what we've already added

            # Iterate through rows starting from row 2
            for row in sheet.iter_rows(min_row=2, max_col=5, values_only=True):
                # Column 5 is at index 4
                if len(row) >= 5:
                    value = row[4]
                    if value is not None:
                        gate_str = str(value).strip()
                        
                        # 2. Check for empty strings AND avoid duplicates
                        if gate_str and gate_str not in seen_gates:
                            seen_gates.add(gate_str)
                            gate_options.append(gate_str)
                            
            wb.close() # Close workbook to free up resources

        except Exception as e:
            print(f"Error Loading Dropdown Options: {e}")
            
        return gate_options
    # --- Paramiko SSH/SFTP Methods ---

    def ssh_bbb_connect(self):
        print("Connecting to BBB", flush=True)
        bbb_ip = '192.168.7.2'
        bbb_user = 'raj'
        bbb_pass = 'Jetway'
        
        self.ssh_bbb = paramiko.SSHClient()
        self.ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
        
        print("Connected to BBB", flush=True)
        self.sftp_bbb = self.ssh_bbb.open_sftp()
        time.sleep(self.s_pause)

    def ssh_bbb_run(self, cmd):
        if not self.ssh_bbb:
            print("SSH not connected!")
            return ""
            
        stdin, stdout, stderr = self.ssh_bbb.exec_command(cmd)
        output = stdout.read().decode()
        error = stderr.read().decode()
        
        if output:
            print(f"Output:\n{output}", flush=True)
        if error:
            print(f"Errors:\n{error}", flush=True)
        return output

    def ssh_bbb_upload(self, file, bbb_file):
        if not self.sftp_bbb:
            print("SFTP not connected!")
            return
        self.sftp_bbb.put(file, bbb_file)

    def ssh_bbb_close(self):
        print("Closing Connection to BBB", flush=True)
        if self.sftp_bbb:
            self.sftp_bbb.close()
        if self.ssh_bbb:
            self.ssh_bbb.close()
        time.sleep(self.s_pause)
        print("Closed Connection to BBB", flush=True)

    log_output = QTextEdit(height=10, width=30)

    valid_ip = True
    gate = None
    router_input = None       

    def lookup_excel(self, sheet):
        global gate_ip
        global gate_netmask
        global gate_gateway
        global valid_ip
        global gate

        file_path = sheet
        to_find = gate

        def is_valid_ip(ip_string):
            try:
                ipaddress.ip_address(ip_string)
                return True
            except ValueError:
                return False
    
        try:
            wb = openpyxl.load_workbook(file_path)
            sheet = wb.active
            
            for row in sheet.iter_rows(values_only=True):
                for idx, cell in enumerate(row):
                    if str(cell) == to_find:
                        if row[idx + 1] is not None:
                            gate_ip = row[idx - 3]
                            gate_netmask = row[idx - 2]
                            gate_gateway = row[idx - 1]
                        print(row[idx + 10])
        except Exception:
         
               return False

    def run_and_test_script(self):
        global gate_ip
        global gate_netmask
        global gate_gateway
        global temp_pass

        error = False
        traceback = False

        script_path = os.path.join(os.path.dirname(__file__), "teltonika.py")
        crash_lines = deque(maxlen=50)

        try:
            #VALID IP CHECK
            if valid_ip == False:
                return
            
            #RUN AUTOMATION SCRIPT
            process = subprocess.Popen(["python", script_path, str(gate_ip), str(gate_netmask), str(gate_gateway), str(temp_pass)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        except:
            return
        
        process.wait()

    def user_submit(self, user_entry):
        global temp_pass
        
        temp_pass = user_entry.split("PW:")[1].split(";")[0]
        print("Temp Pass: ", temp_pass)
        self.run_and_test_script(self)
        
class InstructionsScreen(QWidget): 
    """The second screen users can navigate to."""
    def __init__(self, navigation_stack): 
        super().__init__() 
        self.stack = navigation_stack 
        self.init_ui() 

    def init_ui(self): 
        # Create the main layout for the widget
        layout = QVBoxLayout(self) 
        layout.setContentsMargins(10, 10, 10, 10) 
        layout.setAlignment(Qt.AlignCenter) 

        title = QLabel('Instructions for Set Up and Programming') 
        title.setStyleSheet('''
            font-size: 24px; 
            font-weight: bold; 
            margin-bottom: 20px;
        ''') 

        subtitle = QLabel('To be added...') 
        subtitle.setStyleSheet('font-size: 18px; margin-bottom: 20px;') 

        # Button to return to home 
        home_button = QPushButton('Back to Home') 
        home_button.setFixedWidth(200) 
        home_button.clicked.connect(self.go_to_home) 

        # Add widgets to the layout
        layout.addWidget(title, alignment=Qt.AlignCenter) 
        layout.addWidget(subtitle, alignment=Qt.AlignCenter) 
        layout.addWidget(home_button, alignment=Qt.AlignCenter) 

    def go_to_home(self):
        # Index 0 corresponds to the HomePage
        self.stack.setCurrentIndex(0)

class FAQScreen(QWidget):
    """The second screen users can navigate to."""
    def __init__(self, navigation_stack):
        super().__init__()
        self.stack = navigation_stack
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignCenter)

        title = QLabel("FAQs")
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        
        # Button to return to home
        home_button = QPushButton("Back to Home")
        home_button.setFixedWidth(200)
        home_button.clicked.connect(self.go_to_home)

        layout.addWidget(title, alignment=Qt.AlignCenter)
        layout.addWidget(home_button, alignment=Qt.AlignCenter)
        self.setLayout(layout)

    def go_to_home(self):
        # Index 0 corresponds to the HomePage
        self.stack.setCurrentIndex(0)

class MainWindow(QMainWindow):
    """The main application window hosting the navigation stack."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Router Programming Station Application")
        self.resize(800, 600)

        # Initialize the stack manager
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)

        # Instantiate screens and pass the central navigation stack to them
        self.home_screen = HomePage(self.stacked_widget)
        self.prog_screen = ProgrammingScreen(self.stacked_widget)
        self.inst_screen = InstructionsScreen(self.stacked_widget)
        self.faq_screen = FAQScreen(self.stacked_widget)

        # Add screens to the stack manager
        self.stacked_widget.addWidget(self.home_screen)  # Index 0
        self.stacked_widget.addWidget(self.prog_screen)  # Index 1
        self.stacked_widget.addWidget(self.inst_screen)  # Index 2
        self.stacked_widget.addWidget(self.faq_screen)  # Index 3

        # Force application to start on the Home Screen
        self.stacked_widget.setCurrentIndex(0)

if __name__ == "__main__":
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())