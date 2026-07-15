# error_handler.py
import sys
import os
import datetime
import traceback
import threading
import asyncio
import subprocess
import atexit
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QApplication

# Global buffer for all output/errors
_output_buffer = []
_error_popup_shown = False  # Track if error popup has been shown

# Create logs directory
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

# Create a single timestamped crash log file for this run
RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"crash_log_{RUN_TIMESTAMP}.txt")


class LogDialog(QDialog):
    """Dialog to display collected output/errors and save them to a single crash log."""
    def __init__(self, title="Application Log", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 500)

        # Save all collected output/errors to crash log
        self.save_to_crash_log("\n".join(_output_buffer))

        layout = QVBoxLayout(self)

        text_area = QTextEdit(self)
        text_area.setReadOnly(True)
        text_area.setPlainText("\n".join(_output_buffer))
        layout.addWidget(text_area)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)  # Just close, don't exit app
        layout.addWidget(buttons)

    def save_to_crash_log(self, text):
        """Write all output/errors to the single crash log file for this run."""
        try:
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("=== Application Log ===\n")
                f.write(f"Run started: {RUN_TIMESTAMP}\n")
                f.write(f"{'-'*40}\n")
                f.write(text)
                f.write(f"\n{'-'*40}\n")
            sys.__stdout__.write(f"[INFO] Log saved: {LOG_FILE}\n") # type:ignore
        except Exception as e: 
            sys.__stderr__.write(f"[ERROR] Failed to save log: {e}\n") # type: ignore


def _collect_output(message, is_error=False):
    """Add output to buffer and show popup immediately if it's an error."""
    global _error_popup_shown
    _output_buffer.append(message)

    if is_error and not _error_popup_shown:
        _error_popup_shown = True
        app = QApplication.instance()
        if app is not None:
            dlg = LogDialog(title="Error Detected")
            dlg.exec_()  # Show popup but don't exit
        else:
            sys.__stdout__.write("\n".join(_output_buffer) + "\n") # type: ignore


# ---------------- Exception Hooks ----------------
def global_exception_hook(exctype, value, tb):
    error_msg = "".join(traceback.format_exception(exctype, value, tb))
    _collect_output(error_msg, is_error=True)
    sys.__excepthook__(exctype, value, tb)


def threading_exception_hook(args):
    error_msg = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))
    _collect_output(error_msg, is_error=True)


def asyncio_exception_handler(loop, context):
    msg = context.get("exception")
    if msg:
        error_msg = "".join(traceback.format_exception(type(msg), msg, msg.__traceback__))
    else:
        error_msg = context.get("message", "Unknown asyncio error")
    _collect_output(error_msg, is_error=True)


# ---------------- Output Capture ----------------
class StreamInterceptor:
    """Redirects stdout/stderr to also log output."""
    def __init__(self, original_stream, is_error=False):
        self.original_stream = original_stream
        self.is_error = is_error

    def write(self, message):
        if message.strip():
            _collect_output(message.strip(), is_error=self.is_error)
        self.original_stream.write(message)

    def flush(self):
        self.original_stream.flush()


# ---------------- Subprocess Wrapper ----------------
def safe_subprocess_run(*popenargs, **kwargs):
    """Wrapper for subprocess.run that auto-captures output/errors."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    try:
        result = subprocess.run(*popenargs, **kwargs, check=True)
        if result.stdout:
            _collect_output(result.stdout.strip())
        if result.stderr:
            _collect_output(result.stderr.strip(), is_error=True)
        return result
    except subprocess.CalledProcessError as e:
        if e.stdout:
            _collect_output(e.stdout.strip())
        if e.stderr:
            _collect_output(e.stderr.strip(), is_error=True)
        raise


# ---------------- Show Final Log at Exit ----------------
def _show_log_on_exit():
    """Show the collected log in a popup at program exit."""
    app = QApplication.instance()
    if app is not None:
        dlg = LogDialog(title="Final Application Log")
        dlg.exec_()
    else:
        sys.__stdout__.write("\n".join(_output_buffer) + "\n") # type: ignore


# ---------------- Install Hooks ----------------
def install_error_handler():
    sys.excepthook = global_exception_hook
    threading.excepthook = threading_exception_hook  # Python 3.8+
    sys.stderr = StreamInterceptor(sys.stderr, is_error=True)
    sys.stdout = StreamInterceptor(sys.stdout, is_error=False)

    try:
        loop = asyncio.get_event_loop()
        loop.set_exception_handler(asyncio_exception_handler)
    except RuntimeError:
        pass

    subprocess.run = safe_subprocess_run

    # Show log at exit
    atexit.register(_show_log_on_exit)


# Install immediately when imported
install_error_handler()
