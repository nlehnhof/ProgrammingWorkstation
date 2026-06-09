from abc import ABC, abstractmethod
import sys
import shutil
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from abc import ABC, abstractmethod

class AbstractDevice(ABC):
    """Abstract base class for all hardware devices."""

    @abstractmethod
    def connect(self, ipaddr, user, pswd):
        """Establish connection to the device."""
        pass

    @abstractmethod
    def disconnect(self):
        """Close connection to the device."""
        pass

    @abstractmethod
    def upload(self, file: str, dev_file: str):
        """Upload a file to the device."""
        pass

    @abstractmethod
    def get_device_info(self) -> dict:
        """Return device metadata."""
        pass

    @abstractmethod
    def run(self):
        """Run a command on device"""
        pass


class AbstractProtocol(ABC):
    """Abstract base class for communication protocols."""

    @abstractmethod
    def open(self):
        pass

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def send(self, data: bytes):
        pass

    @abstractmethod
    def receive(self, size: int) -> bytes:
        pass
