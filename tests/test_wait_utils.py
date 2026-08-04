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
    ShellClosed,
    StepTimeout,
    read_until,
    verify_remote_file,
    wait_for_prompt,
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


def test_wait_for_prompt_returns_on_admin_cli_prompt():
    shell = FakeShell([b"config saved\r\n", b"admin@IX20-1234> "])
    assert "admin@IX20-1234>" in wait_for_prompt(shell, timeout=5, echo=False)


def test_wait_for_prompt_ignores_angle_bracket_mid_output():
    """A ">" inside command output is not the prompt coming back.

    This is the firmware-copy race: an unanchored prompt pattern would return
    while the 36 MB scp is still running, and the ls check that follows would
    then race the transfer it exists to verify.
    """
    shell = FakeShell([b"scp: /tmp/fw.bin -> local, 40% done\r\n"])
    with pytest.raises(StepTimeout):
        wait_for_prompt(shell, timeout=1, echo=False)


def test_wait_for_prompt_does_not_match_access_menu():
    """The Digi access menu ends in ":" -- it is not a prompt."""
    shell = FakeShell([b"Select access or quit [a/s/q]: "])
    with pytest.raises(StepTimeout):
        wait_for_prompt(shell, timeout=1, echo=False)


def test_wait_for_prompt_matches_real_admin_cli_banner():
    """Replays the bytes the IX20 sends after "a" at the access menu.

    The prompt is wrapped in cursor control -- "\\x1b[0K>\\x1b[2C" -- so the
    caret is followed by an escape sequence, not end-of-buffer. Matching the
    raw stream timed out for 60s on a prompt that was plainly on screen.
    """
    banner = (
        b"Connecting now...\r\n Press Tab to autocomplete commands\r\n"
        b" Type 'exit' to disconnect from the Admin CLI\r\n\x1b[0K>\x1b[2C"
    )
    assert wait_for_prompt(FakeShell([banner]), timeout=5, echo=False).endswith(">")


def test_read_until_strips_escapes_from_returned_text():
    """Callers parse this output, so escapes must not reach them."""
    shell = FakeShell([b"\x1b[0K-rw-r-----  1 root root  36361400 IX20-firmware.bin\x1b[2C>"])
    assert "\x1b" not in read_until(shell, [r">"], timeout=5, echo=False)


def test_read_until_matches_escape_split_across_chunks():
    """A sequence broken over two recv() calls must still be stripped."""
    shell = FakeShell([b"done\r\n\x1b[0K>\x1b[", b"2C"])
    assert wait_for_prompt(shell, timeout=5, echo=False).endswith(">")


def test_wait_for_prompt_matches_prompt_split_across_chunks():
    shell = FakeShell([b"done\r\nadmin@IX20", b"-1234> "])
    assert "admin@IX20-1234>" in wait_for_prompt(shell, timeout=5, echo=False)


def test_read_until_password_prompt_ignores_the_bbb_login_banner():
    """Anchored prompt patterns must not fire on the BeagleBone's MOTD.

    The router's scp prints the BBB's login banner before its own password
    prompt, and that banner says "default username:password is [debian:temppwd]".
    An unanchored "[Pp]assword:?" matched it, so the password was sent into the
    banner, the real prompt went unanswered, and the session hung until the
    router's idle timeout closed it.
    """
    shell = FakeShell([
        b"Debian GNU/Linux 11\r\n",
        b"default username:password is [debian:temppwd]\r\n",
        b"raj@192.168.2.183's password: ",
    ])
    output = read_until(
        shell,
        [r"[Pp]assword:[ \t]*\Z", r"[Pp]assphrase[^:\r\n]*:[ \t]*\Z"],
        timeout=5,
        echo=False,
    )
    assert output.rstrip().endswith("password:")
    assert "temppwd" in output, "should have read past the banner, not stopped on it"


class ClosingShell(FakeShell):
    """A shell whose peer hangs up -- what a rebooting router looks like."""

    def eof(self):
        return not self._chunks


def test_read_until_raises_when_device_hangs_up():
    """A rebooting router must not cost a full timeout of dead waiting.

    `system restore` reboots the IX20, killing the channel. Without an EOF
    check the reader cannot tell that from "no output yet" and sits on the
    dead socket for the entire 900s config-restore timeout.
    """
    shell = ClosingShell([b"Restoring configuration...\r\n"])
    with pytest.raises(ShellClosed):
        read_until(shell, [r"never arrives"], timeout=30, echo=False, poll=0.01)


def test_read_until_still_matches_before_the_peer_hangs_up():
    shell = ClosingShell([b"Restore complete\r\n"])
    assert "Restore complete" in read_until(
        shell, [r"Restore complete"], timeout=5, echo=False
    )


def test_read_until_times_out_normally_when_shell_has_no_eof_hook():
    """FakeShell has no eof(); such shells are assumed open, as before."""
    with pytest.raises(StepTimeout):
        read_until(FakeShell([b"working\n"]), [r"nope"], timeout=1, echo=False, poll=0.05)


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
