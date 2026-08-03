"""Locate the app's folders whether it runs from source or as a built exe.

Two different roots matter:

* `app_root()` -- where the *mutable, extensible* data lives: `devices/`,
  `core/devices.json`, `logs/`. Running from source that's the repo root;
  frozen it's the folder holding the .exe. Deliberately NOT inside the
  PyInstaller bundle: adding a device has to be a matter of dropping a folder
  next to the exe, not rebuilding it. The device tree is also written to at
  runtime (Excel stamps, router_labels/, crash_logs/), and bundled data is
  read-only and discarded when the app exits.

* `bundle_root()` -- where read-only assets that ship with the app live
  (`resources/images/`). Frozen, PyInstaller unpacks these to `sys._MEIPASS`.
"""

import os
import sys

# main.py understands this flag and runs the given script instead of the GUI.
RUN_SCRIPT_FLAG = "--run-script"


def is_frozen():
    return getattr(sys, "frozen", False)


def app_root():
    """Folder containing devices/, core/ and logs/."""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def bundle_root():
    """Folder containing bundled read-only assets."""
    return getattr(sys, "_MEIPASS", app_root())


def resource_path(*parts):
    """Path to a read-only asset that ships with the app."""
    return os.path.join(bundle_root(), *parts)


def devices_root():
    return os.path.join(app_root(), "devices")


def device_dir(name):
    return os.path.join(devices_root(), name)


def registered_devices():
    """Device folder names, read fresh from disk so new devices show up."""
    root = devices_root()
    if not os.path.isdir(root):
        return []
    return sorted(
        name for name in os.listdir(root)
        if os.path.isdir(os.path.join(root, name))
        and not name.startswith((".", "__"))
    )


def script_command(script_path, *args):
    """Command line for running a device automation script as a child process.

    Frozen, `sys.executable` is the packaged app rather than a Python
    interpreter -- launching it directly would start a second copy of the GUI.
    The app re-invokes itself in script-runner mode instead (see main.py).
    """
    string_args = [str(a) for a in args]
    if is_frozen():
        return [sys.executable, RUN_SCRIPT_FLAG, script_path, *string_args]
    return [sys.executable, script_path, *string_args]
