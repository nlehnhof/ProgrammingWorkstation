"""The channel between a hardware script and the GUI.

A device's hardware script (`digix20.py`, `teltonika.py`) runs as a *subprocess*
of the app, so its stdout is the only way back. Two kinds of line come out of
it, and this module owns both ends of that conversation:

* **Milestones** -- machine-readable, for the Status checklist:

      ##STATUS##<step_id>|<state>|<detail>

  `step_id` matches an entry in that device's `checklist.json`, which is what
  turns a milestone into a row in the panel.

* **Everything else** -- human-readable output shown to the operator, which by
  convention marks a failure with "Incorrect!" and reports the device's MAC as
  "MAC Addr: ...".

Emitting, parsing and the loop that reads a running child all live here so the
format is defined once. When the emitting and parsing sides each carried their
own copy of the literal, a change to one silently stopped the other from
recognising anything.
"""

import subprocess
from collections import deque

PREFIX = "##STATUS##"
SEPARATOR = "|"

# States the Status panel understands (see pages/status_panel.py STATES).
PENDING = "PENDING"
RUNNING = "RUNNING"
PASS = "PASS"
FAIL = "FAIL"
SENT = "SENT"
WAIT = "WAIT"
SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Emitting -- used by the hardware scripts
# ---------------------------------------------------------------------------

def emit(step_id, state, detail=""):
    """Announce a milestone. flush=True because the parent reads us live."""
    print(f"{PREFIX}{step_id}{SEPARATOR}{state}{SEPARATOR}{detail}", flush=True)


def running(step_id):
    """This milestone has started; the panel begins its elapsed timer."""
    emit(step_id, RUNNING)


def passed(step_id, detail=""):
    emit(step_id, PASS, detail)


def failed(step_id, detail=""):
    emit(step_id, FAIL, detail)


def skipped(step_id, detail=""):
    """Deliberately not done -- neither a success nor a failure."""
    emit(step_id, SKIPPED, detail)


def sent(step_id, detail=""):
    """A momentary acknowledgement inside a running step."""
    emit(step_id, SENT, detail)


def waiting(step_id, detail=""):
    """A progress note under a running step, e.g. the reboot wait."""
    emit(step_id, WAIT, detail)


# ---------------------------------------------------------------------------
# Parsing -- used by prog_dev.py
# ---------------------------------------------------------------------------

def parse(line):
    """(step_id, state, detail) for a marker line, or None if it isn't one.

    Splits at most twice so a detail message containing "|" survives intact.
    """
    text = line.strip()
    if not text.startswith(PREFIX):
        return None

    parts = text[len(PREFIX):].split(SEPARATOR, 2)
    step_id = parts[0] if parts else ""
    state = parts[1] if len(parts) > 1 else ""
    detail = parts[2] if len(parts) > 2 else ""
    return step_id, state, detail


def forwarder(callback):
    """Wrap a GUI callback so a broken checklist can never kill a run.

    The callback crosses a thread boundary into Qt. Programming the hardware is
    the job; failing to draw a tick mark is not a reason to abandon a router
    mid-flash, so errors here are reported and swallowed.
    """
    def report(step_id, state, detail=""):
        if callback is None:
            return
        try:
            callback(step_id, state, detail)
        except Exception as exc:
            print(f"Could not update the status checklist: {exc}", flush=True)

    return report


# ---------------------------------------------------------------------------
# Watching a running hardware script
# ---------------------------------------------------------------------------

# Conventions both hardware scripts follow in their human-readable output.
FAILURE_MARKER = "Incorrect"
TRACEBACK_MARKER = "Traceback"
MAC_MARKER = "MAC Addr:"

CRASH_LOG_LINES = 200


def watch_process(command, report, log_lines=CRASH_LOG_LINES):
    """Run a hardware script and consume its output in a single pass.

    One pass matters. An earlier version looped over `process.stdout` twice --
    the first loop drained the pipe, so the second, which held all the failure
    detection and MAC capture, iterated over an exhausted stream and did
    nothing at all. Every run looked like a success.

    Forwards milestone markers to `report`, prints everything else for the
    operator, keeps a rolling buffer for the crash log, and watches for the
    failure/MAC conventions above.

    :returns: {"failed": bool, "detail": str|None, "mac": str|None,
               "log": list[str], "returncode": int}
    """
    log = deque(maxlen=log_lines)
    failed = False
    detail = None
    mac = None

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    with process.stdout:  # type: ignore[union-attr]
        for line in process.stdout:  # type: ignore[union-attr]
            marker = parse(line)
            if marker is not None:
                step_id, state, note = marker
                if state == FAIL:
                    failed = True
                    detail = note or detail
                report(step_id, state, note)
                continue  # markers are plumbing, not operator-facing output

            print(line, end="")
            statement = line.strip()
            log.append(statement)

            if FAILURE_MARKER in statement:
                failed = True
                detail = detail or statement
            if TRACEBACK_MARKER in statement:
                failed = True
            if MAC_MARKER in statement:
                mac = statement.split(MAC_MARKER)[1].strip()

    process.wait()
    if process.returncode != 0:
        failed = True
        detail = detail or f"{command[1] if len(command) > 1 else 'script'} " \
                           f"exited with code {process.returncode}"

    return {
        "failed": failed,
        "detail": detail,
        "mac": mac,
        "log": list(log),
        "returncode": process.returncode,
    }
