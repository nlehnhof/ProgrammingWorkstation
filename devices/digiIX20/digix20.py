"""Digi IX20 provisioning -- runs as a subprocess launched by prog_dev.py.

Usage: python digix20.py <gate_ip> <gate_netmask> <gate_gateway> <default_pass>

Every verification in here waits on something observable: a prompt handed back
by the Admin CLI, a command's real exit status, an SFTP stat, or a port/SSH
login answering again after a reboot. Nothing is confirmed on the strength of a
`time.sleep()`.

Milestones are announced on stdout with a machine-readable marker
(##STATUS##<id>|<state>|<detail>) alongside the normal human-readable prints;
prog_dev.py forwards those to the GUI checklist and drops the marker lines.
"""

import ipaddress
import os
import re
import subprocess
import sys
import time
import traceback

# Repo root, so `resources.utilities...` imports resolve no matter the cwd.
DEVICE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(DEVICE_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from resources.utilities import status as _status
from resources.utilities.device_config import load_config
from resources.utilities.mac_utils import extract_mac
from resources.utilities.network_utils import prefix_length
from resources.utilities.ssh_session import SSHSession
from resources.utilities.wait_utils import (
    DIGI_PROMPT,
    ShellClosed,
    StepTimeout,
    port_is_open,
    read_until,
    run_checked,
    run_cli,
    verify_remote_file,
    wait_for_port,
    wait_for_ssh,
    wait_for_prompt,
)

CONFIG = load_config(DEVICE_DIR, env_prefix="DIGIIX20_")

# Digi's SSH access menu: "a" drops into the Admin CLI. Not every unit shows
# it -- see open_admin_cli.
ADMIN_CLI_KEY = "a"
ACCESS_MENU = r"\[a/s/q\]|Select access"


class StepError(RuntimeError):
    """A provisioning milestone failed. Message is shown to the operator."""


# ----------------------------------------------------------------------------
# Status protocol -- see resources/utilities/status.py for the wire format.
# Aliased locally so every milestone below reads as a plain verb.
# ----------------------------------------------------------------------------

status = _status.emit
step_running = _status.running
step_pass = _status.passed
step_sent = _status.sent
step_wait = _status.waiting
step_fail = _status.failed


# ----------------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------------

if len(sys.argv) > 4:
    gate_ip = sys.argv[1]
    gate_netmask = sys.argv[2]
    gate_gateway = sys.argv[3]
    default_pass = sys.argv[4]
else:
    print("UNKNOWN", flush=True)
    print("Incorrect! digix20.py needs gate ip, netmask, gateway and password.", flush=True)
    sys.exit(2)

print(gate_ip, flush=True)
print(gate_netmask, flush=True)
print(gate_gateway, flush=True)


def gate_prefix():
    """Prefix length from the sheet's netmask (no hardcoded /24)."""
    return prefix_length(gate_netmask, default=24)


# ----------------------------------------------------------------------------
# Shared run state
# ----------------------------------------------------------------------------

class Run:
    """Values discovered in one milestone and needed by a later one."""

    bbb_ip = None
    pc_interface_index = None
    pc_static_applied = False
    mac_address = None
    firmware_already_current = False
    detected_stage = None
    router_ip = None
    serial_number = None


# ----------------------------------------------------------------------------
# Connection helpers
# ----------------------------------------------------------------------------

def bbb_session():
    print("Connecting to BBB", flush=True)
    session = SSHSession(
        CONFIG["bbb_ip"],
        CONFIG["bbb_user"],
        CONFIG["bbb_password"],
        timeout=CONFIG["ssh_timeout"],
    )
    session.ensure_connected()
    print("Connected to BBB", flush=True)
    return session


def router_session(host, password):
    print("Connecting to Router", flush=True)
    session = SSHSession(
        host,
        CONFIG["router_user"],
        password,
        timeout=CONFIG["ssh_timeout"],
    )
    session.ensure_connected()
    print("Connected to Router", flush=True)
    return session


def router_session_any(host, passwords):
    """Connect to the router trying each password in turn.

    Unlike the old nested bare-except, a total failure raises instead of
    handing back a half-dead client the caller keeps using.
    """
    last_error = None
    for password in passwords:
        if not password:
            continue
        try:
            return router_session(host, password)
        except Exception as exc:
            last_error = exc
    raise StepError(f"Incorrect! Could not authenticate to router at {host}: {last_error}")


def open_admin_cli(session):
    """Open a shell and make sure we end up at a live Admin CLI prompt.

    Some IX20s present the access menu ("Select access or quit [a/s/q]:") on
    login and need an "a" to reach the Admin CLI. Others log straight into it
    and greet you with "Type 'exit' to disconnect from the Admin CLI" and a
    prompt -- there, "a" is an unknown command that buys nothing and can leave
    the session wedged. Decide from what the device actually sent rather than
    sending the key unconditionally.
    """
    shell = session.invoke_shell(timeout=CONFIG["cli_timeout"])

    banner = ""
    try:
        banner = read_until(shell, [ACCESS_MENU, DIGI_PROMPT], timeout=30)
    except Exception:
        pass

    if re.search(ACCESS_MENU, banner):
        print("Access menu detected; selecting the Admin CLI.", flush=True)
        run_cli(shell, ADMIN_CLI_KEY, timeout=CONFIG["cli_timeout"])
    elif re.search(DIGI_PROMPT, banner):
        print("Already at the Admin CLI prompt.", flush=True)
    else:
        # Saw neither -- the menu may simply have been missed. Try the key.
        print("No prompt or menu seen; sending the Admin CLI key.", flush=True)
        run_cli(shell, ADMIN_CLI_KEY, timeout=CONFIG["cli_timeout"])

    # Bare newline: confirms the CLI is actually answering before any real
    # command is issued, and re-syncs if a keystroke was dropped.
    run_cli(shell, "", timeout=CONFIG["cli_timeout"])
    return shell


def pull_file_to_router(shell, remote_name, router_path, expected_size):
    """Have the router scp a file off the BBB, then verify it landed.

    The `ls` check only runs after the prompt comes back, so it can never race
    the transfer the way the old fixed-sleep version did.

    Use bare `ls <dir>/` -- the Admin CLI already returns a long listing with
    sizes and rejects an explicit `-l`:

        -rw-r-----  1 root  root  36361400 Apr  3 05:39 IX20-firmware.bin
    """
    shell.send(
        f"scp host {Run.bbb_ip} user {CONFIG['bbb_user']} "
        f"remote /home/{CONFIG['bbb_user']}/{remote_name} "
        f"local {router_path} to local\n"
    )

    # The router prompts for the BBB password before it starts copying. Match
    # only a prompt that is actually waiting for input -- trailing colon, end
    # of buffer -- not the word "password" anywhere in the output. The BBB's
    # login banner announces "default username:password is [debian:temppwd]",
    # which satisfied the old loose pattern: the password went into the banner,
    # the real prompt went unanswered, and the session sat there until the
    # router's idle timeout killed it ten minutes later.
    read_until(
        shell,
        [r"[Pp]assword:[ \t]*\Z", r"[Pp]assphrase[^:\r\n]*:[ \t]*\Z"],
        timeout=60,
    )
    shell.send(CONFIG["bbb_password"] + "\n")

    # Prompt returns only once scp has finished.
    wait_for_prompt(shell, timeout=CONFIG["scp_timeout"])

    router_dir = os.path.dirname(router_path).replace("\\", "/") or "/tmp"
    listing = run_cli(shell, f"ls {router_dir}/", timeout=CONFIG["cli_timeout"])
    basename = os.path.basename(router_path)

    # Match the file's own line, so an unrelated leftover in /tmp that happens
    # to be the right size can't stand in for the copy we just made.
    entry = next((l for l in listing.splitlines() if basename in l), None)
    if entry is None:
        raise StepError(f"Incorrect! Failed to copy over {basename} to the router.")

    # Timestamps in the listing are 2-digit, so \d{4,} only picks up the size.
    sizes = [int(n) for n in re.findall(r"\b(\d{4,})\b", entry)]
    if expected_size and expected_size not in sizes:
        raise StepError(
            f"Incorrect! {basename} on the router is not {expected_size} bytes "
            f"(saw {sizes or 'no size'}) -- transfer was incomplete."
        )
    print(f"{basename} verified on router ({expected_size} bytes)", flush=True)


def push_file_to_bbb(session, local_path, remote_name):
    """SFTP a file to the BBB and verify size. put() returns only when done."""
    if not os.path.isfile(local_path):
        raise StepError(f"Incorrect! Local file not found: {local_path}")

    expected_size = os.path.getsize(local_path)
    remote_path = f"/home/{CONFIG['bbb_user']}/{remote_name}"
    session.upload(local_path, remote_path)
    verify_remote_file(session.sftp, remote_path, expected_size)
    return expected_size


# ----------------------------------------------------------------------------
# PowerShell helpers (run on this PC, not on the router)
# ----------------------------------------------------------------------------

def powershell(command, check=True, quiet=False):
    """Run a PowerShell command locally and return its stdout."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip() and not quiet:
        print(result.stdout.strip(), flush=True)
    if result.stderr.strip():
        print(result.stderr.strip(), flush=True)
    if check and result.returncode != 0:
        raise StepError(
            f"Incorrect! PowerShell command failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


def is_admin():
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except Exception:
        return False


def find_pc_interface_index():
    """Interface index of the adapter facing the router.

    Checks every subnet the router uses over the course of a run, not just its
    factory address: by the time the static-IP milestone needs this, the config
    restore has already moved the router off 192.168.2.x, so keying on that one
    subnet finds nothing. Falls back to the connected wired adapter, which is
    what the operator has the router plugged into.
    """
    subnets = [
        CONFIG["router_temp_ip"].rsplit(".", 1)[0],
        CONFIG["router_post_restore_ip"].rsplit(".", 1)[0],
        CONFIG["pc_static_ip"].rsplit(".", 1)[0],
        gate_ip.rsplit(".", 1)[0],
    ]

    for subnet in subnets:
        output = powershell(
            "Get-NetIPAddress -AddressFamily IPv4 | "
            f"Where-Object {{ $_.IPAddress -like '{subnet}.*' }} | "
            "Select-Object -First 1 -ExpandProperty InterfaceIndex",
            check=False,
        )
        match = re.search(r"\d+", output)
        if match:
            return match.group(0)

    # Fallback: the connected wired adapter -- but never the one facing the
    # BeagleBone. That link is always up, so a naive "first Ethernet adapter"
    # pick lands on it and reconfigures the wrong NIC.
    bbb_subnet = CONFIG["bbb_ip"].rsplit(".", 1)[0]
    output = powershell(
        "$bbb = @(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { "
        f"$_.IPAddress -like '{bbb_subnet}.*' }} | "
        "Select-Object -ExpandProperty InterfaceIndex); "
        "Get-NetAdapter -Physical | Where-Object { $_.Status -eq 'Up' -and "
        "$_.MediaType -eq '802.3' -and $bbb -notcontains $_.ifIndex } | "
        "Select-Object -First 1 -ExpandProperty ifIndex",
        check=False,
    )
    match = re.search(r"\d+", output)
    return match.group(0) if match else None


def set_pc_static_ip(address, prefix, gateway=None):
    index = Run.pc_interface_index
    if not index:
        raise StepError(
            "Incorrect! Could not find the PC network adapter on the router's subnet."
        )

    # Catch a stale router address here rather than letting New-NetIPAddress
    # reject it with a wall of CIM error text. A gateway outside the address's
    # own subnet always means a caller passed an address the router has since
    # moved off.
    if gateway:
        network = ipaddress.IPv4Network(f"{address}/{prefix}", strict=False)
        try:
            on_subnet = ipaddress.IPv4Address(gateway) in network
        except ValueError:
            on_subnet = False
        if not on_subnet:
            raise StepError(
                f"Incorrect! Gateway {gateway} is not inside {network}, so the PC "
                f"cannot be set to {address}/{prefix} -- the router address is stale."
            )

    # DHCP has to come off the interface first. Adding a static address while
    # the interface is still DHCP-managed leaves it Tentative and then Invalid
    # -- it shows up in Get-NetIPAddress, so a presence check passes, but it
    # never carries traffic and everything routed through it fails.
    powershell(f"Set-NetIPInterface -InterfaceIndex {index} -Dhcp Disabled", check=False)

    powershell(
        f"Get-NetIPAddress -InterfaceIndex {index} -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false",
        check=False,
    )
    powershell(
        f"Remove-NetRoute -InterfaceIndex {index} -DestinationPrefix 0.0.0.0/0 "
        "-Confirm:$false -ErrorAction SilentlyContinue",
        check=False,
    )

    command = f"New-NetIPAddress -InterfaceIndex {index} -IPAddress {address} -PrefixLength {prefix}"
    if gateway:
        command += f" -DefaultGateway {gateway}"
    powershell(command, quiet=True)
    Run.pc_static_applied = True

    wait_for_pc_address(index, address)
    print(f"PC static IP set to {address}/{prefix}", flush=True)


def wait_for_pc_address(index, address, timeout=30, interval=1):
    """Block until Windows has finished duplicate-address detection.

    A new address is Tentative until DAD completes and only Preferred means it
    can actually be used. Checking that the address merely *appears* passes
    while it is still unusable, which is what made the router look unreachable
    on a subnet the PC had supposedly just joined.
    """
    deadline = time.monotonic() + timeout
    state = None
    while time.monotonic() < deadline:
        output = powershell(
            f"(Get-NetIPAddress -InterfaceIndex {index} -IPAddress {address} "
            "-AddressFamily IPv4 -ErrorAction SilentlyContinue).AddressState",
            check=False,
            quiet=True,
        )
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        state = lines[-1] if lines else None

        if state == "Preferred":
            return
        if state == "Invalid":
            raise StepError(
                f"Incorrect! Windows rejected PC address {address} -- either the "
                "link is down or another device already holds that address."
            )
        time.sleep(interval)

    raise StepError(
        f"Incorrect! PC address {address} never became usable (state: {state or 'absent'})."
    )


def restore_pc_dhcp():
    index = Run.pc_interface_index
    if not index or not Run.pc_static_applied:
        return
    print("Restoring PC network adapter to DHCP", flush=True)
    powershell(
        f"Get-NetIPAddress -InterfaceIndex {index} -AddressFamily IPv4 "
        "-ErrorAction SilentlyContinue | Remove-NetIPAddress -Confirm:$false",
        check=False,
    )
    powershell(
        f"Remove-NetRoute -InterfaceIndex {index} -DestinationPrefix 0.0.0.0/0 "
        "-Confirm:$false -ErrorAction SilentlyContinue",
        check=False,
    )
    powershell(f"Set-NetIPInterface -InterfaceIndex {index} -Dhcp Enabled", check=False)
    powershell(
        f"Set-DnsClientServerAddress -InterfaceIndex {index} -ResetServerAddresses",
        check=False,
    )
    Run.pc_static_applied = False


# ----------------------------------------------------------------------------
# Milestone 1 -- Checking IP
# ----------------------------------------------------------------------------

def find_bbb_ip(session):
    """Read the BBB's address on the router subnet, running dhclient if needed."""
    pattern = CONFIG["bbb_subnet_pattern"]
    broadcast = CONFIG["router_temp_ip"].rsplit(".", 1)[0] + ".255"

    def candidates():
        output, _, _ = run_checked(session, "ip addr show eth0")
        found = re.findall(pattern, output)
        print(found, flush=True)
        return [
            ip for ip in found
            if ip not in (broadcast, CONFIG["router_temp_ip"])
        ]

    ips = candidates()
    if not ips:
        print(f"{CONFIG['router_temp_ip'].rsplit('.', 1)[0]} not in output", flush=True)
        print("Requesting a DHCP lease on the BBB...", flush=True)
        # recv_exit_status inside run_checked blocks until dhclient exits.
        run_checked(session, "sudo -n /sbin/dhclient -v eth0", timeout=120)
        ips = candidates()

    if not ips:
        raise StepError("Incorrect! Failed to find an IP address on the BeagleBone.")
    return ips[0]


def check_ip():
    step_running("check_ip")
    print("Checking network addresses...", flush=True)

    session = bbb_session()
    try:
        Run.bbb_ip = find_bbb_ip(session)
        print(f"BBB IP: {Run.bbb_ip}", flush=True)
    finally:
        print("Closing Connection to BBB", flush=True)
        session.close()
        print("Closed Connection to BBB", flush=True)

    Run.pc_interface_index = find_pc_interface_index()
    if Run.pc_interface_index:
        print(f"PC network adapter index: {Run.pc_interface_index}", flush=True)
    else:
        print("PC network adapter on the router subnet not found yet.", flush=True)

    try:
        wait_for_port(CONFIG["router_temp_ip"], 22, up=True, timeout=60, label="router")
    except Exception as exc:
        raise StepError(
            f"Incorrect! Router not reachable at {CONFIG['router_temp_ip']}: {exc}"
        ) from exc
    print(f"Router reachable at {CONFIG['router_temp_ip']}", flush=True)

    step_pass("check_ip")


# ----------------------------------------------------------------------------
# Milestone 2 -- Firmware #1 install
# ----------------------------------------------------------------------------

def firmware_update():
    step_running("firmware_1")
    print("Updating router firmware...", flush=True)

    expected = expected_firmware_version()

    # Ask what the router already runs before doing any work. A box that is
    # already on the target image will not re-flash it: `system firmware
    # update` returns to the prompt without ever printing "Firmware update
    # completed", so the wait below would sit out its full timeout. This is the
    # normal case for any router that has been through this flow before -- a
    # config factory-reset does not roll the firmware back.
    if expected:
        router = router_session_any(
            CONFIG["router_temp_ip"], [default_pass, CONFIG["router_new_password"]]
        )
        try:
            with open_admin_cli(router) as shell:
                running, alt = read_firmware_versions(shell)
        finally:
            router.close()

        if running == expected:
            print(f"Router already runs firmware {running}; skipping the update.",
                  flush=True)
            Run.firmware_already_current = True
            step_pass("firmware_1")
            return
        if running:
            print(f"Router runs firmware {running}; updating to {expected}.", flush=True)

    local_firmware = os.path.join(DEVICE_DIR, "firmware", CONFIG["firmware_filename"])

    session = bbb_session()
    try:
        print("Copying firmware to BBB...", flush=True)
        size = push_file_to_bbb(session, local_firmware, CONFIG["firmware_remote_name"])
        print("Firmware copied to BBB", flush=True)
    finally:
        print("Closing Connection to BBB", flush=True)
        session.close()
        print("Closed Connection to BBB", flush=True)

    router = router_session_any(
        CONFIG["router_temp_ip"], [default_pass, CONFIG["router_new_password"]]
    )
    try:
        with open_admin_cli(router) as shell:
            print("Pulling firmware onto the router...", flush=True)
            pull_file_to_router(
                shell,
                CONFIG["firmware_remote_name"],
                CONFIG["firmware_router_path"],
                size,
            )

            print("Installing firmware -- this takes a few minutes...", flush=True)
            shell.send(f"system firmware update file {CONFIG['firmware_router_path']}\n")
            # Matching the prompt too means an update that says nothing useful
            # fails immediately with whatever the router *did* say, instead of
            # burning the whole timeout waiting for a message already decided
            # not to come. The IX20 prints nothing between the command and its
            # result, so the prompt cannot match early here.
            output = read_until(
                shell,
                [r"Firmware update completed", r"[Ee]rror", r"[Ff]ail", DIGI_PROMPT],
                timeout=CONFIG["firmware_update_timeout"],
            )
            if "Firmware update completed" not in output:
                detail = " ".join(output.split())[-300:] or "no output"
                raise StepError(f"Incorrect! Failed to update firmware -- router said: {detail}")
            print("Firmware update completed", flush=True)
    finally:
        print("Closing Connection to Router", flush=True)
        router.close()
        print("Closed Connection to Router", flush=True)

    step_pass("firmware_1")


# ----------------------------------------------------------------------------
# Milestone 3 -- First reboot
# ----------------------------------------------------------------------------

def reboot_router(host, passwords, step_id):
    """Send reboot, confirm the box actually goes down, then wait for it back.

    The session stays open until the router stops answering. Closing the
    channel straight after the send tears it down before the CLI has processed
    the line, and the reboot silently never happens -- which leaves the staged
    firmware sitting in the inactive bank while everything downstream carries
    on against the old image.

    Failing to go down is fatal here rather than a warning: without a real
    reboot the bank never switches, so continuing only produces a confusing
    failure later.
    """
    router = router_session_any(host, passwords)
    try:
        shell = open_admin_cli(router)
        try:
            print("Rebooting Router", flush=True)
            shell.send("reboot\n")
            step_sent(step_id, "reboot command sent")

            # Answer a confirmation prompt if this build asks for one. Either
            # way, reading here keeps the channel alive while the CLI acts on
            # the command.
            try:
                answer = read_until(
                    shell,
                    [r"\[y/n\]", r"\(y/n\)", r"[Aa]re you sure", r"[Rr]eboot"],
                    timeout=15,
                )
                if re.search(r"y/n|[Aa]re you sure", answer):
                    print("Confirming the reboot prompt...", flush=True)
                    shell.send("y\n")
            except Exception:
                pass

            step_wait(step_id, "Wait ~2 min for device to reboot...")
            print("Waiting for the router to go down...", flush=True)
            try:
                wait_for_port(host, 22, up=False, timeout=180, label="router")
            except StepTimeout as exc:
                raise StepError(
                    "Incorrect! Router never went down after the reboot command -- "
                    f"it is still answering on {host}:22. The firmware bank will not "
                    "switch without a real reboot."
                ) from exc
            print("Router is going down.", flush=True)
        finally:
            try:
                shell.close()
            except Exception:
                pass
    finally:
        router.close()

    print("Waiting for the router to come back...", flush=True)
    wait_for_port(host, 22, up=True, timeout=CONFIG["reboot_timeout"], label="router")


def expected_firmware_version():
    """Version the router should report once the new image is running.

    Taken from `firmware_version` if configured, otherwise read out of the
    firmware filename (".../IX20-25.2.56.67-asof-...") so there is only one
    place to update when the image is replaced.
    """
    configured = CONFIG.get("firmware_version")
    if configured:
        return configured
    match = re.search(r"(\d+\.\d+\.\d+\.\d+)", CONFIG["firmware_filename"])
    return match.group(1) if match else None


def read_firmware_versions(shell):
    """Return (running, inactive) firmware versions from `show system`.

        Firmware Version         : 25.2.56.67
        Alt. Firmware Version    : 25.2.54.212

    Either may be None if the field is absent. Reporting both makes a failure
    diagnosable: it separates "the reboot didn't switch banks" from "the image
    never staged".
    """
    output = run_cli(shell, "show system", timeout=CONFIG["cli_timeout"])
    running = re.search(
        r"^[ \t]*Firmware Version[ \t]*:[ \t]*(\S+)", output, re.MULTILINE
    )
    alt = re.search(
        r"^[ \t]*Alt\.? Firmware Version[ \t]*:[ \t]*(\S+)", output, re.MULTILINE
    )
    return (running.group(1) if running else None), (alt.group(1) if alt else None)


def wait_for_firmware(host, passwords, expected, timeout, interval=10):
    """Poll the router until it reports `expected` firmware, or give up.

    Port 22 answering is not the same as booted. After a firmware update the
    IX20 still has to switch banks, and it can come up, do first-boot work and
    go down again before it settles -- so a single check the moment SSH opens
    reads whatever happens to be running at that instant.

    Every probe is a real login plus `show system`: the decision to continue is
    driven by what the device reports, never by a fixed wait. `interval` is a
    probe cadence, not a guess at how long booting takes.
    """
    if not expected:
        print("No firmware version to check against; skipping verification.", flush=True)
        return None, None

    deadline = time.monotonic() + timeout
    last_seen = None
    last_error = None

    while time.monotonic() < deadline:
        try:
            session = router_session_any(host, passwords)
            try:
                with open_admin_cli(session) as shell:
                    running, alt = read_firmware_versions(shell)
            finally:
                session.close()

            if running == expected:
                return running, alt
            if running:
                last_seen = (running, alt)
                print(f"Router reports firmware {running}; waiting for {expected}...",
                      flush=True)
        except Exception as exc:
            # Still rebooting, or the CLI is not up yet. Both are expected here.
            last_error = exc

        remaining = int(deadline - time.monotonic())
        if remaining <= 0:
            break
        print(f"Waiting for the router to finish booting... ~{remaining}s left", flush=True)
        time.sleep(interval)

    if last_seen:
        running, alt = last_seen
        raise StepError(
            f"Incorrect! Router is running firmware {running}, expected {expected} "
            f"(inactive bank: {alt or 'unknown'}) -- the update did not apply."
        )
    raise StepError(
        f"Incorrect! Could not confirm firmware {expected} within {timeout}s "
        f"of rebooting: {last_error}"
    )


def first_reboot():
    step_running("reboot_1")

    # Nothing was flashed, so there is no bank switch pending and no reason to
    # spend three minutes rebooting.
    if Run.firmware_already_current:
        print("Firmware was already current; no reboot needed.", flush=True)
        step_pass("reboot_1")
        return

    reboot_router(
        CONFIG["router_temp_ip"],
        [default_pass, CONFIG["router_new_password"]],
        "reboot_1",
    )

    # The bank switch happens across this boot, so keep asking until the router
    # actually reports the new image rather than checking the instant SSH opens.
    step_wait("reboot_1", "Waiting for the router to finish booting...")
    running, alt = wait_for_firmware(
        CONFIG["router_temp_ip"],
        [default_pass, CONFIG["router_new_password"]],
        expected_firmware_version(),
        timeout=CONFIG["firmware_boot_timeout"],
    )
    if running:
        print(f"Confirmed firmware {running} is running (inactive bank: {alt or 'unknown'})",
              flush=True)

    print("Firmware updated; reboot complete. Move to configurations.", flush=True)
    step_pass("reboot_1")


# ----------------------------------------------------------------------------
# Milestone 4 -- Configuration push
# ----------------------------------------------------------------------------

def configure():
    step_running("config_push")
    print("Configuring router...", flush=True)

    local_config = os.path.join(DEVICE_DIR, "configs", CONFIG["config_filename"])

    session = bbb_session()
    try:
        Run.bbb_ip = find_bbb_ip(session)
        print("Copying configuration to BBB...", flush=True)
        size = push_file_to_bbb(session, local_config, CONFIG["config_remote_name"])
        print("Configuration copied to BBB", flush=True)
    finally:
        print("Closing Connection to BBB", flush=True)
        session.close()
        print("Closed Connection to BBB", flush=True)

    router = router_session_any(
        CONFIG["router_temp_ip"], [default_pass, CONFIG["router_new_password"]]
    )
    try:
        with open_admin_cli(router) as shell:
            print("Pulling configuration onto the router...", flush=True)
            pull_file_to_router(
                shell,
                CONFIG["config_remote_name"],
                CONFIG["config_router_path"],
                size,
            )

            print("Restoring configuration -- this takes a few minutes...", flush=True)
            shell.send(f"system restore {CONFIG['config_router_path']}\n")
            # First, confirm the restore actually started.
            output = ""
            try:
                output = read_until(
                    shell,
                    [r"Restoring with backup", r"[Ee]rror", r"[Ff]ail"],
                    timeout=CONFIG["restore_ack_timeout"],
                )
            except (StepTimeout, ShellClosed) as exc:
                print(f"Restore produced no acknowledgement ({type(exc).__name__}).",
                      flush=True)

            if re.search(r"[Ee]rror|[Ff]ail", output):
                detail = " ".join(output.split())[-300:]
                raise StepError(f"Incorrect! Failed to restore the configuration: {detail}")
            if "Restoring with backup" in output:
                print("Configuration restore accepted by the router.", flush=True)

            # Then stay on the shell until the router goes away. Two reasons
            # this cannot just close and poll: dropping the channel aborts the
            # restore, exactly as it aborted `reboot`; and an unread channel
            # can fill its window and stall the remote process. `system restore`
            # prints no completion line -- it unpacks the archive and reboots --
            # so the session dying *is* the finish signal, which the transport
            # keepalive now makes detectable.
            step_wait("config_push", "Unpacking configuration, then rebooting...")
            try:
                tail = read_until(
                    shell,
                    [r"[Ee]rror", r"[Ff]ail"],
                    timeout=CONFIG["config_restore_timeout"],
                )
                if re.search(r"[Ee]rror|[Ff]ail", tail):
                    detail = " ".join(tail.split())[-300:]
                    raise StepError(
                        f"Incorrect! Failed to restore the configuration: {detail}"
                    )
            except ShellClosed:
                print("Router closed the session; it is rebooting to apply the restore.",
                      flush=True)
            except StepTimeout:
                print("Restore stopped producing output; checking whether the router "
                      "rebooted.", flush=True)
    finally:
        print("Closing Connection to Router", flush=True)
        router.close()
        print("Closed Connection to Router", flush=True)

    # `system restore` reboots the router onto its new address. Only its *going
    # away* is observable from here -- this PC is still on the router's old
    # subnet and has no route to 192.168.81.x, so waiting for it to come back
    # has to happen after the PC moves, which is the next milestone.
    # With no completion message and no channel EOF to rely on, the router
    # leaving its old address is the only trustworthy evidence the restore
    # took. Treat failing to leave as a failure rather than pressing on.
    step_wait("config_push", "Wait ~2 min for device to reboot...")
    print("Waiting for the router to drop its old address...", flush=True)
    try:
        wait_for_port(
            CONFIG["router_temp_ip"], 22, up=False,
            timeout=CONFIG["reboot_timeout"], label="router",
        )
    except StepTimeout as exc:
        raise StepError(
            f"Incorrect! Router never left {CONFIG['router_temp_ip']} after the "
            "configuration restore -- the new configuration was not applied."
        ) from exc
    print("Router is rebooting onto its new address.", flush=True)

    # The restore just moved the router. Run.router_ip holds whatever the scan
    # found at startup, which is now stale -- leaving it would hand the next
    # milestone the old address as a gateway.
    Run.router_ip = CONFIG["router_post_restore_ip"]

    print("Router configured correctly.", flush=True)
    step_pass("config_push")


# ----------------------------------------------------------------------------
# Milestone 5 -- Switching static IP (this PC's adapter)
# ----------------------------------------------------------------------------

def switch_static_ip():
    step_running("static_ip")
    print("Switching the PC to a static IP on the router's subnet...", flush=True)

    if not is_admin():
        raise StepError(
            "Incorrect! Changing the PC IP address needs administrator rights. "
            "Close the app and re-open it with 'Run as administrator', then try again."
        )

    if not Run.pc_interface_index:
        Run.pc_interface_index = find_pc_interface_index()

    # Prefer the address the probe actually found the router on over the one
    # config expects it to be at.
    post_ip = Run.router_ip or CONFIG["router_post_restore_ip"]
    prefix = 24
    set_pc_static_ip(CONFIG["pc_static_ip"], prefix, gateway=post_ip)

    # Now that the PC can reach the new subnet, absorb the rest of the reboot
    # the config restore kicked off.
    step_wait("static_ip", "Wait for the router to finish rebooting...")
    session = wait_for_ssh(
        post_ip,
        CONFIG["router_user"],
        CONFIG["router_post_restore_password"],
        timeout=CONFIG["reboot_timeout"],
        ssh_timeout=CONFIG["ssh_timeout"],
    )
    session.close()
    print(f"Router reachable at {post_ip}", flush=True)

    step_pass("static_ip")


# ----------------------------------------------------------------------------
# Milestone 6 -- Changing IP address (the router's LAN interface)
# ----------------------------------------------------------------------------

def change_ip_address():
    step_running("change_ip")
    print("Changing the router IP address to the gate address...", flush=True)

    iface = CONFIG["router_lan_interface"]
    prefix = gate_prefix()

    router = router_session_any(
        Run.router_ip or CONFIG["router_post_restore_ip"],
        [CONFIG["router_post_restore_password"], CONFIG["router_new_password"], default_pass],
    )
    try:
        with open_admin_cli(router) as shell:
            run_cli(shell, "config", timeout=CONFIG["cli_timeout"])
            run_cli(shell, f"network interface {iface} ipv4", timeout=CONFIG["cli_timeout"])
            run_cli(shell, f"address {gate_ip}/{prefix}", timeout=CONFIG["cli_timeout"])
            if gate_gateway and gate_gateway != "None":
                run_cli(shell, f"gateway {gate_gateway}", timeout=CONFIG["cli_timeout"])

            # `save` is what applies the address, and applying it drops the one
            # this session is running over -- so the connection being reset is
            # the change taking effect, not a failure. A save the router
            # *rejects* leaves the address alone, so the session survives and
            # the error comes back on the prompt below.
            try:
                saved = run_cli(shell, "save", timeout=CONFIG["cli_timeout"])
            except ShellClosed:
                print("Router closed the session as it applied the new address.",
                      flush=True)
                saved = ""

            if re.search(r"[Ee]rror", saved):
                raise StepError(f"Incorrect! Router rejected the new address: {gate_ip}/{prefix}")
            step_sent("change_ip", "new address saved")
    finally:
        try:
            router.close()
        except Exception:
            pass

    # The router drops the old address as it applies the change, so follow it.
    print(f"Moving the PC onto the gate subnet to follow the router to {gate_ip}...",
          flush=True)
    set_pc_static_ip(pc_ip_on_gate_subnet(), prefix, gateway=gate_ip)

    session = wait_for_ssh(
        gate_ip,
        CONFIG["router_user"],
        CONFIG["router_post_restore_password"],
        timeout=240,
        ssh_timeout=CONFIG["ssh_timeout"],
    )
    session.close()
    print(f"Router now answering at {gate_ip}", flush=True)

    Run.router_ip = gate_ip
    step_pass("change_ip")


def pc_ip_on_gate_subnet():
    """Pick a free-looking address for the PC inside the gate's own subnet.

    This has to be derived from the netmask, not by swapping the last octet.
    The sheet's 255.255.255.128 puts gate 172.18.43.202 in 172.18.43.128/25,
    where the old ".123" guess lands in 172.18.43.0/25 -- a different subnet
    entirely, so the PC came up unable to reach the router it had just joined
    the network to talk to.

    Counts down from the top of the range, which stays clear of the low
    addresses infrastructure and DHCP pools tend to occupy.
    """
    network = ipaddress.IPv4Network(f"{gate_ip}/{gate_prefix()}", strict=False)
    if network.num_addresses <= 2:
        raise StepError(
            f"Incorrect! {gate_ip}/{gate_prefix()} has no room for a second host."
        )

    taken = {ipaddress.IPv4Address(gate_ip)}
    try:
        taken.add(ipaddress.IPv4Address(gate_gateway))
    except ValueError:
        pass

    candidate = int(network.broadcast_address) - 1
    lowest = int(network.network_address) + 1
    while candidate >= lowest:
        address = ipaddress.IPv4Address(candidate)
        if address not in taken:
            return str(address)
        candidate -= 1

    raise StepError(f"Incorrect! No free address available in {network}.")


# ----------------------------------------------------------------------------
# Milestone 7 -- Testing
# ----------------------------------------------------------------------------

def capture_identity(shell):
    """Read the MAC and serial from the top-level Admin CLI.

    Must run *before* any `config` command. Once the shell descends into the
    configuration tree, `show system` is not a valid command there, and
    `show network interface <if>` returns the stored configuration rather than
    live state -- a MAC is not configuration, so neither yields one. Reading
    this first is why the label came out with a blank MA field.
    """
    try:
        system = run_cli(shell, "show system", timeout=CONFIG["cli_timeout"])
    except Exception as exc:
        print(f"Could not read the MAC address from show system: {exc}", flush=True)
        system = ""

    found = re.search(
        r"^[ \t]*MAC Address[ \t]*:[ \t]*([0-9A-Fa-f:.-]{12,17})", system, re.MULTILINE
    )
    Run.mac_address = found.group(1) if found else extract_mac(system)

    serial = re.search(r"^[ \t]*Serial Number[ \t]*:[ \t]*(\S+)", system, re.MULTILINE)
    if serial:
        Run.serial_number = serial.group(1)
        print("Router Serial: " + Run.serial_number, flush=True)

    if not Run.mac_address:
        iface = CONFIG["router_lan_interface"]
        try:
            net = run_cli(shell, f"show network interface {iface}",
                          timeout=CONFIG["cli_timeout"])
            Run.mac_address = extract_mac(net, interface=iface) or extract_mac(net)
        except Exception as exc:
            print(f"Could not read the MAC address from {iface}: {exc}", flush=True)

    # A missing MAC leaves a blank field on the label but is not fatal.
    if Run.mac_address:
        print("MAC Addr: " + Run.mac_address, flush=True)
    else:
        print("MAC Address Not Correctly Extracted", flush=True)


def testing():
    step_running("testing")
    print("Testing the configured router...", flush=True)

    iface = CONFIG["router_lan_interface"]

    router = router_session_any(
        gate_ip,
        [CONFIG["router_post_restore_password"], CONFIG["router_new_password"], default_pass],
    )
    try:
        with open_admin_cli(router) as shell:
            capture_identity(shell)

            run_cli(shell, "config", timeout=CONFIG["cli_timeout"])
            address = run_cli(
                shell, f"network interface {iface} ipv4 address", timeout=CONFIG["cli_timeout"]
            )
            if gate_ip not in address:
                raise StepError(
                    f"Incorrect! Router reports the wrong address on {iface}: expected {gate_ip}."
                )
            print(f"Confirmed {iface} address is {gate_ip}", flush=True)

            rules = run_cli(shell, "firewall dnat", timeout=CONFIG["cli_timeout"])
            rules += run_cli(shell, "show", timeout=CONFIG["cli_timeout"])

            modbus = "modbus" in rules.lower()
            enip = "enip" in rules.lower()
            if not modbus and not enip:
                raise StepError(
                    "Incorrect! Port forwarding rules are wrong -- neither modbus nor ENIP found."
                )
            print(f"Firewall rules found -- modbus: {modbus}, ENIP: {enip}", flush=True)

            run_cli(shell, "exit", timeout=CONFIG["cli_timeout"])
    finally:
        print("Closing Connection to Router", flush=True)
        router.close()
        print("Closed Connection to Router", flush=True)

    step_pass("testing")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

STEPS = [
    ("check_ip", check_ip),
    ("firmware_1", firmware_update),
    ("reboot_1", first_reboot),
    ("config_push", configure),
    ("static_ip", switch_static_ip),
    ("change_ip", change_ip_address),
    ("testing", testing),
]

# Where the router sits tells us how much of the flow it has already been
# through. A run that died after the config restore leaves the box on its
# post-restore address, and starting over from "check_ip" then fails
# immediately because the factory address is gone -- which is why every failed
# attempt used to need a factory reset before the next one.
STAGE_FACTORY = "factory"
STAGE_CONFIGURED = "configured"
STAGE_GATE = "gate"

RESUME_AT = {
    STAGE_FACTORY: "check_ip",
    STAGE_CONFIGURED: "static_ip",
    STAGE_GATE: "testing",
}


def port_open_from_bbb(session, host, port=22, timeout=3):
    """TCP check run on the BeagleBone, which shares the router's LAN."""
    command = (
        f"timeout {timeout} bash -c '</dev/tcp/{host}/{port}' "
        ">/dev/null 2>&1 && echo OPEN || echo CLOSED"
    )
    try:
        output, _, _ = run_checked(session, command, timeout=timeout + 15, echo=False)
    except Exception:
        return False
    return "OPEN" in output


def router_authenticates(host):
    """Confirm a host answering on port 22 is actually our router.

    An open port is not proof of identity. This PC has several interfaces, and
    an address can resolve over one of them to something entirely unrelated --
    192.168.210.1 (a documented IX20 factory default) routes over Wi-Fi to a
    device on the office network here, and looked exactly like a found router.
    Acting on that would resume the flow at the wrong milestone. Only a login
    with one of the router's known passwords identifies it.
    """
    for password in (default_pass,
                     CONFIG["router_new_password"],
                     CONFIG["router_post_restore_password"]):
        if not password:
            continue
        try:
            session = router_session(host, password)
            session.close()
            return True
        except Exception:
            continue
    print(f"Something answers on {host}:22 but it is not the router.", flush=True)
    return False


def find_router_ip():
    """Discover where the router actually is, before deciding anything else.

    Asked of this PC first (free), then of the BeagleBone. The BBB sits on the
    router's LAN holding addresses on every subnet this flow uses
    (192.168.2.x, 192.168.81.x, 10.28.18.x), so it can see the router wherever
    it currently is. That beats moving this PC's adapter onto each candidate
    subnet in turn to look -- slow, needs elevation, and it leaves the NIC in a
    strange state when the guess is wrong.
    """
    candidates = [CONFIG["router_temp_ip"], CONFIG["router_post_restore_ip"], gate_ip]

    for host in candidates:
        if port_is_open(host, 22, timeout=2) and router_authenticates(host):
            print(f"Router answering at {host} from this PC.", flush=True)
            return host

    try:
        session = bbb_session()
    except Exception as exc:
        print(f"Could not reach the BeagleBone to look for the router: {exc}", flush=True)
        return None

    try:
        # Whatever the BBB routes through *is* the router, so a default route
        # points straight at it even on an address we do not have in config.
        # Only the addresses this flow actually puts the router on. The BBB's
        # default route was tried here once and only ever produced 10.28.18.1
        # -- the TR test rig, not a Digi -- so guessing from routing tables is
        # dropped in favour of checking the addresses we know we use.
        for host in candidates:
            if port_open_from_bbb(session, host):
                print(f"Router answering at {host} (seen from the BeagleBone).", flush=True)
                return host
    finally:
        print("Closing Connection to BBB", flush=True)
        session.close()

    # Last resort: the gate address. The BeagleBone holds no address on the
    # gate subnet, so it structurally cannot see a router that has already been
    # moved there -- a run that got as far as change_ip leaves the device
    # invisible to every check above. This PC has to join that subnet to look.
    return find_router_on_gate_subnet()


def find_router_on_gate_subnet():
    """Join the gate subnet briefly to see if the router is already there."""
    if not is_admin():
        print("Not elevated; cannot check the gate subnet for an already-moved router.",
              flush=True)
        return None

    print(f"Checking whether the router has already moved to {gate_ip}...", flush=True)
    try:
        if not Run.pc_interface_index:
            Run.pc_interface_index = find_pc_interface_index()
        set_pc_static_ip(pc_ip_on_gate_subnet(), gate_prefix(), gateway=gate_ip)
    except Exception as exc:
        print(f"Could not join the gate subnet to check: {exc}", flush=True)
        return None

    if port_is_open(gate_ip, 22, timeout=3) and router_authenticates(gate_ip):
        print(f"Router answering at {gate_ip} from this PC.", flush=True)
        return gate_ip

    print(f"Nothing answering at {gate_ip} either.", flush=True)
    return None


def stage_for(host):
    """Map the router's current address onto how far the flow has got."""
    if host == CONFIG["router_temp_ip"]:
        return STAGE_FACTORY
    if host == gate_ip:
        return STAGE_GATE
    # Anything else means the config restore has already moved it off the
    # factory address, whether or not that address is the one we expected.
    return STAGE_CONFIGURED


def resume_index():
    """Index into STEPS to start from, based on where the router actually is."""
    step_running("scan")
    try:
        host = find_router_ip()
    except Exception as exc:
        print(f"Could not determine the router's state ({exc}); starting from the top.",
              flush=True)
        host = None

    if not host:
        print("Could not find the router at any known address; starting from the top.",
              flush=True)
        # The gate-subnet check may have parked the PC on a static address.
        # Undo it, or check_ip runs against the wrong adapter configuration.
        try:
            restore_pc_dhcp()
        except Exception:
            pass
        # The scan itself finished -- it just found nothing. check_ip is what
        # fails if the router really is unreachable.
        status("scan", "PASS", "no router found; running full flow")
        return 0

    status("scan", "PASS", f"found at {host}")
    Run.router_ip = host
    stage = stage_for(host)
    Run.detected_stage = stage
    resume_step = RESUME_AT[stage]
    index = next(i for i, (step_id, _) in enumerate(STEPS) if step_id == resume_step)

    if index == 0:
        print(f"Router found at {host} in factory state; running the full flow.", flush=True)
        return 0

    print(f"Router found at {host} -- it is already past "
          f"{STEPS[index - 1][0]}. Resuming at {resume_step}.", flush=True)
    for step_id, _ in STEPS[:index]:
        status(step_id, "PASS", "already done")
    return index


def main():
    print("Starting... ", flush=True)
    current_step = None
    try:
        start = resume_index()
        for step_id, func in STEPS[start:]:
            current_step = step_id
            func()
    except StepError as exc:
        step_fail(current_step or "check_ip", str(exc))
        print(str(exc), flush=True)
        traceback.print_exc()
        return 1
    except Exception as exc:
        step_fail(current_step or "check_ip", f"{type(exc).__name__}: {exc}")
        print(f"Incorrect! {type(exc).__name__}: {exc}", flush=True)
        traceback.print_exc()
        return 1
    finally:
        try:
            restore_pc_dhcp()
        except Exception as exc:
            print(f"Could not restore the PC network adapter to DHCP: {exc}", flush=True)

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
