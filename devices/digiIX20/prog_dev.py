import time
from resources.utilities.excel_utils import lookup_excel
import subprocess
import sys
import os
from collections import deque
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

    print("Logging output")
    output_logs = "output_logs"
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.makedirs(output_logs, exist_ok=True)
    filename_log = f"log_{airport}_{gate}_{timestamp}.txt"
    filepath = os.path.join(output_logs, filename_log)

    with process.stdout: # type:ignore
        for line in process.stdout: # type:ignore
            statement = line.strip()
            crash_lines.append(statement)
            with open(filepath, "w") as file:
                file.write(f"{statement}\n")

    end_time = time.perf_counter()
    crash_lines.append(start_time)
    crash_lines.append(end_time)
    with open(filepath, "w") as file:
        file.write(f" {start_time} : {end_time}\n")

    try:
        print("Creating Label")
        label_log = " "
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        router_labels = "router_labels"
        os.makedirs(router_labels, exist_ok=True)
        filename_label = f"label_{airport}_{gate}_{timestamp}.txt"
        filepath = os.path.join(router_labels, filename_label)
        with open(filepath, "w") as file:
            print("Writing Label Info")
            first_line = "GATE " + str(gate_num) +" SN" + str(bridge_serial) + "," + "PN: " + str(router_num) + "," + "MA: " + str(mac_addr) + "," + "IP: " + str(gate_ip) # type:ignore
            file.write(first_line)
    except:
        print("Label not created", flush=True)