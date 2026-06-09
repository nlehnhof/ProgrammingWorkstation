import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from device import AbstractProtocol

class DeviceManager:
    """Manages available devices and their creation."""

    def __init__(self):
        self.device_classes = {}

    def register_device(self, name: str, device_class):
        self.device_classes[name] = device_class

    def create_device(self, name: str, protocol: AbstractProtocol):
        if name not in self.device_classes:
            raise ValueError(f"Device '{name}' not registered.")
        os.makedirs(f"devices/{name}", exist_ok=False)
        return self.device_classes[name](protocol)
