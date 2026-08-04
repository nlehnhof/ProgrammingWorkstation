# Programming Workstation — repository map

This application consolidates the programming of the various field devices we ship. It lets an operator:

- add a device (with its configs, firmware, programs and data), and
- program and test that device.

For a plain-language explanation of *what the app does and why*, see [`../cheat_sheet.md`](../cheat_sheet.md).
For the detailed technical documentation set, see [`../documentation/`](../documentation/).

## Directory map

```
> build
    The automatic build for the .bat file that allows launch from the desktop.

> core
    Top-level modules for the application.
    > devices.json
        The device registry. The device name is the top-level key; a device's
        entry must contain "Name" and "Path", and may contain anything else
        (username, password, IP address, ...). Stored as plain text.
    > manager.py
        DeviceManager, the registry's only interface.
        > create_device(data)
            Called from the Add Device page. Validates that "Name" and "Path"
            are present, copies the folder at "Path" into devices/{Name}/, and
            writes the entry to devices.json. Raises with an operator-readable
            message on bad input; the page turns that into a dialog.
        > get_credentials(name)
            Everything recorded for one device, or None.
        > names()
            The registered device names, re-read from disk so a device added
            during a session appears without restarting.
        > manager = DeviceManager()
            One shared registry for the whole application.
    > main.spec
        The PyInstaller build recipe. Run `pyinstaller core/main.spec` from
        the repo root. See ../SETUP.md §6.
    > requirements.txt
        Packages and versions required to run the application.

> devices
    One folder per device the app can program. This is the whole extension
    mechanism -- adding a device means adding a folder, not writing a class.
    Each folder contains that device's firmware, configs, spreadsheets and:
    > prog_dev.py       the entry point the app calls (run_main_script)
    > <hardware>.py     the script that actually talks to the device
    > device_config.json  addresses, credentials, filenames, timeouts
    > checklist.json    milestone rows for the live Status panel (optional)
    > instructions.txt  cabling steps; these become the checkboxes that gate
                        the Program button
    Written to at runtime: crash_logs/, router_labels/, and the .xlsx sheets.

> logs
    One timestamped log file per application launch, holding every print
    statement and error. Written by pages/error_log_page.py.

> pages
    The application's UI.
    > main_window.py      the stacked widget; the high-level navigation class
    > home_page.py        welcome, and the two options: add device, program device
    > add_device_page.py  the form for registering a device
    > program_page.py     select device/airport/gate, scan the QR code, run.
                          Runs the device's prog_dev.py on a background thread
                          and shows a live PASS/FAIL checklist beside the form.
    > connection_page.py  shows the correct wiring of the device
    > error_log_page.py   collects all output into the log file and raises the
                          error pop-up. Installs itself on import.
    > status_panel.py     the live milestone checklist

> resources
    Supporting material for the application.
    > images        the wiring photo used by connection_page.py
    > documentation the rules for writing documentation in this repo
    > utilities     the shared layer every device builds on -- see below

> tests
    pytest suite for resources/utilities/ and the device orchestration layer.
    Run with `python -m pytest tests/` from the repo root.
```

## The shared layer (`resources/utilities/`)

Device code should reach for these rather than writing its own. They are the tested part of the codebase.

| Module | What it is for |
| --- | --- |
| `app_paths.py` | Where things are, from source *and* inside a packaged .exe |
| `excel_utils.py` | Reading the gate spreadsheets **by column name**, never by position |
| `reporting.py` | What a run leaves behind: crash log, spreadsheet stamp, label file |
| `status.py` | Milestones from a hardware script to the GUI checklist; running a child script |
| `ssh_session.py` | Pooled SSH connections that time out and always close |
| `wait_utils.py` | Waits driven by an observed event, never a fixed `sleep()` |
| `device_config.py` | Config precedence: defaults → `device_config.json` → env vars |
| `network_utils.py` | IP and subnet validation |
| `mac_utils.py` | MAC extraction that copes with several `ifconfig`/`ip link` formats |
| `elevate.py` | Relaunching elevated, for the steps that reconfigure this PC's network |
| `fonts.py` | Shared UI fonts |

## Where labels go

Each device writes its label `.txt` files to `devices/{device}/router_labels/`. The Brady printer watches that folder and prints on new files.
