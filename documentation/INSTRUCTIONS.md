# INSTRUCTIONS.md — Programming Workstation

**Version:** 2.1 · **Last updated:** 2026-08-04 (teltonika.py migration)

> **Setting up a machine that has never run this before?** Start with
> [`SETUP.md`](SETUP.md). This file assumes the repo already runs.
>
> **Not a programmer?** [`CHEAT_SHEET.md`](CHEAT_SHEET.md) explains what this
> app is and how it works in one page, without code.

## Setup

`pytest` is **not** in `requirements.txt`, so a freshly created `venv/` won't have it — install it separately if you need the test suite.

1. **`venv/` (Python 3.13)** has the app's GUI/hardware dependencies (`PyQt5`, `paramiko`, `openpyxl`, `ping3`) plus `pyinstaller`. Use it to run the app:
   ```
   ./venv/Scripts/python.exe main.py
   ```
   If it's ever missing dependencies, reinstall from the repo root:
   ```
   ./venv/Scripts/python.exe -m pip install -r requirements.txt
   ```
2. To run the **test suite**, run it as a module from the **repository root** (not the bare `pytest` executable) — there's no `conftest.py` or `pyproject.toml` adding the project root to `sys.path`, so a bare `pytest` invocation fails every test with `ModuleNotFoundError: No module named 'resources'`:
   ```
   ./venv/Scripts/python.exe -m pytest tests/
   ./venv/Scripts/python.exe -m pytest tests/test_ssh_session.py::test_connects_lazily_on_first_use   # single test
   ```
   All 83 tests should pass. If `pytest` is missing, `./venv/Scripts/python.exe -m pip install pytest`.

There is no linter/formatter configuration in this repo (no `.flake8`, `pyproject.toml`, `.pre-commit-config.yaml`).

## Tutorial: first run walkthrough

1. Launch the app: `./venv/Scripts/python.exe main.py`. Windows will show a UAC prompt — accept it (see Warnings). You land on the Home page.
2. Click **Add Device** to register a new device folder — fill in `Name` and `Path` at minimum, following the on-screen example row, then **Create Device**. You get a dialog either way: confirmation, or the specific reason it failed.
3. Click **Home**, then **Program Device**. Pick a registered device, an airport spreadsheet, and a gate from the dropdowns.
4. Tick every cabling checkbox. These come from `devices/{device}/instructions.txt` and gate the Program button — it stays disabled until all are ticked.
5. Scan (or type) the device's QR code text into the password field and hit **Submit** — the app extracts whatever follows `PW:` up to the next `;`, or uses the raw text if that pattern isn't present.
6. Hit **Program Device**. The run happens on a background worker thread, so the window stays responsive for the several minutes hardware operations take. For a device that ships a `checklist.json` (both `digiIX20` and `TR` do), the right-hand **Status** panel shows each milestone flipping to a green `PASS` or red `FAIL`, with an elapsed timer on the step in flight.
7. On completion, check the device's own folder for artifacts — `devices/{device}/router_labels/` and `devices/{device}/crash_logs/` — plus the source Excel file, where the gate's row now carries the MAC, a timestamp (**black = success, red = failure**), and hyperlinks to the label and any crash log.

### Reading the spreadsheet afterwards

The gate's row is the record of what happened:

| Column | Meaning |
| --- | --- |
| `MAC Address` | Read off the device during the run |
| `Router Programmed On` | Timestamp — **red means the run failed** |
| `Label` | Hyperlink to the generated label file (absent if the run failed) |
| `Crash Report` (1st) | Hyperlink to the programming crash log; blanked on success |
| `PRG #` | How many times this gate has been programmed |
| `Router Tested On` | Functional-test timestamp, same red/black convention |
| `Crash Report` (2nd) | Test crash log |
| `Test #` | How many times this gate has been tested |

A failed run deliberately produces **no label**. A printable label for a router that did not program is worse than none, because somebody can stick it on.

## Warnings

- **Programming a Digi IX20 needs administrator rights.** The flow reconfigures this PC's network adapter, so the app relaunches itself elevated on startup (UAC prompt). Decline it and everything still runs except the **Switching static IP** milestone, which fails with an explanatory message. See `SETUP.md` §5.
- **Credentials are stored in plaintext.** `core/devices.json` and each `devices/*/device_config.json` are not encrypted or masked. This is a known, documented limitation, not an oversight.
- **A cancelled Digi run can leave the PC on a static IP.** `digix20.py` restores DHCP in a `finally` block, but force-killing the app skips it. Fix via Settings → Network → adapter → IPv4 → Obtain automatically.
- **Close the spreadsheet before running.** If the airport `.xlsx` is open in Excel, the run completes but the save fails; you get a message saying so, and the label file still exists on disk.
- **Don't edit `og_configs/` or `og_testfile/`.** Those are the pristine templates. Each run copies them to `configs/`/`testfile/` and edits the copy.

