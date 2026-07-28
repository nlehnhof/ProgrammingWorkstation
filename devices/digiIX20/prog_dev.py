import time
from resources.utilities.excel_utils import lookup_excel
import subprocess
import sys
import os
from collections import deque

start_time = time.perf_counter()
current = os.getcwd()
print("current dir:", current, flush=True)

s_pause = 1
l_pause = 2

dropdown = None
valid_ip = True

def run_main_script(airport, gate, default_pass):
    start_time = time.perf_counter()
    gate_ip = None
    gate_netmask = None
    gate_gateway = None
      
    dir_path = os.path.dirname(__file__)
    print("Directory path:", dir_path)
    script_path = os.path.join(dir_path, "digix20.py")
    sheet = os.path.join(dir_path, airport)
    print(script_path, flush=True)
    lookup_excel(sheet, gate)

    crash_lines = deque(maxlen=50)
    error = False
    traceback = False

    if valid_ip == False:
        print("Invalid IP!")
        return

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    print("Running digix20.py", flush = True)

    process = subprocess.Popen([sys.executable, script_path, str(gate_ip), str(gate_netmask), str(gate_gateway), str(default_pass)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in process.stdout: # type:ignore
        print(line, end="")

    process.wait()
    excel = os.path.join(dir_path, airport)
    airport = airport.removesuffix(".xlsx")
    print(excel, flush=True)

    with process.stdout: # type:ignore
        for line in process.stdout: # type:ignore
            statement = line.strip()
            crash_lines.append(statement)

    end_time = time.perf_counter()
    crash_lines.append(start_time)
    crash_lines.append(end_time)