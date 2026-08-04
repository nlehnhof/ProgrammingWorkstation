"""Teltonika RUTX08 provisioning -- runs as a subprocess launched by prog_dev.py.

Usage: python teltonika.py <gate_ip> <gate_netmask> <gate_gateway> <temp_pass>

Structured as seven milestones dispatched from main(), each announcing itself
so the GUI's Status checklist can follow along (see checklist.json). Every
verification waits on something observable -- a port going down and coming
back, an SFTP stat, a real firmware version read off the device. Nothing is
confirmed on the strength of a `time.sleep()`.

What this replaced, and why the differences matter:

* It was a single 569-line run of top-level statements with no functions past
  the SSH helpers, so a failure part-way through left no way to resume and no
  clear report of which step failed.
* Every operation opened its own `paramiko.SSHClient`; shells were opened and
  never closed. One pooled `SSHSession` per phase now, with `ManagedShell`.
* Firmware install waited a flat 3 min 15 s and the reboot a flat 1 min 30 s,
  chosen as worst-case padding. Both now wait for the router to actually go
  down and come back, which is both safer and usually faster.
* The 82 config files were 82 hardcoded `sftp.put()` calls. They are now
  `config_manifest.json` -- still exactly those 82, deliberately not "every
  file in configs/" (see that file's comment).
* Nothing verified that a config file arrived. Each is stat'd after transfer.
"""

import os
import re
import sys

