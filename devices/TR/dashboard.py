#GUI
import tkinter as tk
import threading
import time
import openpyxl
from openpyxl.styles import Font
from openpyxl.worksheet.hyperlink import Hyperlink

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

start_time = time.perf_counter()

print("current dir:", os.getcwd())
print("files in dir: ", os.listdir())

s_pause = 1
l_pause = 2

# Set up the window for the Router Automation
root = tk.Tk()
root.title("Router Automation")
root.update_idletasks()
root.minsize(root.winfo_reqwidth(), root.winfo_reqheight())

dropdown = None
valid_ip = True

    
def ssh_bbb_connect():
    print("Connecting to BBB", flush=True)
    global ssh_bbb, sftp_bbb
    bbb_ip = '192.168.7.2'
    bbb_user = 'raj'
    bbb_pass = 'Jetway'

    ssh_bbb = paramiko.SSHClient()
    ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
    print("Connected to BBB", flush=True)
    
    sftp_bbb = ssh_bbb.open_sftp()
    time.sleep(s_pause)
    
def ssh_bbb_run(cmd):
    global ssh_bbb
    stdin, stdout, stderr = ssh_bbb.exec_command(cmd)
   
    output = stdout.read().decode()
    error = stderr.read().decode()
    
    if output is not None:
        print("Output:\n", output, flush=True)
    if error is not None:
        print("Errors:\n", error, flush=True)
    return output

def ssh_bbb_upload(file, bbb_file):
    global sftp_bbb
    sftp_bbb.put(file, bbb_file)
    
def ssh_bbb_close():
    print("Closing Connection to BBB", flush=True)
    global ssh_bbb, sftp_bbb
    if sftp_bbb:
        sftp_bbb.close()
    if ssh_bbb:
        ssh_bbb.close()
    time.sleep(s_pause)
    print("Closed Connection to BBB", flush=True)
    
############## Column 0 DropDown ##############
drop_frame1 = tk.Frame(root)
drop_frame1.grid(row=0, column=0, sticky='n')

tk.Label(drop_frame1, text='Drop Down1').grid(row=0, column=0)
drop_output1 = tk.Text(drop_frame1, height=10, width=20, state='disabled')
drop_output1.grid(row=0, column=0, sticky='n')

excel = None

def show_drop1(text):
    drop_output1.config(state='normal')
    drop_output1.insert(tk.END, text + "\n")
    drop_output1.see(tk.END)
    drop_output1.config(state='disabled')
    
def drop_change1(*args):
    global excel, selected_excel, dropdown, selected_gate
    excel = selected_excel.get()
    
    show_drop1(f"Selected: {excel}")
    gate_options = get_dropdown(str(excel))
    
    if dropdown:
        dropdown.destroy()
        
    selected_gate = tk.StringVar()
    
    if gate_options:
        selected_gate.set(gate_options[0] if gate_options else "No Data")  # Set a default value
        
    dropdown = tk.OptionMenu(drop_frame, selected_gate, *gate_options)
    dropdown.grid(row=1, column=1, sticky='n')
    
    selected_gate.trace_add("write", drop_change)

def on_gate_selected(*args):
    global gate
    gate = selected_gate.get()
    show_drop(f"Selected: {gate}")
    lookup_excel(excel)
    
def get_excel_files(folder_path):
    return [f for f in os.listdir(folder_path) if f.endswith(".xlsx") and f != "oshkosh_log.xlsx"]

excel_files = get_excel_files("C:/Users/admin/Documents/teltonika") #UPDATED
print(excel_files)
selected_excel = tk.StringVar()
selected_excel.set(excel_files[0] if excel_files else "No Data")
selected_excel.trace_add("write", drop_change1)

#drop down menu
dropdown1 = tk.OptionMenu(drop_frame1, selected_excel, *excel_files)
dropdown1.grid(row=1, column=0, sticky='n')

############## Column 1 DropDown ##############
drop_frame = tk.Frame(root)
drop_frame.grid(row=0, column=1, sticky='n')

tk.Label(drop_frame, text='Drop Down').grid(row=0, column=1)
drop_output = tk.Text(drop_frame, height=10, width=20, state='disabled')
drop_output.grid(row=0, column=1, sticky='n')

gate = None

def show_drop(text):
    drop_output.config(state='normal')
    drop_output.insert(tk.END, text + "\n")
    drop_output.see(tk.END)
    drop_output.config(state='disabled')
    
def drop_change(*args):
    global gate
    gate = selected_gate.get()
    show_drop(f"Selected: {gate}")
    lookup_excel(excel)
    
def get_dropdown(filepath=excel):
    gate_options = []
    
    try:
        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active
        for row in sheet.iter_rows(min_row=2, max_col=5, values_only=True):
            value = row[4]
            if value is not None:
                gate_options.append(str(value))
                
    except Exception as e:
        print(f"Error Loading Dropdown Options")
        
    return gate_options

gate_options = get_dropdown(selected_excel.get())
selected_gate = tk.StringVar()
selected_gate.set(gate_options[0] if gate_options else "No Data")  # Set a default value
selected_gate.trace_add("write", drop_change)

#drop down menu
dropdown = tk.OptionMenu(drop_frame, selected_gate, *gate_options)
dropdown.grid(row=1, column=1, sticky='n')
    
############## Column 2 Excel ##############
excel_frame = tk.Frame(root)
excel_frame.grid(row=0, column=2, sticky='n')

tk.Label(excel_frame, text='Excel Search').grid(row=0, column=2)
excel_output = tk.Text(excel_frame, height=10, width=20, state='disabled')
excel_output.grid(row=0, column=2, sticky='n')

def is_valid_ip(ip_string):
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False
    
def show_excel(text):
    excel_output.config(state='normal')
    excel_output.insert(tk.END, text + "\n")
    excel_output.see(tk.END)
    excel_output.config(state='disabled')

