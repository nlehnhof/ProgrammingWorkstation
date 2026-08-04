"""GUI-facing orchestration for the Teltonika RUTX08.

This is the entry point `pages/program_page.py` calls. It does the bookkeeping
around a run -- look the gate up in the spreadsheet, launch `teltonika.py` as a
subprocess, run the functional test against the BeagleBone, then record the
outcome -- while `teltonika.py` does everything that touches the router.

Loaded with exec() into a fresh namespace (see program_page.py), so this module
has no reliable `__file__` and resolves paths from the current working
directory / `app_root()`. The only required export is `run_main_script`.

Two habits from the previous version are worth naming, because they are why
this file used to be six times longer and quietly wrong:

* Its output loop ran twice over the same pipe. The first pass drained it, so
  the second -- which held all the failure detection, the MAC capture and the
  crash logging -- iterated over an exhausted stream. Every run recorded a
  success. The shared `status.watch_process` makes one pass.
* Every spreadsheet update re-scanned the sheet for the gate row and addressed
  cells by hardcoded column number (`column=7` for the MAC, and so on), copied
  out four times. `resources.utilities.reporting` does it once, by header name.
"""

import os

from resources.utilities import status
from resources.utilities.app_paths import app_root, device_dir, script_command
from resources.utilities.device_config import load_config
from resources.utilities.excel_utils import find_column as _find_column
from resources.utilities.excel_utils import get_header_map as _get_header_map
from resources.utilities.excel_utils import lookup_excel as _lookup_excel
from resources.utilities.network_utils import prefix_length
from resources.utilities.reporting import (
    COLUMNS,
    record_result,
    record_test_result,
    write_crash_log,
)
from resources.utilities.ssh_session import SSHSession
from resources.utilities.templating import TemplateError, stage_template
from resources.utilities.wait_utils import run_checked

TEST_SCRIPT = "FloodLighToggle.py"
TEST_SUCCESS_MARKER = "Bytes in received"
PLACEHOLDER_IP = "127.0.0.1"

# The BeagleBone needs its own address on the gate subnet to talk to the
# router. .123 by convention, moved to .100 when the gate itself owns .123.
BBB_HOST_OCTET = "123"
BBB_ALTERNATE_OCTET = "100"

# Set by lookup_excel, read by run_main_script. Module-level rather than
# returned because this module is exec()'d and the GUI reaches in for them.
gate_ip = None
gate_netmask = None
gate_gateway = None
valid_ip = True

# Filled in by load_device_config once a run knows which folder it is in.
sudo_password = ""


# ---------------------------------------------------------------------------
# Spreadsheet access
# ---------------------------------------------------------------------------

def get_header_map(sheet):
    """Header text -> column numbers. See resources/utilities/excel_utils.py."""
    return _get_header_map(sheet)


def col(header_map, key, occurrence=None):
    """Column number for a logical field name such as "mac" or "prg_count".

    Device code names the *field* it wants; the header text it maps to lives in
    one table (`reporting.COLUMNS`). `occurrence` picks between the sheet's two
    "Crash Report" columns when the caller needs to be explicit.
    """
    name, default_occurrence = COLUMNS[key]
    return _find_column(
        header_map, name,
        default_occurrence if occurrence is None else occurrence,
    )


def _resolve_sheet(sheet, device):
    """Find an airport sheet given either a full path or a bare filename."""
    candidates = [
        sheet,
        os.path.join("devices", device, sheet),
        os.path.join(device_dir(device), sheet),
        os.path.join(app_root(), "devices", device, sheet),
    ]
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return sheet


def lookup_excel(sheet, gate, device):
    """Read the gate's network settings into this module's globals.

    Sets `valid_ip = False` rather than raising when the sheet is unusable --
    a missing gate or a malformed address is operator-fixable data, and the
    caller checks the flag before going anywhere near the hardware.
    """
    global gate_ip, gate_netmask, gate_gateway, valid_ip

    gate_ip = gate_netmask = gate_gateway = None
    valid_ip = True

    path = _resolve_sheet(sheet, device)
    try:
        found = _lookup_excel(path, gate)
    except (KeyError, ValueError, OSError) as exc:
        print(f"{exc}", flush=True)
        print("Select another option.", flush=True)
        valid_ip = False
        return

    gate_ip = found["gate_ip"]
    gate_netmask = found["netmask"]
    gate_gateway = found["gateway"]
    print(f"Gate IP: {gate_ip}", flush=True)
    print(f"Netmask: {gate_netmask}", flush=True)
    print(f"Gateway: {gate_gateway}", flush=True)


