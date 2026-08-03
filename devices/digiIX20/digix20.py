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
import traceback

# Repo root, so `resources.utilities...` imports resolve no matter the cwd.
DEVICE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(DEVICE_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from resources.utilities.device_config import load_config
from resources.utilities.mac_utils import extract_mac
from resources.utilities.ssh_session import SSHSession
from resources.utilities.wait_utils import (
    read_until,
    run_checked,
    run_cli,
    verify_remote_file,
    wait_for_port,
    wait_for_ssh,
    wait_for_prompt,
)

CONFIG = load_config(DEVICE_DIR, env_prefix="DIGIIX20_")

# Digi's SSH menu: "a" drops into the Admin CLI.
ADMIN_CLI_KEY = "a"


class StepError(RuntimeError):
    """A provisioning milestone failed. Message is shown to the operator."""


# ----------------------------------------------------------------------------
# Status protocol
# ----------------------------------------------------------------------------

def status(step_id, state, detail=""):
    print(f"##STATUS##{step_id}|{state}|{detail}", flush=True)


def step_running(step_id):
    status(step_id, "RUNNING")


def step_pass(step_id):
    status(step_id, "PASS")


def step_sent(step_id, detail):
    status(step_id, "SENT", detail)


def step_wait(step_id, detail):
    status(step_id, "WAIT", detail)


def step_fail(step_id, detail):
    status(step_id, "FAIL", detail)


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
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{gate_netmask}").prefixlen
    except ValueError:
        print(f"Could not read netmask '{gate_netmask}', assuming /24", flush=True)
        return 24


# ----------------------------------------------------------------------------
# Shared run state
# ----------------------------------------------------------------------------

class Run:
    """Values discovered in one milestone and needed by a later one."""

    bbb_ip = None
    pc_interface_index = None
    pc_static_applied = False
    mac_address = None


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
    """Open a shell and drop into the Admin CLI, returning the ManagedShell."""
    shell = session.invoke_shell(timeout=CONFIG["cli_timeout"])
    # Drain the login banner / menu, then select the Admin CLI.
    try:
        read_until(shell, [r">", r"#", r"\$"], timeout=15)
    except Exception:
        pass
    run_cli(shell, ADMIN_CLI_KEY, timeout=CONFIG["cli_timeout"])
    return shell


def pull_file_to_router(shell, remote_name, router_path, expected_size):
    """Have the router scp a file off the BBB, then verify it landed.

    The `ls -l` check only runs after the prompt comes back, so it can never
    race the transfer the way the old fixed-sleep version did.
    """
    shell.send(
        f"scp host {Run.bbb_ip} user {CONFIG['bbb_user']} "
        f"remote /home/{CONFIG['bbb_user']}/{remote_name} "
        f"local {router_path} to local\n"
    )

    # The router prompts for the BBB password before it starts copying.
    read_until(shell, [r"[Pp]assword:?", r"assphrase"], timeout=60)
    shell.send(CONFIG["bbb_password"] + "\n")

    # Prompt returns only once scp has finished.
    wait_for_prompt(shell, timeout=CONFIG["scp_timeout"])

    listing = run_cli(shell, f"ls -l {router_path}", timeout=CONFIG["cli_timeout"])
    basename = os.path.basename(router_path)
    if basename not in listing:
        raise StepError(f"Incorrect! Failed to copy over {basename} to the router.")

    sizes = [int(n) for n in re.findall(r"\b(\d{4,})\b", listing)]
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

def powershell(command, check=True):
    """Run a PowerShell command locally and return its stdout."""
    result = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
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
    """Interface index of the adapter currently on the router's default subnet."""
    subnet = CONFIG["router_temp_ip"].rsplit(".", 1)[0]
    output = powershell(
        "Get-NetIPAddress -AddressFamily IPv4 | "
        f"Where-Object {{ $_.IPAddress -like '{subnet}.*' }} | "
        "Select-Object -First 1 -ExpandProperty InterfaceIndex",
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
    powershell(command)
    Run.pc_static_applied = True

    check = powershell(
        f"Get-NetIPAddress -InterfaceIndex {index} -AddressFamily IPv4 | "
        "Select-Object -ExpandProperty IPAddress",
        check=False,
    )
    if address not in check:
        raise StepError(f"Incorrect! PC static IP {address} was not applied.")
    print(f"PC static IP set to {address}/{prefix}", flush=True)


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
            output = read_until(
                shell,
                [r"Firmware update completed", r"[Ee]rror", r"[Ff]ail"],
                timeout=CONFIG["firmware_update_timeout"],
            )
            if "Firmware update completed" not in output:
                raise StepError("Incorrect! Failed to update firmware.")
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
    """Send reboot, then wait for the box to actually go down and come back."""
    router = router_session_any(host, passwords)
    try:
        with open_admin_cli(router) as shell:
            print("Rebooting Router", flush=True)
            shell.send("reboot\n")
            step_sent(step_id, "reboot command sent")
    finally:
        router.close()

    step_wait(step_id, "Wait ~2 min for device to reboot...")
    print("Waiting for the router to reboot...", flush=True)

    # Going down first avoids mistaking the pre-reboot session for "back up".
    try:
        wait_for_port(host, 22, up=False, timeout=120, label="router")
    except Exception:
        print("Router did not drop its SSH port; continuing to wait for it to answer.",
              flush=True)

    wait_for_port(host, 22, up=True, timeout=CONFIG["reboot_timeout"], label="router")


def first_reboot():
    step_running("reboot_1")
    reboot_router(
        CONFIG["router_temp_ip"],
        [default_pass, CONFIG["router_new_password"]],
        "reboot_1",
    )

    session = wait_for_ssh(
        CONFIG["router_temp_ip"],
        CONFIG["router_user"],
        default_pass,
        timeout=CONFIG["reboot_timeout"],
        ssh_timeout=CONFIG["ssh_timeout"],
    )
    session.close()

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
            output = read_until(
                shell,
                [r"[Rr]estor(?:e|ed|ing) (?:complete|success)", r"Rebooting",
                 r"[Ee]rror", r"[Ff]ail"],
                timeout=CONFIG["config_restore_timeout"],
            )
            if re.search(r"[Ee]rror|[Ff]ail", output) and not re.search(
                r"[Rr]estor(?:e|ed) (?:complete|success)", output
            ):
                raise StepError("Incorrect! Failed to restore the configuration.")
            print("Configuration restore accepted by the router.", flush=True)
    finally:
        print("Closing Connection to Router", flush=True)
        router.close()
        print("Closed Connection to Router", flush=True)

    # `system restore` reboots the router itself onto its new address.
    step_wait("config_push", "Wait ~2 min for device to reboot...")
    print("Waiting for the router to reboot onto its new address...", flush=True)
    wait_for_port(
        CONFIG["router_post_restore_ip"], 22, up=True,
        timeout=CONFIG["reboot_timeout"], label="router",
    )

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

    post_ip = CONFIG["router_post_restore_ip"]
    prefix = 24
    set_pc_static_ip(CONFIG["pc_static_ip"], prefix, gateway=post_ip)

    session = wait_for_ssh(
        post_ip,
        CONFIG["router_user"],
        CONFIG["router_post_restore_password"],
        timeout=180,
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
        CONFIG["router_post_restore_ip"],
        [CONFIG["router_post_restore_password"], CONFIG["router_new_password"], default_pass],
    )
    try:
        with open_admin_cli(router) as shell:
            run_cli(shell, "config", timeout=CONFIG["cli_timeout"])
            run_cli(shell, f"network interface {iface} ipv4", timeout=CONFIG["cli_timeout"])
            run_cli(shell, f"address {gate_ip}/{prefix}", timeout=CONFIG["cli_timeout"])
            if gate_gateway and gate_gateway != "None":
                run_cli(shell, f"gateway {gate_gateway}", timeout=CONFIG["cli_timeout"])
            saved = run_cli(shell, "save", timeout=CONFIG["cli_timeout"])
            if re.search(r"[Ee]rror", saved):
                raise StepError(f"Incorrect! Router rejected the new address: {gate_ip}/{prefix}")
            step_sent("change_ip", "new address saved")
    finally:
        router.close()

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

    step_pass("change_ip")


def pc_ip_on_gate_subnet():
    """Pick a free-looking address for the PC on the gate's subnet.

    Uses .123 (the address the BBB/test rig already uses on TR) unless the gate
    itself is .123, in which case .100 -- the same flip TR's test step does.
    """
    parts = gate_ip.split(".")
    parts[-1] = "100" if parts[-1] == "123" else "123"
    return ".".join(parts)


# ----------------------------------------------------------------------------
# Milestone 7 -- Testing
# ----------------------------------------------------------------------------

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

            # Best effort: the label wants a MAC, but a missing one is not fatal.
            try:
                net = run_cli(shell, f"show network interface {iface}",
                              timeout=CONFIG["cli_timeout"])
                Run.mac_address = extract_mac(net, interface=iface) or extract_mac(net)
            except Exception as exc:
                print(f"Could not read the MAC address: {exc}", flush=True)

            if Run.mac_address:
                print("MAC Addr: " + Run.mac_address, flush=True)
            else:
                print("MAC Address Not Correctly Extracted", flush=True)
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


def main():
    print("Starting... ", flush=True)
    current_step = None
    try:
        for step_id, func in STEPS:
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