## Adding a new device type

A device is a **folder**, not a class — there is no base class to subclass. Because nothing is enforced by an interface, the app instead relies on a handful of names and file locations being exactly right. Get one wrong and the failure is usually silent or misleading, so the rules come first.

### The rules — what the app requires by name

These are hard requirements, each enforced by a specific line of code. Nothing checks them ahead of time; you find out at run time.

| Rule | Enforced at | What you see if you break it |
| --- | --- | --- |
| The programming file is named **exactly `prog_dev.py`**, directly inside `devices/{NAME}/` | `pages/program_page.py:196` | Dialog: "No `prog_dev.py` found for '{device}'." The run never starts. |
| It defines a module-level function named **exactly `run_main_script`** | `pages/program_page.py:46` | `KeyError: 'run_main_script'` in the error log, after the operator has already pressed Program |
| `run_main_script` takes **four positional parameters**, in the order `(airport, gate, temp_pass, device)` | `pages/program_page.py:46` | `TypeError` about argument count, in the error log |
| `instructions.txt` exists and holds **at least one non-blank line** | `pages/program_page.py:269–290` | The Program button stays greyed out forever — see the trap below |
| Airport sheets are `.xlsx` in the device folder, carrying the standard header row | `excel_utils.get_excel_files` / `get_dropdown` | Empty Airport or Gate dropdown |

The parameter names are yours to choose — the call is positional — but the order and the meaning are fixed:

| Position | Value passed | Note |
| --- | --- | --- |
| 1 | Airport sheet **filename**, including `.xlsx` | Not the airport name. Both devices do `airport.removesuffix(".xlsx")` when they need the bare name. |
| 2 | Gate identifier, as shown in the Gate dropdown | Read from the `PBB SN` column |
| 3 | Temporary device password | Parsed out of the scanned QR text (`PW:...;`), else the raw text |
| 4 | Registered device name, which is also the folder name | Use it with `app_paths.device_dir(device)` |

### Four traps in how `prog_dev.py` is loaded

`prog_dev.py` is not imported. `ProgramWorker.run` reads the file and runs `exec(code, namespace)` on it (`pages/program_page.py:41–46`), which changes four things:

1. **There is no reliable `__file__`.** Resolve every path from `app_paths.device_dir(device)` or `app_root()`. A relative path resolves against the app's working directory, not the device folder.
2. **Module-level code runs the moment Program is pressed**, before `run_main_script` is called. Keep the top of the file to imports and constants; anything expensive or side-effecting there runs inside the worker thread with no milestone reporting around it.
3. **`progress_callback` is injected into the namespace, not passed as an argument.** Reach it with `globals().get("progress_callback")` and wrap it in `status.forwarder(...)`, which tolerates its absence — that is what keeps the module runnable outside the GUI. Both devices open with exactly `report = status.forwarder(globals().get("progress_callback"))`.
4. **`sys.exit()` is treated as success.** `ProgramWorker.run` catches `SystemExit` and emits `finished_ok` (`:47–50`), deliberately, so a device script can't take the app down. Signal failure by **raising** out of `run_main_script` — the worker turns any other exception into the `failed` signal, the error log and a dialog. `digiIX20` raises `DigiProgrammingError` for this.

### The `instructions.txt` trap

A device with no `instructions.txt`, or one containing only blank lines, **can never be programmed** — the Program button stays disabled with no error shown anywhere.

The cause: `load_instructions` ends by disabling the button (`:284`), and the only thing that re-enables it is `update_button_state`, which is wired solely to the `stateChanged` signal of the checkboxes built from that file (`:279`). No lines means no checkboxes, which means nothing can ever call it. So although the file is nominally a list of cabling steps, treat it as a required part of the contract.

### Walkthrough

