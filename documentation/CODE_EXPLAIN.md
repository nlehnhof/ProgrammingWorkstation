# CODE_EXPLAIN.md — Programming Workstation

**Last commit:** `2e84f6c` — "DOCS.md file" (2026-07-30)

Function-level explanation of every source file in the app, grouped by directory. The Teltonika device implementation (`devices/TR/`) has its own nested `documentation/CODE_EXPLAIN.md` with the same level of detail — it's not repeated here. The Digi IX20 implementation (`devices/digiIX20/`) is covered briefly at the end of this file since it's much smaller and still early-stage.

## Entry point

### `main.py` — **Simple**
Builds the `QApplication`, sets Fusion style and a hardcoded green-button/white-background stylesheet, constructs one `MainPage`, and calls `app.exec_()`. Importing `pages.error_log_page` (`main.py:9`) is what activates the global error handler for the whole process — see `pages/error_log_page.py` below.

## `core/` — device registry

### `core/manager.py` — **Medium**
`DeviceManager` (`core/manager.py:22`) is the only class here, instantiated once as a module-level singleton `manager` (`core/manager.py:139`) that every page imports and shares.
- `create_device(data)` (`core/manager.py:29`): validates `data["Name"]`/`data["Path"]` are present (bare `except:` swallows any other error and just prints, `core/manager.py:41-46`), rejects duplicate names and missing source paths, stores everything-but-`Name` into `self.device_credentials[name]`, calls `_save_devices()`, then `shutil.copytree`s the source folder into `devices/{name}/`.
- `get_credentials(name)` (`core/manager.py:77`) reads `devices.json` fresh from disk on every call rather than using the in-memory dict — a minor inconsistency, since `create_device` writes to memory-then-file but reads go straight to file.
- `_load_devices()` / `_save_devices()` (`core/manager.py:99`, `:113`): load-on-init and merge-on-save against `core/devices.json`, defensively resetting to `{}` on malformed JSON rather than crashing.

## `device_types/` — unused abstraction layer

### `device_types/base_device.py` — **Simple**
Abstract `Device(ABC)` (`device_types/base_device.py:4`) requiring `connect`/`disconnect`/`upload`/`run`. Constructor validates `name` is a non-empty string and stores extra kwargs in `self.params`.

### `device_types/ssh_device.py`, `device_types/telnet_device.py` — **Simple**
Straightforward `paramiko`/`telnetlib` implementations of `Device`. **Not used anywhere in the actual programming flow** — `devices/TR/teltonika.py` talks to hardware directly with its own inline `paramiko` calls rather than instantiating `SSHDevice`. These classes are referenced only via the wildcard imports in `pages/add_device_page.py:7` and `pages/program_page.py:5`, and neither page actually constructs one.

### `device_types/__init__.py` — **Medium** (behaviorally surprising, not logically complex)
Runs a filesystem scan at import time: for every `.py` file in the package directory, `importlib.import_module` it, then use `inspect.getmembers` to hoist every function/class into the package's global namespace (`device_types/__init__.py:26-33`). Separately, `extract_class_names` (`device_types/__init__.py:15`) AST-parses each file for class definitions into `all_classes`, and both `all_classes` and the print statement at `device_types/__init__.py:41` fire as a side effect of the import — meaning `from device_types import *` (used in three page files) prints `All Classes: {...}` to stdout every time.

### `devices/__init__.py` — **Simple**
`registered_devices` is a list of directory names under `devices/` (excluding `__pycache__`), recomputed at import time. Also `print()`s at import (`devices/__init__.py:8`), same caveat as above.

## `pages/` — PyQt5 UI

### `pages/main_window.py` — **Simple**
`MainPage` (`pages/main_window.py:13`) builds the `QStackedWidget` and adds all four pages at fixed indices 0–3 (`pages/main_window.py:28-31`). See `WORKFLOW.md` §1 for the navigation diagram.

### `pages/home_page.py` — **Simple**
Two buttons jump to indices 1 and 2. `showEvent` (`pages/home_page.py:47`) and the `currentChanged`-driven `on_page_changed` (`pages/home_page.py:53`) both refresh `devices_list`/other pages' `.refresh()` whenever navigation occurs — this is the mechanism that keeps device dropdowns in sync across pages without an explicit event bus. Note the file's header comment reads `# add_device_page.py` (`pages/home_page.py:1`) — a copy-paste leftover, not a functional issue.

