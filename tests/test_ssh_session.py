import socket
from unittest.mock import MagicMock, patch

import pytest

from resources.utilities.ssh_session import SSHCommandTimeout, SSHSession, connect_with_fallback


def make_mock_client():
    client = MagicMock()
    transport = MagicMock()
    transport.is_active.return_value = True
    client.get_transport.return_value = transport
    return client


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_connects_lazily_on_first_use(mock_ssh_client_cls):
    mock_ssh_client_cls.return_value = make_mock_client()
    session = SSHSession("host", "user", "pass")
    assert mock_ssh_client_cls.call_count == 0
    session.ensure_connected()
    assert mock_ssh_client_cls.call_count == 1


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_connection_is_pooled_across_multiple_calls(mock_ssh_client_cls):
    mock_ssh_client_cls.return_value = make_mock_client()
    session = SSHSession("host", "user", "pass")

    stdout1 = MagicMock()
    stdout1.read.return_value = b"out1"
    stderr1 = MagicMock()
    stderr1.read.return_value = b""
    mock_ssh_client_cls.return_value.exec_command.return_value = (MagicMock(), stdout1, stderr1)

    session.run("cmd1")
    session.run("cmd2")

    # Only one physical connect() call despite two commands (this is the pooling fix).
    assert mock_ssh_client_cls.return_value.connect.call_count == 1
    assert mock_ssh_client_cls.call_count == 1


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_reconnects_if_transport_drops(mock_ssh_client_cls):
    dead_client = make_mock_client()
    dead_client.get_transport.return_value.is_active.return_value = False
    live_client = make_mock_client()
    mock_ssh_client_cls.side_effect = [dead_client, live_client]

    session = SSHSession("host", "user", "pass")
    session.ensure_connected()
    session._client = dead_client  # force stale state
    session.ensure_connected()

    assert mock_ssh_client_cls.call_count == 2


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_run_passes_timeout_to_exec_command(mock_ssh_client_cls):
    client = make_mock_client()
    mock_ssh_client_cls.return_value = client
    stdout = MagicMock()
    stdout.read.return_value = b"ok"
    stderr = MagicMock()
    stderr.read.return_value = b""
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    session = SSHSession("host", "user", "pass", timeout=15)
    session.run("some command")

    _, kwargs = client.exec_command.call_args
    assert kwargs["timeout"] == 15


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_run_raises_ssh_command_timeout_instead_of_hanging(mock_ssh_client_cls):
    client = make_mock_client()
    mock_ssh_client_cls.return_value = client
    stdout = MagicMock()
    stdout.read.side_effect = socket.timeout()
    stderr = MagicMock()
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    session = SSHSession("host", "user", "pass", timeout=5)
    with pytest.raises(SSHCommandTimeout):
        session.run("hung command")


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_invoke_shell_is_closable_via_context_manager(mock_ssh_client_cls):
    client = make_mock_client()
    mock_ssh_client_cls.return_value = client
    channel = MagicMock()
    client.invoke_shell.return_value = channel

    session = SSHSession("host", "user", "pass")
    with session.invoke_shell() as shell:
        shell.send("ls\n")

    channel.close.assert_called_once()


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_close_is_idempotent_and_releases_client_and_sftp(mock_ssh_client_cls):
    client = make_mock_client()
    mock_ssh_client_cls.return_value = client
    sftp = MagicMock()
    client.open_sftp.return_value = sftp

    session = SSHSession("host", "user", "pass")
    _ = session.sftp
    session.close()
    session.close()  # should not raise

    sftp.close.assert_called_once()
    client.close.assert_called_once()


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_session_as_context_manager_closes_on_exit(mock_ssh_client_cls):
    client = make_mock_client()
    mock_ssh_client_cls.return_value = client

    with SSHSession("host", "user", "pass") as session:
        session.ensure_connected()

    client.close.assert_called_once()


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_connect_with_fallback_uses_first_candidate_that_connects(mock_ssh_client_cls):
    good_client = make_mock_client()
    mock_ssh_client_cls.return_value = good_client

    candidates = [
        ("192.168.1.1", "root", "temp-pass"),
        ("192.168.81.1", "root", "temp-pass"),
    ]
    session = connect_with_fallback(candidates)

    assert session.host == "192.168.1.1"
    assert mock_ssh_client_cls.call_count == 1


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_connect_with_fallback_tries_next_candidate_on_failure(mock_ssh_client_cls):
    failing_client = make_mock_client()
    failing_client.connect.side_effect = OSError("no route to host")
    good_client = make_mock_client()
    mock_ssh_client_cls.side_effect = [failing_client, good_client]

    candidates = [
        ("192.168.1.1", "root", "temp-pass"),
        ("192.168.81.1", "root", "temp-pass"),
    ]
    session = connect_with_fallback(candidates)

    assert session.host == "192.168.81.1"
    assert mock_ssh_client_cls.call_count == 2


@patch("resources.utilities.ssh_session.paramiko.SSHClient")
def test_connect_with_fallback_raises_connection_error_when_all_fail(mock_ssh_client_cls):
    failing_client = make_mock_client()
    failing_client.connect.side_effect = OSError("no route to host")
    mock_ssh_client_cls.return_value = failing_client

    candidates = [
        ("192.168.1.1", "root", "temp-pass"),
        ("192.168.81.1", "root", "temp-pass"),
    ]
    with pytest.raises(ConnectionError):
        connect_with_fallback(candidates)
