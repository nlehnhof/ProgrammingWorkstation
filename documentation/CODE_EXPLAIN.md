# CODE_EXPLAIN.md — Programming Workstation

**Last commit:** `79c2b64` (2026-08-03) — describes the code as of `ccd15af`, "Automate Digi IX20 flow, add live Status checklist, fix packaged build"

Function-level explanation of every source file in the app, grouped by directory. The Teltonika device implementation (`devices/TR/`) has its own nested `documentation/CODE_EXPLAIN.md` with the same level of detail — it's not repeated here. The Digi IX20 implementation (`devices/digiIX20/`) is covered at the end of this file.

Complexity ratings default to **simple** per `resources/documentation/DOCS.md`; only genuinely intricate files are rated higher.

## New in `ccd15af`

Why each addition exists:

- **`resources/utilities/app_paths.py`** — the app had to work both from source and as a packaged .exe with an external, writable `devices/` folder. One module now owns that distinction instead of scattered `__file__`/`getcwd()` guesses.
- **`resources/utilities/wait_utils.py`** — device automation confirmed work with fixed `time.sleep()`s, so verification could run before the operation it verified. Every wait here is driven by an observed event instead.
- **`resources/utilities/elevate.py`** — the Digi flow reconfigures the PC's network adapter, which needs an elevated process, and Windows can only elevate by starting a new one.
- **`pages/status_panel.py`** — replaces the static instruction text with live PASS/FAIL milestones, which required moving the run off the GUI thread.
- **`devices/digiIX20/{checklist,device_config}.json`** — milestone labels and externalised configuration for the Digi.

Changed behaviour: `program_device()` no longer blocks the GUI; `StreamInterceptor` survives a windowed build with no streams; `devices/__init__.py` scans the external device folder; both `prog_dev.py` files launch children through `script_command()`.

## Entry point

### `main.py` — **Simple**
Three things happen before Qt exists (`main.py:1-30`): the working directory is pinned to `app_paths.app_root()`; `--run-script <path>` is intercepted and `runpy`-executed instead of starting the GUI (packaged builds only — see `app_paths.script_command`); and `elevate.ensure_admin()` relaunches the process elevated, showing a dialog and continuing unelevated if the operator declines. Then it builds the `QApplication`, sets Fusion style and a green-button/white-background stylesheet, constructs one `MainPage`, and calls `app.exec_()`. Importing `pages.error_log_page` is what activates the global error handler for the whole process.

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
`registered_devices` is a list of device folder names, recomputed at import time, and still `print()`s as a side effect. It now delegates to `app_paths.registered_devices()`, which scans **`app_root()/devices`** rather than this package's own directory — that indirection is what lets a packaged build read the `devices/` folder sitting next to the .exe, so new devices appear without a rebuild.

## `pages/` — PyQt5 UI

### `pages/main_window.py` — **Simple**
`MainPage` (`pages/main_window.py:13`) builds the `QStackedWidget` and adds all four pages at fixed indices 0–3 (`pages/main_window.py:28-31`). See `WORKFLOW.md` §1 for the navigation diagram.

### `pages/home_page.py` — **Simple**
Two buttons jump to indices 1 and 2. `showEvent` (`pages/home_page.py:47`) and the `currentChanged`-driven `on_page_changed` (`pages/home_page.py:53`) both refresh `devices_list`/other pages' `.refresh()` whenever navigation occurs — this is the mechanism that keeps device dropdowns in sync across pages without an explicit event bus. Note the file's header comment reads `# add_device_page.py` (`pages/home_page.py:1`) — a copy-paste leftover, not a functional issue.

### `pages/add_device_page.py` — **Medium**
`AddDevice` (`pages/add_device_page.py:15`) renders a static "Example Device" reference block plus a dynamic list of key/value row widgets (`add_row`/`remove_row`, `pages/add_device_page.py:189,222`). `on_submit` (`pages/add_device_page.py:229`) walks `self.rows`, pulls the two `QLineEdit`s out of each row widget, and builds a dict that must contain `Name`/`Path` (missing keys just print a message and fall through — `create_device` is still called with a possibly-incomplete dict, `pages/add_device_page.py:239-248`). The `QIcon("utilities\\trash.jpg")` path (`pages/add_device_page.py:211`) is a Windows-style relative path that doesn't correspond to any file in this repo (the actual asset is `resources/utilities/trash.jpg`) — the delete-row button icon likely renders blank.

