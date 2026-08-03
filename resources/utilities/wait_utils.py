"""Completion-driven waits for device automation.

The old device scripts confirmed work with a fixed `time.sleep()` followed by a
single `recv()` -- so a `ls /tmp/` check could easily race the file transfer it
was supposed to verify. Everything here waits on an *observed event* instead:
a prompt coming back, a command's exit status, a listening port, a file that
actually exists at the expected size.

Reboots are the one case that has to be polled (nothing can be observed while
the box is down). The poll interval is a probe cadence, not a guess at how long
the reboot takes -- the decision to continue is still driven by the port
answering again.
"""

import re
import socket
import time

from resources.utilities.ssh_session import SSHSession, SSHCommandTimeout

# Digi Admin CLI prompts:  "admin@IX20-1234>"  /  "(config)>"  /  a bare ">"
DIGI_PROMPT = r"(?:^|\n)[^\r\n]*(?:>|#|\$)[ \t]*$"

DEFAULT_POLL_INTERVAL = 2


class StepTimeout(TimeoutError):
    """Raised when an expected marker never arrives within the timeout."""


class RemoteFileMissing(RuntimeError):
    """Raised when a file we just transferred is absent or the wrong size."""


def read_until(shell, patterns, timeout, echo=True, poll=0.2):
    """Read from `shell` until any regex in `patterns` matches, or timeout.

    Streams whatever arrives to stdout as it arrives, so the GUI/terminal keeps
    showing live output instead of one dump at the end.

    :param shell: a ManagedShell (or anything with .recv(int) -> bytes)
    :param patterns: iterable of regex strings; matched against everything
        received so far
    :returns: the full accumulated text
    :raises StepTimeout: if no pattern matched before `timeout` seconds
    """
    if isinstance(patterns, str):
        patterns = [patterns]
    compiled = [re.compile(p, re.MULTILINE) for p in patterns]

    deadline = time.monotonic() + timeout
    buffer = ""

    while True:
        try:
            chunk = shell.recv(4096)
        except SSHCommandTimeout:
            chunk = b""

        if chunk:
            text = chunk.decode(errors="replace") if isinstance(chunk, bytes) else chunk
            buffer += text
            if echo:
                print(text, end="", flush=True)

            for pattern in compiled:
                if pattern.search(buffer):
                    if echo and not buffer.endswith("\n"):
                        print(flush=True)
                    return buffer
        else:
            if time.monotonic() >= deadline:
                break
            time.sleep(poll)

        if time.monotonic() >= deadline:
            break

    raise StepTimeout(
        f"Timed out after {timeout}s waiting for {[p.pattern for p in compiled]}"
    )


def wait_for_prompt(shell, timeout=60, echo=True):
    """Wait for the device CLI to hand the prompt back -- i.e. the previous
    command has actually finished."""
    return read_until(shell, [DIGI_PROMPT], timeout=timeout, echo=echo)


def run_cli(shell, command, timeout=60, echo=True):
    """Send `command`, then block until the prompt returns.

    This is the gate that makes "don't verify until the previous command
    completed" true: nothing after this call runs until the device is idle.
    """
    shell.send(command + "\n")
    return wait_for_prompt(shell, timeout=timeout, echo=echo)


def run_checked(session, command, timeout=None, label=None, echo=True):
    """Run a command over exec_command and wait for its real exit status.

    `recv_exit_status()` blocks until the remote process exits, so the caller
    can never inspect results of a command that hasn't finished. Returns
    (stdout_text, stderr_text, exit_status).
    """
    client = session.ensure_connected()
    effective_timeout = timeout if timeout is not None else session.timeout
    stdin, stdout, stderr = client.exec_command(command, timeout=effective_timeout)
    try:
        output = stdout.read().decode(errors="replace")
        error = stderr.read().decode(errors="replace")
        status = stdout.channel.recv_exit_status()
    except socket.timeout as exc:
        raise SSHCommandTimeout(
            f"Command timed out after {effective_timeout}s: {command}"
        ) from exc

    if echo:
        if output.strip():
            print("Output:\n", output, flush=True)
        if error.strip():
            print("Errors:\n", error, flush=True)
    return output, error, status


def port_is_open(host, port=22, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_port(host, port=22, up=True, timeout=300, interval=DEFAULT_POLL_INTERVAL,
                  progress_every=30, label=None):
    """Poll `host:port` until it is reachable (`up=True`) or gone (`up=False`).

    Prints a countdown-style line every `progress_every` seconds so the
    operator still sees movement during a reboot.
    """
    what = label or f"{host}:{port}"
    deadline = time.monotonic() + timeout
    last_note = time.monotonic()

    while time.monotonic() < deadline:
        if port_is_open(host, port, timeout=min(interval, 3)) == up:
            return True
        now = time.monotonic()
        if now - last_note >= progress_every:
            remaining = int(deadline - now)
            state = "come up" if up else "go down"
            print(f"Waiting for {what} to {state}... ~{remaining}s left", flush=True)
            last_note = now
        time.sleep(interval)

    state = "come up" if up else "go down"
    raise StepTimeout(f"Timed out after {timeout}s waiting for {what} to {state}")


def wait_for_ssh(host, username, password, timeout=300, interval=DEFAULT_POLL_INTERVAL,
                 ssh_timeout=30, progress_every=30):
    """Poll until SSH authentication actually succeeds; return the SSHSession.

    A successful login is the only trustworthy "the device finished rebooting"
    signal -- the port can be listening before the CLI is ready.
    """
    deadline = time.monotonic() + timeout
    last_note = time.monotonic()
    last_error = None

    while time.monotonic() < deadline:
        session = SSHSession(host, username, password, timeout=ssh_timeout)
        try:
            session.ensure_connected()
            return session
        except Exception as exc:
            last_error = exc
            session.close()

        now = time.monotonic()
        if now - last_note >= progress_every:
            remaining = int(deadline - now)
            print(f"Waiting for SSH on {host}... ~{remaining}s left", flush=True)
            last_note = now
        time.sleep(interval)

    raise StepTimeout(f"Timed out after {timeout}s waiting for SSH on {host}: {last_error}")


def verify_remote_file(sftp, remote_path, expected_size=None):
    """Confirm a transferred file exists and (optionally) is the right size.

    sftp.put() only returns once the transfer is complete, so this runs
    strictly after the copy -- no sleep involved.
    """
    try:
        stat = sftp.stat(remote_path)
    except IOError as exc:
        raise RemoteFileMissing(f"{remote_path} not found after transfer") from exc

    if expected_size is not None and stat.st_size != expected_size:
        raise RemoteFileMissing(
            f"{remote_path} is {stat.st_size} bytes, expected {expected_size}"
        )
    return stat.st_size
