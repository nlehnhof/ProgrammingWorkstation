"""Relaunch the app with administrator rights when it doesn't have them.

The Digi IX20 flow reconfigures this PC's network adapter (New-NetIPAddress /
Remove-NetIPAddress), which Windows only permits for an elevated process.

Windows cannot grant privileges to a process that is already running, so the
only way to "become admin" is to start a fresh elevated process and exit this
one. ShellExecuteW with the "runas" verb is what raises the UAC prompt.

Note the working directory: an elevated process would otherwise start in
C:\\Windows\\System32, and this app resolves core/devices.json, logs/ and
devices/{device}/... relative to the current directory. lpDirectory pins it
back to the repo root.
"""

import ctypes
import os
import sys

# Passed to the relaunched copy so a machine where elevation silently fails
# can't bounce between UAC prompts forever.
ELEVATED_FLAG = "--elevated"

SW_SHOWNORMAL = 1
ERROR_CANCELLED = 1223


def is_admin():
    """True if this process is running elevated. False on any non-Windows OS."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


def _quote(arg):
    return f'"{arg}"' if (" " in arg or "\t" in arg) else arg


def _relaunch_command():
    """(executable, parameter string) for restarting this app."""
    args = list(sys.argv[1:])
    if ELEVATED_FLAG not in args:
        args.append(ELEVATED_FLAG)

    if getattr(sys, "frozen", False):
        # Packaged .exe -- sys.executable IS the app.
        return sys.executable, " ".join(_quote(a) for a in args)

    script = os.path.abspath(sys.argv[0])
    return sys.executable, " ".join(_quote(a) for a in [script] + args)


def relaunch_as_admin(working_dir=None):
    """Start an elevated copy of this app. Returns True if it was launched.

    Raises PermissionError if the operator dismissed the UAC prompt.
    """
    executable, params = _relaunch_command()
    directory = working_dir or os.path.dirname(os.path.abspath(sys.argv[0]))

    shell32 = ctypes.windll.shell32  # type: ignore[attr-defined]
    shell32.ShellExecuteW.restype = ctypes.c_void_p
    result = shell32.ShellExecuteW(
        None, "runas", executable, params, directory, SW_SHOWNORMAL
    )

    # ShellExecuteW returns > 32 on success; smaller values are error codes.
    code = int(result) if result is not None else 0
    if code > 32:
        return True
    if code == ERROR_CANCELLED:
        raise PermissionError("Administrator access was declined at the UAC prompt.")
    raise OSError(f"Could not relaunch as administrator (ShellExecuteW returned {code}).")


def ensure_admin(working_dir=None):
    """Relaunch elevated and exit, unless already elevated or already retried.

    Returns True if this process may continue, False if the caller should stop
    (it won't normally return False -- the process exits instead).
    """
    if os.name != "nt" or is_admin():
        return True

    if ELEVATED_FLAG in sys.argv:
        # We already tried once and still aren't admin. Carry on unelevated
        # rather than loop; the static-IP milestone will report the problem.
        print("Warning: running without administrator rights. "
              "The 'Switching static IP' step will fail.", flush=True)
        return True

    relaunch_as_admin(working_dir=working_dir)

    # os._exit skips atexit handlers -- error_log_page registers one that would
    # otherwise pop a log dialog from this process as it goes away.
    os._exit(0)
