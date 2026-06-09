from device_types.base_device import Device
import os
import shutil
from device_types import *
import sys
import inspect
from utilities.network_utils import is_valid_ip

import subprocess
import paramiko
import socket
import select
import argparse
from collections import deque
from datetime import datetime
import time

import json
from typing import Dict, Any


class DeviceManager:
    def __init__(self, json_path: str = "devices.json"):
        # Dictionary to store device objects
        self.json_path = json_path
        self.devices = {}
        self._load_devices()
        
    def create_device(self, data: Dict):
        """
        Create a device entry, copy its files, and store credentials.

        :param name: Unique device name
        :param device_obj: Device object instance
        :param folder_path: Path to source folder
        :param ip_address: Device IP address
        :param username: Login username
        :param password: Login password (stored in memory)
        :param etc: etc
        """
        try: 
            name = data["Name"]
            dpath = data["Path"]
            dtype = data["type"]
        except:
            return print("To Add a Device, the Device must have a name, a path, and a type.")

        # Directory containing device modules
        current_dir = os.path.dirname(__file__)
        print(current_dir, flush=True)
        path = os.path.join(current_dir, dpath)
        print(path, flush=True)
        time.sleep(2)

        # Validate inputs
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Device name must be a non-empty string.")
        if name in self.devices:
            raise KeyError(f"Device '{name}' already exists.")
        if not os.path.isdir(path):
            raise FileNotFoundError(f"Source folder '{path}' does not exist.")

        # Save credentials in memory (⚠ not persistent — for security)
        name = data["Name"]
        # Create a nested dictionary for this device
        self.device_credentials[name] = {
            key: value
            for key, value in data.items()
            if key != "Name"
        }
        self._save_devices()

        destination = os.path.join(current_dir, "devices", name)
        # Create destination directory
        dest = shutil.copytree(path, destination, dirs_exist_ok=True)

    def get_credentials(self, name: str):
        """Retrieve stored credentials for a device from a JSON file."""
        if not os.path.exists(self.json_path):
            # No credentials file found
            return None

        try:
            with open(self.json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Ensure the JSON is a dictionary
            if not isinstance(data, dict):
                raise ValueError("Invalid credentials file format.")

            return data.get(name, None)

        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error reading credentials file: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def _load_devices(self):
        """Load devices from Json file if it exists"""
        if os.path.exists(self.json_path):
            try:
                with open(self.json_path, "r", encoding="utf-8") as f:
                    self.device_credentials = json.load(f)
                if not isinstance(self.device_credentials, dict):
                    raise ValueError("Invalid JSON structure: Expected a Dict")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error reading {self.json_path}: {e}")
                self.device_credentials = {}
        else:
            self.device_credentials = {}

    def _save_devices(self):
        """Append new device credentials to JSON file without overwriting existing ones."""
        try:
            # Load existing credentials if file exists
            if os.path.exists(self.json_path):
                try:
                    with open(self.json_path, "r", encoding="utf-8") as f:
                        existing_data = json.load(f)
                    if not isinstance(existing_data, dict):
                        print(f"Warning: {self.json_path} contains invalid format. Resetting.")
                        existing_data = {}
                except (json.JSONDecodeError, OSError) as e:
                    print(f"Error reading {self.json_path}: {e}")
                    existing_data = {}
            else:
                existing_data = {}

            # Merge new credentials (overwrites keys if they already exist)
            existing_data.update(self.device_credentials)

            # Save merged data
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(existing_data, f, indent=4)

        except OSError as e:
            print(f"Error writing to {self.json_path}: {e}")

manager = DeviceManager()