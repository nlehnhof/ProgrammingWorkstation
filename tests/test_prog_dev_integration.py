"""Integration tests for devices/TR/prog_dev.py's Excel + shell-leak fixes.

prog_dev.py isn't a normal importable package (the app loads it with
exec()/subprocess, see pages/program_page.py), so it's loaded here the same
way: as a standalone module from its file path.
"""

import importlib.util
import os
from unittest.mock import MagicMock

import openpyxl
import pytest

PROG_DEV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "devices", "TR", "prog_dev.py"
)

REAL_HEADERS = [
    "PBB Gate", "Gate IP", "Netmask", "Gateway", "PBB SN", "Jetway PN",
    "MAC Address", "Router Programmed On", "Label", "Crash Report",
    "PRG #", "Router Tested On", "Crash Report", "Test #", "Notes",
]


@pytest.fixture
def prog_dev():
    spec = importlib.util.spec_from_file_location("prog_dev_under_test", PROG_DEV_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_workbook(path, rows, headers=REAL_HEADERS):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    wb.save(path)
    return path


def test_col_helper_resolves_real_columns_by_name(prog_dev):
    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.append(REAL_HEADERS)
    header_map = prog_dev.get_header_map(sheet)

    assert prog_dev.col(header_map, "mac") == 7
    assert prog_dev.col(header_map, "programmed_on") == 8
    assert prog_dev.col(header_map, "label") == 9
    assert prog_dev.col(header_map, "crash_report", 0) == 10
    assert prog_dev.col(header_map, "prg_count") == 11
    assert prog_dev.col(header_map, "tested_on") == 12
    assert prog_dev.col(header_map, "crash_report", 1) == 13
    assert prog_dev.col(header_map, "test_count") == 14


def test_lookup_excel_sets_globals_and_flags_valid_ip(tmp_path, prog_dev, monkeypatch):
    devices_dir = tmp_path / "devices" / "ACME"
    devices_dir.mkdir(parents=True)
    make_workbook(
        devices_dir / "airport.xlsx",
        rows=[[21, "10.28.18.2", "255.255.255.0", "10.28.18.1", 10000]],
    )
    monkeypatch.chdir(tmp_path)

    prog_dev.lookup_excel("airport.xlsx", "10000", "ACME")

    assert prog_dev.valid_ip is True
    assert prog_dev.gate_ip == "10.28.18.2"
    assert prog_dev.gate_netmask == "255.255.255.0"
    assert prog_dev.gate_gateway == "10.28.18.1"


def test_lookup_excel_flags_invalid_ip_instead_of_crashing(tmp_path, prog_dev, monkeypatch):
    devices_dir = tmp_path / "devices" / "ACME"
    devices_dir.mkdir(parents=True)
    make_workbook(
        devices_dir / "airport.xlsx",
        rows=[[21, "garbage-ip", "255.255.255.0", "10.28.18.1", 10000]],
    )
    monkeypatch.chdir(tmp_path)

    prog_dev.lookup_excel("airport.xlsx", "10000", "ACME")

    assert prog_dev.valid_ip is False


def test_lookup_excel_flags_missing_gate_instead_of_crashing(tmp_path, prog_dev, monkeypatch):
    devices_dir = tmp_path / "devices" / "ACME"
    devices_dir.mkdir(parents=True)
    make_workbook(
        devices_dir / "airport.xlsx",
        rows=[[21, "10.28.18.2", "255.255.255.0", "10.28.18.1", 10000]],
    )
    monkeypatch.chdir(tmp_path)

    prog_dev.lookup_excel("airport.xlsx", "no-such-gate", "ACME")

    assert prog_dev.valid_ip is False


def test_ssh_run_shell_closes_channel_even_on_normal_use(prog_dev):
    from resources.utilities.ssh_session import ManagedShell

    session = MagicMock()
    channel = MagicMock()
    channel.recv.return_value = b"ok"
    session.invoke_shell.return_value = ManagedShell(channel)

    prog_dev.ssh_run_shell(session, "echo hi")

    channel.close.assert_called_once()


def test_ssh_run_shell_returns_none_without_session_or_command(prog_dev):
    assert prog_dev.ssh_run_shell(None, "cmd") is None
    assert prog_dev.ssh_run_shell(MagicMock(), None) is None
