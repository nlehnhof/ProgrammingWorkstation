# Programming Workstation — where the documentation lives

**Branch:** `docs-and-simplify` · **Last commit:** `e96074a` (2026-08-04) — "Simplify onto a shared utility layer; delete dead abstractions"

## Start here

| If you want to… | Read |
| --- | --- |
| Understand what this is, in plain language | [`documentation/CHEAT_SHEET.md`](documentation/CHEAT_SHEET.md) |
| Set up a machine that has never run this | [`documentation/SETUP.md`](documentation/SETUP.md) |
| Use the app day to day | [`documentation/INSTRUCTIONS.md`](documentation/INSTRUCTIONS.md) |
| Understand how the files fit together | [`documentation/WORKFLOW.md`](documentation/WORKFLOW.md) |
| Understand what a specific file or function does | [`documentation/CODE_EXPLAIN.md`](documentation/CODE_EXPLAIN.md) |
| Work on the Teltonika device specifically | [`devices/TR/documentation/`](devices/TR/documentation/) |

## The one-paragraph version

A PyQt5 desktop app that walks a technician through provisioning field devices — currently a Teltonika RUTX08 (`devices/TR/`) and a Digi IX20 (`devices/digiIX20/`), both used in airport gate-control installations. The operator registers a device type, picks an airport and gate from an Excel sheet, confirms the cabling, and the app runs that device's programming script — firmware flash, config push, functional test. It then writes a printable label and stamps the result back into the spreadsheet. Programming runs on a background thread with a live PASS/FAIL checklist.

## Architecture in five lines

- **A device is a folder**, not a class. `devices/{NAME}/` holds everything that device needs; registering one copies the folder and records it in `core/devices.json`. There is no base class to subclass.
- **`pages/`** is the UI: a `QStackedWidget` with four pages, plus a global error handler that logs everything and pops one dialog per run.
- **`resources/utilities/`** is the shared, tested layer — spreadsheets, SSH, waits, config, and the run-reporting that produces labels and crash logs.
- **Each device's `prog_dev.py`** is orchestration only: look up the gate, run the hardware script as a subprocess, record what happened. Both are now thin (104 and 364 lines).
- **Each device's hardware script** (`digix20.py`, `teltonika.py`) is the part that actually talks to the router, and is the only place that should need to know anything about it. Both are now structured as milestone functions that report progress to the GUI checklist.

## Known limitations

Carried forward because they are still true:

- **Credentials are plaintext** in `core/devices.json` and each `device_config.json`. Deliberate and documented, not an oversight.
- **TR cannot resume a failed run.** `digix20.py` detects where the router currently is and restarts at the right milestone; `teltonika.py` only has a coarse "already programmed, skip everything" check, so a failure part-way through still means a factory reset. This is now the largest difference between the two devices.
- **`devices/TR/JKC-SLC.xlsx` is a corrupt file** and needs replacing from a good copy. It is skipped gracefully rather than crashing the app.

The full, current list is in [`documentation/INSTRUCTIONS.md`](documentation/INSTRUCTIONS.md#known-issues--future-actions).
