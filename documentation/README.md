# Programming Workstation — Documentation

**Version:** 1.1 · **Branch:** `sparse` · **Last commit:** `95a372e` — "Update WORKFLOW.md and CODE_EXPLAIN.md for ccd15af" (2026-08-03 10:59)

*Doc style note: formal structure with easy-to-read explanations, Mermaid diagrams for workflow, and `file:line` citations (no inline code excerpts). Set by user preference when this folder was created.*

## Overview

The Programming Workstation is a PyQt5 desktop app that walks a technician through provisioning field devices — a Teltonika RUTX08 router (`devices/TR/`) and a Digi IX20 router (`devices/digiIX20/`), both used in airport gate-control installations. The operator registers a device type, confirms hardware wiring, picks an airport/gate from an Excel sheet, and the app runs that device's programming script (firmware flash, config push, functional test), then writes a label file and updates the Excel log. Programming runs on a background thread, and a live Status panel shows each milestone turning green PASS or red FAIL as it completes.

**Important context for anyone reading these docs:** the two device implementations are at different stages, and the difference matters constantly.

- **`devices/digiIX20/`** was rewritten in `ccd15af` onto the shared utility layer: pooled `SSHSession` connections, completion-driven waits (`wait_utils`), layered config precedence (`device_config.json` + `DIGIIX20_*` env vars), and header-based Excel lookups.
- **`devices/TR/`** has **not** been migrated. `teltonika.py` and `prog_dev.py` still open raw `paramiko` connections, wait on fixed `time.sleep()` calls, hardcode credentials, and read Excel columns by position. `devices/TR/device_config.json` exists but nothing reads it, so `TR_*` environment variables have no effect.

This documentation set describes the code as it actually runs today and flags that split wherever it is load-bearing. The Digi implementation is the reference for migrating TR.

## Where to start

- **New machine, nothing installed yet?** → `../SETUP.md` (repo root) — prerequisites, virtual environment, administrator rights, building the .exe, and a verification checklist.
- **Repo already runs, want to use it?** → `INSTRUCTIONS.md`
- **Want to understand how it fits together?** → `WORKFLOW.md`, then `CODE_EXPLAIN.md`

## Files in this folder

**WORKFLOW.md** : Traces application startup, page-to-page navigation, and the full device-programming call chain — the background worker thread, the `exec()`-based script loading, the `##STATUS##` milestone protocol, and config precedence. Also covers how the app locates its data when run from source versus as a packaged .exe.
Keywords: stacked widget, navigation, `QThread`, `exec()`, subprocess, `##STATUS##`, config precedence, `app_root`, packaging.
Questions answered:
1. How does the user move between pages, and what triggers each transition?
2. What actually happens, file by file, when "Program Device" is clicked?
3. Why does `prog_dev.py` run via `exec()` instead of a normal import, and what is in its namespace?
4. How do milestone updates get from the hardware script to the Status panel?
5. How does the app find `devices/` when it is packaged as an .exe?

**CODE_EXPLAIN.md** : Function-level walkthrough of every source file in the app (excluding `devices/TR/`, which has its own nested documentation folder), with a complexity rating per file. Opens with a "New in `ccd15af`" section explaining why each recently added module exists.
Keywords: `DeviceManager`, `ProgramWorker`, `StatusPanel`, `SSHSession`, `wait_utils`, `app_paths`, `elevate`, error handling.
Questions answered:
1. What does each file in `core/`, `pages/`, `device_types/`, `resources/utilities/`, and `devices/digiIX20/` actually do?
2. Which shared utilities are wired into which device, versus only covered by tests?
3. Where are the known bugs and copy-paste artifacts (stale header comments, mismatched asset paths)?
4. What triggers the global error dialog, and where do crash logs get written?
5. Is `device_types/` (the `Device` abstract base class) actually used?

**INSTRUCTIONS.md** : Day-to-day usage for a developer or operator already set up — a first-run walkthrough, warnings, how to add a device type, and an FAQ. For first-time setup on a new machine, see `../SETUP.md` instead.
Keywords: running the app, pytest, Status panel, `checklist.json`, adding a device type, administrator rights.
Questions answered:
1. How do I run the app and the test suite, and which test failures are expected?
2. What does a programming run look like from the operator's side?
3. How do I add a brand-new device type, with or without a live checklist?
4. What are the known footguns before I touch device automation code?
5. Why do `TR_*` environment variables do nothing?

## Related documentation

- `../SETUP.md` — first-time setup on a device that has never run this before: prerequisites, environment creation, UAC/administrator behaviour, building and staging the packaged .exe.
- `devices/TR/documentation/` — nested documentation folder for the Teltonika RUTX08 device implementation specifically (it's substantial enough, and self-contained enough, to warrant its own set). Note it predates `ccd15af` and does not describe the shared-utility migration, which TR has not undergone anyway.
- `../DOCUMENTATION_OVERVIEW.md` and `../devices/TR/TR_DEVICE_DOCUMENTATION.md` — pre-existing docs describing the target/aspirational architecture. Useful for understanding *where the refactor is headed*, but not an accurate description of what currently runs.
- `../resources/documentation/DOCS.md` — the documentation style guide this folder's rules are based on.
