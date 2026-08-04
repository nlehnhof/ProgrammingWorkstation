# CODE_EXPLAIN.md — Programming Workstation

**Last commit:** `HEAD` (2026-08-04) — "Migrate teltonika.py onto the shared layer"

Function-level explanation of every source file in the app, grouped by directory. The Teltonika device implementation (`devices/TR/`) has its own nested `documentation/CODE_EXPLAIN.md`; the Digi IX20 implementation (`devices/digiIX20/`) is covered at the end of this file.

Complexity ratings default to **simple** per `../resources/documentation/DOCS.md` ("error on the side of simple"); only genuinely intricate files are rated higher.

## New and changed in `e96074a`

**Three new modules in `resources/utilities/`**, each extracted because both devices needed the same thing and each had written its own copy:

- **`excel_utils.py`** (rewritten) — header-name-based access to the gate spreadsheets. Both devices previously read cells by position, which returns the wrong data the moment a sheet's columns differ. This module implements the API `tests/test_excel_utils.py` had already been written against but which had never existed.
- **`status.py`** — the `##STATUS##` protocol between a hardware script and the GUI checklist, *and* `watch_process()`, the loop that runs a child script and consumes its output. Both halves in one module so the marker format is defined once.
- **`reporting.py`** — crash log, spreadsheet stamping, label writing. This bookkeeping appeared four times in `devices/TR/prog_dev.py` alone, each copy re-scanning the sheet and hardcoding column numbers.

**Deleted:** `device_types/` in its entirety. All four files (`base_device.py`, `ssh_device.py`, `telnet_device.py`, `__init__.py`) held working code — a `Device` ABC with `SSHDevice`/`TelnetDevice` implementations, and an `__init__.py` that walked the folder with `importlib`/`ast` to re-export whatever it found — but nothing ever instantiated any of it. `core/manager.py` imported `Device` and `pages/add_device_page.py` imported `SSHDevice` without using either; `home_page`, `connection_page` and `add_device_page` did `from device_types import *` for no symbols they referenced. The `__init__.py` scan also printed `All Classes: {...}` to stdout on every app start.

**Rewritten:** `devices/TR/prog_dev.py` (943 → 364 lines) and `devices/digiIX20/prog_dev.py` (353 → 104). `core/manager.py` lost twelve unused imports and its `devices`/`device_credentials` split.

**Since then, `devices/TR/teltonika.py` has been migrated too**, adding a fourth shared module:

- **`templating.py`** — the `og_*` → working-copy staging both devices' template folders need. Its `patch_file` verifies by counting replacements rather than checking the new value is present afterwards, which is what catches a substitution that silently did nothing.

That work also gave TR a `checklist.json` (so it has the live Status panel), moved its 82 hardcoded `sftp.put()` calls into `config_manifest.json`, and replaced its fixed `time.sleep()` waits with port down/up checks. Details are in `devices/TR/documentation/CODE_EXPLAIN.md`.

## Entry point

### `main.py` — **Simple**
Three things happen before Qt exists (`main.py:1-30`): the working directory is pinned to `app_paths.app_root()`; `--run-script <path>` is intercepted and `runpy`-executed instead of starting the GUI (packaged builds only — see `app_paths.script_command`); and `elevate.ensure_admin()` relaunches the process elevated, showing a dialog and continuing unelevated if the operator declines. Then it builds the `QApplication`, sets Fusion style and a green-button/white-background stylesheet, constructs one `MainPage`, and calls `app.exec_()`. Importing `pages.error_log_page` is what activates the global error handler for the whole process.

## `core/` — device registry

### `core/manager.py` — **Simple**
A "device" here is a *folder*, not a class — that is the whole extension mechanism. `DeviceManager` (`core/manager.py:27`) is instantiated once as the module-level singleton `manager` (`core/manager.py:115`) that every page imports.

- `names()` re-reads the registry from disk, so a device registered during a session appears in the dropdowns without a restart.
- `get_credentials(name)` returns everything recorded for one device, or `None`.
- `create_device(data)` validates that `Name` and `Path` are present and non-blank, rejects duplicates and missing source folders, `shutil.copytree`s the folder into `devices/{Name}/`, and merges the entry into `core/devices.json`. It **raises** (`ValueError`/`KeyError`/`FileNotFoundError`) with an operator-readable message; the previous version printed and returned, then had `create_device` called anyway with an incomplete dict.
- `_load()`/`_save()` treat a corrupt `devices.json` as empty rather than crashing the app, and `_save` merges over what is on disk so two open copies of the app don't drop each other's device.

