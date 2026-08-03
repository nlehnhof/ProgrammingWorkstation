"""Registry of available device folders.

Scans `app_root()/devices` at import time rather than this package's own
directory, so a built exe reads the device folder sitting beside it. That is
what lets a new device be added by dropping in a folder -- no rebuild.
"""

from resources.utilities.app_paths import registered_devices as _scan

registered_devices = _scan()

__all__ = ["registered_devices"]

# Print results
print("Registered Devices:", registered_devices)