### `pages/add_device_page.py` — **Medium**
`AddDevice` (`pages/add_device_page.py:15`) renders a static "Example Device" reference block plus a dynamic list of key/value row widgets (`add_row`/`remove_row`, `pages/add_device_page.py:189,222`). `on_submit` (`pages/add_device_page.py:229`) walks `self.rows`, pulls the two `QLineEdit`s out of each row widget, and builds a dict that must contain `Name`/`Path` (missing keys just print a message and fall through — `create_device` is still called with a possibly-incomplete dict, `pages/add_device_page.py:239-248`). The `QIcon("utilities\\trash.jpg")` path (`pages/add_device_page.py:211`) is a Windows-style relative path that doesn't correspond to any file in this repo (the actual asset is `resources/utilities/trash.jpg`) — the delete-row button icon likely renders blank.

### `pages/program_page.py` — **Complex**
The largest and most consequential page — see `WORKFLOW.md` §4 for the full data-flow diagram. Highlights:
- `program_device()` (`pages/program_page.py:132`): reads `devices/{device}/prog_dev.py` as text and `exec()`s it (`:136-151`), then immediately calls the resulting `run_main_script` synchronously on the GUI thread — the whole ~7-minute provisioning flow blocks the Qt event loop.
- `load_instructions()` (`pages/program_page.py:178`) reads a per-device checklist from a **hardcoded absolute path**, `C:\Users\u324754\programming_workstation\devices\{device}\instructions.txt` (`pages/program_page.py:188`), rather than a path relative to the repo — this only works on the original developer's machine and silently no-ops (via the `FileNotFoundError` catch) everywhere else, meaning the "Program Device" button's checkbox-gating (`update_button_state`, `pages/program_page.py:206`) never enables on any other machine.
- `update_airports`/`update_gates` (`pages/program_page.py:164,211`) populate dropdowns from `resources.utilities.excel_utils.get_excel_files`/`get_dropdown`, keyed off whatever the operator selected previously.
- `on_submit()` (`pages/program_page.py:261`) parses a scanned QR string for a `PW:...;` segment to extract `temp_pass`, falling back to using the raw scanned text if the pattern isn't present.

### `pages/connection_page.py` — **Simple**
Static instructional page showing `resources/images/router.jpg`; "YES" jumps to index 2. Also carries a stale `# add_device_page.py` header comment (`pages/connection_page.py:1`).

### `pages/error_log_page.py` — **Medium**
Despite the filename, the header comment says `# error_handler.py` (`pages/error_log_page.py:1`) — another naming artifact. Installs itself globally the moment it's imported (`install_error_handler()` call at `pages/error_log_page.py:163`, executed at module scope):
- `sys.excepthook`, `threading.excepthook`, and the asyncio loop's exception handler all route into `_collect_output(..., is_error=True)` (`pages/error_log_page.py:76-93`).
- `sys.stdout`/`sys.stderr` are wrapped in `StreamInterceptor` (`pages/error_log_page.py:97`), so **every** `print()` in the app is captured into `_output_buffer`, not just exceptions.
- `subprocess.run` is monkey-patched to `safe_subprocess_run` (`pages/error_log_page.py:156`, definition at `:113`) which forces `capture_output=True, text=True, check=True` on every call site in the process — this applies even to code that didn't ask for it.
- One `LogDialog` (`pages/error_log_page.py:25`) is shown on first error (`_error_popup_shown` flag prevents repeats) and again unconditionally at process exit via `atexit` (`pages/error_log_page.py:159`).
- A fresh timestamped crash log path is computed once at import time (`RUN_TIMESTAMP`/`LOG_FILE`, `pages/error_log_page.py:21-22`) and reused for the whole run — one file per app launch, not per error.

## `resources/utilities/` — shared utility layer

This layer is well-tested (`tests/`) but, per `WORKFLOW.md` §5, only partially wired into the actual device scripts.

### `resources/utilities/device_config.py` — **Simple**
`load_config(device_dir, filename="device_config.json", env_prefix="TR_")` (`resources/utilities/device_config.py:36`) layers `DEFAULTS` → JSON file → env vars, coercing `ssh_timeout`/`test_script_timeout` to `int` from env vars. Fully covered by `tests/test_device_config.py`. No caller currently exists in `devices/TR/`.

