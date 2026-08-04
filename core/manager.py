"""The registry of device types the app knows how to program.

A "device" here is a *folder*, not a class. Registering one copies a source
folder into `devices/{Name}/` and records its details in `core/devices.json`;
from then on the Program page lists it and runs the `prog_dev.py` it contains.
That is the whole extension mechanism -- there is no base class to subclass and
no code change needed to add a device.

Known limitation, deliberate and documented rather than accidental: whatever
extra keys an operator enters (passwords included) are stored as plain text in
`devices.json`.
"""

import json
import os
import shutil

from resources.utilities.app_paths import app_root, device_dir

# Beside this file, so it is found whether the app runs from source or as the
# packaged exe -- and so it sits next to the devices/ tree it describes.
DEVICES_JSON = os.path.join(app_root(), "core", "devices.json")

REQUIRED_KEYS = ("Name", "Path")


class DeviceManager:
    def __init__(self, json_path=DEVICES_JSON):
        self.json_path = json_path
        self.devices = self._load()

    # -- registry -----------------------------------------------------------

    def _load(self):
        """Read the registry, treating an unreadable file as an empty one.

        A corrupt devices.json must not stop the app from starting: the
        operator can still re-register a device, which rewrites the file.
        """
        if not os.path.exists(self.json_path):
            return {}
        try:
            with open(self.json_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"Could not read {self.json_path}: {exc}", flush=True)
            return {}

        if not isinstance(data, dict):
            print(f"{self.json_path} is not a JSON object; ignoring it.", flush=True)
            return {}
        return data

    def _save(self):
        """Write the registry back, merging over whatever is on disk.

        Merging rather than overwriting matters when two copies of the app are
        open: the one that saves second would otherwise drop the other's device.
        """
        on_disk = self._load()
        on_disk.update(self.devices)
        self.devices = on_disk

        try:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as handle:
                json.dump(on_disk, handle, indent=4)
        except OSError as exc:
            print(f"Could not write {self.json_path}: {exc}", flush=True)

    # -- public API ---------------------------------------------------------

    def names(self):
        """Registered device names, refreshed from disk."""
        self.devices = self._load()
        return sorted(self.devices)

    def get_credentials(self, name):
        """Everything recorded for one device, or None if it isn't registered."""
        return self._load().get(name)

    def create_device(self, data):
        """Register a device and copy its folder into `devices/{Name}/`.

        `data` needs at least "Name" and "Path"; any other keys are stored
        alongside them. Raises ValueError / FileNotFoundError / KeyError with a
        message meant for the operator, rather than reporting failure by
        printing and returning.
        """
        missing = [key for key in REQUIRED_KEYS if not str(data.get(key, "")).strip()]
        if missing:
            raise ValueError(
                f"A device needs both 'Name' and 'Path'. Missing: {', '.join(missing)}."
            )

        name = str(data["Name"]).strip()
        source = str(data["Path"]).strip()

        if name in self._load():
            raise KeyError(f"A device called '{name}' is already registered.")
        if not os.path.isdir(source):
            raise FileNotFoundError(f"Source folder does not exist: {source}")

        destination = device_dir(name)
        shutil.copytree(source, destination, dirs_exist_ok=True)
        print(f"Copied {source} -> {destination}", flush=True)

        self.devices[name] = {key: value for key, value in data.items() if key != "Name"}
        self.devices[name]["Name"] = name
        self._save()
        return destination


# One shared instance: the pages all read the same registry.
manager = DeviceManager()