## `pages/` — PyQt5 UI

### `pages/main_window.py` — **Simple**
`MainPage` (`pages/main_window.py:13`) builds the `QStackedWidget` and adds all four pages at fixed indices 0–3. See `WORKFLOW.md` §1.

### `pages/home_page.py` — **Simple**
Two buttons jump to `ADD_DEVICE_PAGE`/`PROGRAM_PAGE` (`pages/home_page.py:9-10`, named constants rather than bare integers). `on_page_changed` (`:53`), wired to `currentChanged`, calls `.refresh()` on whichever page just became visible — this is the mechanism keeping device dropdowns in sync across pages without an event bus. The invisible `devices_list` widget it used to populate (created but never added to a layout) is gone.

### `pages/add_device_page.py` — **Simple**
`AddDevice` (`pages/add_device_page.py:8`) renders a static "Example Device" reference block plus a dynamic list of key/value row widgets (`add_row`/`remove_row`). `on_submit` walks the rows, builds a dict, and hands it to `manager.create_device()`, reporting either outcome in a `QMessageBox` — necessary because a packaged windowed build has no console for a `print()` to land in. The write-only `device_dropdown` (never added to any layout, only ever contributing the string `"Select Device Type..."` as `data["type"]`) has been removed along with `device_types/`.

Still outstanding: the `QIcon("utilities\\trash.jpg")` path does not match the actual asset location, so the delete-row button icon renders blank.

### `pages/program_page.py` — **Complex**
The largest and most consequential page — see `WORKFLOW.md` §4 for the full data-flow diagram.

- `ProgramWorker(QThread)` (`:16`): does the `exec()` of `devices/{device}/prog_dev.py` and the `run_main_script(...)` call on a background thread, seeding the exec namespace with `{"progress_callback": self._emit_progress}`. Reports via `progress`/`finished_ok`/`failed` signals, and swallows `SystemExit` so a device script calling `sys.exit()` can't take the app down.
- `program_device()` (`:183`): validates the dropdowns, resets the Status panel, disables the Program button and starts the worker.
- `on_program_failed(tb_text)`: marks the in-flight row FAIL and writes the traceback to `sys.stderr` **from the GUI thread**, because `error_log_page`'s interceptor opens a modal dialog on stderr writes.
- `load_instructions()` reads `devices/{device}/instructions.txt`, building one `QCheckBox` per line; `update_button_state()` enables Program only when all are ticked.
- `load_checklist()` (`:239`) feeds `status_panel.set_steps()` from `devices/{device}/checklist.json`; a device without that file gets an empty panel.
- `refresh()` (`:318`) now calls `manager.names()` instead of opening and parsing `core/devices.json` inline.
- `on_submit()` (`:332`) parses a scanned QR string for a `PW:...;` segment to extract `temp_pass`, falling back to the raw scanned text.

### `pages/status_panel.py` — **Medium**
Renders the live milestone checklist to the right of the form. `load_checklist(device_dir)` reads `checklist.json` and returns `(steps, image_path)`, tolerating a missing or malformed file. `StepRow` is one line — icon, label with time estimate, right-aligned status — with `set_state`, `set_note` and `set_status_text` kept separate so a `WAIT` note and the running elapsed timer don't overwrite each other. `StatusPanel.update_step(step_id, state, detail)` maps the protocol states onto those rows: `RUNNING` starts a 1-second `QTimer` showing elapsed `m:ss`, `PASS`/`FAIL`/`SKIPPED` stop it, `SENT` briefly takes the status column, and `WAIT` puts the device's own wording under the label. Colours reuse the app palette (`#4CAF50` green, `#D32F2F` red).

### `pages/connection_page.py` — **Simple**
Static instructional page showing `router.jpg`, located through `app_paths.resource_path()` so it resolves inside a packaged bundle; "YES" jumps to index 2.

### `pages/error_log_page.py` — **Medium**
Installs itself globally the moment it's imported (`install_error_handler()` at module scope):

