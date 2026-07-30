import time
from resources.utilities.excel_utils import lookup_excel
import subprocess
import sys
import os
from collections import deque
import openpyxl
from datetime import datetime

start_time = time.perf_counter()
current = os.getcwd()
print("current dir:", current, flush=True)

s_pause = 1
l_pause = 2

dropdown = None
valid_ip = True

def run_main_script(airport, gate, default_pass, device):
    start_time = time.perf_counter()

    file_path = os.path.abspath(f"devices/{device}/prog_dev.py")
    print(file_path)
    dir_path = os.path.dirname(file_path)
    print("Directory path:", dir_path)
    script_path = os.path.join(dir_path, "digix20.py")
    sheet = os.path.join(dir_path, airport)
    print("sheet", sheet, flush=True)
    print(script_path, flush=True)

    gate_ip, gate_netmask, gate_gateway = lookup_excel(sheet, gate)

    crash_lines = deque(maxlen=50)
    error = False
    traceback = False

    if valid_ip == False:
        print("Invalid IP!")
        return

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    print("Running digix20.py", flush = True)

    print(gate_ip, flush=True)
    print(gate_netmask, flush=True)

    process = subprocess.Popen([sys.executable, script_path, str(gate_ip), str(gate_netmask), str(gate_gateway), str(default_pass)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in process.stdout: # type:ignore
        print(line, end="")

    process.wait()
    excel = os.path.join(dir_path, airport)
    airport = airport.removesuffix(".xlsx")
    # print(excel, flush=True)

    with process.stdout: # type:ignore
        for line in process.stdout: # type:ignore
            statement = line.strip()
            crash_lines.append(statement)

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
                    filename_crash = f"crash_log_{device}_{excel_name}_{gate}_{timestamp}.txt"
                    filepath = os.path.join(crash_folder, filename_crash)

                    with open(filepath, "w") as file:
                        file.write(crash_log)
                              
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

                    filename_label = f"label_{device}_{airport}_{gate}_{timestamp}.txt"
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
                        file.write(first_line)

                    with open(filepath, "r") as file:
                        print("Label File Contents")
                        print(file.read())
                    
                except Exception as e:
                    print(f"An Error Occurred 1: {e}")

        if traceback is True:
            try:
                crash_log = "\n".join(crash_lines)
                    
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                crash_folder = "crash_logs"
                os.makedirs(crash_folder, exist_ok=True)
                excel_name = excel.removesuffix(".xlsx")
                print("airport ", airport)

                filename_crash = f"crash_log_{device}_{airport}_{gate}_{timestamp}.txt"
                filepath = os.path.join(crash_folder, filename_crash)

                with open(filepath, "w") as file:
                    file.write(crash_log)
                    
            except Exception as e:
                print(f"An Error Occurred 3: {e}")

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