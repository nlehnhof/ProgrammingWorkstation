# INSTRUCTIONS.md — Programming Workstation

**Version:** 1.1 · **Last updated:** 2026-08-03

> **Setting up a machine that has never run this before?** Start with
> [`../SETUP.md`](../SETUP.md). This file assumes the repo already runs.

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
2. To run the **test suite**, you need an environment with both `pytest` and `openpyxl` available. Run it as a module from the **repository root** (not the bare `pytest` executable) — there's no `conftest.py` or `pyproject.toml` adding the project root to `sys.path`, so a bare `pytest` invocation fails every test with `ModuleNotFoundError: No module named 'resources'`:
   ```
   python -m pytest tests/
   python -m pytest tests/test_ssh_session.py::test_connects_lazily_on_first_use   # single test
   ```
   If neither environment has both tools, `pip install pytest` into `venv/` and run from there.

There is no linter/formatter configuration in this repo (no `.flake8`, `pyproject.toml`, `.pre-commit-config.yaml`).

## Tutorial: first run walkthrough

1. Launch the app: `./venv/Scripts/python.exe main.py`. You land on the Home page.
2. Click **Add Device** to register a new device folder (see `core/manager.py`'s `create_device` in `CODE_EXPLAIN.md`) — fill in `Name` and `Path` at minimum, following the on-screen example row.
3. Click **Home**, then **Program Device**. Pick a registered device, an airport spreadsheet, and a gate from the dropdowns.
4. Scan (or type) the device's QR code text into the password field and hit **Submit** — the app extracts whatever follows `PW:` up to the next `;`, or uses the raw text if that pattern isn't present.
5. Hit **Program Device**. The run happens on a background worker thread (`ProgramWorker` in `pages/program_page.py`), so the window stays responsive for the several minutes hardware operations take. For a device that ships a `checklist.json` (currently `digiIX20`), the right-hand **Status** panel shows each milestone flipping to a green `PASS` or red `FAIL` as it completes, with an elapsed timer on the step in flight. A device without that file shows an empty Status panel and is otherwise unchanged.
6. On completion, check `logs/` for the run's crash log, and the device's own folder for artifacts — `devices/TR/labels/` for TR, `devices/digiIX20/router_labels/` and `devices/digiIX20/crash_logs/` for the Digi — plus the source Excel file for the generated label/MAC/timestamp.

## Warnings

- **Programming a Digi IX20 needs administrator rights.** The flow reconfigures this PC's network adapter, so the app relaunches itself elevated on startup (UAC prompt). Decline it and everything still runs except the **Switching static IP** milestone, which fails with an explanatory message. See `../SETUP.md` §5.
- **Env var overrides only apply to devices that read them.** `resources/utilities/device_config.py` supports per-device overrides, and `devices/digiIX20/digix20.py` uses it — `DIGIIX20_BBB_IP` and friends work there. **TR still does not**: `devices/TR/teltonika.py` and `prog_dev.py` hardcode their IPs/passwords, so `TR_*` variables have no effect.
- **Credentials are stored in plaintext.** `core/devices.json`, `devices/digiIX20/device_config.json`, and the hardcoded constants throughout `devices/TR/*.py` are not encrypted or masked.
- **A cancelled Digi run can leave the PC on a static IP.** `digix20.py` restores DHCP in a `finally` block, but force-killing the app skips it. Fix via Settings → Network → adapter → IPv4 → Obtain automatically.

## Adding a new device type

Follow the existing pattern rather than the (currently unused) `device_types.Device` abstract base class:
1. Create `devices/{NAME}/` with its own `prog_dev.py` exposing a `run_main_script(airport, gate, temp_pass, device)` function — this is what `ProgramWorker.run` in `pages/program_page.py` calls after `exec()`-loading the file.
2. Add an `instructions.txt` (one cabling step per line; these become the checkboxes gating the Program button) and any airport `.xlsx` templates the device needs.
3. Optionally add a `checklist.json` to get the live Status panel — see `devices/digiIX20/checklist.json`. Your hardware script then prints `##STATUS##<step_id>|<state>|<detail>` lines (states: `RUNNING`, `PASS`, `FAIL`, `SENT`, `WAIT`) and `prog_dev.py` forwards them to the GUI. Without this file the panel is simply empty.
4. Optionally add a `device_config.json` and call `resources.utilities.device_config.load_config(dir, env_prefix="{NAME}_")` from your script, as `digix20.py` does. TR does not, so treat it as available rather than required.
5. Launch child scripts with `resources.utilities.app_paths.script_command(...)` rather than `[sys.executable, ...]` — in a packaged build `sys.executable` is the app itself, not Python.
6. Register it via **Add Device** in the running app (writes to `core/devices.json` and copies the folder). No rebuild is needed for a packaged install: `devices/` lives beside the .exe.

## Known bugs / future actions (as observed in code, not aspirational)

- `resources/utilities/excel_utils.py` and `network_utils.py` are missing functions (`find_column`, `get_header_map`, `open_workbook`, `require_columns`, `find_row_by_value`, `validate_subnet`) that `tests/test_excel_utils.py` / `test_network_utils.py` already test against — these two test files currently fail to collect. Either the refactor needs finishing, or the tests need to be reconciled with the smaller current API.
- `devices/TR/prog_dev.py` and `teltonika.py` still duplicate logic (`is_valid_ip`, `validate_subnet`, SSH connect/run/close, MAC extraction) that has tested, more robust equivalents in `resources/utilities/`. `devices/digiIX20/digix20.py` was rewritten onto that shared layer (`SSHSession`, `wait_utils`, `mac_utils`, `device_config`) and is the reference for doing the same to TR — which would also replace TR's remaining fixed `time.sleep()` waits with completion-driven ones.
- `pages/add_device_page.py:211` references a trash-icon path (`utilities\\trash.jpg`) that doesn't match the actual asset location (`resources/utilities/trash.jpg`).
- `core/manager.py:41-46` uses a bare `except:` around required-field validation, which will silently swallow unrelated errors (e.g. a typo'd key access elsewhere) as if they were the "missing Name/Path" case.
- Several stale header comments (`# add_device_page.py` atop `connection_page.py`, `home_page.py`, and `error_log_page.py`'s `# error_handler.py`) suggest these files started life as copies of another page — harmless, but worth cleaning up if touching those files anyway.

## FAQ

**Q: Why does `pytest` fail with `ModuleNotFoundError: No module named 'resources'`?**
A: You ran the bare `pytest` executable instead of `python -m pytest` from the repo root. See Setup above.

**Q: I set a `TR_*` environment variable and nothing changed. Why?**
A: `devices/TR/teltonika.py` and `prog_dev.py` don't call `load_config()` — the env var precedence system exists and is tested, but isn't wired into the TR scripts. It *is* wired into the Digi, so `DIGIIX20_*` variables do take effect.

**Q: Why does `device_types` exist if nothing uses it?**
A: It looks like scaffolding for a planned plugin-style device abstraction that the actual implementation (subprocess-based `prog_dev.py`/hardware scripts per device folder) ended up not needing. See `CODE_EXPLAIN.md`.

**Q: The "Program Device" button won't enable — what's wrong?**
A: Every cabling checkbox has to be ticked first — they gate the button. If no checkboxes appear at all, `devices/{device}/instructions.txt` is missing or empty.

**Q: The Status panel is empty for my device.**
A: That device has no `checklist.json`. Only `digiIX20` ships one; TR intentionally does not. See "Adding a new device type" above.

**Q: Does the window still freeze during programming?**
A: No. As of v1.1 the run is on a `QThread` worker and the UI stays responsive. Older notes describing a frozen window are out of date.
