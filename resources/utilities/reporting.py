"""Recording the outcome of a programming run: crash log, sheet, label.

Every device ends a run the same way -- write the tail of the output to a
crash log if something went wrong, stamp the gate's row in the airport
spreadsheet, and produce the label file the Brady printer picks up. That
bookkeeping was written out longhand, four times over, inside each device's
`prog_dev.py`; each copy re-scanned the sheet for the gate row and addressed
cells by hardcoded column number. This is the one implementation they share.

Two conventions worth knowing, both inherited from how the sheets are read by
hand afterwards:

* The "Router Programmed On" timestamp is **red on failure, black on success**.
  That colour is how an operator scanning the sheet spots a gate that needs
  redoing.
* A failed run still stamps the sheet but writes **no label**. A printable
  label for a router that did not program is worse than no label at all,
  because somebody can stick it on.
"""

import os
from datetime import datetime

import openpyxl
from openpyxl.styles import Font

from resources.utilities.excel_utils import (
    cell_text,
    find_column,
    find_row_by_value,
    get_header_map,
)

CRASH_DIR = "crash_logs"
LABEL_DIR = "router_labels"

RED = Font(color="FF0000")
BLACK = Font(color="000000")
LINK = Font(color="0000FF", underline="single")

# Logical field -> (header text, which occurrence of it).
COLUMNS = {
    "gate": ("PBB Gate", 0),
    "serial": ("PBB SN", 0),
    "part": ("Jetway PN", 0),
    "mac": ("MAC Address", 0),
    "programmed_on": ("Router Programmed On", 0),
    "label": ("Label", 0),
    "crash_report": ("Crash Report", 0),
    "prg_count": ("PRG #", 0),
    "tested_on": ("Router Tested On", 0),
    "test_crash_report": ("Crash Report", 1),
    "test_count": ("Test #", 0),
}


def column_for(header_map, field):
    """Column number for a logical field name, or None if the sheet lacks it.

    Returns None rather than raising: sheets in the field are at different
    template versions, and a missing optional column ("Test #", say) must not
    abort a run that has already programmed the hardware.
    """
    name, occurrence = COLUMNS[field]
    try:
        return find_column(header_map, name, occurrence)
    except KeyError:
        return None


def timestamp():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


# ---------------------------------------------------------------------------
# Crash logs
# ---------------------------------------------------------------------------

def write_crash_log(device_dir, device, airport, gate, lines):
    """Save the tail of a failed run beside the device's own files.

    Returns the bare filename (which is what goes in the sheet cell) or None
    if it could not be written -- never raises, because losing the log must
    not also lose the sheet update that points at it.
    """
    try:
        folder = os.path.join(device_dir, CRASH_DIR)
        os.makedirs(folder, exist_ok=True)

        filename = f"crash_log_{device}_{airport}_{gate}_{timestamp()}.txt"
        path = os.path.join(folder, filename)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

        print(f"Crash log written: {path}", flush=True)
        return filename
    except OSError as exc:
        print(f"Could not write the crash log: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def write_label_file(device_dir, filename, gate_num, serial, part, mac, gate_ip):
    """Write the label the Brady printer watches for.

    Fields are run through `cell_text`, so a blank or literal-"None" cell
    prints as empty rather than putting the word "None" on a sticker.
    """
    folder = os.path.join(device_dir, LABEL_DIR)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, filename)

    if not cell_text(part):
        print("Warning: no Jetway PN in the sheet for this gate; "
              "the label's PN will be blank.", flush=True)
    if not cell_text(mac):
        print("Warning: no MAC address captured; the label's MA will be blank.",
              flush=True)

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(f"GATE {cell_text(gate_num)} SN{cell_text(serial)},")
        handle.write(f"PN: {cell_text(part)},")
        handle.write(f"MA: {cell_text(mac)},")
        handle.write(f"IP: {cell_text(gate_ip)},")

    with open(path, "r", encoding="utf-8") as handle:
        print("Label file contents:", handle.read(), flush=True)

    return path


# ---------------------------------------------------------------------------
# The whole end-of-run record
# ---------------------------------------------------------------------------

