# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A PyQt5 desktop app ("Programming Workstation") that automates provisioning of embedded devices in the field — a Teltonika RUTX08 router (`devices/TR/`) and a Digi IX20 router (`devices/digiIX20/`), both used in airport gate-control installations. It walks an operator through: register a device type → confirm hardware wiring → pick an airport/gate from an Excel sheet → run the device's programming script (firmware flash, config push, functional test) → generate a label and update the Excel log.

Credentials are stored as plaintext in `core/devices.json` and each `devices/*/device_config.json`. This is a known, documented limitation — treat hardcoded-looking IPs/passwords as intentional lab defaults, not bugs, unless told otherwise.

Documentation, in order of usefulness:
- `cheat_sheet.md` — one page, plain language, no code. Start here for orientation.
- `documentation/` — the maintained set: `README.md`, `WORKFLOW.md`, `CODE_EXPLAIN.md`, `INSTRUCTIONS.md`. Kept in sync with each commit; this is the source of truth.
- `devices/TR/documentation/` — the same set, scoped to the Teltonika device.
- `DOCUMENTATION_OVERVIEW.md` — a signpost to the above; it used to be a second parallel description and is no longer.
- `resources/documentation/DOCS.md` — this repo's conventions for *writing* documentation. Follow it if asked to add or update docs anywhere in the tree.

## Running the app and tests

Use `venv/` (Python 3.13) for everything — it has PyQt5, paramiko, openpyxl, ping3, pytest and pyinstaller:

```
./venv/Scripts/python.exe main.py
./venv/Scripts/python.exe -m pytest tests/
./venv/Scripts/python.exe -m pytest tests/test_ssh_session.py::test_connects_lazily_on_first_use
```

Run tests from the **repo root** with `-m pytest` (not the bare `pytest` executable) so `resources`/`devices`/`core` resolve as top-level packages — there's no `conftest.py` or `pyproject.toml` adding the rootdir to `sys.path`. All 83 tests should pass; a failure is a real regression, not pre-existing noise.

There is no linter/formatter config in this repo (no `.flake8`, `pyproject.toml`, `.pre-commit-config.yaml`) — don't invent style-check commands.

## Architecture

**Navigation** is a `QStackedWidget` in `pages/main_window.py` (`MainPage`) with four indexed pages plus a non-stacked error dialog:

```
home_page (0) → add_device_page (1)         [register a new device type]
              → program_page (2)            [the main flow: select, then run]
connection_page (3)                          [wiring photo; not currently wired into the flow]
error_log_page                               [triggered on exception, any point]
```

- **A device is a folder, not a class.** `devices/{NAME}/` holds that device's `prog_dev.py`, hardware script, `device_config.json`, `checklist.json`, `instructions.txt` and spreadsheets. There is no base class to subclass — `device_types/` used to exist for that and was deleted in `e96074a` (all four files were 100% commented out).
- **`core/manager.py`** — single `DeviceManager` instance (module-level `manager = DeviceManager()`), owns `core/devices.json`. `create_device()` validates, copies a source folder into `devices/{name}/`, and **raises** on bad input so the page can show a dialog. `manager.names()` re-reads from disk, so pages see devices added during the session.
- **How a device gets programmed**: `pages/program_page.py` builds a namespace and does a literal `exec(code, namespace)` on `devices/{device}/prog_dev.py` — it is not imported as a normal module, and has no reliable `__file__`. `tests/test_prog_dev_integration.py` mirrors this with `importlib.util.spec_from_file_location`. Static import graphs won't show the edge from `program_page.py`.
- **The run happens on a `QThread`** (`ProgramWorker`), and the hardware script runs as a **subprocess** of that. Milestones travel back over the child's stdout.

### The shared layer (`resources/utilities/`)

This is the reusable, tested layer. **Both devices' `prog_dev.py` are built on it — prefer extending these over adding one-off logic in a device folder.**

