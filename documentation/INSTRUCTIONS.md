# INSTRUCTIONS.md — Programming Workstation

**Version:** 1.0 · **Last updated:** 2026-07-30

## Setup

This machine has two separate Python environments, and neither has everything the project needs — check which one you're using before assuming a command will work.

1. **`venv/` (Python 3.13)** has the app's GUI/hardware dependencies (`PyQt5`, `paramiko`, `openpyxl`, `ping3`) but **not** `pytest`. Use it to run the app:
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
5. Hit **Program Device**. This runs synchronously on the GUI thread (see `WORKFLOW.md` §4) and can take several minutes for hardware operations like firmware flashing — the window will appear unresponsive during this time, which is expected, not a hang.
6. On completion, check `logs/` for the run's crash log, and (for the TR device) `devices/TR/labels/` and the source Excel file for the generated label/MAC/timestamp.

## Warnings

- **The "Program Device" checklist may never enable.** `pages/program_page.py:188` reads a per-device instructions file from a hardcoded path (`C:\Users\u324754\...`) specific to the original developer's machine. On any other machine this silently fails to load and the checkboxes that gate the Program button never appear — if the button stays disabled with no visible checklist, this is why.
- **Environment variable overrides are unsafe if mismatched.** `resources/utilities/device_config.py` supports `TR_*` env var overrides, but as of this commit **no TR device script actually reads them** — setting `TR_BBB_IP` etc. currently has no effect on `devices/TR/teltonika.py` or `prog_dev.py`, whose IPs/passwords are hardcoded in source. Don't assume env var docs elsewhere in the repo reflect current behavior.
- **Credentials are stored in plaintext.** `core/devices.json` and the hardcoded constants throughout `devices/TR/*.py` are not encrypted or masked.
- **The device-programming step runs on the main thread** and blocks the UI event loop for the duration of hardware operations (roughly 7+ minutes for the TR device's firmware flash + reboot cycle).

## Adding a new device type

Follow the existing pattern rather than the (currently unused) `device_types.Device` abstract base class:
1. Create `devices/{NAME}/` with its own `prog_dev.py` exposing a `run_main_script(airport, gate, temp_pass, device)` function — this is what `pages/program_page.py:152` calls after `exec()`-loading the file.
2. Add an `instructions.txt` and any airport `.xlsx` templates the device needs.
3. Register it via **Add Device** in the running app (writes to `core/devices.json` and copies the folder).
4. If you want configuration to actually be overridable, call `resources.utilities.device_config.load_config()` from your script — note this is not yet done by the existing TR implementation, so don't assume it's a required pattern, just an available one.

## Known bugs / future actions (as observed in code, not aspirational)

- `resources/utilities/excel_utils.py` and `network_utils.py` are missing functions (`find_column`, `get_header_map`, `open_workbook`, `require_columns`, `find_row_by_value`, `validate_subnet`) that `tests/test_excel_utils.py` / `test_network_utils.py` already test against — these two test files currently fail to collect. Either the refactor needs finishing, or the tests need to be reconciled with the smaller current API.
- `devices/TR/prog_dev.py` and `teltonika.py` duplicate logic (`is_valid_ip`, `validate_subnet`, SSH connect/run/close, MAC extraction) that already has tested, more robust equivalents in `resources/utilities/`. Wiring these scripts up to the shared layer would remove the duplication and pick up the timeout/pooling/format-robustness improvements for free.
- `pages/add_device_page.py:211` references a trash-icon path (`utilities\\trash.jpg`) that doesn't match the actual asset location (`resources/utilities/trash.jpg`).
- `core/manager.py:41-46` uses a bare `except:` around required-field validation, which will silently swallow unrelated errors (e.g. a typo'd key access elsewhere) as if they were the "missing Name/Path" case.
- Several stale header comments (`# add_device_page.py` atop `connection_page.py`, `home_page.py`, and `error_log_page.py`'s `# error_handler.py`) suggest these files started life as copies of another page — harmless, but worth cleaning up if touching those files anyway.

## FAQ

**Q: Why does `pytest` fail with `ModuleNotFoundError: No module named 'resources'`?**
A: You ran the bare `pytest` executable instead of `python -m pytest` from the repo root. See Setup above.

**Q: I set a `TR_*` environment variable and nothing changed. Why?**
A: As of this commit, `devices/TR/teltonika.py` and `prog_dev.py` don't call `load_config()` at all — the env var precedence system exists and is tested, but isn't wired into the TR device scripts yet.

**Q: Why does `device_types` exist if nothing uses it?**
A: It looks like scaffolding for a planned plugin-style device abstraction that the actual implementation (subprocess-based `prog_dev.py`/hardware scripts per device folder) ended up not needing. See `CODE_EXPLAIN.md`.

**Q: The "Program Device" button won't enable — what's wrong?**
A: Almost certainly the hardcoded instructions-file path bug described under Warnings above.