### `pages/program_page.py` — **Complex**
The largest and most consequential page — see `WORKFLOW.md` §4 for the full data-flow diagram. Highlights:
- `ProgramWorker(QThread)`: does the `exec()` of `devices/{device}/prog_dev.py` and the `run_main_script(...)` call on a background thread, seeding the exec namespace with `{"progress_callback": self._emit_progress}`. Reports via `progress`/`finished_ok`/`failed` signals, and swallows `SystemExit` so a device script calling `sys.exit()` can't take the app down.
- `program_device()`: validates the dropdowns (checking `.currentText()`, not the always-truthy `QComboBox` objects), resets the Status panel, disables the Program button and starts the worker. It no longer blocks the Qt event loop.
- `on_program_failed(tb_text)`: marks the in-flight row FAIL and writes the traceback to `sys.stderr` **from the GUI thread**, because `error_log_page`'s interceptor opens a modal dialog on stderr writes.
- `load_instructions()` reads `devices/{device}/instructions.txt` via `app_paths.device_dir()`, building one `QCheckBox` per line; `update_button_state()` enables Program only when all are ticked.
- `load_checklist()` feeds `status_panel.set_steps()` from `devices/{device}/checklist.json`; a device without that file gets an empty panel.
- `update_airports`/`update_gates` populate dropdowns from `resources.utilities.excel_utils.get_excel_files`/`get_dropdown`; `refresh()` reads `core/devices.json` resolved against `app_root()`.
- `on_submit()` parses a scanned QR string for a `PW:...;` segment to extract `temp_pass`, falling back to the raw scanned text.

### `pages/status_panel.py` — **Medium**
Renders the live milestone checklist to the right of the form. `load_checklist(device_dir)` reads `checklist.json` and returns `(steps, image_path)`, tolerating a missing or malformed file. `StepRow` is one line — icon, label with time estimate, right-aligned status — with `set_state`, `set_note` and `set_status_text` kept separate so a `WAIT` note and the running elapsed timer don't overwrite each other. `StatusPanel.update_step(step_id, state, detail)` maps the five protocol states onto those rows: `RUNNING` starts a 1-second `QTimer` showing elapsed `m:ss`, `PASS`/`FAIL` stop it, `SENT` briefly takes the status column, and `WAIT` puts the device's own wording under the label. Colours reuse the app palette (`#4CAF50` green, `#D32F2F` red).

### `pages/connection_page.py` — **Simple**
Static instructional page showing `router.jpg`, now located through `app_paths.resource_path()` so it resolves inside a packaged bundle; "YES" jumps to index 2. Also carries a stale `# add_device_page.py` header comment (`pages/connection_page.py:1`).

### `pages/error_log_page.py` — **Medium**
Despite the filename, the header comment says `# error_handler.py` (`pages/error_log_page.py:1`) — another naming artifact. Installs itself globally the moment it's imported (`install_error_handler()` call at `pages/error_log_page.py:163`, executed at module scope):
- `sys.excepthook`, `threading.excepthook`, and the asyncio loop's exception handler all route into `_collect_output(..., is_error=True)` (`pages/error_log_page.py:76-93`).
- `sys.stdout`/`sys.stderr` are wrapped in `StreamInterceptor`, so **every** `print()` in the app is captured into `_output_buffer`, not just exceptions. All raw writes go through `_write_raw()`, which no-ops when the underlying stream is `None` or closed — required for packaged windowed builds (`console=False`), where `sys.stdout`, `sys.stderr` and their `__stdout__`/`__stderr__` originals are all `None`. Without it the first `print()` raised `AttributeError` and killed the .exe before its window appeared.
- `subprocess.run` is monkey-patched to `safe_subprocess_run` (`pages/error_log_page.py:156`, definition at `:113`) which forces `capture_output=True, text=True, check=True` on every call site in the process — this applies even to code that didn't ask for it.
- One `LogDialog` (`pages/error_log_page.py:25`) is shown on first error (`_error_popup_shown` flag prevents repeats) and again unconditionally at process exit via `atexit` (`pages/error_log_page.py:159`).
- A fresh timestamped crash log path is computed once at import time (`RUN_TIMESTAMP`/`LOG_FILE`, `pages/error_log_page.py:21-22`) and reused for the whole run — one file per app launch, not per error.

## `resources/utilities/` — shared utility layer

This layer is well-tested (`tests/`). As of `ccd15af` the Digi device uses it throughout; TR still does not (see `WORKFLOW.md` §5).