def lookup_excel(sheet):
    file_path = sheet
    to_find = gate

    global gate_ip
    global gate_netmask
    global gate_gateway
    global valid_ip
    
    try:
        print("filepath =", file_path)
        print("exists+", os.path.exists(file_path))
        wb = openpyxl.load_workbook(file_path)
        sheet = wb.active
        
        for row in sheet.iter_rows(values_only=True):
            for idx, cell in enumerate(row):
                if str(cell) == to_find:
                    if row[idx + 1] is not None:
                        gate_ip = row[idx - 3]
                        gate_netmask = row[idx - 2]
                        gate_gateway = row[idx - 1]
                        if is_valid_ip(gate_ip):
                            show_excel(f"Gate IP: {gate_ip}")
                            show_excel(f"Netmask: {gate_netmask}")
                            show_excel(f"Gateway: {gate_gateway}")
                        else:
                            show_excel(f"Invalid IP: {gate_ip}")
                            show_excel("Select Another Option")
                            valid_ip = False
                    print(row[idx + 10])
                    if row[idx + 10] is not None:
                        show_excel("This Option has been Programmed Before")
                        show_excel("Press Start if you Wish to Continue")

    except Exception as e:
        show_excel(f"Error Reading File: {type(e).__name__}: {e}")
        print("Excel Read Error:", type(e).__name__, e)
        import traceback; traceback.print_exc()

############## Column 3 Checklist ##############
check_frame = tk.Frame(root)
check_frame.grid(row=0, column=3, sticky='n')

tk.Label(check_frame).grid(row=0, column=3)
status_text = tk.Text(check_frame, height=10, width=15, state='disabled')
status_text.grid(row=0, column=3, sticky='n')

def check(text):
    status_text.config(state='normal')
    status_text.insert(tk.END, text + "\n")
    status_text.see(tk.END)
    status_text.config(state='disabled')
        