- `sys.excepthook`, `threading.excepthook`, and the asyncio loop's exception handler all route into `_collect_output(..., is_error=True)`.
- `sys.stdout`/`sys.stderr` are wrapped in `StreamInterceptor`, so **every** `print()` in the app is captured into `_output_buffer`, not just exceptions. All raw writes go through `_write_raw()`, which no-ops when the underlying stream is `None` or closed — required for packaged windowed builds (`console=False`), where all four stream objects are `None`. Without it the first `print()` raised `AttributeError` and killed the .exe before its window appeared.
- `subprocess.run` is monkey-patched to `safe_subprocess_run`, which forces `capture_output=True, text=True, check=True` on every call site in the process — this applies even to code that didn't ask for it.
- One `LogDialog` is shown on first error (`_error_popup_shown` prevents repeats) and again unconditionally at process exit via `atexit`.
- A fresh timestamped crash log path is computed once at import time and reused for the whole run — one file per app launch, not per error.

## `resources/utilities/` — the shared layer

Fully covered by `tests/` (83 tests). **Every file in both device folders builds on this layer.**

### `resources/utilities/excel_utils.py` — **Medium**
Header-name-based access to the airport spreadsheets. The design is driven by two properties of the real sheets:

- `get_header_map(sheet)` (`:65`) returns `{header_text: [1-based columns]}` — a *list*, because "Crash Report" legitimately appears twice (programming crash, then test crash). Raises `ValueError` on a blank header row rather than returning an empty map that turns every later lookup into a confusing `KeyError`.
- `find_column(header_map, name, occurrence=0)` (`:85`) matches case-insensitively and takes an occurrence index. Its `KeyError` names what *was* available.
- `require_columns` (`:110`) fails once listing every missing header, instead of one at a time.
- `find_row_by_value` (`:121`) compares as text, because the gate identifier arrives from a GUI dropdown as a string while the sheet stores it as a number.
- `lookup_excel(path, gate)` (`:135`) returns `{"gate_ip", "netmask", "gateway"}` and **raises** rather than returning blanks — `KeyError` for an absent gate, `ValueError` for missing headers or an address that doesn't sit inside its own netmask. That stops a run before any hardware is touched.
- `open_workbook` (`:41`) guarantees `close()`, and turns openpyxl's raw `BadZipFile: File is not a zip file` into a `ValueError` naming the file. `devices/TR/JKC-SLC.xlsx` is a real corrupt sheet in this repo; before this it could crash the Gate dropdown.
- `cell_text(value)` (`:177`) maps blanks *and* the literal text `"None"` to `""`, so neither can be printed onto a physical label.
- `get_excel_files`/`get_dropdown` (`:187`, `:199`) feed the Airport and Gate dropdowns; `get_dropdown` reads the serial column by header name and returns `[]` on any unreadable file.

### `resources/utilities/status.py` — **Medium**
Owns both ends of the hardware-script-to-GUI conversation.

- **Emitting** (`emit`, `running`, `passed`, `failed`, `skipped`, `sent`, `waiting`, `:44-77`) — what a hardware script calls. `digix20.py` aliases these to its own `step_*` names.
- **Parsing** — `parse(line)` (`:81`) returns `(step_id, state, detail)` or `None`, splitting at most twice so a detail message containing `|` survives.
- `forwarder(callback)` (`:97`) wraps the GUI callback so an exception while drawing a tick mark can never abandon a router mid-flash.
- `watch_process(command, report)` (`:127`) runs a hardware script and makes **one** pass over its stdout: forwarding markers, printing everything else, keeping a 200-line rolling buffer for the crash log, and watching for the `Incorrect` and `MAC Addr:` output conventions. Returns `{failed, detail, mac, log, returncode}`. The single pass is the fix for the bug described in `WORKFLOW.md` §4.

### `resources/utilities/reporting.py` — **Medium**
Everything a run leaves behind. `COLUMNS` (`:42`) maps a logical field name (`"mac"`, `"prg_count"`, `"test_crash_report"`) to a header name and occurrence, so device code never names a column number.

- `write_crash_log` (`:79`) saves the tail of a failed run under `crash_logs/` and returns the bare filename. Never raises — losing the log must not also lose the sheet update pointing at it.
- `write_label_file` (`:106`) writes the Brady printer's label, warning about (but tolerating) a missing PN or MAC.
- `record_result` (`:139`) is the main entry: stamps MAC, timestamp, crash-log hyperlink and `PRG #` on the gate's row, then writes the label unless the run failed. Returns the label filename or `None`, and never raises — the hardware is already programmed by this point, so a spreadsheet problem is reported and survived.
- `record_test_result` (`:221`) does the same for the functional-test columns.
- `column_for` (`:57`) returns `None` for an absent column rather than raising, because sheets in the field are at different template versions and a missing optional column must not abort a completed run.

