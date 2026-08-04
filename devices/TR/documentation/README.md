# Teltonika RUTX08 (TR) Device — Documentation

**Version:** 3.0 · **Branch:** `docs-and-simplify` · **Last commit:** `HEAD` — "Migrate teltonika.py onto the shared layer" (2026-08-04)

*Doc style: formal structure, easy-to-read explanations, Mermaid diagrams, `file:line` citations only — same preferences recorded in `../../../documentation/README.md`.*

## Overview

This folder documents `devices/TR/` in isolation: the Teltonika RUTX08 router provisioning implementation, which is substantial and self-contained enough to warrant its own documentation set separate from the rest of the app (see `../../../documentation/` for the app shell around it).

**Read this first if you're debugging a TR provisioning run.** It describes what actually runs today.

**Both files now sit on the shared utility layer.** `prog_dev.py` was migrated first (943 → 364 lines, taking three real bugs with it); `teltonika.py` followed, becoming seven dispatched milestones with pooled `SSHSession` connections, completion-driven waits, and configuration read from `device_config.json`.

Two consequences worth knowing up front:

- **TR has a live Status checklist now.** Nine milestones, the same panel the Digi has had.
- **`TR_*` environment variables work everywhere.** Nothing is hardcoded in either script.

The one thing to be careful about: `config_manifest.json` lists the **82** files pushed to the router, deliberately not all 94 in `og_configs/`. The 12 it omits are per-unit device state. See `CODE_EXPLAIN.md`.

## Files in this folder

**WORKFLOW.md** : Diagrams the two-process pipeline (`prog_dev.py` orchestrating a `teltonika.py` subprocess) and the config-file copy/patch/revert cycle.
Keywords: subprocess, SSH, sysupgrade, Excel logging, label generation, crash logs.
Questions answered:
1. What are the 9 steps `teltonika.py` actually performs, in order?
2. How does `prog_dev.py` decide whether a run succeeded or failed?
3. What gets written back to the airport Excel file, and how is the cell chosen?
4. What's the relationship between `og_configs/`/`configs/` and `og_testfile/`/`testfile/`?
5. How does the router's IP get reverted after a successful run?

**CODE_EXPLAIN.md** : Function-level walkthrough of `teltonika.py`, `prog_dev.py`, and `FloodLighToggle.py`.
Keywords: `ssh_router_connect`, `run_main_script`, `run_test_script`, `lookup_excel`, Modbus/TCP.
Questions answered:
1. What does each function in `teltonika.py` do, and in what order do they run?
2. What does `prog_dev.py`'s `run_main_script` vs. `run_test_script` each handle?
3. How is the router's MAC address extracted, and how reliable is it?
4. What does the Modbus toggle test actually verify?
5. Which hardcoded IPs/passwords remain, and where?

**INSTRUCTIONS.md** : Operator + developer instructions specific to running a TR provisioning cycle.
Keywords: firmware, BeagleBone Black, wiring, gate IP, subnet.
Questions answered:
1. What hardware needs to be connected, and how, before starting?
2. What do I do if the router doesn't have a factory-default state?
3. How do I read `debugging.md` for prior incident history?
4. What are the timing expectations for a normal run?
5. What breaks if the firmware version changes?

## Related documentation

- `../TR_DEVICE_DOCUMENTATION.md` — the older, longer reference for this device. It describes the target architecture (config precedence, `SSHSession`, `mac_utils`), which `prog_dev.py` has now reached and `teltonika.py` has not. Useful for design intent and for the hardware/wiring background.
- `../debugging.md` — a running incident log the previous developer kept by hand; still useful for recognizing recurring failure signatures.
- `../../../documentation/` — the app-wide documentation folder (pages, `core/manager.py`, shared utilities).