def record_result(device_dir, excel_path, device, airport, gate, gate_ip,
                  mac_addr=None, failed=False, crash_filename=None,
                  write_label=True):
    """Stamp the gate's row and, unless the run failed, write its label.

    Returns the label filename, or None if no label was produced. Never
    raises: the hardware is already programmed by the time this runs, so a
    spreadsheet problem is reported and survived rather than thrown.
    """
    try:
        workbook = openpyxl.load_workbook(excel_path)
    except (OSError, KeyError) as exc:
        print(f"Could not open {excel_path}: {exc}", flush=True)
        return None

    try:
        sheet = workbook.active
        if sheet is None:
            print("Result could not be logged: the workbook has no active sheet.",
                  flush=True)
            return None

        header_map = get_header_map(sheet)
        row = find_row_by_value(sheet, gate)
        if row is None:
            print(f"Result could not be logged: gate {gate} is not in the sheet.",
                  flush=True)
            return None

        def read(field):
            column = column_for(header_map, field)
            return sheet.cell(row=row, column=column).value if column else None

        def write(field, value, font=None):
            column = column_for(header_map, field)
            if column is None:
                return None
            cell = sheet.cell(row=row, column=column)
            cell.value = value
            if font is not None:
                cell.font = font
            return cell

        serial = read("serial")
        part = read("part")
        gate_num = read("gate")

        # A MAC captured this run wins; otherwise keep whatever the sheet holds
        # from a previous one, so the label still gets a value.
        if mac_addr:
            write("mac", mac_addr, BLACK)
        mac = read("mac")

        print(f"Bridge serial: {serial} | Part: {part} | MAC: {mac} | Gate: {gate_num}",
              flush=True)

        write("programmed_on", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              RED if failed else BLACK)
        _link_or_clear(write, "crash_report", device_dir, CRASH_DIR, crash_filename, failed)
        _bump_counter(sheet, header_map, row, "prg_count")

        label_filename = None
        if write_label:
            label_filename = f"label_{device}_{airport}_{gate}_{timestamp()}.txt"
            path = write_label_file(device_dir, label_filename, gate_num, serial,
                                    part, mac, gate_ip)
            cell = write("label", label_filename, LINK)
            if cell is not None:
                cell.hyperlink = os.path.abspath(path)
        else:
            print("Run failed -- sheet updated, but no label written.", flush=True)

        _save(workbook, excel_path)
        return label_filename

    except Exception as exc:
        print(f"Could not record the result: {exc}", flush=True)
        return None
    finally:
        workbook.close()


def record_test_result(device_dir, excel_path, gate, failed, crash_filename=None):
    """Stamp the functional-test columns ("Router Tested On" and friends).

    Separate from `record_result` because testing is a distinct pass over the
    hardware with its own timestamp, crash log and counter -- and not every
    device runs one.
    """
    try:
        workbook = openpyxl.load_workbook(excel_path)
    except (OSError, KeyError) as exc:
        print(f"Could not open {excel_path}: {exc}", flush=True)
        return

    try:
        sheet = workbook.active
        if sheet is None:
            return

        header_map = get_header_map(sheet)
        row = find_row_by_value(sheet, gate)
        if row is None:
            print(f"Test result could not be logged: gate {gate} is not in the sheet.",
                  flush=True)
            return

        def write(field, value, font=None):
            column = column_for(header_map, field)
            if column is None:
                return None
            cell = sheet.cell(row=row, column=column)
            cell.value = value
            if font is not None:
                cell.font = font
            return cell

        write("tested_on", datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
              RED if failed else BLACK)
        _link_or_clear(write, "test_crash_report", device_dir, CRASH_DIR,
                       crash_filename, failed)
        _bump_counter(sheet, header_map, row, "test_count")

        _save(workbook, excel_path)
    except Exception as exc:
        print(f"Could not record the test result: {exc}", flush=True)
    finally:
        workbook.close()


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _link_or_clear(write, field, device_dir, folder, filename, failed):
    """Point the cell at a new crash log, or clear a stale one on success."""
    if filename:
        cell = write(field, filename, LINK)
        if cell is not None:
            cell.hyperlink = os.path.abspath(os.path.join(device_dir, folder, filename))
    elif not failed:
        # Success with no crash log: blank out a link left by an earlier
        # failed attempt, so the row does not keep advertising a dead problem.
        write(field, " ")


def _bump_counter(sheet, header_map, row, field):
    """Increment an attempt counter, treating a blank cell as zero."""
    column = column_for(header_map, field)
    if column is None:
        return
    cell = sheet.cell(row=row, column=column)
    try:
        cell.value = int(cell.value) + 1
    except (TypeError, ValueError):
        cell.value = 1
    cell.font = BLACK


def _save(workbook, path):
    try:
        workbook.save(path)
    except PermissionError:
        print(f"Could not save {path} -- close it in Excel and run again.", flush=True)