### `resources/utilities/app_paths.py` — **Simple**
Answers "where are things" for both source and packaged runs. `app_root()` returns the repo root, or the folder holding the .exe when `sys.frozen` — it locates mutable data (`devices/`, `core/`, `logs/`). `bundle_root()` returns `sys._MEIPASS` when frozen and backs `resource_path()` for read-only assets. `devices_root()`/`device_dir(name)`/`registered_devices()` build on `app_root()`, so a packaged build reads the external device folder. `script_command(script, *args)` returns `[main.exe, --run-script, script, ...]` when frozen and `[python.exe, script, ...]` otherwise, because a frozen `sys.executable` is the app rather than an interpreter.

### `resources/utilities/wait_utils.py` — **Medium**
Completion-driven replacements for fixed sleeps. `read_until(shell, patterns, timeout)` accumulates shell output, echoing it live, and returns as soon as any regex matches — raising `StepTimeout` rather than hanging. `wait_for_prompt`/`run_cli` build on it: `run_cli` sends a command and blocks until the CLI hands the prompt back, which is what guarantees a verification step cannot run before the operation it verifies has finished. `run_checked` uses `recv_exit_status()` for a real pass/fail on `exec_command`. `wait_for_port`/`wait_for_ssh` poll a reboot down-then-up, treating a successful login as the completion signal. `verify_remote_file(sftp, path, expected_size)` stats a transferred file and raises `RemoteFileMissing` if absent or short. Covered by `tests/test_wait_utils.py`.

