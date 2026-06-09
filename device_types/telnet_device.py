from .base_device import Device
import telnetlib

class TelnetDevice(Device):
    """Telnet implementation of the Device interface."""

    def __init__(self, hostname, username, password, port=23):
        self.hostname = hostname
        self.username = username
        self.password = password
        self.port = port
        self._tn = None

    def connect(self):
        try:
            self._tn = telnetlib.Telnet(self.hostname, self.port, timeout=10)
            self._tn.read_until(b"login: ")
            self._tn.write(self.username.encode('ascii') + b"\n")
            self._tn.read_until(b"Password: ")
            self._tn.write(self.password.encode('ascii') + b"\n")
            print(f"[Telnet] Connected to {self.hostname}")
        except Exception as e:
            raise ConnectionError(f"[Telnet] Connection failed: {e}")

    def run(self, cmd):
        if not self._tn:
            raise ConnectionError("[Telnet] Not connected.")
        self._tn.write(cmd.encode('ascii') + b"\n")
        output = self._tn.read_until(b"#", timeout=5).decode(errors="replace")
        return output.strip(), ""

    def disconnect(self):
        if self._tn:
            self._tn.write(b"exit\n")
            self._tn.close()
            self._tn = None
            print(f"[Telnet] Disconnected from {self.hostname}")