1. Create `devices/{NAME}/` with a `prog_dev.py` satisfying the rules above. `devices/digiIX20/prog_dev.py` is 104 lines and is the reference to copy.
2. Add an `instructions.txt` (one cabling step per line; these become the checkboxes gating the Program button) and the airport `.xlsx` sheets the device needs. Sheets must carry the standard header row — see `devices/digiIX20/IP_TEMPLATE.xlsx`. Note that `get_excel_files` hides two things from the Airport dropdown: Excel's `~$` lock files, and any sheet named `oshkosh_log.xlsx`.
3. Use the shared layer rather than writing your own:
   - `excel_utils.lookup_excel(path, gate)` for the gate's network settings.
   - `status.watch_process(command, report)` to run your hardware script and consume its output.
   - `reporting.record_result(...)` for the crash log, sheet stamp and label.
   - `ssh_session.SSHSession` and `wait_utils` for anything touching hardware.
4. Optionally add a `checklist.json` to get the live Status panel — see `devices/digiIX20/checklist.json`. Your hardware script then calls `status.running("step_id")` / `status.passed(...)` / `status.failed(...)`, and the markers reach the GUI automatically. Without this file the panel is simply empty. **The `id` in each checklist entry must match the `step_id` your script emits**, character for character: `StatusPanel.update_step` returns silently on an id it doesn't recognise (`pages/status_panel.py:255`), so a typo shows up as a row that never moves off `PENDING` rather than as an error.
5. Optionally add a `device_config.json` and call `device_config.load_config(dir, env_prefix="{NAME}_")`. Put new tunables in the JSON file; reach for an env var only when the value genuinely differs per deployment machine.
6. Launch child scripts with `app_paths.script_command(...)` rather than `[sys.executable, ...]` — in a packaged build `sys.executable` is the app itself, not Python.
7. Register it via **Add Device** in the running app (writes `core/devices.json` and copies the folder). No rebuild is needed for a packaged install: `devices/` lives beside the .exe.

## Known issues / future actions

Observed in code, not aspirational:

- **`devices/TR/JKC-SLC.xlsx` is corrupt** — it is not a valid `.xlsx` (openpyxl: "File is not a zip file"). It is skipped gracefully now (the Gate dropdown comes back empty rather than crashing), but the file itself still needs replacing from a good copy.
- **TR cannot resume a failed run.** `digix20.py` works out where the router currently is and restarts at the right milestone; `teltonika.py` only has a coarse "already programmed, skip everything" check, so a failure part-way through still means a factory reset before the next attempt. This is now the largest behavioural difference between the two devices.
- **`pages/add_device_page.py` references a trash-icon path** (`utilities\\trash.jpg`) that doesn't match the actual asset location, so the delete-row button renders blank.
- **`ConnectionPage` is unreachable from the normal flow.** It exists at index 3 but nothing navigates to it; the per-device cabling checkboxes do the hardware-verification job instead. Either wire it in or remove it.
- **`error_log_page` monkey-patches `subprocess.run` process-wide**, forcing `check=True` and `capture_output=True` on every call site, including code that didn't ask for it.

## FAQ

**Q: Why does `pytest` fail with `ModuleNotFoundError: No module named 'resources'`?**
A: You ran the bare `pytest` executable instead of `python -m pytest` from the repo root. See Setup above.

**Q: I set a `TR_*` environment variable. Does it work now?**
A: Yes, as of `e96074a`. `devices/TR/prog_dev.py` calls `load_config(folder, env_prefix="TR_")`, so `TR_BBB_IP` and friends take effect there. Note the values used *inside* `teltonika.py` are still hardcoded — the config only reaches the orchestration and test layers so far.

**Q: The Gate dropdown is empty.**
A: Either that sheet has no `PBB SN` column in its header row, or the file is unreadable. The reason is printed to the console; `devices/TR/JKC-SLC.xlsx` is a known-corrupt example.

**Q: The "Program Device" button won't enable — what's wrong?**
A: Every cabling checkbox has to be ticked first. If no checkboxes appear at all, `devices/{device}/instructions.txt` is missing or empty.

**Q: The Status panel is empty for my device.**
A: That device has no `checklist.json`. Both `digiIX20` and `TR` ship one; a device you add yourself will not until you write it. See "Adding a new device type".

**Q: A gate row got a red timestamp but no crash log link. Why?**
A: The crash log couldn't be written (usually a permissions problem on `crash_logs/`). The failure is still recorded by the red timestamp — `reporting.write_crash_log` never raises, because losing the log must not also lose the sheet update.

**Q: Whatever happened to `device_types/`?**
A: Deleted in `e96074a`. The four files held working code, but nothing used it — `core/manager.py` and `pages/add_device_page.py` imported `Device` and `SSHDevice` without ever instantiating them, and three pages did `from device_types import *` for no symbols they referenced. Devices are folders; that was always the real extension mechanism.
