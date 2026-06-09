import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import serial
from device import AbstractDevice, AbstractProtocol
import paramiko
import time

class SerialProtocol(AbstractProtocol):
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None

    def open(self):
        self.ser = serial.Serial(self.port, self.baudrate, timeout=1)

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()

    def send(self, data: bytes):
        if self.ser:
            self.ser.write(data)

    def receive(self, size: int) -> bytes:
        if self.ser:
            return self.ser.read(size)
        return b''


class SSHDevice(AbstractDevice):
    def __init__(self, name: str, pause: float = 0.5):
        self.name = name
        self.pause = pause
        self.ssh_client = None
        self.sftp_client = None

    def connect(self, ipaddr: str, user: str, pswd: str):
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(ipaddr, username=user, password=pswd)
        self.sftp_client = self.ssh_client.open_sftp()
        time.sleep(self.pause)
        print(f"Connected to {self.name}", flush=True)

    def disconnect(self):
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()
        time.sleep(self.pause)
        print(f"Closed connection to {self.name}", flush=True)

    def upload(self, file: str, dev_file: str):
        if not self.sftp_client:
            raise ConnectionError("SFTP connection not established.")
        self.sftp_client.put(file, dev_file)
        print(f"Uploaded {file} to {self.name}")

    def get_device_info(self) -> dict:
        if not self.ssh_client:
            raise ConnectionError("SSH connection not established.")
        stdin, stdout, stderr = self.ssh_client.exec_command("uname -a")
        info = stdout.read().decode().strip()
        return {"device_name": self.name, "system_info": info}