# ---------------------------------------------------------------------------
# BeagleBone access
# ---------------------------------------------------------------------------

def ssh_run_shell(session, command):
    """Run one command on an interactive shell, answering a sudo prompt.

    Needed because `sudo ip addr add ...` asks for a password on stdin, which
    `exec_command` cannot answer. Returns the shell's output, or None if there
    is nothing to do.

    The `with` block is the point: the old version returned the live channel to
    a caller that never closed it, leaking a shell per invocation until the
    BeagleBone refused new sessions.
    """
    if session is None or command is None:
        return None

    with session.invoke_shell() as shell:
        shell.recv(1000)  # drain the login banner
        shell.send(command + "\n")
        output = shell.recv(4096).decode(errors="replace")

        if "[sudo] password for" in output:
            shell.send(sudo_password + "\n")
            output += shell.recv(4096).decode(errors="replace")

        print(output, flush=True)
        return output


def load_device_config(folder):
    """TR's settings: DEFAULTS -> device_config.json -> TR_* env vars.

    Previously the BBB address and password were hardcoded in three separate
    places in this file, so `devices/TR/device_config.json` existed but nothing
    read it and `TR_*` environment variables had no effect. They work now.
    """
    global sudo_password

    config = load_config(folder, env_prefix="TR_")
    # ssh_run_shell answers a sudo prompt and is called from the test flow with
    # only a session; keeping the password here avoids threading config through
    # a helper whose whole job is one command.
    sudo_password = config["bbb_password"]
    return config


def bbb_session(config):
    print("Connecting to BBB", flush=True)
    session = SSHSession(
        config["bbb_ip"], config["bbb_user"], config["bbb_password"],
        timeout=config["ssh_timeout"],
    )
    session.ensure_connected()
    print("Connected to BBB", flush=True)
    return session


def bbb_address_for(address):
    """The BeagleBone's own address on the gate's subnet."""
    parts = str(address).split(".")
    parts[-1] = BBB_ALTERNATE_OCTET if parts[-1] == BBB_HOST_OCTET else BBB_HOST_OCTET
    return ".".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_main_script(airport, gate, temp_pass, device):
    """Program one Teltonika router and record the result in the airport sheet."""
    report = status.forwarder(globals().get("progress_callback"))

    folder = device_dir(device)
    script_path = os.path.join(folder, "teltonika.py")
    excel = os.path.join(folder, airport)
    airport_name = airport.removesuffix(".xlsx")

    lookup_excel(excel, gate, device)
    if not valid_ip:
        raise RuntimeError(
            f"Gate {gate} in {airport} has no usable network settings. "
            "Pick another gate, or correct the spreadsheet."
        )

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    print("Running teltonika.py...", flush=True)
    outcome = status.watch_process(
        script_command(script_path, gate_ip, gate_netmask, gate_gateway, temp_pass),
        report,
    )

    crash_filename = None
    if outcome["failed"]:
        crash_filename = write_crash_log(
            folder, device, airport_name, gate, outcome["log"]
        )

    # The sheet is stamped either way -- a red timestamp and a crash-log link
    # are how a failure gets recorded -- but a failed run writes no label. A
    # printable label for a router that did not program is worse than none,
    # because somebody can stick it on.
    #
    # This milestone is reported here rather than in teltonika.py: the label and
    # the sheet are written by this process, after the hardware script exits.
    if outcome["failed"]:
        report("label", status.SKIPPED, "run failed -- no label produced")
    else:
        report("label", status.RUNNING)

    label_filename = record_result(
        device_dir=folder,
        excel_path=excel,
        device=device,
        airport=airport_name,
        gate=gate,
        gate_ip=gate_ip,
        mac_addr=outcome["mac"],
        failed=outcome["failed"],
        crash_filename=crash_filename,
        write_label=not outcome["failed"],
    )

    if outcome["failed"]:
        message = outcome["detail"] or "Router programming failed. See the crash log."
        print("Programming failed. Check the crash log.", flush=True)
        raise RuntimeError(message)

    if label_filename:
        report("label", status.PASS, label_filename)
        print(f"Label written: {label_filename}", flush=True)
    else:
        report("label", status.FAIL, "label could not be written")

    # Only test a router that programmed. Testing one that did not just
    # produces a second, confusing failure.
    run_test_script(folder, device, airport_name, excel, gate, report)

    print("Programming and testing complete. Continue to the next device.", flush=True)


