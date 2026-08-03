"""Tests for the completion-driven wait helpers.

These cover the behaviour that replaced the old `time.sleep()`-then-check
pattern: read_until must return as soon as the expected marker arrives (and
raise rather than hang if it never does), and verify_remote_file must reject a
transfer that is missing or short instead of assuming it worked.
"""

import io
import pytest

from resources.utilities.wait_utils import (
    RemoteFileMissing,
    StepTimeout,
    read_until,
    verify_remote_file,
)


class FakeShell:
    """Hands back queued chunks, then empty bytes forever."""

    def __init__(self, chunks):
        self._chunks = list(chunks)
        self.sent = []

    def send(self, data):
        self.sent.append(data)
        return len(data)

    def recv(self, nbytes):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


class FakeStat:
    def __init__(self, size):
        self.st_size = size


class FakeSFTP:
    def __init__(self, files):
        self._files = files

    def stat(self, path):
        if path not in self._files:
            raise IOError(f"No such file: {path}")
        return FakeStat(self._files[path])


def test_read_until_returns_on_match():
    shell = FakeShell([b"Installing...\n", b"Firmware update completed\n"])
    output = read_until(shell, [r"Firmware update completed"], timeout=5, echo=False)
    assert "Firmware update completed" in output


def test_read_until_accumulates_across_chunks():
    """A marker split across two reads still matches."""
    shell = FakeShell([b"Firmware update ", b"completed\n"])
    output = read_until(shell, [r"Firmware update completed"], timeout=5, echo=False)
    assert "Firmware update completed" in output


def test_read_until_matches_any_pattern():
    shell = FakeShell([b"scp: transfer failed\n"])
    output = read_until(shell, [r"completed", r"[Ff]ail"], timeout=5, echo=False)
    assert "failed" in output


def test_read_until_times_out_when_marker_never_arrives():
    shell = FakeShell([b"still working\n"])
    with pytest.raises(StepTimeout):
        read_until(shell, [r"never appears"], timeout=1, echo=False, poll=0.05)


def test_read_until_echoes_output(capsys):
    shell = FakeShell([b"hello prompt> "])
    read_until(shell, [r"prompt>"], timeout=5, echo=True)
    assert "hello prompt>" in capsys.readouterr().out


def test_verify_remote_file_accepts_matching_size():
    sftp = FakeSFTP({"/tmp/fw.bin": 1234})
    assert verify_remote_file(sftp, "/tmp/fw.bin", 1234) == 1234


def test_verify_remote_file_rejects_missing_file():
    sftp = FakeSFTP({})
    with pytest.raises(RemoteFileMissing):
        verify_remote_file(sftp, "/tmp/fw.bin", 1234)


def test_verify_remote_file_rejects_short_transfer():
    """A truncated copy must not be reported as a success."""
    sftp = FakeSFTP({"/tmp/fw.bin": 900})
    with pytest.raises(RemoteFileMissing):
        verify_remote_file(sftp, "/tmp/fw.bin", 1234)


def test_verify_remote_file_skips_size_check_when_unknown():
    sftp = FakeSFTP({"/tmp/fw.bin": 900})
    assert verify_remote_file(sftp, "/tmp/fw.bin") == 900