Two conventions this module enforces: the "Router Programmed On" timestamp is **red on failure, black on success** (how an operator spots a gate needing redoing), and **a failed run writes no label** (a label for a router that did not program is worse than none, because somebody can stick it on).

### `resources/utilities/app_paths.py` — **Simple**
Answers "where are things" for both source and packaged runs. `app_root()` returns the repo root, or the folder holding the .exe when `sys.frozen` — it locates mutable data (`devices/`, `core/`, `logs/`). `bundle_root()` returns `sys._MEIPASS` when frozen and backs `resource_path()` for read-only assets. `script_command(script, *args)` returns `[main.exe, --run-script, script, ...]` when frozen and `[python.exe, script, ...]` otherwise, because a frozen `sys.executable` is the app rather than an interpreter.

### `resources/utilities/wait_utils.py` — **Medium**
Completion-driven replacements for fixed sleeps. `read_until(shell, patterns, timeout)` accumulates shell output, echoing it live, and returns as soon as any regex matches — raising `StepTimeout` rather than hanging. `wait_for_prompt`/`run_cli` build on it: `run_cli` sends a command and blocks until the CLI hands the prompt back, which is what guarantees a verification step cannot run before the operation it verifies has finished. `run_checked` uses `recv_exit_status()` for a real pass/fail on `exec_command`. `wait_for_port`/`wait_for_ssh` poll a reboot down-then-up, treating a successful login as the completion signal. `verify_remote_file` stats a transferred file and raises `RemoteFileMissing` if absent or short.

### `resources/utilities/ssh_session.py` — **Medium**
`SSHSession` lazily connects (`ensure_connected`), pools the connection and one SFTP client, and exposes `run()`/`upload()`/`invoke_shell()`. `ManagedShell` wraps a raw `invoke_shell()` channel as a context manager so it's always closed, converting `socket.timeout` into `SSHCommandTimeout`. Transport keepalives make a device that reboots mid-command detectable rather than leaving a reader waiting out its full timeout on a dead socket. Used by `devices/digiIX20/digix20.py` and, as of `e96074a`, by `devices/TR/prog_dev.py`.

### `resources/utilities/device_config.py` — **Simple**
`load_config(device_dir, filename, env_prefix)` layers `DEFAULTS` → JSON file → env vars, coercing timeouts to `int`. `digix20.py:48` calls it with `env_prefix="DIGIIX20_"`; `devices/TR/prog_dev.py:160` with `env_prefix="TR_"` — the TR call site is new, and is why `TR_*` variables now have an effect.

### `resources/utilities/network_utils.py` — **Simple**
`is_valid_ip` (`:10`) wraps `ipaddress.ip_address`. `validate_subnet(ip, netmask)` (`:19`) returns `(ok, network_cidr)` — returning the network, not just a bool, is what lets a caller say *which* subnet an address landed in. `prefix_length(netmask, default=24)` (`:35`) exists so device scripts stop assuming `/24`; the real sheets contain `255.255.255.128` gates where that assumption put the PC on the wrong subnet.

### `resources/utilities/mac_utils.py` — **Simple**
`extract_mac(text, interface=None)` searches for MACs near a named interface first (checking that line and the next two, since both `ifconfig` and `ip link` wrap output), trying labeled formats (`HWaddr`, `ether`, `link/ether`) before a bare regex fallback; returns `None` rather than raising.

