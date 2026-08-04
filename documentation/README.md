# Programming Workstation — Documentation

**Version:** 2.0 · **Branch:** `docs-and-simplify` · **Last commit:** `e96074a` — "Simplify onto a shared utility layer; delete dead abstractions" (2026-08-04)

*Doc style note: formal structure with easy-to-read explanations, Mermaid diagrams for workflow, and `file:line` citations (no inline code excerpts). Set by user preference when this folder was created.*

> **In a hurry, or not a programmer?** Read [`../cheat_sheet.md`](../cheat_sheet.md) instead — one page, plain language, no code.

## Overview

The Programming Workstation is a PyQt5 desktop app that walks a technician through provisioning field devices — a Teltonika RUTX08 router (`devices/TR/`) and a Digi IX20 router (`devices/digiIX20/`), both used in airport gate-control installations. The operator registers a device type, confirms hardware wiring, picks an airport/gate from an Excel sheet, and the app runs that device's programming script (firmware flash, config push, functional test), then writes a label file and updates the Excel log. Programming runs on a background thread, and a live Status panel shows each milestone turning green PASS or red FAIL as it completes.

## What changed in `e96074a`

The previous version of these docs described a codebase split in two: a well-tested shared utility layer that only the Digi used, and a Teltonika implementation that duplicated all of it badly. **That split is gone.** Both devices now sit on the same shared layer, and the layer itself is complete.

Three things are worth knowing before reading further:

1. **Spreadsheets are read by column *name*, never by position.** `resources/utilities/excel_utils.py` resolves every column through the header row. The old positional reads (`row[idx - 3]`, `column=7`) silently returned the wrong cell whenever a sheet's columns differed.
2. **The end-of-run bookkeeping is one module.** Crash log, spreadsheet stamp and label file all live in `resources/utilities/reporting.py`. Each device's `prog_dev.py` previously wrote that out longhand, four times over.
3. **`device_types/` no longer exists.** All four files in it were 100% commented out. Devices are folders, not classes — that has always been the real extension mechanism.

The measurable effect: `devices/TR/prog_dev.py` went from 943 to 361 lines, `devices/digiIX20/prog_dev.py` from 353 to 104, and the test suite from 44 passing / 6 failing / 2 uncollectable modules to **66 passing**.

## Where to start

- **Not a developer, or just want the gist?** → [`../cheat_sheet.md`](../cheat_sheet.md)
- **New machine, nothing installed yet?** → [`../SETUP.md`](../SETUP.md) — prerequisites, virtual environment, administrator rights, building the .exe, and a verification checklist.
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

**CODE_EXPLAIN.md** : Function-level walkthrough of every source file in the app (excluding `devices/TR/`, which has its own nested documentation folder), with a complexity rating per file. Opens with a section on what the `e96074a` simplification removed and why.
Keywords: `DeviceManager`, `ProgramWorker`, `StatusPanel`, `SSHSession`, `excel_utils`, `reporting`, `status`, `wait_utils`, error handling.
Questions answered:
1. What does each file in `core/`, `pages/`, `resources/utilities/`, and `devices/digiIX20/` actually do?
2. What lives in the shared utility layer, and which device uses which part of it?
3. Why is a spreadsheet column looked up by header name instead of by number?
4. What triggers the global error dialog, and where do crash logs get written?
5. How does a milestone travel from a hardware script to a row in the Status panel?

**INSTRUCTIONS.md** : Day-to-day usage for a developer or operator already set up — a first-run walkthrough, warnings, how to add a device type, and an FAQ. For first-time setup on a new machine, see `../SETUP.md` instead.
Keywords: running the app, pytest, Status panel, `checklist.json`, adding a device type, administrator rights.
Questions answered:
1. How do I run the app and the test suite?
2. What does a programming run look like from the operator's side?
3. How do I add a brand-new device type, with or without a live checklist?
4. What are the known footguns before I touch device automation code?
5. What is still worth fixing?

## Related documentation

- `../cheat_sheet.md` — one-page, plain-language summary of what the app is and how it is built. Written for someone who is not going to read any code.
- `../SETUP.md` — first-time setup on a device that has never run this before: prerequisites, environment creation, UAC/administrator behaviour, building and staging the packaged .exe.
- `../devices/TR/documentation/` — nested documentation folder for the Teltonika RUTX08 device implementation specifically.
- `../resources/documentation/DOCS.md` — the documentation style guide this folder's rules are based on.
