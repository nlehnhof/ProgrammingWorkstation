"""Per-device folders -- one directory per device type the app can program.

Each subfolder holds everything that device needs: `prog_dev.py` (the entry
point the app calls), its hardware script, `device_config.json`, `checklist.json`,
`instructions.txt` and the airport spreadsheets.

Nothing is imported from here. Device folders are discovered on disk at the
moment they are needed -- see `resources.utilities.app_paths.registered_devices`
and `core.manager.DeviceManager.names`. Scanning lazily rather than at import
time is what lets a device be added to a running, packaged build by dropping a
folder next to the .exe.
"""
