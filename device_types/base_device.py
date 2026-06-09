from abc import ABC, abstractmethod
from typing import Any

class Device(ABC):
    """
    Abstract base class for all devices.
    Every device must implement connect, disconnect, upload, and run.
    """

    def __init__(self, name: str, **kwargs):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Device name must be a non-empty string.")
        self.name = name
        self.connected = False
        self.params = kwargs  # Store extra parameters for the device

    @abstractmethod
    def connect(self) -> Any:
        """Connect to the device."""
        pass

    @abstractmethod
    def disconnect(self) -> Any:
        """Disconnect from the device."""
        pass

    @abstractmethod
    def upload(self, file: str, path: str) -> Any:
        """Upload data to the device."""
        pass

    @abstractmethod
    def run(self, cmd: str) -> Any:
        """Run the program on the device."""
        pass

    def __repr__(self):
        return f"<{self.__class__.__name__} name='{self.name}' connected={self.connected} params={self.params}>"
