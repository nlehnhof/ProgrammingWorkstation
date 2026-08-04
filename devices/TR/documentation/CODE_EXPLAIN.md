# CODE_EXPLAIN.md — TR Device

**Last commit:** `e96074a` (2026-08-04) — "Simplify onto a shared utility layer; delete dead abstractions"

## New in `e96074a`

`prog_dev.py` was rewritten onto the shared utility layer: **943 → 361 lines**, with three real bugs removed along the way (see below). `teltonika.py` was **not** touched and is still the pre-refactor code described here.

Read this as two files at two different stages. `prog_dev.py` is now the reference for what `teltonika.py` should become.

## `prog_dev.py` — **Medium** (361 lines)

The GUI-facing orchestration layer, `exec()`-loaded by `pages/program_page.py`. It looks the gate up, runs `teltonika.py` as a subprocess, runs the functional test, and records the outcome. It no longer defines its own copies of anything in `resources/utilities/`.

### Spreadsheet access

- `get_header_map(sheet)` (`:67`) and `col(header_map, key, occurrence=None)` (`:72`) resolve a column by **logical field name** — `"mac"`, `"programmed_on"`, `"prg_count"`, `"test_crash_report"`. The field-to-header mapping is `reporting.COLUMNS`; the hardcoded `column=7` / `column=8` / `column=12` integers scattered through the old file are gone. `occurrence` distinguishes the sheet's two `"Crash Report"` columns.
- `lookup_excel(sheet, gate, device)` (`:100`) keeps its 3-argument shape and its "set globals, flag `valid_ip`" behaviour, because that is what the GUI and `tests/test_prog_dev_integration.py` expect — but it delegates the actual read to `excel_utils.lookup_excel`, so the lookup is now header-based and validates the address against its own netmask. The old version read the three cells *immediately to the left* of the matched gate cell, which returned the wrong values in any sheet whose columns differed.
- `_resolve_sheet(sheet, device)` (`:86`) accepts either a full path or a bare filename, trying the working directory and `app_root()` in turn.

### Running the hardware

- `run_main_script(airport, gate, temp_pass, device)` (`:199`) is the entry point. It looks up the gate, refuses to continue if `valid_ip` is false, runs `teltonika.py` through `status.watch_process`, then calls `reporting.write_crash_log` and `reporting.record_result`. It raises on failure so the app's global error handler shows a dialog.

  > **Bug fixed here.** The old version looped over `process.stdout` **twice**. The first loop drained the pipe; the second — which held all the failure detection, MAC capture, crash logging and label generation — iterated an already-exhausted stream and did nothing. Every run recorded a success, with a black timestamp and no MAC. `status.watch_process` makes exactly one pass.

  > **Second bug fixed.** The old flow called `run_test_script` before that second loop, so the functional test ran even when programming had already failed, producing a confusing second failure. Testing now happens only after a successful program.

- `run_test_script(folder, device, airport, excel, gate)` (`:261`) drives the Modbus floodlight toggle from the BeagleBone: stage the script, upload it, give the BBB an address on the gate subnet, run it, and record the result via `reporting.record_test_result`. It collects failures into a list rather than returning early, so a run reports everything that went wrong rather than only the first thing. Its nested redefinitions of `ssh_bbb_connect`/`ssh_bbb_run` — which shadowed the module-level ones — are gone; there is one `bbb_session` (`:177`) built on `SSHSession`.
- `ssh_run_shell(session, command)` (`:133`) sends one command into an interactive shell and auto-answers a `"[sudo] password for"` prompt, which is how the BBB gets its temporary static IP. It now uses `ManagedShell` as a context manager.

  > **Third bug fixed.** The old version returned the live channel to a caller that never closed it, leaking a shell per invocation until the BeagleBone refused new sessions.

- `bbb_address_for(address)` (`:188`) picks the BBB's address on the gate subnet — `.123` by convention, `.100` when the gate itself owns `.123`. The prefix comes from `network_utils.prefix_length(gate_netmask)` rather than an assumed `/24`.
- `stage_test_script(folder, address)` (`:327`) copies `og_testfile/` to `testfile/` and rewrites `127.0.0.1` to this gate's address, verifying the substitution took.

### Configuration

- `load_device_config(folder)` (`:160`) calls `device_config.load_config(folder, env_prefix="TR_")`. **This call site is new.** `devices/TR/device_config.json` had existed since the config system was introduced, but nothing read it — the BBB address and password were hardcoded in three separate places in this file. `TR_*` environment variables now take effect for the orchestration and test layers.