def run_test_script(folder, device, airport, excel, gate, report=None):
    """Drive the Modbus floodlight toggle from the BeagleBone.

    Copies the pristine test script out of `og_testfile/`, points it at this
    gate's address, uploads it, gives the BeagleBone an address on the gate
    subnet, and runs it. Success is the script reporting bytes received back
    from the PLC.
    """
    report = report or status.forwarder(globals().get("progress_callback"))
    report("testing", status.RUNNING)

    config = load_device_config(folder)
    failures = []

    print("Copying the test file from the backup folder", flush=True)
    local_script = stage_test_script(folder, gate_ip)
    if local_script is None:
        failures.append(f"{TEST_SCRIPT} could not be prepared locally.")

    session = None
    try:
        session = bbb_session(config)

        if local_script:
            print(f"Copying {TEST_SCRIPT} to the BBB", flush=True)
            session.upload(local_script, f"/home/{config['bbb_user']}/{TEST_SCRIPT}")

            listing, _, _ = run_checked(session, f"ls -l /home/{config['bbb_user']}/")
            if TEST_SCRIPT not in listing:
                failures.append(f"Incorrect! {TEST_SCRIPT} not found on the BBB.")

        bbb_ip = bbb_address_for(gate_ip)
        prefix = prefix_length(gate_netmask)
        print(f"Adding {bbb_ip}/{prefix} to the BBB so it can reach the router", flush=True)
        ssh_run_shell(session, f"sudo ip addr add local {bbb_ip}/{prefix} dev eth0")

        addresses, _, _ = run_checked(session, "ip addr show eth0")
        if bbb_ip not in addresses:
            failures.append(f"Incorrect! {bbb_ip} was not added to the BBB.")

        print("Running the test script now...", flush=True)
        output, _, _ = run_checked(
            session, f"python {TEST_SCRIPT}", timeout=config["test_script_timeout"]
        )
        if TEST_SUCCESS_MARKER not in output:
            failures.append(f"Incorrect! The test script did not report "
                            f"'{TEST_SUCCESS_MARKER}'.")
            failures.append(output)

    except Exception as exc:
        failures.append(f"Incorrect! Test failed: {type(exc).__name__}: {exc}")
    finally:
        if session is not None:
            print("Closing Connection to BBB", flush=True)
            session.close()

    failed = bool(failures)
    crash_filename = None
    if failed:
        print("Error found during the router test", flush=True)
        crash_filename = write_crash_log(
            folder, f"test_{device}", airport, gate, failures
        )
        report("testing", status.FAIL, failures[0])
    else:
        print("No error during the router test", flush=True)
        report("testing", status.PASS)

    record_test_result(folder, excel, gate, failed=failed, crash_filename=crash_filename)


def stage_test_script(folder, address):
    """Copy `og_testfile/` to `testfile/` and point the script at `address`.

    The originals are never edited in place: each run rewrites a fresh working
    copy, so a previous gate's address cannot leak into this one's test. Shared
    with teltonika.py, which does the same for `og_configs/`.

    Returns the staged path, or None if it could not be prepared -- the caller
    records that as a test failure rather than aborting.
    """
    try:
        return stage_template(
            os.path.join(folder, "og_testfile"),
            os.path.join(folder, "testfile"),
            TEST_SCRIPT,
            PLACEHOLDER_IP,
            address,
        )
    except TemplateError as exc:
        print(f"Incorrect! Could not prepare {TEST_SCRIPT}: {exc}", flush=True)
        return None
