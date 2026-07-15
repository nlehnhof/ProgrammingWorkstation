#GUI
# import tkinter as tk
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
import re
from datetime import datetime
from collections import deque
import ipaddress

import shutil
import argparse
import socket
import select

start_time = time.perf_counter()
current = os.getcwd()
print("current dir:", os.getcwd())
print("files in dir: ", os.listdir())

s_pause = 1
l_pause = 2

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

def is_valid_ip(ip_string):
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False
    
def validate_subnet(ip_str, netmask_str):
    """
    Determine if an IP belongs to the subnet defined by its own IP and netmask.
    
    Args:
        ip_str (str): IPv4 address (e.g., "10.120.80.4")
        netmask_str (str): Netmask in dotted decimal (e.g., "255.255.255.0")
    
    Returns:
        tuple: (bool, str) -> (True/False, calculated subnet in CIDR notation)
    """
    try:
        # Convert dotted decimal netmask to prefix length
        prefix_length = ipaddress.IPv4Network(f"0.0.0.0/{netmask_str}").prefixlen
        
        # Build network object from IP + prefix
        network = ipaddress.IPv4Network(f"{ip_str}/{prefix_length}", strict=False)
        
        # Check if IP is in its own network (always True unless invalid input)
        ip_obj = ipaddress.IPv4Address(ip_str)
        return (ip_obj in network, str(network))
    
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError):
        return (False, None)

    
def lookup_excel(sheet, gate, device):
    path = os.path.join(f"devices/{device}", sheet)
    file_path = os.path.join(os.getcwd(), path)
    # file_path = sheet
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
        if sheet is None:
            return
        
        for row in sheet.iter_rows(values_only=True):
            for idx, cell in enumerate(row):
                if str(cell) == to_find:
                    if row[idx + 1] is not None:
                        gate_ip = row[idx - 3]
                        gate_netmask = row[idx - 2]
                        gate_gateway = row[idx - 1]
                        if is_valid_ip(gate_ip) and validate_subnet(gate_ip, gate_netmask):
                            print(f"Gate IP: {gate_ip}", flush=True)
                            print(f"Netmask: {gate_netmask}", flush=True)
                            print(f"Gateway: {gate_gateway}", flush=True)
                        else:
                            print(f"Invalid IP and/or subnet: {gate_ip}; {gate_netmask}", flush=True)
                            print("Select Another Option", flush=True)
                            valid_ip = False
                    if row[idx + 10] is not None:
                        print("This Option has been Programmed Before")
                        print("Press Start if you Wish to Continue")

    except Exception as e:
        print(f"Error Reading File: {type(e).__name__}: {e}")
        print("Excel Read Error:", type(e).__name__, e)
        import traceback; traceback.print_exc()

