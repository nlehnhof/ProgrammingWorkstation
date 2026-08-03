"""GUI-facing orchestration for the Digi IX20.

Loaded by pages/program_page.py with exec() into a fresh namespace, so this
module gets no __file__ and must resolve paths from the current working
directory (the repo root). The only required export is run_main_script().

If the page seeded the namespace with `progress_callback`, milestone updates
emitted by digix20.py are forwarded to it so the Status checklist can update
live. Without it, everything still works -- the callback is optional.
"""

import os
import subprocess
import sys
import time
from collections import deque
from datetime import datetime

import openpyxl
from openpyxl.styles import Font

from resources.utilities.app_paths import app_root, script_command
from resources.utilities.excel_utils import lookup_excel

start_time = time.perf_counter()
current = os.getcwd()
print("current dir:", current, flush=True)

STATUS_PREFIX = "##STATUS##"

# Column positions in the airport sheets (see IP_TEMPLATE.xlsx headers).
COLUMN_NAMES = {
    "gate": "PBB Gate",
    "serial": "PBB SN",
    "part": "Jetway PN",
    "mac": "MAC Address",
    "programmed_on": "Router Programmed On",
    "label": "Label",
    "crash": "Crash Report",
}

# Fallbacks if a sheet has no recognisable header row.
FALLBACK_COLUMNS = {
    "gate": 1,
    "serial": 5,
    "part": 6,
    "mac": 7,
    "programmed_on": 8,
    "label": 9,
    "crash": 10,
}


class DigiProgrammingError(RuntimeError):
    """Raised when the device did not program successfully.

    Propagates out of run_main_script so the app's global error handler logs
    it and shows the operator a dialog, the same way TR surfaces failures.
    """


def get_header_map(sheet):
    """Map lower-cased header text in row 1 to its 1-based column number."""
    headers = {}
    for cell in next(sheet.iter_rows(min_row=1, max_row=1), ()):
        if cell.value is not None:
            headers[str(cell.value).strip().lower()] = cell.column
    return headers


def col(header_map, key):
    """Column number for a logical field, by header name where possible."""
    name = COLUMN_NAMES[key].lower()
    if name in header_map:
        return header_map[name]
    return FALLBACK_COLUMNS[key]


def find_gate_row(sheet, gate):
    """Row number whose gate/serial cell matches the selected dropdown value."""
    for row in sheet.iter_rows(values_only=False):
        for cell in row:
            if cell.value is not None and str(cell.value) == str(gate):
                return cell.row
    return None


