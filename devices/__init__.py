from pathlib import Path

current_dir = Path(__file__).parent
registered_devices = [p.name for p in current_dir.iterdir() if p.is_dir() and p.name != "__pycache__"]

__all__ = ["registered_devices"]

# Print results
print("Registered Devices:", registered_devices)