def run_main_script(airport, gate, temp_pass, device):
    lookup_excel(airport, gate, device)
    current_dir = os.getcwd()
    device_path = os.path.join(current_dir, f"devices\\{device}")
    script_path = os.path.join(device_path, "teltonika.py")
    print(script_path, flush=True)

    crash_lines = deque(maxlen=50)
    error = False
    traceback = False

    #VALID IP CHECK
    if valid_ip == False:
        print("Invalid IP!")
        print("Exiting Script!")
        print("Close and Reopen Program!")
        return
    
    #RUN AUTOMATION SCRIPT

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    print("Running teltonika.py...", flush=True)

    process = subprocess.Popen([sys.executable, script_path, str(gate_ip), str(gate_netmask), str(gate_gateway), str(temp_pass)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in process.stdout:
        print(line, end="")

    process.wait()
    excel = os.path.join(device_path, airport)
    airport = airport.removesuffix(".xlsx")
    print(excel, flush=True)

    run_test_script(device_path, device, airport, excel, gate)
    
    # Read output line-by-line in real time
    with process.stdout: # type: ignore
        for line in process.stdout: # type: ignore
            statement = line.strip()
            crash_lines.append(statement)

            #####################  NON-TRACEBACK ERROR HANDLING #####################
            
            if "Incorrect" in line:
                error = True
                try:
                    crash_log = "\n".join(crash_lines)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    crash_folder = "crash_logs"
                    os.makedirs(crash_folder, exist_ok=True)
                    # excel_name = excel.removesuffix(".xlsx") # type:ignore
                    excel_name = airport
                    print("Airport: ", airport, flush=True)
                    filename_crash = f"crash_log_{excel_name}_{gate}_{timestamp}.txt"
                    filepath = os.path.join(crash_folder, filename_crash)

                    with open(filepath, "w") as file:
                        file.write(crash_log)
                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                    
                    to_find = gate
                    found = False
                    
                    current_datetime = datetime.now()
                    
                    if sheet is None:
                        return print("excel not found", flush=True)
                    for row in sheet.iter_rows(values_only=False):
                        for cell in row:
                            if str(cell.value) == to_find:
                                print("Crash Log")
                                t_row = cell.row
                                t_col = cell.column
                                file_path_crash = os.path.abspath(os.path.join(device_path, f"crash_logs/{filename_crash}")) 
                                cell = sheet.cell(row=t_row, column=10) # type:ignore
                                cell.value = filename_crash
                                cell.hyperlink = file_path_crash
                                cell.font = Font(color="0000FF", underline="single")
                                
                                print("Read Date and Time")
                                t_cell = sheet.cell(row=t_row, column=8) # type:ignore
                                t_cell.value = current_datetime
                                t_cell.font = Font(color="FF0000")
                                
                                found = True
                        if found:
                            break
                    
                    if not found:
                        print("Error Couldn't be Logged")
                    
                    wb.save(excel)
                    
                    current_datetime = datetime.now()
                
                except Exception as e:
                    print(f"An Error Occurred: {e}")
            
                #create label text file
                try:
                    print("Creating Label")
                    label_log = " "
                    
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    router_labels = "router_labels"
                    os.makedirs(router_labels, exist_ok=True)
                    excel_name = airport

                    filename_label = f"label_{airport}_{gate}_{timestamp}.txt"
                    filepath = os.path.join(router_labels, filename_label)

                    wb = openpyxl.load_workbook(excel)
                    
                    to_find = gate
                    found = False
                            
                    for row in sheet.iter_rows(values_only=False): # type: ignore
                        for cell in row:
                            if str(cell.value) == to_find:
                                print("Collecting Label Info")
                                t_row = cell.row
                                t_col = cell.column
                                bridge_serial = sheet.cell(row=t_row, column=t_col).value # type: ignore
                                router_num = sheet.cell(row=t_row, column=6).value # type: ignore
                                mac_addr = sheet.cell(row=t_row, column=7).value # type: ignore
                                gate_num = sheet.cell(row=t_row, column=1).value # type: ignore
                                
                                print("Bridge Serial: ", bridge_serial)
                                print("Router Num: ", router_num)
                                print("Mac_addr: ", mac_addr)
                                print("Gate Num: ", mac_addr)
                                
                                found = True
                        if found:
                            break
                        
                    if not found:
                        print("Traceback Error Couldn't be Logged")
                            
                    wb.save(excel)
                    print(filepath, flush=True)
                    print(filepath)
                    with open(filepath, "w") as file:
                        print("Writing Label Info")
                        first_line = "GATE " + str(gate_num) +" SN" + str(bridge_serial) + "," + "PN: " + str(router_num) + "," + "MA: " + str(mac_addr) + "," + "IP: " + str(gate_ip) # type:ignore
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
                            
                    for row in sheet.iter_rows(values_only=False): # type: ignore
                        for cell in row:
                            if str(cell.value) == to_find:
                                t_row = cell.row
                                t_col = cell.column
                                file_path_label = os.path.abspath(os.path.join(device_path, f"router_labels/{filename_label}"))
                                
                                #Label
                                cell = sheet.cell(row=t_row, column=9) # type: ignore
                                cell.value = filename_label
                                cell.hyperlink = file_path_label
                                cell.font = Font(color="0000FF", underline="single")
                                
                                #Program Number
                                cell = sheet.cell(row=t_row, column=11) # type: ignore
                                if cell.value is None:
                                    cell.value = int(1)
                                else:
                                    cell.value = cell.value + 1
                                cell.font = Font(color="000000")
                                
                                cell = sheet.cell(row=t_row, column=11) # type: ignore
                                cell.value = "Not Tested"
                                cell.font = Font(color="000000")
                                
                                found = True
                        if found:
                            break
                            
                    if not found:
                        print("Label File Couldn't be Logged")
                            
                    wb.save(excel)

                except Exception as e:
                    print(f"An Error Occurred 1: {e}")
                
            if "Traceback" in statement:
                traceback = True

            if "MAC Addr:" in statement:
                mac_addr = statement.split("MAC Addr:")[1].strip()
                
                print("MAC Address: ", mac_addr)
                
                try:
                    wb = openpyxl.load_workbook(excel)
                    sheet = wb.active
                    
                    to_find = gate
                    found = False
                    
                    for row in sheet.iter_rows(values_only=False): # type:ignore
                        for cell in row:
                            if str(cell.value) == to_find:
                                t_row = cell.row
                                t_col = cell.column
                                
                                t_cell = sheet.cell(row=t_row, column=7) # type:ignore
                                t_cell.value = mac_addr
                                t_cell.font = Font(color="000000")

                                found = True
                        if found:
                            break
                    
                    if not found:
                        print("Mac Address Couldn't be Logged")
                    
                    wb.save(excel)
                    
                except Exception as e:
                    print(f"An Error Occurred 2: {e}")
                
        # #end of automation python file
        # process.wait()
        
        ################### Traceback File Creation and Logging #####################
        
        current_datetime = datetime.now()
        
        if traceback is True:
            try:
                crash_log = "\n".join(crash_lines)
                    
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                crash_folder = "crash_logs"
                os.makedirs(crash_folder, exist_ok=True)
                excel_name = excel.removesuffix(".xlsx")
                print("airport ", airport)

                filename_crash = f"crash_log_2_{airport}_{gate}_{timestamp}.txt"
                filepath = os.path.join(crash_folder, filename_crash)

                with open(filepath, "w") as file:
                    file.write(crash_log)
                    
                wb = openpyxl.load_workbook(excel)
                sheet = wb.active
                    
                to_find = gate
                found = False
                    
                for row in sheet.iter_rows(values_only=False): # type:ignore
                    for cell in row:
                        if str(cell.value) == to_find:
                            t_row = cell.row
                            t_col = cell.column
                            file_path_crash = os.path.abspath(f"crash_logs/{filename_crash}")
                            cell = sheet.cell(row=t_row, column=10) # type:ignore
                            cell.value = filename_crash
                            cell.hyperlink = file_path_crash
                            cell.font = Font(color="0000FF", underline="single")
                                
                            found = True
                    if found:
                        break
                    
                if not found:
                    print("Traceback Error Couldn't be Logged")
                    
                wb.save(excel)

            except Exception as e:
                print(f"An Error Occurred 3: {e}")
        
        ########################## ADD TIMESTAMP ############################
        
        current_datetime = datetime.now()
        
        try:
            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
            
            to_find = gate
            print("selected excel", excel)
            print("selected gate", gate)
            found = False
            
            for row in sheet.iter_rows(values_only=False): # type:ignore
                for cell in row:
                    if str(cell.value) == to_find:
                        t_row = cell.row
                        t_col = cell.column
                        print("row:", t_row)
                        print("col:", t_col)
                        print("Error Value: ", error)
                        
                        #change date time color to red
                        if error is True or traceback is True:
                            t_cell = sheet.cell(row=t_row, column=8)# type:ignore
                            t_cell.value = current_datetime
                            t_cell.font = Font(color="FF0000")
                        
                        #date time color to black
                        else:
                            print("correct spot")
                            t_cell = sheet.cell(row=t_row, column=8) # type:ignore
                            t_cell.value = current_datetime
                            t_cell.font = Font(color="000000")
                            
                            print("Trying to Remove Crash Log File")

                            #remove the crash file if it exists
                            t_cell = sheet.cell(row=t_row, column=10) # type:ignore
                            print(t_cell.value)
                            t_cell.value = " "

                        found = True
                if found:
                    break
            
            if not found:
                print("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            print(f"An Error Occurred 4: {e}")
            
        ########################## CREATE A LABEL ##########################
        try:
            print("Creating Label")            
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            router_labels = "router_labels"
            os.makedirs(router_labels, exist_ok=True)
            excel_name = excel.removesuffix(".xlsx")

            filename_label = f"labe2l_{airport}_{gate}_{timestamp}.txt"
            filepath = os.path.join(router_labels, filename_label)

            wb = openpyxl.load_workbook(excel)
            sheet = wb.active
                    
            to_find = gate
            found = False
                    
            for row in sheet.iter_rows(values_only=False): # type:ignore
                for cell in row:
                    if str(cell.value) == to_find:
                        print("Collecting Label Info")
                        t_row = cell.row
                        t_col = cell.column

                        bridge_serial = sheet.cell(row=t_row, column=t_col).value # type:ignore
                        router_num = sheet.cell(row=t_row, column=6).value# type:ignore
                        mac_addr = sheet.cell(row=t_row, column=7).value# type:ignore
                        gate_num = sheet.cell(row=t_row, column=1).value# type:ignore
                                
                        print("Bridge Serial: ", bridge_serial)
                        print("Router Num: ", router_num)
                        print("Mac_addr: ", mac_addr)
                        print("Gate Num: ", gate_num)
                        mac_addr = str(mac_addr)
                        
                        found = True
                if found:
                    break
            if not found:
                print("Error Couldn't be Logged")
                    
            wb.save(excel)
            
            with open(filepath, "w") as file:
                print("Writing Label Info")
                first_line = "GATE " + str(gate_num) +" SN" + str(bridge_serial) + "," # type:ignore
                second_line = "PN: " + str(router_num) + "," # type:ignore
                third_line = "MA: " + str(mac_addr) + "," # type:ignore
                fourth_line = "IP: " + str(gate_ip) + "," # type:ignore
                file.write(first_line)
                file.write(second_line)
                file.write(third_line)
                file.write(fourth_line)
                
            with open(filepath, "r") as file:
                print("Label File Contents")
                print(file.read())
                print("Programming and Testing Complete.")
                print("Saving log file...")
                print("Device programming complete. Continue to next Device.")
                sys.exit(0)
                
        except Exception as e:
            print(f"An Error Occurred: {e}")

def run_test_script(device_path, device, airport, excel, gate):
# def run_test_script():
    def ssh_bbb_connect():
        global ssh_bbb, sftp_bbb
        bbb_ip = '192.168.7.2'
        bbb_user = 'raj'
        bbb_pass = 'Jetway'

        ssh_bbb = paramiko.SSHClient()
        ssh_bbb.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_bbb.connect(bbb_ip, username=bbb_user, password=bbb_pass)
        
        sftp_bbb = ssh_bbb.open_sftp()
        time.sleep(1)
    
    def ssh_bbb_run(cmd):
        global ssh_bbb
        stdin, stdout, stderr = ssh_bbb.exec_command(cmd)
        output = stdout.read().decode()
        error = stdout.read().decode()
        if output is not None:
            print(output)
        if error is not None:
            print(error)
        return output
    
    def ssh_run_shell(client=None, command=None):
        global ssh_bbb
        bbb_pass = "Jetway"
        
        print(client)
        if client is None:
            return
        shell = client.invoke_shell()
            
        time.sleep(1)
        shell.recv(1000)
        
        if command is None:
            return
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

        print(output)
        return shell

    #error value
    output1 = None
    output2 = None
    output3 = None
    output4 = None
    test_error = None
    
    lookup_excel(airport+".xlsx", gate, device)

    if valid_ip == False:
        print("Invalid IP!")
        print("Exiting Script!")
        print("Close and Reopen Program!")
        return
    print("Copying Test File from Backup Folder")

    print("Getting router ip...", flush=True)
    ssh_bbb_connect()
    time.sleep(s_pause)
    output = ssh_bbb_run("ip addr show eth0")
    time.sleep(s_pause)

    # Regex for IPV4
    pattern_ipv4 = r'\b10.\d{1,3}\.\d{1,3}.123\b'
    ipv4s = re.findall(pattern_ipv4, output)
    print(ipv4s, flush=True)
    # for addr in ipv4s:
    #     if addr != "10.28.18.123":
    #         print(f"Router already programmed to IP:{addr}", flush=True)
    #         gate_ip = str(ipv4s[2])

    source_folder = os.path.join(device_path, 'og_testfile')
    destination_folder = os.path.join(device_path, 'testfile')

    os.makedirs(destination_folder, exist_ok=True)

    for filename in os.listdir(source_folder):
        source_path = os.path.join(source_folder, filename)
        destination_path = os.path.join(destination_folder)
        
        if os.path.isfile(source_path):
            shutil.copy2(source_path, destination_path)

    old_ip = "127.0.0.1"
    new_ip = str(gate_ip)
    print("new_ip: ", new_ip, flush=True)

    with open(os.path.join(device_path, f"testfile/FloodLighToggle.py"), 'r') as file:
        content = file.read()
        
    print("Replacing Old Gate Ip")
    time.sleep(1)
    updated_content = content.replace(old_ip, new_ip)

    with open(os.path.join(device_path, f"testfile/FloodLighToggle.py"), 'w') as file:
        file.write(updated_content)

    with open(os.path.join(device_path, f"testfile/FloodLighToggle.py"), 'r') as file:
        verify = file.read()
        if new_ip in verify:
            print("New Gate IP Updated")
            print("New Gate IP: ", new_ip, flush=True)
            
        else:
            print("Incorrect! New Gate IP Not Updated Dash")
            print("old ip: ", old_ip)
            test_error = True
            output1 = "New Gate IP Did Not Update Correctly!"
            
    time.sleep(s_pause)

    ssh_bbb_connect()
    print("Copying FloodLighToggle.py File to BBB")
    time.sleep(s_pause)
    ssh_bbb_upload(os.path.join(device_path, "testfile/FloodLighToggle.py"), "/home/raj/FloodLighToggle.py")
    time.sleep(s_pause)

    print("Verifying FloodLighToggle.py File Upload")
    time.sleep(s_pause)
    output = ssh_bbb_run("ls -l /home/raj/")
    time.sleep(s_pause)
    
    if "FloodLighToggle.py" in output:
        print("FloodLighToggle.py found on BBB")
            
    else:
        print("Incorrect! FloodLighToggle.py not found on BBB!")
        ssh_bbb_close()
        exit()
        test_error = True
        output2 = "FloodLighToggle.py not found on BBB!"
        
    time.sleep(s_pause)
    print("\n")
    
    #add local ip to BBB
    ip_parts = gate_ip.split(".")
    print("ip_parts: ", ip_parts)
    end_num = ip_parts[-1]
    if end_num == "123":
        ip_parts[-1] = "100"
    else:
        ip_parts[-1] = "123"
    bbb_ip = ".".join(ip_parts)
    print(bbb_ip)
    print("bbb_ip: ", bbb_ip, flush=True)
    
    print("Setting Up Static IP of BBB to Router")
    time.sleep(1)
    print("Displaying Current IP(s)")
    time.sleep(1)
    ssh_bbb_run("ip addr show eth0")
    time.sleep(1)
    print("Adding Static IP to access Router")
    time.sleep(1)
    
    # Adding static IP to access Router
    try:
        ssh_run_shell(ssh_bbb, f"sudo ip addr add local {bbb_ip}/24 dev eth0")
    except Exception as e:
        output = e
         
    print(f"Added {bbb_ip}/24 Static IP to eth0")
    time.sleep(1)
    print("Displaying Current IP(s)")
    time.sleep(1)
    
    output = ssh_bbb_run("ip addr show eth0")
    
    if f"{bbb_ip}" not in output:
        test_error = True
        output3 = f"{bbb_ip} not added to BBB successfully"
        
    time.sleep(1)
    
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

        filename_crash = f"test_crash_log_{airport}_{gate}_{timestamp}.txt"
        filepath = os.path.join(crash_folder, filename_crash)
        
        with open(filepath, "w") as file:
            file.write("\n".join(crash_log))
            
    else:
        test_error = False

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
        print("Traceback Error Couldn't be Logged")
                            
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
                        file_path_crash = os.path.abspath(os.path.join(device_path, f"crash_logs/{filename_crash}")) 
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
                print("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            print(f"An Error Occurred: {e}")
            
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
                print("Date and Time Couldn't be Logged")
            
            wb.save(excel)
            
        except Exception as e:
            print(f"An Error Occurred: {e}")

end_time = time.perf_counter()

# """