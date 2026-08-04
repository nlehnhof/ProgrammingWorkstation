"""Reusable, pooled SSH connection with timeouts and leak-safe shell handling.

Replaces the old pattern (repeated in teltonika.py / prog_dev.py) of opening a
brand-new paramiko.SSHClient for every single command and never closing shell
channels returned by invoke_shell(). SSHSession keeps one connection alive
across calls (connection pooling), applies a timeout to every blocking
network call so an unresponsive router/BBB can't hang the app forever, and
wraps invoke_shell() so the returned channel is always closable via `with`.
"""

import socket

import paramiko

DEFAULT_TIMEOUT = 30
DEFAULT_KEEPALIVE = 15


class SSHCommandTimeout(TimeoutError):
    """Raised when a remote command does not respond within the timeout."""


class ManagedShell:
    """Wraps a paramiko Channel from invoke_shell() so it is never left open."""

    def __init__(self, channel, timeout=DEFAULT_TIMEOUT):
        self._channel = channel
        self._channel.settimeout(timeout)
        self._closed = False

    def send(self, data):
        if isinstance(data, str):
            data = data.encode()
        return self._channel.send(data)

    def recv(self, nbytes):
        try:
            return self._channel.recv(nbytes)
        except socket.timeout as exc:
            raise SSHCommandTimeout("Timed out waiting for shell output") from exc

    def eof(self):
        """True once the far end is gone -- e.g. the device rebooted.

        Without this a reader cannot tell "the peer hung up" from "nothing has
        arrived yet", and waits out its full timeout on a dead channel.
        """
        if self._closed or self._channel.closed or self._channel.eof_received:
            return True
        transport = self._channel.get_transport()
        return transport is None or not transport.is_active()

    def close(self):
        if not self._closed:
            self._channel.close()
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


class SSHSession:
    """A pooled SSH connection to a single host.

    Usage:
        with SSHSession(host, user, password) as session:
            session.run("some command")
            session.upload(local, remote)
            with session.invoke_shell() as shell:
                shell.send("cmd\\n")
                shell.recv(1000)
    """

    def __init__(self, host, username, password, port=22, timeout=DEFAULT_TIMEOUT,
                 keepalive=DEFAULT_KEEPALIVE):
        self.host = host
        self.username = username
        self.password = password
        self.port = port
        self.timeout = timeout
        self.keepalive = keepalive
        self._client = None
        self._sftp = None

    def is_connected(self):
        transport = self._client.get_transport() if self._client else None
        return transport is not None and transport.is_active()

    def ensure_connected(self):
        if not self.is_connected():
            self._disconnect()
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(
                self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=self.timeout,
            )
            # An embedded device that reboots mid-command just stops answering
            # -- no FIN, no channel EOF -- so the socket sits in ESTABLISHED and
            # a reader waits out its whole timeout on a peer that is gone.
            # Keepalives make the transport notice and go inactive.
            transport = client.get_transport()
            if transport is not None and self.keepalive:
                transport.set_keepalive(self.keepalive)
            self._client = client
        return self._client

    @property
    def sftp(self):
        client = self.ensure_connected()
        if self._sftp is None:
            self._sftp = client.open_sftp()
        return self._sftp

    def run(self, command, timeout=None):
        """Run a command and return (stdout_text, stderr_text).

        Raises SSHCommandTimeout instead of hanging forever if the remote
        side never responds.
        """
        client = self.ensure_connected()
        effective_timeout = timeout if timeout is not None else self.timeout
        stdin, stdout, stderr = client.exec_command(command, timeout=effective_timeout)
        try:
            output = stdout.read().decode(errors="replace")
            error = stderr.read().decode(errors="replace")
        except socket.timeout as exc:
            raise SSHCommandTimeout(
                f"Command timed out after {effective_timeout}s: {command}"
            ) from exc
        return output, error

    def upload(self, local_path, remote_path):
        self.sftp.put(local_path, remote_path)

    def invoke_shell(self, timeout=None):
        client = self.ensure_connected()
        channel = client.invoke_shell()
        return ManagedShell(channel, timeout=timeout if timeout is not None else self.timeout)

    def _disconnect(self):
        if self._sftp is not None:
            try:
                self._sftp.close()
            finally:
                self._sftp = None
        if self._client is not None:
            try:
                self._client.close()
            finally:
                self._client = None

    def close(self):
        self._disconnect()

    def __enter__(self):
        self.ensure_connected()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def connect_with_fallback(candidates, timeout=DEFAULT_TIMEOUT):
    """Try each (host, username, password) in `candidates`, in order.

    Returns the first SSHSession that connects successfully. Raises
    ConnectionError (chaining the last failure) if none do -- instead of
    silently leaving the caller with a half-open/unconnected client, which
    is what the old nested try/except in teltonika.py's ssh_router_connect
    did on a full failure.
    """
    last_error = None
    for host, username, password in candidates:
        session = SSHSession(host, username, password, timeout=timeout)
        try:
            session.ensure_connected()
            return session
        except Exception as exc:
            last_error = exc
    raise ConnectionError(f"Could not connect to any of {len(candidates)} candidate(s): {last_error}")
