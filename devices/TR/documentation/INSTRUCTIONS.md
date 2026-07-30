# INSTRUCTIONS.md — TR Device

**Version:** 1.0 · **Last updated:** 2026-07-30

## Setup

No extra setup beyond the root `../../../documentation/INSTRUCTIONS.md` — this folder's scripts run as ordinary subprocesses of the main app using the same `venv/`. You do need, physically:
- A Teltonika RUTX08 (or compatible RutOS 0.7.22.3+ router).
- A BeagleBone Black reachable at `192.168.7.2` (hardcoded — see `CODE_EXPLAIN.md`), wired per `resources/images/router.jpg` (shown on the app's Connection page).
- The firmware binary already present at `devices/TR/RUTX_R_00.07.22.3_WEBUI.bin` and the 94-file `og_configs/`/`og_testfile/` templates intact.

## Tutorial: running one gate

1. From the main app, go to **Program Device**, pick `TR` as the device.
2. Pick the airport `.xlsx` for this deployment, then the gate number.
3. Scan the router's QR code (or type its temp password) and hit **Submit**.
4. Hit **Program Device**. Expect roughly 7–8 minutes total: config templating happens near-instantly, firmware install/boot is the bulk of the wait (~3.5 min install + ~1.5 min reboot, both are `time.sleep()` calls in `teltonika.py`, not polled waits).
5. Watch console output for `"Incorrect!"` lines — those are the script's own self-checks failing, and each one corresponds to a specific step in `WORKFLOW.md` §2.
6. After completion, check the airport `.xlsx`: the gate's row should have a MAC address, a black (not red) timestamp, and a new label file linked in. If the timestamp is red or a crash-log link appears, something failed — see `../debugging.md` for prior incidents with similar symptoms.

## Warnings

- **Config precedence docs (`../TR_DEVICE_DOCUMENTATION.md`) describe features this folder's scripts don't use.** `device_config.json`, `TR_*` env vars, `SSHSession`/`ManagedShell`, and `mac_utils.extract_mac` are all real, tested code in `resources/utilities/` — but `teltonika.py` and `prog_dev.py` hardcode everything directly and don't call into any of it. Don't debug a "config override isn't taking effect" issue by checking `device_config.json` — check the hardcoded constants in the script instead.
- **Excel columns are positional, not header-based**, in both `prog_dev.py`'s `lookup_excel` and its crash-log/label/MAC-writing code. Reordering columns in an airport template will silently corrupt writes rather than raising an error.
- **The crash-log/MAC/label-writing block in `run_main_script` may be dead code on a normal run** — see the pipe-exhaustion issue noted in `WORKFLOW.md` §4 / `CODE_EXPLAIN.md`. If the Excel log isn't updating the way you expect after a run that otherwise looked clean, this is the first thing to check, not a symptom of the device itself misbehaving.
- **`ssh_router_connect`'s fallback logic swallows connection errors silently** (bare `except:` at `devices/TR/teltonika.py:120-126`) — a router that fails to respond on both the temp and fallback IP will print "Errors in Authentication" and continue executing subsequent steps rather than aborting cleanly.
- The MAC regex/extraction logic in `teltonika.py` only understands the old `HWaddr`-style `ifconfig` output; a firmware update that changes busybox's `ifconfig` formatting (as `resources/utilities/mac_utils.py`'s docstring notes happened once already) will make MAC extraction silently return nothing.

## Future actions

- Wire `teltonika.py`/`prog_dev.py` up to `resources/utilities/device_config.py`, `ssh_session.py`, and `mac_utils.py` to eliminate the duplicated, less-robust logic — this is clearly the direction `../TR_DEVICE_DOCUMENTATION.md` was written to describe, it just hasn't landed in code yet.
- Investigate/fix the apparent double-read of `process.stdout` in `prog_dev.py:run_main_script` (`devices/TR/prog_dev.py:193-194` vs. `:204-205`).
- Move Excel column lookups to name-based (`get_header_map`/`find_column`, once `resources/utilities/excel_utils.py` actually implements them — see root `documentation/INSTRUCTIONS.md`'s "Known bugs" section) instead of hardcoded integers.
- Update `../TR_DEVICE_DOCUMENTATION.md`'s "94 files" vs. documented "82 files" `og_configs/` count, and its "Updated Imports (Sparse Branch)" section, which doesn't match current `teltonika.py`/`prog_dev.py` imports.

## FAQ

**Q: The router already has an IP other than the template default — what happens?**
A: `teltonika.py:194-201` checks for an address matching `10.\d+\.\d+\.123` via the BBB and exits immediately (`sys.exit(0)`) without programming if found, printing `"Router already programmed to IP:{addr}"`.

**Q: Where do I look for prior incident history on a weird failure?**
A: `../debugging.md` — a running hand-kept log of specific failure signatures (IP mismatches, firmware update prompts, ping failures) with the developer's hypotheses and outcomes.

**Q: Can I safely edit `og_configs/`?**
A: Yes, deliberately — it's the reusable template for every future gate. Never hand-edit `configs/` directly; it's overwritten from `og_configs/` at the start of every run (`devices/TR/teltonika.py:229-234`).

**Q: What does `oshkosh_log.xlsx` do?**
A: It's excluded from the airport dropdown (`resources/utilities/excel_utils.py:11`) and appears to function as a master deployment log across airports rather than a selectable gate sheet.
