# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A PyQt5 desktop app ("Programming Workstation") that automates provisioning of embedded devices in the field — currently a Teltonika RUTX08 router (`devices/TR/`) used in airport gate-control installations. It walks an operator through: register a device type → verify hardware wiring → pick an airport/gate from an Excel sheet → run the device's programming script (firmware flash, config push, functional test) → generate a label and update the Excel log.

Current branch `sparse` is the active development line. Config/credential handling is explicitly called out as unfinished in `DOCUMENTATION_OVERVIEW.md` and `devices/TR/TR_DEVICE_DOCUMENTATION.md` — treat hardcoded-looking IPs/passwords as intentional lab defaults, not bugs, unless told otherwise.

Two existing docs are the primary source of truth and go deeper than this file:
- `DOCUMENTATION_OVERVIEW.md` — whole-app architecture, data flow, known limitations.
- `devices/TR/TR_DEVICE_DOCUMENTATION.md` — the TR device's 9-step provisioning flow, config precedence, file layout.
- `resources/documentation/DOCS.md` — this repo's own conventions for *writing* documentation (READme.md/WORKFLOW.md/CODE_EXPLAIN.md/etc. per folder). Follow it if asked to add or update docs anywhere in the tree.

## Running the app and tests

Two separate Python environments exist on this machine and neither has everything:

- **`venv/` (Python 3.13)** — has the app's real dependencies (PyQt5, paramiko, openpyxl, ping3). Use this to run the app:
  ```
  ./venv/Scripts/python.exe main.py
  ```
- **Tests need `pytest`**, which is not installed in `venv/`. If a system/other Python has `pytest` + `openpyxl` available, run tests from the **repo root** with `-m pytest` (not the bare `pytest` executable) so `resources`/`devices`/`core` resolve as top-level packages — there's no `conftest.py` or `pyproject.toml` adding the rootdir to `sys.path`:
  ```
  python -m pytest tests/
  python -m pytest tests/test_ssh_session.py::test_connects_lazily_on_first_use  # single test
  ```
  If neither environment has both `pytest` and the app deps, `pip install pytest` into `venv/` first.

Note: `test_excel_utils.py` and `test_network_utils.py` currently reference functions (`find_column`, `validate_subnet`) that don't match the current implementations in `resources/utilities/excel_utils.py` / `network_utils.py` — expect pre-existing collection errors there unrelated to your change unless you're specifically asked to reconcile them.

There is no linter/formatter config in this repo (no `.flake8`, `pyproject.toml`, `.pre-commit-config.yaml`) — don't invent style-check commands.

## Architecture

**Navigation** is a `QStackedWidget` in `pages/main_window.py` (`MainPage`) with four indexed pages plus a non-stacked error dialog:

```
home_page (0) → add_device_page (1)              [register a new device type]
              → program_page (2) → connection_page (3) → back to program_page → run
error_log_page                                     [triggered on exception, any point]
```

- **`core/manager.py`** — single `DeviceManager` instance (module-level `manager = DeviceManager()`), owns `devices.json` (device name → credentials/path). `create_device()` copies a source folder into `devices/{name}/`. Credentials are plaintext JSON — known limitation, not accidental.
- **`device_types/`** — an abstract `Device` base class (`connect`/`disconnect`/`upload`/`run`) with SSH/Telnet stubs. **Not used by the actual programming flow** — `pages/add_device_page.py` references it, but real device automation (`devices/TR/teltonika.py`) talks to hardware directly via `SSHSession`, not through this abstraction. Don't assume new device types must implement `Device`.
- **`device_types/__init__.py` and `devices/__init__.py`** run import-time filesystem scans and `print()` side effects (`extract_class_names`, `registered_devices`) — importing either package has observable console output; this is existing behavior, not a bug to silently "fix" unless asked.
- **How a device gets programmed**: `pages/program_page.py` builds a namespace and does a literal `exec(code, namespace)` on `devices/{device}/prog_dev.py` (see `program_page.py:134,151`) — it is not imported as a normal module. `tests/test_prog_dev_integration.py` mirrors this by loading it via `importlib.util.spec_from_file_location` instead of `import devices.TR.prog_dev`. Keep this in mind when tracing calls into `prog_dev.py` — static import graphs won't show the edge from `program_page.py`.
- **Device-specific logic lives entirely under `devices/{DEVICE_NAME}/`** (e.g. `devices/TR/`), isolated from the shared app. `devices/TR/prog_dev.py` is the GUI-facing Excel/orchestration layer; `devices/TR/teltonika.py` is the actual 9-step hardware automation (config push, firmware flash, password reset, MAC extraction, reboot) it calls into. See `TR_DEVICE_DOCUMENTATION.md` for the step-by-step.
- **Shared utilities (`resources/utilities/`)** are the reusable, tested layer — prefer extending these over adding one-off logic in a device folder:
  - `device_config.py` — three-tier config precedence: `DEFAULTS` (in code) → `device_config.json` (per-device folder) → `{PREFIX}_*` env vars (e.g. `TR_BBB_IP`). `load_config(device_dir)` is called with `os.path.dirname(__file__)` from within each device's script.
  - `ssh_session.py` — `SSHSession` (pooled, lazy-connect, timeout-enforced) and `ManagedShell` (context manager for interactive shells, e.g. `passwd` prompts). Always reuse a session across multiple commands rather than opening new SSH connections.
  - `mac_utils.py` — `extract_mac()` handles multiple `ifconfig`/`ip link` output formats; returns `None` rather than raising on no match.
  - `excel_utils.py` — header-name-based column lookup (`get_header_map`/`find_column`) instead of hardcoded column indices, plus `open_workbook()` context manager guaranteeing the workbook closes.
  - `network_utils.py` — IP/subnet validation.
- **Error handling** is centralized in `pages/error_log_page.py`: a global exception hook buffers output, shows one dialog (no spam), and writes a timestamped file to `logs/`. The app is designed to degrade gracefully rather than crash on device errors — preserve that behavior when touching error paths.
- **`devices/TR/` also holds non-code assets** that matter operationally: `og_configs/` (82 router config files, template — never modify in place; working copies go to `configs/`), `og_testfile/`/`testfile/` (same original/working-copy split for the Modbus test script), per-airport `.xlsx` gate sheets, and `labels/` (generated label text files a physical Brady printer watches for).

## Working in this repo

- When adding a new device type, follow the existing pattern: a `devices/{NAME}/` folder with its own `prog_dev.py`, `device_config.json`, and config templates — not a new `device_types/` subclass (that abstraction is currently dead code).
- `devices/TR/history/` holds abandoned prior implementations (`dashboard.py`, `prog_dev_old.py`, `tel2.py`) — reference only, not live code.
- Respect the config precedence order in `device_config.py` when changing device behavior: add new tunables to `DEFAULTS` first, and only reach for an env var override if the value genuinely needs to differ per deployment machine.