### `resources/utilities/elevate.py` — **Simple**
`is_admin()` wraps `shell32.IsUserAnAdmin()`. `relaunch_as_admin()` calls `ShellExecuteW(..., "runas", ...)`, pinning `lpDirectory` to the app root because an elevated process would otherwise start in `C:\Windows\System32`; it raises `PermissionError` when the operator dismisses UAC and `OSError` on other failures. `ensure_admin()` ties them together — no-op when already elevated, otherwise relaunch and `os._exit(0)` (skipping `atexit`, so `error_log_page` doesn't pop a dialog on the way out). A `--elevated` flag on the relaunched copy prevents an infinite UAC loop where elevation silently fails.

### `resources/utilities/device_config.py` — **Simple**
`load_config(device_dir, filename="device_config.json", env_prefix="TR_")` (`resources/utilities/device_config.py:36`) layers `DEFAULTS` → JSON file → env vars, coercing `ssh_timeout`/`test_script_timeout` to `int` from env vars. Fully covered by `tests/test_device_config.py`. `devices/digiIX20/digix20.py` calls it with `env_prefix="DIGIIX20_"`; no caller exists in `devices/TR/`.

### `resources/utilities/ssh_session.py` — **Medium**
`SSHSession` (`resources/utilities/ssh_session.py:53`) lazily connects (`ensure_connected`, `:78`), pools the connection and one SFTP client, and exposes `run()`/`upload()`/`invoke_shell()`. `ManagedShell` (`:22`) wraps a raw `invoke_shell()` channel as a context manager so it's always closed, converting `socket.timeout` into `SSHCommandTimeout` (`:35-39`). `connect_with_fallback` (`:149`) tries a list of `(host, user, password)` candidates in order. Covered by `tests/test_ssh_session.py`. Used by `devices/digiIX20/digix20.py`; **not** by `devices/TR/teltonika.py` or `prog_dev.py`, which still open a raw `paramiko.SSHClient()` per connection.

### `resources/utilities/mac_utils.py` — **Simple**
`extract_mac(text, interface=None)` (`resources/utilities/mac_utils.py:17`) searches for MACs near a named interface first (checking that line and the next two, since both `ifconfig` and `ip link` wrap output), trying labeled formats (`HWaddr`, `ether`, `link/ether`) before a bare regex fallback; returns `None` rather than raising. Covered by `tests/test_mac_utils.py`. Called by `devices/digiIX20/digix20.py`; `devices/TR/teltonika.py` still uses its own inline single-format parser (`"HWaddr" in line`) that predates this module.

### `resources/utilities/excel_utils.py` — **Simple** (but incomplete relative to its own tests)
Currently exposes only three functions: `get_excel_files(folder_path)` (`:9`, lists `.xlsx` files excluding `oshkosh_log.xlsx`), `get_dropdown(filepath)` (`:13`, returns column-E values from row 2 down — a positional read), and `lookup_excel(sheet, gate)` (`:33`, returns a `(gate_ip, gate_netmask, gate_gateway)` tuple found by scanning for a matching cell and reading three cells to its left). **`tests/test_excel_utils.py` imports `find_column`, `find_row_by_value`, `get_header_map`, `open_workbook`, and `require_columns` from this module — none of them exist yet**, so that test file currently fails to collect. This is the clearest evidence that the module is mid-refactor: the tests describe the target (header-name-based lookups with duplicate-header support), the code hasn't caught up.

### `resources/utilities/network_utils.py` — **Simple** (same caveat)
Only `is_valid_ip(ip_string)` (`:5`) exists, wrapping `ipaddress.ip_address`. `tests/test_network_utils.py` also imports `validate_subnet`, which doesn't exist in this file — it does, however, exist as a **duplicate, working implementation** inline in `devices/TR/prog_dev.py:92`.

### `resources/utilities/fonts.py` — **Simple**
Two module-level `QFont` constants (`header_font`, `subtitle_font`) shared across pages.

## `tests/`

Seven files, run with `python -m pytest tests/` from the repo root (`pytest` is not in `requirements.txt` — see `../SETUP.md` §4). `test_device_config.py`, `test_mac_utils.py`, `test_ssh_session.py` and `test_wait_utils.py` pass against current code and exercise the utilities described above. `test_excel_utils.py` and `test_network_utils.py` fail to *collect* (import errors) because they test functions that don't exist in the corresponding modules. `test_prog_dev_integration.py` loads `devices/TR/prog_dev.py` via `importlib.util.spec_from_file_location` (mirroring the real `exec()`-based loading — see `WORKFLOW.md` §4) and asserts against functions (`get_header_map`, `col`, an `ssh_run_shell(session, cmd)` accepting an `SSHSession`) that don't exist in that file — six failures, pre-existing and unrelated to the Digi work. Note `devices/digiIX20/prog_dev.py` *does* now implement `get_header_map`/`col`, so that test file describes an API TR has yet to adopt.

### `tests/test_wait_utils.py` — **Simple**
Fake shell and SFTP objects covering the behaviour that replaced fixed sleeps: `read_until` returning on a match, matching across chunk boundaries, matching any of several patterns, and raising `StepTimeout` when the marker never arrives; `verify_remote_file` accepting a correct size and rejecting a missing or short transfer.

## `devices/digiIX20/`

The Digi IX20 implementation, rewritten in `ccd15af` onto the shared utility layer.

### `devices/digiIX20/digix20.py` — **Complex**
The hardware automation script, run as a child process with `(gate_ip, netmask, gateway, default_pass)` as `sys.argv`. Configuration comes from `load_config(DEVICE_DIR, env_prefix="DIGIIX20_")`; transport is `SSHSession`/`ManagedShell`; every wait uses `wait_utils`, so no verification runs before the operation it checks has completed. Structured as seven milestone functions dispatched from `main()` — `check_ip`, `firmware_update`, `first_reboot`, `configure`, `switch_static_ip`, `change_ip_address`, `testing` — each announcing itself via `status()` as `##STATUS##id|state|detail`. Failures raise `StepError`; `main()` catches, emits `FAIL`, prints a traceback and returns a non-zero exit code, and a `finally` block restores the PC adapter to DHCP. `switch_static_ip` shells out to PowerShell against this PC's own NIC and fails with an explicit message when not elevated. `pull_file_to_router` is the two-hop pattern: SFTP to the BeagleBone, verify size, have the router `scp` it, wait for the prompt, then check name and size.

### `devices/digiIX20/prog_dev.py` — **Medium**
The GUI-facing layer, `exec()`'d by `ProgramWorker`. `run_main_script(airport, gate, default_pass, device)` looks up the gate row with the shared `lookup_excel(sheet, gate)`, spawns `digix20.py` through `script_command()`, and consumes the child's stdout in a **single** loop that forwards `##STATUS##` markers to `progress_callback` (suppressing them from operator output), watches for `Incorrect`/`Traceback`, and buffers lines for the crash log. It honours the child's exit code and raises `DigiProgrammingError` on failure so the error log picks it up. `get_header_map`/`col`/`find_gate_row` resolve Excel columns by header name with positional fallbacks; `update_sheet_and_label` writes the MAC, a red-or-black timestamp, hyperlinks to the crash log and label, and the Brady label file under `devices/digiIX20/router_labels/`.

### `devices/digiIX20/checklist.json` / `device_config.json` — **Simple**
`checklist.json` lists the seven milestone rows (`id`, `label`, `estimate`) the Status panel renders. `device_config.json` externalises everything previously hardcoded — BBB and router addresses, credentials, the `eth2` LAN interface, firmware/config filenames and timeouts — all overridable with `DIGIIX20_*` environment variables.

Operator instructions live as numbered steps with reference photos in `devices/digiIX20/instructions/manual_instructions.txt` and `digistepN.png`.