def run_main_script():
    global excel, selected_gate, selected_excel

    error = False
    traceback = False
    
    script_path = os.path.join(os.path.dirname(__file__), "teltonika.py")
    crash_lines = deque(maxlen=50)
    
    try:
        #VALID IP CHECK
        if valid_ip == False:
            log("Invalid IP!")
            log("Exiting Script!")
            log("Close and Reopen Program!")
            return
        
        #RUN AUTOMATION SCRIPT
        process = subprocess.Popen(["python", script_path, str(gate_ip), str(gate_netmask), str(gate_gateway), str(temp_pass)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        check("Checklist")
        check("[ ] Updated Gate IP")
        check("[ ] Upload Test Files")
        check("[ ] Install Firmware")
        check("[ ] Reset Passwords")
        check("[ ] Upload Configuration Files")
        check("[ ] Router Reboot")
        check(" ")
        check(" ")
        
        for line in process.stdout:
            statement = line.strip()
            crash_lines.append(statement)
            log(statement)
            
            #####################  NON-TRACEBACK ERROR HANDLING #####################
            
            if "Incorrect" in statement:
                error = True
                try:
                    crash_log = "\n".join(crash_lines)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    crash_folder = "crash_logs"
                    os.makedirs(crash_folder, exist_ok=True)
                    excel_name = excel.removesuffix(".xlsx")

                    filename_crash = f"crash_log_{excel_name}_{gate}_{timestamp}.txt"
                    filepath = os.path.join(crash_folder, filename_crash)

                    with open(filepath, "w") as file:
                        file.write(crash_log)
                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                    
                    to_find = gate
                    found = False
                    
                    current_datetime = datetime.now()
                    
                    for row in sheet.iter_rows(values_only=False):
                        for cell in row:
                            if str(cell.value) == to_find:
                                print("Crash Log")
                                t_row = cell.row
                                t_col = cell.column
                                file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
                                cell = sheet.cell(row=t_row, column=10)
                                cell.value = filename_crash
                                cell.hyperlink = file_path_crash
                                cell.font = Font(color="0000FF", underline="single")
                                
                                print("Red Date and Time")
                                t_cell = sheet.cell(row=t_row, column=8)
                                t_cell.value = current_datetime
                                t_cell.font = Font(color="FF0000")
                                
                                found = True
                        if found:
                            break
                    
                    if not found:
                        log("Error Couldn't be Logged")
                    
                    wb.save(excel)
                    
                    current_datetime = datetime.now()
                
                except Exception as e:
                    log(f"An Error Occurred: {e}")
                
                #create label text file
                try:
                    print("Creating Label")
                    label_log = " "
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    router_labels = "router_labels"
                    os.makedirs(router_labels, exist_ok=True)
                    excel_name = excel.removesuffix(".xlsx")

                    filename_label = f"label_{excel_name}_{gate}_{timestamp}.txt"
                    filepath = os.path.join(router_labels, filename_label)

                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                            
                    to_find = gate
                    found = False
                            
                    for row in sheet.iter_rows(values_only=False):
                        for cell in row:
                            if str(cell.value) == to_find:
                                print("Collecting Label Info")
                                t_row = cell.row
                                t_col = cell.column
                                bridge_serial = sheet.cell(row=t_row, column=t_col).value
                                router_num = sheet.cell(row=t_row, column=6).value
                                mac_addr = sheet.cell(row=t_row, column=7).value
                                gate_num = sheet.cell(row=t_row, column=1).value
                                
                                print("Bridge Serial: ", bridge_serial)
                                print("Router Num: ", router_num)
                                print("Mac_addr: ", mac_addr)
                                print("Gate Num: ", mac_addr)
                                
                                found = True
                        if found:
                            break
                        
                    if not found:
                        log("Traceback Error Couldn't be Logged")
                            
                    wb.save(excel)
                    print(filepath, flush=True)
                    log(filepath)
                    with open(filepath, "w") as file:
                        print("Writing Label Info")
                        first_line = "GATE " + str(gate_num) +" SN" + str(bridge_serial) + "," + "PN: " + str(router_num) + "," + "MA: " + str(mac_addr) + "," + "IP: " + str(gate_ip)
                        # second_line = "PN: " + str(router_num) + ","
                        # third_line = "MA: " + str(mac_addr) + ","
                        # fourth_line = "IP: " + str(gate_ip) + ","
                        file.write(first_line)
                        # file.write(second_line)
                        # file.write(third_line)
                        # file.write(fourth_line)
                        
                    with open(filepath, "r") as file:
                        print("Label File Contents")
                        print(file.read())
                        
                    
                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                            
                    to_find = gate
                    found = False
                            
                    for row in sheet.iter_rows(values_only=False):
                        for cell in row:
                            if str(cell.value) == to_find:
                                t_row = cell.row
                                t_col = cell.column
                                file_path_label = os.path.abspath(f"C:/Users/admin/Documents/teltonika/router_labels/{filename_label}") 
                                
                                #Label
                                cell = sheet.cell(row=t_row, column=9)
                                cell.value = filename_label
                                cell.hyperlink = file_path_label
                                cell.font = Font(color="0000FF", underline="single")
                                
                                #Program Number
                                cell = sheet.cell(row=t_row, column=11)
                                if cell.value is None:
                                    cell.value = int(1)
                                else:
                                    cell.value = cell.value + 1
                                cell.font = Font(color="000000")
                                
                                cell = sheet.cell(row=t_row, column=11)
                                cell.value = "Not Tested"
                                cell.font = Font(color="000000")
                                
                                found = True
                        if found:
                            break
                            
                    if not found:
                        log("Label File Couldn't be Logged")
                            
                    wb.save(excel)

                except Exception as e:
                    log(f"An Error Occurred: {e}")
                
                #OSHKOSH LOG
                oshkosh_log_path = "oshkosh_log.xlsx"
        
                wb = openpyxl.load_workbook(oshkosh_log_path)
                sheet = wb.active
                            
                to_find = gate
                found = False
                
                #check for next empty row   
                for row_index, row in enumerate(sheet.iter_rows(min_col=1, max_col=1, values_only=True), start=1):
                    if row[0] is None:
                        target_row = row_index
                        found = True
                        break

                if found:
                    #Airport
                    print("Airport Log")
                    airport_cell = sheet.cell(row=target_row, column=1)
                    airport_cell.value = excel
                    airport_cell.font = Font(color="000000")
                    
                    #Gate
                    print("Gate Log")
                    gate_cell = sheet.cell(row=target_row, column=2)
                    gate_cell.value = int(gate)
                    gate_cell.font = Font(color="000000")
                    
                    #Gate IP
                    print("Gate IP Log")
                    gate_ip_cell = sheet.cell(row=target_row, column=3)
                    gate_ip_cell.value = gate_ip
                    gate_ip_cell.font = Font(color="000000")
                    
                    #Gate Netmask
                    print("Gate Netmask")
                    netmask_cell = sheet.cell(row=target_row, column=4)
                    netmask_cell.value = gate_netmask
                    netmask_cell.font = Font(color="000000")
                    
                    #Gate Gateway
                    print("Gateway")
                    gateway_cell = sheet.cell(row=target_row, column=5)
                    gateway_cell.value = gate_gateway
                    gateway_cell.font = Font(color="000000")
                    
                    #Bridge Serial
                    print("Bridge Serial Log: ", bridge_serial)
                    bridge_cell = sheet.cell(row=target_row, column=6)
                    bridge_cell.value = bridge_serial
                    bridge_cell.font = Font(color="000000")

                    #Router Number
                    print("Router Number Log")
                    router_cell = sheet.cell(row=target_row, column=7)
                    router_cell.value = router_num
                    router_cell.font = Font(color="000000")
                    
                    #Mac Addr
                    print("Mac Addr Log")
                    mac_cell = sheet.cell(row=target_row, column=8)
                    mac_cell.value = mac_addr
                    mac_cell.font = Font(color="000000")
                    
                    #Router Program Date
                    print("Timestamp Log")
                    if error is True or traceback is True:
                        timestamp_cell = sheet.cell(row=target_row, column=9)
                        timestamp_cell.value = current_datetime
                        timestamp_cell.font = Font(color="FF0000")
                    else:
                        timestamp_cell = sheet.cell(row=target_row, column=9)
                        timestamp_cell.value = current_datetime
                        timestamp_cell.font = Font(color="000000")
                    
                    #Label
                    print("Label Log")
                    label_cell = sheet.cell(row=target_row, column=10)
                    file_path_label = os.path.abspath(f"C:/Users/admin/Documents/teltonika/router_labels/{filename_label}") 
                    label_cell.value = filename_label
                    label_cell.hyperlink = file_path_label
                    label_cell.font = Font(color="0000FF", underline="single")
                    
                    #Crash Report
                    print("Crash Log")
                    crash_cell = sheet.cell(row=target_row, column=11)
                    file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
                    crash_cell.value = filename_crash
                    crash_cell.hyperlink = file_path_crash
                    crash_cell.font = Font(color="0000FF", underline="single")
                    
                    #Test is Not Done Yet so we set it None
                    testdate_cell = sheet.cell(row=t_row, column=t_col + 12)
                    testdate_cell.value = "Not Tested"
                    testdate_cell.font = Font(color="000000")
                        
                if not found:
                    log("Oshkosh Log: Info Couldn't be Logged")
                            
                wb.save(oshkosh_log_path)

                #Exit Main Script
                return
                    
            if "Traceback" in statement:
                traceback = True

            ####################################################################
                
            if "New Gate IP Updated" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[ ] Upload Test Files")
                check("[ ] Install Firmware")
                check("[ ] Reset Passwords")
                check("[ ] Upload Configuration Files")
                check("[ ] Router Reboot")
                check(" ")
                check(" ")
            if "FloodLighToggle.py found on BBB" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[X] Upload Test Files")
                check("[ ] Install Firmware")
                check("[ ] Reset Passwords")
                check("[ ] Upload Configuration Files")
                check("[ ] Router Reboot")
                check(" ")
                check(" ")
            if "Install Done" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[X] Upload Test Files")
                check("[X] Install Firmware")
                check("[ ] Reset Passwords")
                check("[ ] Upload Configuration Files")
                check("[ ] Router Reboot")
                check(" ")
                check(" ") 
            if "Done Updating Passwords" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[X] Upload Test Files")
                check("[X] Install Firmware")
                check("[x] Reset Passwords")
                check("[ ] Upload Configuration Files")
                check("[ ] Router Reboot")
                check(" ")
                check(" ")
            if "Copied All Config Files to Router" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[X] Upload Test Files")
                check("[X] Install Firmware")
                check("[x] Reset Passwords")
                check("[x] Upload Configuration Files")
                check("[ ] Router Reboot")
                check(" ")
                check(" ")
            if "Reboot Done" in statement:
                check("Checklist")
                check("[x] Updated Gate IP")
                check("[X] Upload Test Files")
                check("[X] Install Firmware")
                check("[x] Reset Passwords")
                check("[x] Upload Configuration Files")
                check("[x] Router Reboot")
                check(" ")
                check(f"Finished Programming {gate}")
            if "FINISHED SETTING UP ROUTER" in statement:
                log("FINISHED SETTING UP ROUTER")
                log(" ")
                log("NEXT STEP:")
                log(" ")
                log("PRINT LABEL")
                log(" ")
                log("ATTACH LABEL TO ROUTER")
                log(" ")
                log(" ")
            if "MAC Addr:" in statement:
                mac_addr = statement.split("MAC Addr:")[1].strip()
                
                print("MAC Address: ", mac_addr)
                
                try:
                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                    
                    to_find = gate
                    found = False
                    
                    for row in sheet.iter_rows(values_only=False):
                        for cell in row:
                            if str(cell.value) == to_find:
                                t_row = cell.row
                                t_col = cell.column
                                
                                t_cell = sheet.cell(row=t_row, column=7)
                                t_cell.value = mac_addr
                                t_cell.font = Font(color="000000")

                                found = True
                        if found:
                            break
                    
                    if not found:
                        log("Mac Address Couldn't be Logged")
                    
                    wb.save(excel)
                    
                except Exception as e:
                    log(f"An Error Occurred: {e}")
                
        #end of automation python file
        process.wait()
        
        ################### Traceback File Creation and Logging #####################
        
        current_datetime = datetime.now()
        
        if traceback is True:
            try:
                crash_log = "\n".join(crash_lines)
                    
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                crash_folder = "crash_logs"
                os.makedirs(crash_folder, exist_ok=True)
                excel_name = excel.removesuffix(".xlsx")

                filename_crash = f"crash_log_{excel_name}_{gate}_{timestamp}.txt"
                filepath = os.path.join(crash_folder, filename_crash)

                with open(filepath, "w") as file:
                    file.write(crash_log)
                    
                wb = openpyxl.load_workbook(excel)
                sheet = wb.active
                    
                to_find = gate
                found = False
                    
                for row in sheet.iter_rows(values_only=False):
                    for cell in row:
                        if str(cell.value) == to_find:
                            t_row = cell.row
                            t_col = cell.column
                            file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
                            cell = sheet.cell(row=t_row, column=10)
                            cell.value = filename_crash
                            cell.hyperlink = file_path_crash
                            cell.font = Font(color="0000FF", underline="single")
                                
                            found = True
                    if found:
                        break
                    
                if not found:
                    log("Traceback Error Couldn't be Logged")
                    
                wb.save(excel)

            except Exception as e:
                log(f"An Error Occurred: {e}")
        
        ########################## ADD TIMESTAMP ############################
        
        current_datetime = datetime.now()
        
        try:
            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
            
            to_find = gate
            print("selected excel", excel)
            print("selected gate", gate)
            found = False
            
            for row in sheet.iter_rows(values_only=False):
                for cell in row:
                    if str(cell.value) == to_find:
                        t_row = cell.row
                        t_col = cell.column
                        print("row:", t_row)
                        print("col:", t_col)
                        print("Error Value: ", error)
                        
                        #change date time color to red
                        if error is True or traceback is True:
                            print("inside here for some reason")
                            t_cell = sheet.cell(row=t_row, column=8)
                            t_cell.value = current_datetime
                            t_cell.font = Font(color="FF0000")
                        
                        #date time color to black
                        else:
                            print("correct spot")
                            t_cell = sheet.cell(row=t_row, column=8)
                            t_cell.value = current_datetime
                            t_cell.font = Font(color="000000")
                            
                            print("Trying to Remove Crash Log File")

                            #remove the crash file if it exists
                            t_cell = sheet.cell(row=t_row, column=10)
                            print(t_cell.value)
                            t_cell.value = " "

                        found = True
                if found:
                    break
            
            if not found:
                log("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            log(f"An Error Occurred: {e}")
            
        ########################## CREATE A LABEL ##########################
        try:
            print("Creating Label")            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            router_labels = "router_labels"
            os.makedirs(router_labels, exist_ok=True)
            excel_name = excel.removesuffix(".xlsx")

            filename_label = f"label_{excel_name}_{gate}_{timestamp}.txt"
            filepath = os.path.join(router_labels, filename_label)

            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
                    
            to_find = gate
            found = False
                    
            for row in sheet.iter_rows(values_only=False):
                for cell in row:
                    if str(cell.value) == to_find:
                        print("Collecting Label Info")
                        t_row = cell.row
                        t_col = cell.column

                        bridge_serial = sheet.cell(row=t_row, column=t_col).value
                        router_num = sheet.cell(row=t_row, column=6).value
                        mac_addr = sheet.cell(row=t_row, column=7).value
                        gate_num = sheet.cell(row=t_row, column=1).value
                                
                        print("Bridge Serial: ", bridge_serial)
                        print("Router Num: ", router_num)
                        print("Mac_addr: ", mac_addr)
                        print("Gate Num: ", mac_addr)
                        mac_addr = str(mac_addr)
                        
                        found = True
                if found:
                    break
            if not found:
                log("Error Couldn't be Logged")
                    
            wb.save(excel)
            
            with open(filepath, "w") as file:
                print("Writing Label Info")
                first_line = "GATE " + str(gate_num) +" SN" + str(bridge_serial) + ","
                second_line = "PN: " + str(router_num) + ","
                third_line = "MA: " + str(mac_addr) + ","
                fourth_line = "IP: " + str(gate_ip) + ","
                file.write(first_line)
                file.write(second_line)
                file.write(third_line)
                file.write(fourth_line)
                
            with open(filepath, "r") as file:
                print("Label File Contents")
                print(file.read())
                
            
            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
                    
            to_find = gate
            found = False
                    
            for row in sheet.iter_rows(values_only=False):
                for cell in row:
                    if str(cell.value) == to_find:
                        t_row = cell.row
                        t_col = cell.column
                        file_path_label = os.path.abspath(f"C:/Users/admin/Documents/teltonika/router_labels/{filename_label}")
                        
                        #Label 
                        cell = sheet.cell(row=t_row, column=9)
                        cell.value = filename_label
                        cell.hyperlink = file_path_label
                        cell.font = Font(color="0000FF", underline="single")
                        
                        #Program Number
                        cell = sheet.cell(row=t_row, column=11)
                        if cell.value is None:
                            cell.value = int(1)
                        else:
                            cell.value = cell.value + 1
                        cell.font = Font(color="000000")
                        
                        #Test is Not Done Yet so we set it None
                        cell = sheet.cell(row=t_row, column=11)
                        cell.value = "Not Tested"
                        cell.font = Font(color="000000")
                                
                        found = True
                if found:
                    break
                    
            if not found:
                log("Error Couldn't be Logged")
                    
            wb.save(excel)

        except Exception as e:
            log(f"An Error Occurred: {e}")
                
        ################################### OSHKOSH LOG #####################################
        
        oshkosh_log_path = "oshkosh_log.xlsx"
        
        wb = openpyxl.load_workbook(oshkosh_log_path)
        sheet = wb.active
                    
        to_find = gate
        found = False
        
        #check for next empty row   
        for row_index, row in enumerate(sheet.iter_rows(min_col=1, max_col=1, values_only=True), start=1):
            if row[0] is None:
                target_row = row_index
                found = True
                break

        if found:
            #Airport
            print("Airport Log")
            airport_cell = sheet.cell(row=target_row, column=1)
            airport_cell.value = excel
            airport_cell.font = Font(color="000000")
            
            #Gate
            print("Gate Log")
            gate_cell = sheet.cell(row=target_row, column=2)
            gate_cell.value = int(gate)
            gate_cell.font = Font(color="000000")
            
            #Gate IP
            print("Gate IP Log")
            gate_ip_cell = sheet.cell(row=target_row, column=3)
            gate_ip_cell.value = gate_ip
            gate_ip_cell.font = Font(color="000000")
            
            #Gate Netmask
            print("Gate Netmask")
            netmask_cell = sheet.cell(row=target_row, column=4)
            netmask_cell.value = gate_netmask
            netmask_cell.font = Font(color="000000")
                    
            #Gate Gateway
            print("Gateway")
            gateway_cell = sheet.cell(row=target_row, column=5)
            gateway_cell.value = gate_gateway
            gateway_cell.font = Font(color="000000")
            
            #Bridge Serial
            print("Bridge Serial Log: ", bridge_serial)
            bridge_cell = sheet.cell(row=target_row, column=6)
            bridge_cell.value = bridge_serial
            bridge_cell.font = Font(color="000000")

            #Router Number
            print("Router Number Log")
            router_cell = sheet.cell(row=target_row, column=7)
            router_cell.value = router_num
            router_cell.font = Font(color="000000")
            
            #Mac Addr
            print("Mac Addr Log")
            mac_cell = sheet.cell(row=target_row, column=8)
            mac_cell.value = mac_addr
            mac_cell.font = Font(color="000000")
            
            #Router Program Date
            print("Timestamp Log")
            if error is True or traceback is True:
                timestamp_cell = sheet.cell(row=target_row, column=9)
                timestamp_cell.value = current_datetime
                timestamp_cell.font = Font(color="FF0000")
            else:
                timestamp_cell = sheet.cell(row=target_row, column=9)
                timestamp_cell.value = current_datetime
                timestamp_cell.font = Font(color="000000")
            
            #Label
            print("Label Log")
            label_cell = sheet.cell(row=target_row, column=10)
            file_path_label = os.path.abspath(f"C:/Users/admin/Documents/teltonika/router_labels/{filename_label}") 
            label_cell.value = filename_label
            label_cell.hyperlink = file_path_label
            label_cell.font = Font(color="0000FF", underline="single")
            
            #Crash Report
            if error is True or traceback is True:
                print("Crash Log")
                crash_cell = sheet.cell(row=target_row, column=11)
                file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
                crash_cell.value = filename_crash
                crash_cell.hyperlink = file_path_crash
                crash_cell.font = Font(color="0000FF", underline="single")
            
            #Router Test Data Blank
            print("Router Test Data Blank")
            mac_cell = sheet.cell(row=target_row, column=12)
            mac_cell.value = "Not Tested"
            mac_cell.font = Font(color="000000")
                    
        if not found:
            log("Oshkosh Log: Info Couldn't be Logged")
                    
        wb.save(oshkosh_log_path)
        
        #################################################################################
        
    except Exception as e:
        log(f"Failed to Run Script: {e}")
        
    start_button.config(state='normal')
    
    threading.Thread(target=run_test_script, daemon=True).start()

def start():
    start_button.config(state='disabled')
    threading.Thread(target=run_main_script, daemon=True).start()

#Start Button
start_button = tk.Button(check_frame, text="Start", command=start)
start_button.grid(row=1, column=3, sticky='n')

############## Column 4 Test Prints ##############
test_frame = tk.Frame(root)
test_frame.grid(row=0, column=4, sticky='n')

tk.Label(test_frame, text='test').grid(row=0, column=4)
test_output = tk.Text(test_frame, height=10, width=15, state='disabled')
test_output.grid(row=0, column=4, sticky='n')

def test_text(text):
    test_output.config(state='normal')
    test_output.insert(tk.END, text + "\n")
    test_output.see(tk.END)
    test_output.config(state='disabled')

############## Column 5 Log Prints ##############
log_frame = tk.Frame(root)
log_frame.grid(row=0, column=5, sticky='n')

tk.Label(log_frame, text='log Search').grid(row=0, column=5)
log_output = tk.Text(log_frame, height=10, width=40, state='disabled')
log_output.grid(row=0, column=5, sticky='n')

def log(text):
    log_output.config(state='normal')
    log_output.insert(tk.END, text + "\n")
    log_output.see(tk.END)
    log_output.config(state='disabled')
    
################################################ TEST SCRIPT ##############################################

def run_test_script():
    
    def ssh_bbb_connect():
        log("Connecting to BBB")
        global ssh_bbb, sftp_bbb
        bbb_ip = '192.168.7.2'
        bbb_user = 'raj'
        bbb_pass = 'Jetway'

        ssh_bbb = paramiko.SSHClient()
        ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
        log("Connected to BBB")
        
        sftp_bbb = ssh_bbb.open_sftp()
        time.sleep(1)
    
    def ssh_bbb_run(cmd):
        global ssh_bbb
        stdin, stdout, stderr = ssh_bbb.exec_command(cmd)
        output = stdout.read().decode()
        error = stdout.read().decode()
        if output is not None:
            log(output)
        if error is not None:
            log(error)
        return output
    
    def ssh_run_shell(client=None, command=None):
        global ssh_bbb
        bbb_pass = "Jetway"
        
        print(client)
        shell = client.invoke_shell()
            
        time.sleep(1)
        shell.recv(1000)
        
        shell.send(command + '\n')
        time.sleep(1)
        output = shell.recv(1000).decode()
        time.sleep(4)
        
        #add static ip
        if "[sudo] password for" in output:
            shell.send(bbb_pass + '\n')
            time.sleep(1)
            output += shell.recv(2000).decode()
            time.sleep(2)

        log(output)
        return shell

    #error value
    output1 = None
    output2 = None
    output3 = None
    output4 = None
    test_error = None
    
    if valid_ip == False:
        log("Invalid IP!")
        log("Exiting Script!")
        log("Close and Reopen Program!")
        return
    log("Copying Test File from Backup Folder")

    #### Test File Updates ####
    test_text("Test Checklist")
    test_text("[ ] Updated Test File")
    test_text("[ ] Uploaded Test File to BBB")
    test_text("[ ] Added IP to BBB")
    test_text("[ ] Router Tested")
    test_text(" ")
    test_text(" ")
    test_text(" ")
    test_text(" ")
                
    source_folder = 'og_testfile'
    destination_folder = 'testfile'

    os.makedirs(destination_folder, exist_ok=True)

    for filename in os.listdir(source_folder):
        source_path = os.path.join(source_folder, filename)
        destination_path = os.path.join(destination_folder)
        
        if os.path.isfile(source_path):
            shutil.copy2(source_path, destination_path)

    old_ip = "127.0.0.1"
    new_ip = str(gate_ip)
    print("new_ip: ", new_ip, flush=True)
    # ### Set up the xx.123 path
    # ip_parts = gate_ip.split(".")
    # print("ip_parts: ", ip_parts)
    # end_num = ip_parts[-1]
    # if end_num == "123":
    #     ip_parts[-1] = "100"
    # else:
    #     ip_parts[-1] = "123"
    # new_ip = ".".join(ip_parts)
    log(new_ip)

    with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'r') as file:
        content = file.read()
        
    log("Replacing Old Gate Ip")
    time.sleep(1)
    updated_content = content.replace(old_ip, new_ip)

    with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'w') as file:
        file.write(updated_content)

    with open("C:/Users/admin/Documents/teltonika/testfile/FloodLighToggle.py", 'r') as file:
        verify = file.read()
        if new_ip in verify:
            log("New Gate IP Updated")
            print("New Gate IP: ", new_ip, flush=True)
            
            test_text("Test Checklist")
            test_text("[x] Updated Test File")
            test_text("[ ] Uploaded Test File to BBB")
            test_text("[ ] Added IP to BBB")
            test_text("[ ] Router Tested")
            test_text(" ")
            test_text(" ")
            test_text(" ")
            test_text(" ")
            
        else:
            log("Incorrect! New Gate IP Not Updated Dash")
            print("old ip: ", old_ip)
            test_error = True
            output1 = "New Gate IP Did Not Update Correctly!"
            
    time.sleep(s_pause)

    ssh_bbb_connect()
    log("Copying FloodLighToggle.py File to BBB")
    time.sleep(s_pause)
    ssh_bbb_upload("testfile/FloodLighToggle.py", "/home/raj/FloodLighToggle.py")
    time.sleep(s_pause)

    log("Verifying FloodLighToggle.py File Upload")
    time.sleep(s_pause)
    output = ssh_bbb_run("ls -l /home/raj/")
    time.sleep(s_pause)
    
    if "FloodLighToggle.py" in output:
        log("FloodLighToggle.py found on BBB")
        
        test_text("Test Checklist")
        test_text("[x] Updated Test File")
        test_text("[x] Uploaded Test File to BBB")
        test_text("[ ] Added IP to BBB")
        test_text("[ ] Router Tested")
        test_text(" ")
        test_text(" ")
        test_text(" ")
        test_text(" ")
            
    else:
        log("Incorrect! FloodLighToggle.py not found on BBB!")
        ssh_bbb_close()
        exit()
        test_error = True
        output2 = "FloodLighToggle.py not found on BBB!"
        
    time.sleep(s_pause)
    log("\n")
    
    #add local ip to BBB
    ip_parts = gate_ip.split(".")
    print("ip_parts: ", ip_parts)
    end_num = ip_parts[-1]
    if end_num == "123":
        ip_parts[-1] = "100"
    else:
        ip_parts[-1] = "123"
    bbb_ip = ".".join(ip_parts)
    log(bbb_ip)
    print("bbb_ip: ", bbb_ip, flush=True)
    
    log("Setting Up Static IP of BBB to Router")
    time.sleep(1)
    log("Displaying Current IP(s)")
    time.sleep(1)
    ssh_bbb_run("ip addr show eth0")
    time.sleep(1)
    log("Adding Static IP to access Router")
    time.sleep(1)
    
    # Adding static IP to access Router
    try:
        ssh_run_shell(ssh_bbb, f"sudo ip addr add local {bbb_ip}/24 dev eth0")
    except Exception as e:
        output = e
         
    log(f"Added {bbb_ip}/24 Static IP to eth0")
    time.sleep(1)
    log("Displaying Current IP(s)")
    time.sleep(1)
    
    output = ssh_bbb_run("ip addr show eth0")
    
    if f"{bbb_ip}" not in output:
        test_error = True
        output3 = f"{bbb_ip} not added to BBB successfully"
        
    time.sleep(1)
    
    #### Test File Updates ####
    test_text("Test Checklist")
    test_text("[x] Updated Test File")
    test_text("[x] Uploaded Test File to BBB")
    test_text("[x] Added IP to BBB")
    test_text("[ ] Router Tested")
    test_text(" ")
    test_text(" ")
    test_text(" ")
    test_text(" ")
    
    ################## RUN TOGGLE SCRIPT ##################
    print("Running python test script now...", flush=True)
    output = ssh_bbb_run("python FloodLighToggle.py")
    
    crash_log = []
    
    if "Bytes in received" not in output:
        test_error = True
        
        if output1 is not None:
            crash_log.append(output1)
        if output2 is not None:
            crash_log.append(output2)
        if output3 is not None:
            crash_log.append(output3)
        if output is not None:
            crash_log.append(output)
                    
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        crash_folder = "crash_logs"
        os.makedirs(crash_folder, exist_ok=True)
        excel_name = excel.removesuffix(".xlsx")

        filename_crash = f"test_crash_log_{excel_name}_{gate}_{timestamp}.txt"
        filepath = os.path.join(crash_folder, filename_crash)
        
        with open(filepath, "w") as file:
            file.write("\n".join(crash_log))
            
    else:
        test_error = False
        test_text("Test Checklist")
        test_text("[x] Updated Test File")
        test_text("[x] Uploaded Test File to BBB")
        test_text("[x] Added IP to BBB")
        test_text("[x] Router Tested")
        test_text(" ")
        test_text(" ")
        test_text(" ")
        test_text(" ")
        
    #######################################################

    #Adding Test Timestamp
    current_datetime = datetime.now()

    wb = openpyxl.load_workbook(excel)
    sheet = wb.active
                            
    to_find = gate
    found = False
      
    for row in sheet.iter_rows(values_only=False):
        for cell in row:
            if str(cell.value) == to_find:
                print("Collecting Label Info")
                t_row = cell.row
                t_col = cell.column
                bridge_serial = sheet.cell(row=t_row, column=t_col + 1).value
                router_num = sheet.cell(row=t_row, column=t_col + 2).value
                mac_addr = sheet.cell(row=t_row, column=t_col + 3).value
                                
                print("Bridge Serial: ", bridge_serial)
                print("Router Num: ", router_num)
                print("Mac_addr: ", mac_addr)
                                
                found = True
        if found:
            break
                        
    if not found:
        log("Traceback Error Couldn't be Logged")
                            
    wb.save(excel)
                    
    ################# ERROR OCCURED DURING TESTING EXCEL LOGGING #################
                
    if test_error is True:
        print("Error Found During Router Test")
        
        try:
            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
            
            to_find = gate
            print("Test Selected excel: ", excel)
            print("Selected gate: ", gate)
            found = False
            
            for row in sheet.iter_rows(values_only=False):
                for cell in row:
                    if str(cell.value) == to_find:
                        t_row = cell.row
                        t_col = cell.column
                        print("Row:", t_row)
                        print("Col:", t_col)
                        print("Test Error Value: ", test_error)

                        t_cell = sheet.cell(row=t_row, column=12)
                        t_cell.value = current_datetime
                        t_cell.font = Font(color="FF0000")

                        t_row = cell.row
                        t_col = cell.column
                        file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
                        cell = sheet.cell(row=t_row, column=13)
                        cell.value = filename_crash
                        cell.hyperlink = file_path_crash
                        cell.font = Font(color="0000FF", underline="single")
                        
                        cell = sheet.cell(row=t_row, column=14)
                        if cell.value is None:
                            cell.value = int(1)
                        else:
                            cell.value = cell.value + 1
                            cell.font = Font(color="000000")
                            
                        found = True

                if found:
                    break
            
            if not found:
                log("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            log(f"An Error Occurred: {e}")
            
    ################ NO ERROR DURING TESTING EXCEL LOGGING ################
    
    else:
        print("No Error During Router Test")
        
        try:
            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
            
            to_find = gate
            print("Test Selected excel: ", excel)
            print("Test Selected gate: ", gate)
            found = False
            
            for row in sheet.iter_rows(values_only=False):
                for cell in row:
                    if str(cell.value) == to_find:
                        t_row = cell.row
                        t_col = cell.column
                        print("row:", t_row)
                        print("col:", t_col)
                        print("Test Error Value: ", test_error)

                        t_cell = sheet.cell(row=t_row, column=12)
                        t_cell.value = current_datetime
                        t_cell.font = Font(color="000000")
                            
                        print("Trying to Remove Crash Log File")

                        #remove the crash file if it exists
                        t_cell = sheet.cell(row=t_row, column=13)
                        print(t_cell.value)
                        t_cell.value = " "

                        #Test Number Increase by 1
                        cell = sheet.cell(row=t_row, column=14)
                        if cell.value is None:
                            cell.value = int(1)
                        else:
                            cell.value = cell.value + 1
                            cell.font = Font(color="000000")
                                
                        found = True
                if found:
                    break
            
            if not found:
                log("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            log(f"An Error Occurred: {e}")
            
    ############## OSHKOSH LOG #########################
    
    oshkosh_log_path = "oshkosh_log.xlsx"
        
    wb = openpyxl.load_workbook(oshkosh_log_path)
    sheet = wb.active
                    
    to_find = gate
    found = False
        
    #check for next empty row   
    for row_index, row in enumerate(sheet.iter_rows(min_col=1, max_col=1, values_only=True), start=1):
        if row[0] is None:
            target_row = row_index
            found = True
            break

    if found:
        #Airport
        print("Airport Log")
        airport_cell = sheet.cell(row=target_row, column=1)
        airport_cell.value = excel
        airport_cell.font = Font(color="000000")
            
        #Gate
        print("Gate Log")
        gate_cell = sheet.cell(row=target_row, column=2)
        gate_cell.value = int(gate)
        gate_cell.font = Font(color="000000")
            
        #Gate IP
        print("Gate IP Log")
        gate_ip_cell = sheet.cell(row=target_row, column=3)
        gate_ip_cell.value = gate_ip
        gate_ip_cell.font = Font(color="000000")
            
        #Gate Netmask
        print("Gate Netmask")
        netmask_cell = sheet.cell(row=target_row, column=4)
        netmask_cell.value = gate_netmask
        netmask_cell.font = Font(color="000000")
                    
        #Gate Gateway
        print("Gateway")
        gateway_cell = sheet.cell(row=target_row, column=5)
        gateway_cell.value = gate_gateway
        gateway_cell.font = Font(color="000000")
            
        #Bridge Serial
        print("Bridge Serial Log: ", bridge_serial)
        bridge_cell = sheet.cell(row=target_row, column=6)
        bridge_cell.value = bridge_serial
        bridge_cell.font = Font(color="000000")

        #Router Number
        print("Router Number Log")
        router_cell = sheet.cell(row=target_row, column=7)
        router_cell.value = router_num
        router_cell.font = Font(color="000000")
            
        #Mac Addr
        print("Mac Addr Log")
        mac_cell = sheet.cell(row=target_row, column=8)
        mac_cell.value = mac_addr
        mac_cell.font = Font(color="000000")
            
        #Router Test Date
        print("Timestamp Log")
        if test_error is True:
            timestamp_cell = sheet.cell(row=target_row, column=12)
            timestamp_cell.value = current_datetime
            timestamp_cell.font = Font(color="FF0000")
        else:
            timestamp_cell = sheet.cell(row=target_row, column=12)
            timestamp_cell.value = current_datetime
            timestamp_cell.font = Font(color="000000")
            
        #Crash Report
        if test_error is True:
            print("Crash Log")
            crash_cell = sheet.cell(row=target_row, column=13)
            file_path_crash = os.path.abspath(f"C:/Users/admin/Documents/teltonika/crash_logs/{filename_crash}") 
            crash_cell.value = filename_crash
            crash_cell.hyperlink = file_path_crash
            crash_cell.font = Font(color="0000FF", underline="single")
                    
    if not found:
        log("Oshkosh Log: Info Couldn't be Logged")
                    
    wb.save(oshkosh_log_path)
        
    end_time = time.perf_counter()

    print(f"Execution Time: {end_time - start_time:4f} seconds")
    print(f"Ex Time in Minutes: {(end_time - start_time) / 60:4f}")

    if test_error == True:    
        log("BROKEN SOMEWHERE")
    if test_error == False:
        log("IT WORKED YAYAYAYAYY")
    
def test():
    test_button.config(state='disabled')
    threading.Thread(target=run_test_script, daemon=True).start()
    test_button.config(state='normal')

#test Button
test_button = tk.Button(test_frame, text="Test", command=test)
test_button.grid(row=1, column=4, sticky='n')

################ Row 3 Info0 Frame ################
info_frame0 = tk.Frame(root)
info_frame0.grid(row=2, column=0, sticky='n')

tk.Label(info_frame0).grid(row=2, column=0)
info_output0 = tk.Text(info_frame0, height=8, width=20, state='disabled')
info_output0.grid(row=0, column=0, sticky='n')

def info0(text):
    info_output0.config(state='normal')
    info_output0.insert(tk.END, text + "\n")
    info_output0.see(tk.END)
    info_output0.config(state='disabled')
    
info0("ENTER ROUTER INFO")
info0("1. Click on Box Below")
info0("2. Scan Router QR Code")
info0("3. Press Submit")

################ Row 3 Info1 Frame ################
info_frame1 = tk.Frame(root)
info_frame1.grid(row=2, column=1, sticky='n')

tk.Label(info_frame1).grid(row=2, column=1)
info_output1 = tk.Text(info_frame1, height=8, width=20, state='disabled')
info_output1.grid(row=0, column=1, sticky='n')

def info1(text):
    info_output1.config(state='normal')
    info_output1.insert(tk.END, text + "\n")
    info_output1.see(tk.END)
    info_output1.config(state='disabled')

info1("Inform Engineer")
info1("If Any")
info1("Error Occurs")

############## Row 3 Instructions Frame ##############
bl1_frame = tk.Frame(root)
bl1_frame.grid(row=2, column=2, sticky='n')

tk.Label(bl1_frame).grid(row=2, column=2)
bl1_output = tk.Text(bl1_frame, height=8, width=20, state='disabled')
bl1_output.grid(row=0, column=2, sticky='n')

def instruct1(text):
    bl1_output.config(state='normal')
    bl1_output.insert(tk.END, text + "\n")
    bl1_output.see(tk.END)
    bl1_output.config(state='disabled')

instruct1("             INSTRUCTIONS")
instruct1("1. Connect Router to Hardware")
instruct1("2. Select Project from Dropdown")
instruct1("3. Select Bridge Serial from Dropdown")
instruct1("4. Scan Router QR Code")
instruct1("5. Click Start to Run Setup Script")
instruct1("6. Click Test to Run Test Script")

############## Row 3 Hardware Setup Frame ##############
bl2_frame = tk.Frame(root)
bl2_frame.grid(row=2, column=3, sticky='n')

tk.Label(bl2_frame).grid(row=2, column=3)
bl2_output = tk.Text(bl2_frame, height=8, width=15, state='disabled')
bl2_output.grid(row=0, column=3, sticky='n')

def instruct2(text):
    bl2_output.config(state='normal')
    bl2_output.insert(tk.END, text + "\n")
    bl2_output.see(tk.END)
    bl2_output.config(state='disabled')

instruct2("            HARDWARE SETUP")
instruct2("1. Router LAN1 Port to Beagleboneblack   Port using Ethernet Cable")
instruct2("2. Router LAN2 Port to PC Port using    Ethernet Cable")
instruct2("3. Router LAN3 Port to Ethernet Switch  Port using Ethernet Cable")

############## Row 3 Print Label Frame ##############
bl3_frame = tk.Frame(root)
bl3_frame.grid(row=2, column=4, sticky='n')

tk.Label(bl3_frame).grid(row=2, column=4)
bl3_output = tk.Text(bl3_frame, height=8, width=15, state='disabled')
bl3_output.grid(row=0, column=4, sticky='n')

def instruct3(text):
    bl3_output.config(state='normal')
    bl3_output.insert(tk.END, text + "\n")
    bl3_output.see(tk.END)
    bl3_output.config(state='disabled')

instruct3("              PRINT LABEL")
instruct3("1. Open Label Text File")
instruct3("2. Open Label Software")
instruct3("3. Paste Info to Software")
instruct3("4. Print Label")

############## Row 3 Test Text Frame ##############
bl4_frame = tk.Frame(root)
bl4_frame.grid(row=2, column=5, sticky='n')

tk.Label(bl4_frame).grid(row=2, column=5)
bl4_output = tk.Text(bl4_frame, height=8, width=40, state='disabled')
bl4_output.grid(row=0, column=5, sticky='n')

def instruct4(text):
    bl4_output.config(state='normal')
    bl4_output.insert(tk.END, text + "\n")
    bl4_output.see(tk.END)
    bl4_output.config(state='disabled')

instruct4("EMPTY")
instruct4("ADD INFO")

############## Row 4 User Input Scan ##############
input_frame = tk.Frame(root)
input_frame.grid(row=3, column=0, sticky='w')

user_entry = tk.Entry(input_frame, width=10)
user_entry.grid(row=0, column=0)

def user_submit():
    global temp_pass
    user_text=user_entry.get()
    print("User Submitted: ", user_text)
    user_entry.delete(0, tk.END)
    
    temp_pass = user_text.split("PW:")[1].split(";")[0]
    # temp_pass = "Jetway@dm1n"
    print("Temp Pass: ", temp_pass)
    
submit_button = tk.Button(input_frame, text="Submit", command=user_submit)
submit_button.grid(row=0, column=1)
    

root.mainloop()