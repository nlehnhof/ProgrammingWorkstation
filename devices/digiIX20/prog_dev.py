"""GUI-facing orchestration for the Digi IX20.

This is the entry point `pages/program_page.py` calls. It does the bookkeeping
around a run -- look the gate up in the spreadsheet, launch `digix20.py` as a
subprocess, watch its output, then record the outcome -- while `digix20.py`
does everything that actually touches hardware.

Loaded with exec() into a fresh namespace (see program_page.py), so this module
has no `__file__` and resolves paths from `app_root()`. The only required
export is `run_main_script`. If the page seeded the namespace with
`progress_callback`, milestones are forwarded to the Status checklist; without
it everything still works.
"""

import os
import time

from resources.utilities import status
from resources.utilities.app_paths import app_root, script_command
from resources.utilities.excel_utils import lookup_excel
from resources.utilities.reporting import record_result, write_crash_log


class DigiProgrammingError(RuntimeError):
    """The device did not program successfully.

    Propagates out of `run_main_script` so the app's global error handler logs
    it and shows the operator a dialog.
    """


def run_main_script(airport, gate, default_pass, device):
    """Program one Digi IX20 and record the result in the airport sheet."""
    report = status.forwarder(globals().get("progress_callback"))
    started = time.perf_counter()

    device_folder = os.path.join(app_root(), "devices", device)
    script_path = os.path.join(device_folder, "digix20.py")
    excel = os.path.join(device_folder, airport)
    airport_name = airport.removesuffix(".xlsx")

    if not os.path.isfile(script_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    # Read the gate's network settings first: a bad sheet must stop the run
    # before any hardware is touched. lookup_excel raises rather than handing
    # back blanks, so there is nothing to re-check here.
    try:
        gate_config = lookup_excel(excel, gate)
    except (KeyError, ValueError) as exc:
        print(str(exc), flush=True)
        raise DigiProgrammingError(str(exc)) from exc

    gate_ip = gate_config["gate_ip"]
    print(f"Gate {gate}: {gate_ip} / {gate_config['netmask']} via {gate_config['gateway']}",
          flush=True)

    print("Running digix20.py", flush=True)
    outcome = status.watch_process(
        script_command(script_path, gate_ip, gate_config["netmask"],
                       gate_config["gateway"], default_pass),
        report,
    )

    elapsed = time.perf_counter() - started
    print(f"Elapsed: {int(elapsed // 60)} min {int(elapsed % 60)} sec", flush=True)

    crash_filename = None
    if outcome["failed"]:
        crash_filename = write_crash_log(
            device_folder, device, airport_name, gate, outcome["log"]
        )

    # This milestone lives here rather than in digix20.py: the label and the
    # sheet are written by this process, after the hardware script has exited.
    if outcome["failed"]:
        report("label", status.SKIPPED, "run failed -- no label produced")
    else:
        report("label", status.RUNNING)

    label_filename = record_result(
        device_dir=device_folder,
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
        message = outcome["detail"] or "Device programming failed. See the log for details."
        print("Programming failed. Check the Status checklist and the crash log.", flush=True)
        raise DigiProgrammingError(message)

    if label_filename:
        report("label", status.PASS, label_filename)
    else:
        report("label", status.FAIL, "label could not be written")

    print("Programming and testing complete. Continue to the next device.", flush=True)