- `excel_utils.py` — header-name-based access to the gate spreadsheets: `get_header_map`/`find_column`/`require_columns`/`find_row_by_value`, `lookup_excel(path, gate)` returning `{gate_ip, netmask, gateway}` and *raising* on bad data, and `open_workbook()` guaranteeing close. Never address a sheet column by number; "Crash Report" legitimately appears twice, which is why `find_column` takes an `occurrence`.
- `reporting.py` — everything a run leaves behind: `write_crash_log`, `record_result` (sheet stamp + label), `record_test_result`. `COLUMNS` maps a logical field name to a header. Two conventions it enforces: timestamps are **red on failure, black on success**, and **a failed run writes no label**.
- `status.py` — the `##STATUS##<id>|<state>|<detail>` protocol *and* `watch_process(command, report)`, the single-pass loop that runs a hardware script and consumes its output. Emitting and parsing live together on purpose.
- `ssh_session.py` — `SSHSession` (pooled, lazy-connect, timeout-enforced) and `ManagedShell` (context manager, always closes). Reuse a session across commands rather than opening new connections.
- `wait_utils.py` — waits driven by an observed event (a prompt returning, an exit status, a port answering), never a fixed sleep.
- `device_config.py` — three-tier precedence: `DEFAULTS` → `device_config.json` → `{PREFIX}_*` env vars. Called with `env_prefix="DIGIIX20_"` from `digix20.py:48`, and `env_prefix="TR_"` from both `devices/TR/prog_dev.py:160` and `devices/TR/teltonika.py:55`.
- `network_utils.py` — `is_valid_ip`, `validate_subnet`, `prefix_length`. Never assume `/24`; real sheets contain `255.255.255.128` gates.
- `templating.py` — the `og_*` → working-copy staging both devices use. `patch_file` verifies by **counting replacements**, not by checking the new value is present afterwards; the latter passes on a file that already held that value, which is how a silently-failed substitution used to ship the previous gate's config.
- `mac_utils.py` — `extract_mac()` handles several `ifconfig`/`ip link` formats; returns `None` rather than raising.
- `app_paths.py` — where things are, from source and inside a packaged .exe. `script_command()` matters: frozen, `sys.executable` is the app, not Python.

### Both devices are fully migrated

Every file in both device folders sits on the shared layer. Each hardware script is a list of milestone functions dispatched from `main()`, reporting progress through `status`, and both ship a `checklist.json`.

The remaining behavioural difference: **`digix20.py` can resume**, detecting where the router actually is and restarting at the right milestone, while `teltonika.py` only has a coarse "already programmed, skip everything" check.

**`devices/TR/config_manifest.json` is a trap for the unwary.** It lists the 82 config files pushed to a Teltonika. `og_configs/` holds 94 — the other 12 (`certificates`, `log`, `speedtest`, `siteman_*`) are per-unit device state that provisioning must not overwrite. Do not "simplify" this into an `os.listdir()`; `tests/test_tr_config_manifest.py` exists to stop that, and fails if a new file appears in `og_configs/` without a deliberate decision.

### Other things worth knowing

- **Error handling** is centralized in `pages/error_log_page.py`: a global exception hook buffers output, shows one dialog (no spam), and writes a timestamped file to `logs/`. It installs itself at *import time* and monkey-patches `subprocess.run` process-wide. The app degrades gracefully rather than crashing on device errors — preserve that.
- **A stderr write raises a modal dialog**, so it is only safe from the Qt thread. That is why `ProgramWorker` emits a `failed` signal and lets `ProgramPage` do the actual `sys.stderr.write`.
- **`devices/TR/` holds non-code assets** that matter operationally: `og_configs/` (94 router config files, template — never modify in place; working copies go to `configs/`, and only the 82 in `config_manifest.json` are pushed), `og_testfile/`/`testfile/` (same split for the Modbus test script), per-airport `.xlsx` gate sheets, and `labels/` (generated label text a physical Brady printer watches for).
- **`devices/TR/JKC-SLC.xlsx` is corrupt** — not a valid `.xlsx`. It is skipped gracefully; the file itself still needs replacing.

## Working in this repo

- When adding a new device type, add a `devices/{NAME}/` folder with its own `prog_dev.py`, `device_config.json`, `instructions.txt` and config templates. `devices/digiIX20/prog_dev.py` is 104 lines and is the reference to copy.
- Respect the config precedence order in `device_config.py`: add new tunables to the device's `device_config.json` first, and only reach for an env var override if the value genuinely needs to differ per deployment machine.
- `devices/TR/history/` holds abandoned prior implementations (`dashboard.py`, `prog_dev_old.py`, `tel2.py`) — reference only, not live code.
- Runtime output (`logs/`, `crash_logs/`, `router_labels/`, `__pycache__/`) is gitignored. Don't commit it.