### `resources/utilities/ssh_session.py` — **Medium**
`SSHSession` (`resources/utilities/ssh_session.py:53`) lazily connects (`ensure_connected`, `:78`), pools the connection and one SFTP client, and exposes `run()`/`upload()`/`invoke_shell()`. `ManagedShell` (`:22`) wraps a raw `invoke_shell()` channel as a context manager so it's always closed, converting `socket.timeout` into `SSHCommandTimeout` (`:35-39`). `connect_with_fallback` (`:149`) tries a list of `(host, user, password)` candidates in order. Covered by `tests/test_ssh_session.py`. Not called from `devices/TR/teltonika.py` or `prog_dev.py`, which each open their own raw `paramiko.SSHClient()` per connection instead.

### `resources/utilities/mac_utils.py` — **Simple**
`extract_mac(text, interface=None)` (`resources/utilities/mac_utils.py:17`) searches for MACs near a named interface first (checking that line and the next two, since both `ifconfig` and `ip link` wrap output), trying labeled formats (`HWaddr`, `ether`, `link/ether`) before a bare regex fallback; returns `None` rather than raising. Covered by `tests/test_mac_utils.py`. `devices/TR/teltonika.py:512-514` instead uses its own inline single-format parser (`"HWaddr" in line`) that predates this module.

### `resources/utilities/excel_utils.py` — **Simple** (but incomplete relative to its own tests)
Currently exposes only three functions: `get_excel_files(folder_path)` (`:9`, lists `.xlsx` files excluding `oshkosh_log.xlsx`), `get_dropdown(filepath)` (`:13`, returns column-E values from row 2 down — a positional read), and `lookup_excel(sheet, gate)` (`:33`, returns a `(gate_ip, gate_netmask, gate_gateway)` tuple found by scanning for a matching cell and reading three cells to its left). **`tests/test_excel_utils.py` imports `find_column`, `find_row_by_value`, `get_header_map`, `open_workbook`, and `require_columns` from this module — none of them exist yet**, so that test file currently fails to collect. This is the clearest evidence that the module is mid-refactor: the tests describe the target (header-name-based lookups with duplicate-header support), the code hasn't caught up.

### `resources/utilities/network_utils.py` — **Simple** (same caveat)
Only `is_valid_ip(ip_string)` (`:5`) exists, wrapping `ipaddress.ip_address`. `tests/test_network_utils.py` also imports `validate_subnet`, which doesn't exist in this file — it does, however, exist as a **duplicate, working implementation** inline in `devices/TR/prog_dev.py:92`.

### `resources/utilities/fonts.py` — **Simple**
Two module-level `QFont` constants (`header_font`, `subtitle_font`) shared across pages.

## `tests/`

Six files, run with `pytest` (see root `INSTRUCTIONS.md` for the exact command — there's an environment split on this machine between the venv with app dependencies and the Python install with `pytest`). `test_device_config.py`, `test_mac_utils.py`, and `test_ssh_session.py` pass against current code and exercise the utilities described above. `test_excel_utils.py` and `test_network_utils.py` fail to *collect* (import errors) because they test functions that don't exist yet in the corresponding modules. `test_prog_dev_integration.py` loads `devices/TR/prog_dev.py` via `importlib.util.spec_from_file_location` (mirroring the real `exec()`-based loading — see `WORKFLOW.md` §4) and asserts against functions (`get_header_map`, `col`, an `ssh_run_shell(session, cmd)` that accepts an `SSHSession`) that also don't exist in the current `devices/TR/prog_dev.py` — that file's actual `lookup_excel` and `ssh_run_shell` are different, older implementations (see `devices/TR/documentation/CODE_EXPLAIN.md`).

## `devices/digiIX20/` (brief — not nested, less mature than TR)

A second, in-progress device type for the Digi IX20 router. `devices/digiIX20/prog_dev.py` (**Medium**, 219 lines) is structurally similar to the TR device's `prog_dev.py` but noticeably slimmer — no live crash-log/label Excel-writing block is reached in the normal path (the loop only writes on an `"Incorrect"` stdout line, same pattern as TR). Distinctive detail: it's the one script in this repo that actually imports and calls the shared `resources/utilities/excel_utils.lookup_excel(sheet, gate)` (`devices/digiIX20/prog_dev.py:2,32`) with the utility's real 2-argument signature, rather than reimplementing it locally. `devices/digiIX20/digix20.py` (**Complex**, 492 lines) is the hardware automation script, using `pexpect.popen_spawn.PopenSpawn` (not in `requirements.txt`) alongside `paramiko`. Operator instructions live as numbered steps with reference photos in `devices/digiIX20/instructions/manual_instructions.txt` and `digistepN.png`.
