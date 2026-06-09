from device_types.base_device import Device
import os
import shutil

class DeviceManager:
    def __init__(self):
        # Dictionary to store device objects
        self.devices = {}
        # Dictionary to store device credentials securely in memory
        self.device_credentials = {}

    def create_device(self, name: str, device_obj, folder_path: str,
                      ip_address: str, username: str, password: str):
        """
        Create a device entry, copy its files, and store credentials.

        :param name: Unique device name
        :param device_obj: Device object instance
        :param folder_path: Path to source folder
        :param ip_address: Device IP address
        :param username: Login username
        :param password: Login password (stored in memory)
        """

        # Directory containing device modules
        current_dir = os.path.dirname(__file__)
        print(current_dir, flush=True)
        path = os.path.join(current_dir, "devices", folder_path)
        print(path, flush=True)

        # Validate inputs
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Device name must be a non-empty string.")
        if name in self.devices:
            raise KeyError(f"Device '{name}' already exists.")
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Source folder '{path}' does not exist.")

        # Save device object
        self.devices[name] = device_obj

        # Save credentials in memory (⚠ not persistent — for security)
        self.device_credentials[name] = {
            "ip": ip_address,
            "username": username,
            "password": password
        }

        # Create destination directory
        os.makedirs(name, exist_ok=True)

        # Copy files from source folder
        try:
            shutil.copytree(folder_path, name, dirs_exist_ok=True)
            print(f"Device '{name}' created successfully.")
        except FileNotFoundError as e:
            print(f"Error: {e}")
        except Exception as e:
            print(f"Unexpected error: {e}")

    def get_credentials(self, name: str):
        """Retrieve stored credentials for a device."""
        return self.device_credentials.get(name, None)