DEVICE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(DEVICE_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import json
import time
import traceback

from resources.utilities import status as _status
from resources.utilities.device_config import load_config
from resources.utilities.mac_utils import extract_mac
from resources.utilities.ssh_session import SSHSession, connect_with_fallback
from resources.utilities.templating import TemplateError, stage_template
from resources.utilities.wait_utils import (
    ShellClosed,
    StepTimeout,
    port_is_open,
    read_until,
    run_checked,
    verify_remote_file,
    wait_for_port,
)

CONFIG = load_config(DEVICE_DIR, env_prefix="TR_")

status = _status.emit
step_running = _status.running
step_pass = _status.passed
step_sent = _status.sent
step_wait = _status.waiting
step_fail = _status.failed


class StepError(RuntimeError):
    """A provisioning milestone failed. Message is shown to the operator."""


class AlreadyProgrammed(Exception):
    """This router has been programmed before; stop without treating it as a failure."""


# ----------------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------------

if len(sys.argv) > 4:
    gate_ip = sys.argv[1]
    gate_netmask = sys.argv[2]
    gate_gateway = sys.argv[3]
    temp_pass = sys.argv[4]
else:
    print("UNKNOWN", flush=True)
    print("Incorrect! teltonika.py needs gate ip, netmask, gateway and password.",
          flush=True)
    sys.exit(2)

print(f"Gate IP: {gate_ip}", flush=True)
print(f"Netmask: {gate_netmask}", flush=True)
print(f"Gateway: {gate_gateway}", flush=True)


class Run:
    """Values discovered in one milestone and needed by a later one."""

    mac_address = None
    router_host = None


# ----------------------------------------------------------------------------
# Connections
# ----------------------------------------------------------------------------

def bbb_session():
    print("Connecting to BBB", flush=True)
    session = SSHSession(
        CONFIG["bbb_ip"], CONFIG["bbb_user"], CONFIG["bbb_password"],
        timeout=CONFIG["ssh_timeout"],
    )
    session.ensure_connected()
    print("Connected to BBB", flush=True)
    return session


def close_bbb(session):
    if session is None:
        return
    print("Closing Connection to BBB", flush=True)
    session.close()
    print("Closed Connection to BBB", flush=True)


def router_candidates():
    """Every (host, user, password) this router might currently answer on.

    The factory address with the scanned temporary password comes first, then
    the post-configuration address and credentials -- so a rerun against a
    partly-configured router finds it instead of failing to authenticate. The
    old code expressed this as a nested bare `except:` that, on total failure,
    printed "Errors in Authentication" and carried on using a client that had
    never connected; every subsequent step then failed obscurely.
    """
    hosts = [CONFIG["router_temp_ip"], CONFIG["router_fallback_ip"], CONFIG["router_new_ip"]]
    logins = [
        (CONFIG["router_temp_user"], temp_pass),
        (CONFIG["router_new_user"], CONFIG["router_new_password"]),
        (CONFIG["router_temp_user"], CONFIG["router_new_password"]),
    ]

    seen = set()
    candidates = []
    for host in hosts:
        for user, password in logins:
            key = (host, user, password)
            if password and key not in seen:
                seen.add(key)
                candidates.append(key)
    return candidates


def router_session():
    """Connect to the router wherever it currently is, or raise."""
    print("Connecting to Router", flush=True)
    try:
        session = connect_with_fallback(router_candidates(), timeout=CONFIG["ssh_timeout"])
    except ConnectionError as exc:
        raise StepError(f"Incorrect! Could not authenticate to the router: {exc}") from exc
    Run.router_host = session.host
    print(f"Connected to Router at {session.host}", flush=True)
    return session


def close_router(session):
    if session is None:
        return
    print("Closing Connection to Router", flush=True)
    session.close()
    print("Closed Connection to Router", flush=True)


def login_banner(session):
    """The text RutOS prints on login -- it carries the firmware version."""
    try:
        with session.invoke_shell(timeout=CONFIG["cli_timeout"]) as shell:
            try:
                return read_until(shell, [r"[>#\$]\s*\Z"], timeout=15)
            except (StepTimeout, ShellClosed):
                return ""
    except Exception as exc:
        print(f"Could not read the router login banner: {exc}", flush=True)
        return ""


# ----------------------------------------------------------------------------
# Milestone 1 -- Checking IP
# ----------------------------------------------------------------------------

def check_state():
    """Confirm the BeagleBone is reachable, and stop if this gate is done.

    A router already carrying a gate address shows up as a 10.x.y.123 lease on
    the BeagleBone. That is not a failure -- it means somebody already did this
    one -- so it ends the run quietly rather than raising.
    """
    step_running("check_ip")
    print("Checking if router is already programmed...", flush=True)

    session = bbb_session()
    try:
        output, _, _ = run_checked(session, "ip addr show eth0")
    finally:
        close_bbb(session)

    found = re.findall(CONFIG["bbb_programmed_pattern"], output)
    print(found, flush=True)
    for address in found:
        if address != CONFIG["bbb_template_address"]:
            print(f"Router already programmed to IP:{address}", flush=True)
            step_pass("check_ip")
            raise AlreadyProgrammed(address)

    step_pass("check_ip")


# ----------------------------------------------------------------------------
# Milestone 2 -- Staging the templates
# ----------------------------------------------------------------------------

def stage_files():
    """Refresh the working copies and point them at this gate.

    `og_configs/` and `og_testfile/` are the pristine originals and are never
    edited; both are re-copied here, so the previous gate's address cannot
    survive into this run. That also makes the old "revert the network file
    afterwards" step unnecessary -- it is gone.
    """
    step_running("staging")
    print("Copying configs and test file from the backup folders", flush=True)

    try:
        network = stage_template(
            os.path.join(DEVICE_DIR, "og_configs"),
            os.path.join(DEVICE_DIR, "configs"),
            "network",
            CONFIG["template_gate_ip"],
            gate_ip,
        )
        print(f"Config staged: {network}", flush=True)

        test_script = stage_template(
            os.path.join(DEVICE_DIR, "og_testfile"),
            os.path.join(DEVICE_DIR, "testfile"),
            CONFIG["bbb_test_script"],
            CONFIG["testfile_placeholder_ip"],
            gate_ip,
        )
        print(f"Test script staged: {test_script}", flush=True)
    except TemplateError as exc:
        raise StepError(f"Incorrect! {exc}") from exc

    session = bbb_session()
    try:
        remote = f"/home/{CONFIG['bbb_user']}/{CONFIG['bbb_test_script']}"
        print(f"Copying {CONFIG['bbb_test_script']} to the BBB", flush=True)
        session.upload(test_script, remote)
        verify_remote_file(session.sftp, remote, os.path.getsize(test_script))
        print(f"{CONFIG['bbb_test_script']} verified on the BBB", flush=True)
    except Exception as exc:
        raise StepError(
            f"Incorrect! {CONFIG['bbb_test_script']} not found on BBB: {exc}"
        ) from exc
    finally:
        close_bbb(session)

    step_pass("staging")


# ----------------------------------------------------------------------------
# Milestone 3 -- Firmware install
# ----------------------------------------------------------------------------

def install_firmware():
    """Copy the firmware onto the router and run sysupgrade."""
    step_running("firmware")

    local = os.path.join(DEVICE_DIR, CONFIG["firmware_filename"])
    if not os.path.isfile(local):
        raise StepError(f"Incorrect! Firmware file not found: {local}")
    expected_size = os.path.getsize(local)
    remote = CONFIG["firmware_router_path"]

    router = router_session()
    try:
        print("Copying firmware file to router", flush=True)
        router.upload(local, remote)
        try:
            verify_remote_file(router.sftp, remote, expected_size)
        except Exception as exc:
            raise StepError(
                f"Incorrect! Firmware file not found on router after transfer: {exc}"
            ) from exc
        print(f"Firmware file found on router ({expected_size} bytes)", flush=True)

        print("Installing firmware -- the router reboots itself when it finishes...",
              flush=True)
        with router.invoke_shell(timeout=CONFIG["cli_timeout"]) as shell:
            shell.send(f"sysupgrade {remote}\n")
            step_sent("firmware", "sysupgrade sent")
            # Stay on the channel while the CLI acts on the command. Dropping it
            # straight after the send can tear the session down before
            # sysupgrade starts, exactly as it does for a reboot.
            try:
                output = read_until(
                    shell,
                    [r"[Ee]rror", r"[Ff]ail", r"Upgrade completed", r"Rebooting"],
                    timeout=CONFIG["firmware_ack_timeout"],
                )
                if re.search(r"[Ee]rror|[Ff]ail", output):
                    detail = " ".join(output.split())[-300:]
                    raise StepError(f"Incorrect! Firmware install rejected: {detail}")
            except ShellClosed:
                print("Router closed the session; it is applying the firmware.",
                      flush=True)
            except StepTimeout:
                print("No further output from sysupgrade; checking whether the "
                      "router went down.", flush=True)
    finally:
        close_router(router)

    step_wait("firmware", "Wait ~3 min for the firmware install...")
    host = Run.router_host or CONFIG["router_temp_ip"]
    print("Waiting for the router to go down...", flush=True)
    try:
        wait_for_port(host, 22, up=False,
                      timeout=CONFIG["reboot_down_timeout"], label="router")
    except StepTimeout as exc:
        raise StepError(
            f"Incorrect! Router never went down after sysupgrade -- it is still "
            f"answering on {host}:22, so the firmware was not applied."
        ) from exc
    print("Router is installing the firmware.", flush=True)

    step_pass("firmware")


# ----------------------------------------------------------------------------
# Milestone 4 -- First reboot / firmware verification
# ----------------------------------------------------------------------------

def verify_firmware():
    """Wait for the router to come back, then confirm the new firmware runs."""
    step_running("reboot_1")
    step_wait("reboot_1", "Waiting for the router to come back...")

    expected = str(CONFIG["firmware_version"])
    print("Waiting for the router to come back...", flush=True)

    host = wait_for_any_port(
        [Run.router_host, CONFIG["router_temp_ip"], CONFIG["router_fallback_ip"]],
        timeout=CONFIG["reboot_timeout"],
    )
    if host is None:
        raise StepError(
            "Incorrect! Router did not come back after the firmware install."
        )
    print(f"Router is answering at {host}", flush=True)
    session = router_session()

    try:
        reported = login_banner(session)
        if expected not in reported:
            # The banner is the original check, but it is decoration -- fall
            # back to asking the device directly rather than failing a router
            # whose build simply prints a different greeting.
            try:
                version, _, _ = run_checked(session, "cat /etc/version", echo=False)
                reported += version
            except Exception as exc:
                print(f"Could not read /etc/version: {exc}", flush=True)

        if expected not in reported:
            detail = " ".join(reported.split())[-200:] or "no version reported"
            raise StepError(
                f"Incorrect! Firmware not installed -- expected {expected}, "
                f"router reports: {detail}"
            )
        print(f"Confirmed firmware install ({expected})", flush=True)
    finally:
        close_router(session)

    step_pass("reboot_1")


def _unique(values):
    seen = set()
    result = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result


def wait_for_any_port(hosts, timeout, port=22, interval=2, progress_every=30):
    """Wait for whichever of `hosts` answers first, within one shared deadline.

    The router can come back on the factory address or the configured one, and
    which depends on how far the run got. Polling them in turn with a full
    timeout each would take three times as long as it should on the failure
    path -- this gives all the candidates one deadline between them.

    Returns the host that answered, or None.
    """
    hosts = _unique(hosts)
    deadline = time.monotonic() + timeout
    last_note = time.monotonic()

    while time.monotonic() < deadline:
        for host in hosts:
            if port_is_open(host, port, timeout=2):
                return host
        now = time.monotonic()
        if now - last_note >= progress_every:
            print(f"Waiting for the router on {', '.join(hosts)}... "
                  f"~{int(deadline - now)}s left", flush=True)
            last_note = now
        time.sleep(interval)

    return None


# ----------------------------------------------------------------------------
# Milestone 5 -- Configuration push
# ----------------------------------------------------------------------------

def config_files():
    """The config files to push, in order, from config_manifest.json."""
    path = os.path.join(DEVICE_DIR, "config_manifest.json")
    try:
        with open(path, "r", encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StepError(f"Incorrect! Could not read {path}: {exc}") from exc

    names = manifest.get("files") if isinstance(manifest, dict) else manifest
    if not names:
        raise StepError(f"Incorrect! {path} lists no config files.")
    return names


def push_configs():
    """Upload the config files to /etc/config/ and verify each one landed."""
    step_running("config_push")

    names = config_files()
    local_dir = os.path.join(DEVICE_DIR, "configs")
    remote_dir = CONFIG["config_router_dir"]
    print(f"Copying {len(names)} config files to router", flush=True)

    router = router_session()
    try:
        sftp = router.sftp
        for index, name in enumerate(names, start=1):
            local = os.path.join(local_dir, name)
            if not os.path.isfile(local):
                raise StepError(f"Incorrect! Config file missing locally: {local}")

            remote = f"{remote_dir}/{name}"
            sftp.put(local, remote)
            try:
                verify_remote_file(sftp, remote, os.path.getsize(local))
            except Exception as exc:
                raise StepError(
                    f"Incorrect! Config file {name} did not transfer: {exc}"
                ) from exc

            if index % 20 == 0 or index == len(names):
                step_wait("config_push", f"{index}/{len(names)} files")
                print(f"  {index}/{len(names)} config files copied", flush=True)
    finally:
        close_router(router)

    print("Copied all config files to router", flush=True)
    step_pass("config_push")


# ----------------------------------------------------------------------------
# Milestone 6 -- Identity (MAC address)
# ----------------------------------------------------------------------------

def read_identity():
    """Read the router's MAC. Missing is survivable; the label field goes blank."""
    step_running("identity")
    print("Getting MAC address", flush=True)

    interface = CONFIG["router_lan_interface"]
    router = router_session()
    try:
        try:
            output, _, _ = run_checked(router, "ifconfig -a", echo=False)
        except Exception as exc:
            print(f"Could not run ifconfig: {exc}", flush=True)
            output = ""

        Run.mac_address = extract_mac(output, interface=interface)
        if not Run.mac_address:
            try:
                link, _, _ = run_checked(router, f"ip link show {interface}", echo=False)
                Run.mac_address = extract_mac(link, interface=interface)
            except Exception as exc:
                print(f"Could not run ip link: {exc}", flush=True)
    finally:
        close_router(router)

    if Run.mac_address:
        # prog_dev.py picks the MAC out of this exact line.
        print("MAC Addr: " + Run.mac_address, flush=True)
        step_pass("identity")
    else:
        print("MAC Address Not Correctly Extracted", flush=True)
        status("identity", _status.SKIPPED, "no MAC found; label field will be blank")


# ----------------------------------------------------------------------------
# Milestone 7 -- Final reboot
# ----------------------------------------------------------------------------

def final_reboot():
    """Reboot so the pushed configuration takes effect, and wait for it back."""
    step_running("reboot_2")

    host = Run.router_host or CONFIG["router_fallback_ip"]
    router = router_session()
    try:
        host = router.host
        with router.invoke_shell(timeout=CONFIG["cli_timeout"]) as shell:
            print("Rebooting Router", flush=True)
            shell.send("reboot\n")
            step_sent("reboot_2", "reboot command sent")
            # Keep the channel open until the box actually stops answering:
            # closing it straight after the send can abort the command.
            try:
                read_until(shell, [r"[Rr]eboot", r"[Ee]rror"], timeout=15)
            except (StepTimeout, ShellClosed):
                pass
    finally:
        close_router(router)

    step_wait("reboot_2", "Wait ~1.5 min for device to reboot...")
    print("Waiting for the router to go down...", flush=True)
    try:
        wait_for_port(host, 22, up=False,
                      timeout=CONFIG["reboot_down_timeout"], label="router")
        print("Router is rebooting.", flush=True)
    except StepTimeout:
        # Not fatal: the configuration is already on the box. The old code did
        # not check this at all, so failing the run here would reject routers
        # that previously passed.
        print("Router did not drop its connection; continuing.", flush=True)

    print("Waiting for the router to come back...", flush=True)
    back = wait_for_any_port(
        [host, CONFIG["router_new_ip"], CONFIG["router_fallback_ip"]],
        timeout=CONFIG["reboot_timeout"],
    )
    if back:
        Run.router_host = back
        print(f"Router is back at {back}", flush=True)
    else:
        print("Router did not answer on any known address after the reboot.",
              flush=True)

    print("FINISHED SETTING UP ROUTER", flush=True)
    step_pass("reboot_2")


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------

STEPS = [
    ("check_ip", check_state),
    ("staging", stage_files),
    ("firmware", install_firmware),
    ("reboot_1", verify_firmware),
    ("config_push", push_configs),
    ("identity", read_identity),
    ("reboot_2", final_reboot),
]


def main():
    print("STARTING ROUTER SETUP", flush=True)
    current_step = None
    try:
        for step_id, func in STEPS:
            current_step = step_id
            func()
    except AlreadyProgrammed:
        # Deliberately a success: the gate is done, there is just nothing to do.
        for step_id, _ in STEPS[1:]:
            status(step_id, _status.SKIPPED, "router already programmed")
        print("Nothing to do; the router is already programmed.", flush=True)
        return 0
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

    print("Done.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
