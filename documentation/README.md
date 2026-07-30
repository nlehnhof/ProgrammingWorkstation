# Programming Workstation — Documentation

**Version:** 1.0 · **Branch:** `sparse` · **Last commit:** `2e84f6c` — "DOCS.md file" (2026-07-30)

*Doc style note: formal structure with easy-to-read explanations, Mermaid diagrams for workflow, and `file:line` citations (no inline code excerpts). Set by user preference when this folder was created.*

## Overview

The Programming Workstation is a PyQt5 desktop app that walks a technician through provisioning field devices — today, a Teltonika RUTX08 router used in airport gate-control installations, plus an early-stage Digi IX20 implementation. The operator registers a device type, confirms hardware wiring, picks an airport/gate from an Excel sheet, and the app runs that device's programming script (firmware flash, config push, functional test), then writes a label file and updates the Excel log.

**Important context for anyone reading these docs:** this repository is mid-refactor. A shared, tested utility layer (`resources/utilities/`) and a set of higher-level docs (`DOCUMENTATION_OVERVIEW.md`, `devices/TR/TR_DEVICE_DOCUMENTATION.md`) describe a target architecture — pooled SSH sessions, header-based Excel lookups, layered config precedence. The actual production script for the TR device (`devices/TR/teltonika.py`, `devices/TR/prog_dev.py`) has **not** been updated to use that layer yet: it still opens raw `paramiko` connections, hardcodes credentials, and reads Excel columns by position. This documentation set describes the code as it actually runs today, and calls out the gap explicitly where it matters — see `CODE_EXPLAIN.md`.

## Files in this folder

**WORKFLOW.md** : Traces page-to-page navigation, the device-programming call chain (including the `exec()`-based script loading), and the config-loading precedence — with Mermaid diagrams.
Keywords: stacked widget, navigation, `exec()`, subprocess, data flow, config precedence.
Questions answered:
1. How does the user move between pages, and what triggers each transition?
2. What actually happens, file by file, when "Program Device" is clicked?
3. Why does `devices/TR/prog_dev.py` run via `exec()` instead of a normal import?
4. How does device configuration get resolved (and which scripts actually use that resolution)?
5. Where do crash logs, labels, and Excel updates get written?

**CODE_EXPLAIN.md** : Function-level walkthrough of every source file in the app (excluding `devices/TR/`, which has its own nested documentation folder), with a complexity rating per file.
Keywords: `DeviceManager`, `SSHSession`, `ManagedShell`, `extract_mac`, error handling, `QStackedWidget`.
Questions answered:
1. What does each file in `core/`, `pages/`, `device_types/`, and `resources/utilities/` actually do?
2. Which of the "new" `resources/utilities/` functions are actually wired into the app, versus only covered by tests?
3. Where are the known bugs and copy-paste artifacts (stale header comments, hardcoded paths)?
4. What triggers the global error dialog and where do crash logs get written?
5. Is `device_types/` (the `Device` abstract base class) actually used?

**INSTRUCTIONS.md** : Setup and a first-run walkthrough for a developer or operator, with warnings and an FAQ.
Keywords: setup, venv, pytest, running the app, adding a device type.
Questions answered:
1. How do I get the app running locally?
2. How do I run the test suite, and why does it fail if I use the wrong Python?
3. How do I add a brand-new device type?
4. What are the known footguns before I touch device automation code?
5. What's left to do / known bugs worth fixing?

## Related documentation

- `devices/TR/documentation/` — nested documentation folder for the Teltonika RUTX08 device implementation specifically (it's substantial enough, and self-contained enough, to warrant its own set).
- `../DOCUMENTATION_OVERVIEW.md` and `../devices/TR/TR_DEVICE_DOCUMENTATION.md` — pre-existing docs describing the target/aspirational architecture. Useful for understanding *where the refactor is headed*, but not an accurate description of what currently runs.
- `../resources/documentation/DOCS.md` — the original documentation style guide this folder's rules are based on.
