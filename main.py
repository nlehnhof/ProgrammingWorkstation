# main.py
import sys
from PyQt5.QtWidgets import QApplication
from pages.add_device_page import AddDevice
from pages.program_page import ProgramPage
from manager import DeviceManager
from pages.home_page import HomePage
from pages.main_window import MainPage
from PyQt5.QtGui import QPalette, QColor, QFont

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # or "Windows" for Windows-native look
    # app.setPalette(QPalette(QColor("#97BFE1"), QColor("#0B0000")))
    app.setStyleSheet("""
        QWidget { background: #FFFFFF; color: #0B0000; }
        QPushButton { background: #4CAF50; color: white; }
        QPushButton:hover { background: #45a049; }
    """)
    app.setFont(QFont("Helvetica", 10))
    window = MainPage()
    window.resize(600,400)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()