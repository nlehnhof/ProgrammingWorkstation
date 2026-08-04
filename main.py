# main.py
import os
import sys

from resources.utilities.app_paths import RUN_SCRIPT_FLAG, app_root

# Pin the working directory before anything else: the pages and device scripts
# resolve core/devices.json, logs/ and devices/{device}/... relative to it, and
# an elevated relaunch would otherwise start in C:\Windows\System32.
APP_ROOT = app_root()
os.chdir(APP_ROOT)


def _run_script_mode():
    """Run a device automation script instead of the GUI, then exit.

    Only used by a built exe. Frozen, `sys.executable` is this app rather than
    a Python interpreter, so prog_dev.py cannot spawn digix20.py directly --
    it re-invokes the app with this flag and the app plays interpreter.
    """
    import runpy

    script = sys.argv[2]
    sys.argv = [script] + sys.argv[3:]
    runpy.run_path(script, run_name="__main__")


if len(sys.argv) > 2 and sys.argv[1] == RUN_SCRIPT_FLAG:
    _run_script_mode()
    sys.exit(0)

from resources.utilities.elevate import ensure_admin
from PyQt5.QtWidgets import QApplication, QMessageBox
from pages.add_device_page import AddDevice
from pages.program_page import ProgramPage
from core.manager import DeviceManager
from pages.home_page import HomePage
from pages.main_window import MainPage
from PyQt5.QtGui import QPalette, QColor, QFont
import pages.error_log_page

def main():
    app = QApplication(sys.argv)

    # Programming a Digi IX20 changes this PC's network adapter, which needs
    # administrator rights. This relaunches elevated (UAC prompt) and exits;
    # if the operator declines, they can still run everything except the
    # 'Switching static IP' step.
    try:
        ensure_admin(working_dir=APP_ROOT)
    except PermissionError:
        answer = QMessageBox.warning(
            None,
            "Administrator Access Declined",
            "Without administrator rights the 'Switching static IP' step will "
            "fail, so a Digi IX20 cannot be fully programmed.\n\n"
            "Continue anyway?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
    except OSError as exc:
        QMessageBox.warning(
            None,
            "Could Not Restart as Administrator",
            f"{exc}\n\nContinuing without administrator rights.",
        )

    app.setStyle("Fusion")  # or "Windows" for Windows-native look
    # app.setPalette(QPalette(QColor("#97BFE1"), QColor("#0B0000")))
    app.setStyleSheet("""
        QWidget { background: #FFFFFF; color: #0B0000; }
        QPushButton { background: #4CAF50; color: white; }
        QPushButton:hover { background: #45a049; }
        QPushButton:disabled { background: lightgray;}
    """)
    app.setFont(QFont("Helvetica", 10))
    window = MainPage()
    window.resize(1000,600)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()