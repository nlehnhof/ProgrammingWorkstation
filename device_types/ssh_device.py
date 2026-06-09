from .base_device import Device
import paramiko
import time
import os
from typing import Any

class SSHDevice(Device):
    """SSH implementation of the Device interface."""

    def __init__(self, hostname, username, password, port=22):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self._ssh_client = None
        self._sftp_client = None

    def connect(self):
        print(f"Connecting to {self.name}", flush=True)
        try:
            self._ssh_client = paramiko.SSHClient()
            self._ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self._ssh_client.connect(
                hostname=self.hostname,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=10
            )
            print(f"[SSH] Connected to {self.hostname}")
            self._sftp_client = self._ssh_client.open_sftp()
            time.sleep(2)
        except paramiko.SSHException as e:
            raise ConnectionError(f"[SSH] Connection failed: {e}")

    def upload(self, file, path):
        if not self._sftp_client:
            raise ConnectionError("[SSH] Not connected")
        self._sftp_client.put(file, path)

    def run(self, cmd):
        if not self._ssh_client:
            raise ConnectionError("[SSH] Not connected.")
        stdin, stdout, stderr = self._ssh_client.exec_command(cmd)
        output = stdout.read().decode(errors="replace").strip()
        error = stderr.read().decode(errors="replace").strip()
        return output, error

    def disconnect(self):
        if self._ssh_client:
            self._ssh_client.close()
            self._ssh_client = None
            print(f"[SSH] Disconnected from {self.hostname}")