## `teltonika.py` — **Complex** (569 lines, procedural top-level script) — *not yet migrated*

Almost no function decomposition beyond the SSH helpers at the top: the 9-step automation (see `WORKFLOW.md`) is a single linear sequence of module-level statements that runs immediately on execution. Always invoked as a subprocess (`teltonika.py <gate_ip> <netmask> <gateway> <temp_pass>`, `:19-23`), never imported.

- `ssh_bbb_connect`/`ssh_bbb_run`/`ssh_bbb_upload`/`ssh_bbb_close` (`:54,69,80,84`) and the router equivalents (`:96,149,160,164`) are the only functions. Each opens/uses/closes a fresh `paramiko.SSHClient` via module-level globals — no pooling, unlike `resources/utilities/ssh_session.py`.
- `ssh_router_connect(num, admin_num)` (`:96`) has two modes: `num="temp"` tries the factory IP/password first, falling back to the "new" IP/password on failure (nested bare `except:` at `:120-126`); any other value connects directly with the new admin credentials. This dual path is why reruns against a partially-configured router behave differently from a fresh one.
- Hardcoded values live directly in these functions: BBB at `192.168.7.2` / `raj` / `Jetway` (`:57-59`), router temp IP `192.168.1.1`, new IP `192.168.81.1`, new password `Jetway@dm1n` (`:46,99,122,129`), firmware filename (`:334`). These are what `device_config.json` should supply, as it now does one level up.
- MAC extraction (`:497-518`) only understands the single `"eth0" ... "HWaddr"` format; `resources/utilities/mac_utils.extract_mac` handles several and is not called here.
- The "already programmed" checks (`:194-201`, `:567-570`) use `r'\b10.\d{1,3}\.\d{1,3}.123\b'` (`:195`) — note the unescaped `.` before `123`, which matches more loosely than a real dotted-quad check. It is checking for the BBB's own `.123` convention, not validating the router's address.
- Waits are fixed `time.sleep()` calls (`~3.5 min` after `sysupgrade`, `~1.5 min` after reboot) rather than the completion-driven waits in `resources/utilities/wait_utils.py`.

### Migrating it

`devices/digiIX20/digix20.py` is the worked example. In order of value: replace the paramiko helpers with `SSHSession`/`ManagedShell`; replace the fixed sleeps with `wait_for_port`/`wait_for_ssh`/`run_cli`; read config through `load_config(DEVICE_DIR, env_prefix="TR_")`; swap the MAC parser for `mac_utils.extract_mac`; then add `status.running`/`passed`/`failed` calls and a `checklist.json` so TR gets the live Status panel too.

## `FloodLighToggle.py` — **Medium** (558 lines, third-party-derived)

A Modbus/TCP client (attributed to Andy Cranston / Cranston Innovation in its header, `:3`) adapted as the post-programming functional test. Both `teltonika.py` and `prog_dev.py`'s `stage_test_script` patch its hardcoded target IP (`127.0.0.1` → the gate's real IP) before copying it to the BeagleBone and running it there. Success is detected by string-matching `"Bytes in received"` in the BBB's output — there is no structured parsing of the Modbus response on the `prog_dev.py` side.

## Non-code assets

- `og_configs/` / `configs/` (94 files each) — see `WORKFLOW.md` §3 for the copy/patch/revert lifecycle. Never edit `og_configs/`.
- `og_testfile/` / `testfile/` — same pattern, for `FloodLighToggle.py`.
- `*.xlsx` — per-airport gate data. `oshkosh_log.xlsx` is excluded from the dropdown by `excel_utils.get_excel_files`, so it functions as a master log rather than a selectable airport. **`JKC-SLC.xlsx` is corrupt** — not a valid `.xlsx` at all. It is now skipped gracefully (the Gate dropdown comes back empty with a printed reason) instead of crashing, but the file needs replacing from a good copy.
- `labels/`, `router_labels/` — `router_labels/` is where `prog_dev.py` writes new label `.txt` files; a physical Brady label printer watches that folder and moves printed files into `labels/`.
- `history/` — abandoned prior implementations (`dashboard.py`, `prog_dev_old.py`, `tel2.py`, `old_configs/`) kept for reference only.
- `device_config.json` — **now read**, by `prog_dev.py:160`.
