"""Application entry point for KesCollah.
Modern, feature-rich desktop application built with PyQt6.
"""

import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow
from config import APP_NAME


def main():
    # Set Windows AppUserModelID so Windows groups the taskbar icon properly
    if os.name == "nt":
        try:
            myappid = "kesner.kescollah.zeroloosefiles.2.0"
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("KesnerDev")

    # High DPI font smoothing & attribute flags
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
