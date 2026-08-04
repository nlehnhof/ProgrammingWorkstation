# INSTRUCTIONS.md — Programming Workstation

**Version:** 2.0 · **Last updated:** 2026-08-04 (`e96074a`)

> **Setting up a machine that has never run this before?** Start with
> [`../SETUP.md`](../SETUP.md). This file assumes the repo already runs.
>
> **Not a programmer?** [`../cheat_sheet.md`](../cheat_sheet.md) explains what this
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
   All 66 tests should pass. If `pytest` is missing, `./venv/Scripts/python.exe -m pip install pytest`.

There is no linter/formatter configuration in this repo (no `.flake8`, `pyproject.toml`, `.pre-commit-config.yaml`).

## Tutorial: first run walkthrough

1. Launch the app: `./venv/Scripts/python.exe main.py`. Windows will show a UAC prompt — accept it (see Warnings). You land on the Home page.
2. Click **Add Device** to register a new device folder — fill in `Name` and `Path` at minimum, following the on-screen example row, then **Create Device**. You get a dialog either way: confirmation, or the specific reason it failed.
3. Click **Home**, then **Program Device**. Pick a registered device, an airport spreadsheet, and a gate from the dropdowns.
4. Tick every cabling checkbox. These come from `devices/{device}/instructions.txt` and gate the Program button — it stays disabled until all are ticked.
5. Scan (or type) the device's QR code text into the password field and hit **Submit** — the app extracts whatever follows `PW:` up to the next `;`, or uses the raw text if that pattern isn't present.
6. Hit **Program Device**. The run happens on a background worker thread, so the window stays responsive for the several minutes hardware operations take. For a device that ships a `checklist.json` (currently `digiIX20`), the right-hand **Status** panel shows each milestone flipping to a green `PASS` or red `FAIL`, with an elapsed timer on the step in flight.
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

- **Programming a Digi IX20 needs administrator rights.** The flow reconfigures this PC's network adapter, so the app relaunches itself elevated on startup (UAC prompt). Decline it and everything still runs except the **Switching static IP** milestone, which fails with an explanatory message. See `../SETUP.md` §5.
- **Credentials are stored in plaintext.** `core/devices.json` and each `devices/*/device_config.json` are not encrypted or masked. This is a known, documented limitation, not an oversight.
- **A cancelled Digi run can leave the PC on a static IP.** `digix20.py` restores DHCP in a `finally` block, but force-killing the app skips it. Fix via Settings → Network → adapter → IPv4 → Obtain automatically.
- **Close the spreadsheet before running.** If the airport `.xlsx` is open in Excel, the run completes but the save fails; you get a message saying so, and the label file still exists on disk.
- **Don't edit `og_configs/` or `og_testfile/`.** Those are the pristine templates. Each run copies them to `configs/`/`testfile/` and edits the copy.

## Adding a new device type

A device is a **folder**, not a class — there is no base class to subclass.

1. Create `devices/{NAME}/` with a `prog_dev.py` exposing `run_main_script(airport, gate, temp_pass, device)`. This is what `ProgramWorker.run` calls after `exec()`-loading the file. Note it will have no reliable `__file__` — resolve paths with `app_paths.device_dir(device)`.
2. Add an `instructions.txt` (one cabling step per line; these become the checkboxes gating the Program button) and the airport `.xlsx` sheets the device needs. Sheets must carry the standard header row — see `devices/digiIX20/IP_TEMPLATE.xlsx`.
3. Use the shared layer rather than writing your own:
   - `excel_utils.lookup_excel(path, gate)` for the gate's network settings.
   - `status.watch_process(command, report)` to run your hardware script and consume its output.
   - `reporting.record_result(...)` for the crash log, sheet stamp and label.
   - `ssh_session.SSHSession` and `wait_utils` for anything touching hardware.
   `devices/digiIX20/prog_dev.py` is 104 lines and is the reference to copy.
4. Optionally add a `checklist.json` to get the live Status panel — see `devices/digiIX20/checklist.json`. Your hardware script then calls `status.running("step_id")` / `status.passed(...)` / `status.failed(...)`, and the markers reach the GUI automatically. Without this file the panel is simply empty.
5. Optionally add a `device_config.json` and call `device_config.load_config(dir, env_prefix="{NAME}_")`. Put new tunables in the JSON file; reach for an env var only when the value genuinely differs per deployment machine.
6. Launch child scripts with `app_paths.script_command(...)` rather than `[sys.executable, ...]` — in a packaged build `sys.executable` is the app itself, not Python.
7. Register it via **Add Device** in the running app (writes `core/devices.json` and copies the folder). No rebuild is needed for a packaged install: `devices/` lives beside the .exe.

## Known issues / future actions

Observed in code, not aspirational:

- **`devices/TR/JKC-SLC.xlsx` is corrupt** — it is not a valid `.xlsx` (openpyxl: "File is not a zip file"). It is skipped gracefully now (the Gate dropdown comes back empty rather than crashing), but the file itself still needs replacing from a good copy.
- **`devices/TR/teltonika.py` has not been migrated.** `prog_dev.py` has; the hardware script beneath it still opens a raw `paramiko.SSHClient` per connection, waits on fixed `time.sleep()` calls, and parses MACs with its own single-format `"HWaddr" in line` check. `devices/digiIX20/digix20.py` is the reference for doing to it what `e96074a` did to `prog_dev.py`.
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
A: That device has no `checklist.json`. Only `digiIX20` ships one. See "Adding a new device type".

**Q: A gate row got a red timestamp but no crash log link. Why?**
A: The crash log couldn't be written (usually a permissions problem on `crash_logs/`). The failure is still recorded by the red timestamp — `reporting.write_crash_log` never raises, because losing the log must not also lose the sheet update.

**Q: Whatever happened to `device_types/`?**
A: Deleted in `e96074a`. All four files were entirely commented out, and the three pages importing the package pulled in no symbols from it. Devices are folders; that was always the real extension mechanism.