def run_main_script(airport, gate, default_pass, device):
    """Program one Digi IX20 and record the result in the airport sheet."""
    progress = globals().get("progress_callback")

    def report(step_id, state, detail=""):
        if progress is not None:
            try:
                progress(step_id, state, detail)
            except Exception as exc:
                print(f"Could not update the status checklist: {exc}", flush=True)

    run_start = time.perf_counter()

    dir_path = os.path.join(app_root(), "devices", device)
    print("Directory path:", dir_path)
    script_path = os.path.join(dir_path, "digix20.py")
    excel = os.path.join(dir_path, airport)
    print("sheet", excel, flush=True)
    print(script_path, flush=True)

    gate_ip, gate_netmask, gate_gateway = lookup_excel(excel, gate)

    if not gate_ip or not gate_netmask:
        message = (
            f"Invalid IP! No usable address for gate {gate} in {airport}. "
            "Select another option."
        )
        print(message, flush=True)
        raise DigiProgrammingError(message)

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")
    print("Running digix20.py", flush=True)

    print(gate_ip, flush=True)
    print(gate_netmask, flush=True)

    airport_name = airport.removesuffix(".xlsx")

    crash_lines = deque(maxlen=200)
    error = False
    saw_traceback = False
    mac_addr = None
    failure_detail = None

    process = subprocess.Popen(
        script_command(script_path, gate_ip, gate_netmask, gate_gateway, default_pass),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    # One pass over the child's output: forward milestones, watch for failure
    # sentinels, and keep a rolling buffer for the crash log.
    with process.stdout:  # type: ignore[union-attr]
        for line in process.stdout:  # type: ignore[union-attr]
            statement = line.strip()

            if statement.startswith(STATUS_PREFIX):
                payload = statement[len(STATUS_PREFIX):]
                parts = payload.split("|", 2)
                step_id = parts[0] if parts else ""
                state = parts[1] if len(parts) > 1 else ""
                detail = parts[2] if len(parts) > 2 else ""
                if state == "FAIL":
                    error = True
                    failure_detail = detail or failure_detail
                report(step_id, state, detail)
                continue  # markers are plumbing, not operator-facing output

            print(line, end="")
            crash_lines.append(statement)

            if "Incorrect" in statement:
                error = True
                failure_detail = failure_detail or statement
            if "Traceback" in statement:
                saw_traceback = True
            if "MAC Addr:" in statement:
                mac_addr = statement.split("MAC Addr:")[1].strip()

    process.wait()

    if process.returncode != 0:
        error = True
        failure_detail = failure_detail or f"digix20.py exited with code {process.returncode}"

    elapsed = time.perf_counter() - run_start
    print(f"Elapsed: {int(elapsed // 60)} min {int(elapsed % 60)} sec", flush=True)

    crash_filename = None
    if error or saw_traceback:
        crash_filename = write_crash_log(
            dir_path, device, airport_name, gate, crash_lines
        )

    label_filename = update_sheet_and_label(
        dir_path=dir_path,
        excel=excel,
        device=device,
        airport_name=airport_name,
        gate=gate,
        gate_ip=gate_ip,
        mac_addr=mac_addr,
        error=error or saw_traceback,
        crash_filename=crash_filename,
    )

    if error or saw_traceback:
        message = failure_detail or "Device programming failed. See the log for details."
        print("Programming failed. Check the Status checklist and the crash log.",
              flush=True)
        raise DigiProgrammingError(message)

    if label_filename:
        print("Programming and Testing Complete.", flush=True)
    print("Saving log file...", flush=True)
    print("Device programming complete. Continue to next Device.", flush=True)


def write_crash_log(dir_path, device, airport_name, gate, crash_lines):
    """Write the tail of the run's output next to the device's own files."""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        crash_folder = os.path.join(dir_path, "crash_logs")
        os.makedirs(crash_folder, exist_ok=True)

        filename_crash = f"crash_log_{device}_{airport_name}_{gate}_{timestamp}.txt"
        filepath = os.path.join(crash_folder, filename_crash)

        with open(filepath, "w", encoding="utf-8") as file:
            file.write("\n".join(crash_lines))

        print(f"Crash log written: {filepath}", flush=True)
        return filename_crash
    except Exception as e:
        print(f"An Error Occurred writing the crash log: {e}", flush=True)
        return None


def update_sheet_and_label(dir_path, excel, device, airport_name, gate, gate_ip,
                           mac_addr, error, crash_filename):
    """Stamp the airport sheet and write the Brady label file."""
    try:
        print("Creating Label", flush=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        router_labels = os.path.join(dir_path, "router_labels")
        os.makedirs(router_labels, exist_ok=True)

        filename_label = f"label_{device}_{airport_name}_{gate}_{timestamp}.txt"
        filepath = os.path.join(router_labels, filename_label)

        wb = openpyxl.load_workbook(excel)
        sheet = wb.active
        if sheet is None:
            print("Error Couldn't be Logged: no active worksheet", flush=True)
            return None

        header_map = get_header_map(sheet)
        t_row = find_gate_row(sheet, gate)
        if t_row is None:
            print("Error Couldn't be Logged: gate not found in the sheet", flush=True)
            return None

        print("Collecting Label Info", flush=True)
        bridge_serial = sheet.cell(row=t_row, column=col(header_map, "serial")).value
        router_num = sheet.cell(row=t_row, column=col(header_map, "part")).value
        gate_num = sheet.cell(row=t_row, column=col(header_map, "gate")).value

        mac_cell = sheet.cell(row=t_row, column=col(header_map, "mac"))
        if mac_addr:
            mac_cell.value = mac_addr
        sheet_mac = mac_cell.value

        print("Bridge Serial: ", bridge_serial)
        print("Router Num: ", router_num)
        print("Mac_addr: ", sheet_mac)
        print("Gate Num: ", gate_num)

        # Timestamp red on failure, black on success -- same convention as TR.
        stamp = sheet.cell(row=t_row, column=col(header_map, "programmed_on"))
        stamp.value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stamp.font = Font(color="FF0000") if error else Font(color="000000")

        crash_cell = sheet.cell(row=t_row, column=col(header_map, "crash"))
        if crash_filename:
            crash_path = os.path.abspath(os.path.join(dir_path, "crash_logs", crash_filename))
            crash_cell.value = crash_filename
            crash_cell.hyperlink = crash_path
            crash_cell.font = Font(color="0000FF", underline="single")
        elif not error:
            crash_cell.value = " "

        label_cell = sheet.cell(row=t_row, column=col(header_map, "label"))
        label_cell.value = filename_label
        label_cell.hyperlink = os.path.abspath(filepath)
        label_cell.font = Font(color="0000FF", underline="single")

        try:
            wb.save(excel)
        except PermissionError:
            print(f"Could not save {excel} -- close it in Excel and try again.", flush=True)

        with open(filepath, "w", encoding="utf-8") as file:
            print("Writing Label Info", flush=True)
            file.write("GATE " + str(gate_num) + " SN" + str(bridge_serial) + ",")
            file.write("PN: " + str(router_num) + ",")
            file.write("MA: " + str(sheet_mac) + ",")
            file.write("IP: " + str(gate_ip) + ",")

        with open(filepath, "r", encoding="utf-8") as file:
            print("Label File Contents", flush=True)
            print(file.read(), flush=True)

        return filename_label

    except Exception as e:
        print(f"An Error Occurred: {e}", flush=True)
        return None
