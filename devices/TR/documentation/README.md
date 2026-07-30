# Teltonika RUTX08 (TR) Device — Documentation

**Version:** 1.0 · **Branch:** `sparse` · **Last commit:** `2e84f6c` — "DOCS.md file" (2026-07-30)

*Doc style: formal structure, easy-to-read explanations, Mermaid diagrams, `file:line` citations only — same preferences recorded in `../../../documentation/README.md`.*

## Overview

This folder documents `devices/TR/` in isolation: the Teltonika RUTX08 router provisioning implementation, which is substantial and self-contained enough to warrant its own documentation set separate from the rest of the app (see `../../../documentation/` for the app shell around it).

**Read this first if you're debugging a TR provisioning run**, since it explains the actual current behavior of `teltonika.py` and `prog_dev.py` — which is meaningfully different from what `../TR_DEVICE_DOCUMENTATION.md` (the pre-existing, more aspirational doc in this folder) describes. That file documents a planned refactor onto `resources/utilities/` (pooled SSH, header-based Excel, layered config); the scripts in this folder still use the original, self-contained implementation. This documentation set describes what's actually running.

## Files in this folder

**WORKFLOW.md** : Diagrams the two-process pipeline (`prog_dev.py` orchestrating a `teltonika.py` subprocess) and the config-file copy/patch/revert cycle.
Keywords: subprocess, SSH, sysupgrade, Excel logging, label generation, crash logs.
Questions answered:
1. What are the 9 steps `teltonika.py` actually performs, in order?
2. How does `prog_dev.py` decide whether a run succeeded or failed?
3. What gets written back to the airport Excel file, and in which columns?
4. What's the relationship between `og_configs/`/`configs/` and `og_testfile/`/`testfile/`?
5. How does the router's IP get reverted after a successful run?

**CODE_EXPLAIN.md** : Function-level walkthrough of `teltonika.py`, `prog_dev.py`, and `FloodLighToggle.py`.
Keywords: `ssh_router_connect`, `run_main_script`, `run_test_script`, `lookup_excel`, Modbus/TCP.
Questions answered:
1. What does each function in `teltonika.py` do, and in what order do they run?
2. What does `prog_dev.py`'s `run_main_script` vs. `run_test_script` each handle?
3. How is the router's MAC address extracted, and how reliable is it?
4. What does the Modbus toggle test actually verify?
5. Where do the hardcoded IPs/passwords live, and what are they?

**INSTRUCTIONS.md** : Operator + developer instructions specific to running a TR provisioning cycle.
Keywords: firmware, BeagleBone Black, wiring, gate IP, subnet.
Questions answered:
1. What hardware needs to be connected, and how, before starting?
2. What do I do if the router doesn't have a factory-default state?
3. How do I read `debugging.md` for prior incident history?
4. What are the timing expectations for a normal run?
5. What breaks if the firmware version changes?

## Related documentation

- `../TR_DEVICE_DOCUMENTATION.md` — the pre-existing doc describing the target/refactored architecture (config precedence, `SSHSession`, `mac_utils`). Useful for design intent, not accurate for current runtime behavior.
- `../debugging.md` — a running incident log the previous developer kept by hand; still useful for recognizing recurring failure signatures.
- `../../../documentation/` — the app-wide documentation folder (pages, `core/manager.py`, shared utilities).