### `resources/utilities/elevate.py` — **Simple**
`is_admin()` wraps `shell32.IsUserAnAdmin()`. `relaunch_as_admin()` calls `ShellExecuteW(..., "runas", ...)`, pinning `lpDirectory` to the app root because an elevated process would otherwise start in `C:\Windows\System32`. `ensure_admin()` no-ops when already elevated, otherwise relaunches and `os._exit(0)` (skipping `atexit`, so `error_log_page` doesn't pop a dialog on the way out). A `--elevated` flag on the relaunched copy prevents an infinite UAC loop.

### `resources/utilities/templating.py` — **Simple**
`refresh_working_copy(source, dest)` re-copies a template folder, ignoring subdirectories; `patch_file(path, old, new, occurrences=None)` substitutes a placeholder and **verifies by counting replacements**; `stage_template(...)` does both and returns the staged path. Raises `TemplateError` on anything unexpected.

Two details earn their keep. The placeholder is matched as a whole token, so replacing `10.28.18.2` cannot corrupt a `10.28.18.20` elsewhere in the file. And verification counts replacements rather than checking the new value appears afterwards — the latter is satisfied by a file that already contained that address from a previous run, so a substitution that silently failed still looked correct and the previous gate's configuration went onto this gate's router. Covered by `tests/test_templating.py`.

### `resources/utilities/fonts.py` — **Simple**
Two module-level `QFont` constants shared across pages.

## `devices/`

### `devices/__init__.py` — **Simple**
A docstring and nothing else. It used to scan the filesystem and `print()` at import time, which meant importing the package had observable console output and produced a device list frozen at startup. Discovery is now lazy, through `app_paths.registered_devices()` or `manager.names()`.

## `devices/digiIX20/`

### `devices/digiIX20/digix20.py` — **Complex**
The hardware automation script, run as a child process with `(gate_ip, netmask, gateway, default_pass)` as `sys.argv`. Configuration comes from `load_config(DEVICE_DIR, env_prefix="DIGIIX20_")` (`:48`); transport is `SSHSession`/`ManagedShell`; every wait uses `wait_utils`, so no verification runs before the operation it checks has completed. Structured as seven milestone functions dispatched from `main()` — `check_ip`, `firmware_update`, `first_reboot`, `configure`, `switch_static_ip`, `change_ip_address`, `testing` — each announcing itself through the `status` aliases at `:65-70`. Failures raise `StepError`; `main()` catches, emits `FAIL`, prints a traceback and returns a non-zero exit code, and a `finally` block restores the PC adapter to DHCP.

Notable behaviours worth preserving: `resume_index()` detects where the router actually is and skips milestones already completed, so a failed attempt no longer needs a factory reset before the next one; `pc_ip_on_gate_subnet()` derives the PC's address from the real netmask rather than swapping the last octet; and `pull_file_to_router` is the two-hop pattern — SFTP to the BeagleBone, verify size, have the router `scp` it, wait for the prompt, then check name and size.

### `devices/digiIX20/prog_dev.py` — **Simple**
104 lines, down from 353. `run_main_script(airport, gate, default_pass, device)` (`:32`) reads the gate's settings with `excel_utils.lookup_excel` (which raises on bad data, so there is nothing to re-check), runs the hardware script through `status.watch_process`, then hands the outcome to `reporting.write_crash_log` and `reporting.record_result`. It raises `DigiProgrammingError` on failure so the global error handler shows the operator a dialog. The `get_header_map`/`col`/`find_gate_row`/`update_sheet_and_label` functions it used to define locally now live in the shared layer.

### `devices/digiIX20/checklist.json` / `device_config.json` — **Simple**
`checklist.json` lists the milestone rows (`id`, `label`, `estimate`) the Status panel renders — including `scan` (the resume detection) and `label` (written by `prog_dev.py` after the hardware script exits). `device_config.json` externalises BBB and router addresses, credentials, the `eth2` LAN interface, firmware/config filenames and timeouts — all overridable with `DIGIIX20_*` environment variables.

Operator instructions live as numbered steps with reference photos in `devices/digiIX20/instructions/`.

## `tests/`

Nine files, 83 tests, run with `python -m pytest tests/` from the repo root (`pytest` is not in `requirements.txt` — see `SETUP.md` §4). All pass.

`test_templating.py` covers the staging helper, including the two failure modes that motivated it. `test_tr_config_manifest.py` guards the exact set of 82 config files TR pushes — it fails if the manifest ever grows to include the 12 files of per-unit device state in `og_configs/`, or if a new file appears there without a decision about whether it should ship.

`test_excel_utils.py` and `test_network_utils.py` previously failed to *collect*, because they imported functions that had never been written; `e96074a` implemented them, and the tests are what specified the API. `test_prog_dev_integration.py` loads `devices/TR/prog_dev.py` via `importlib.util.spec_from_file_location` (mirroring the real `exec()`-based loading — see `WORKFLOW.md` §4) and covers TR's `get_header_map`/`col` column resolution, `lookup_excel`'s flag-don't-raise behaviour, and that `ssh_run_shell` closes its channel.
