"""Main Application Window for KesCollah File Organizer.
Integrates Sidebar navigation, QStackedWidget views, and System Tray icon.
"""

import os
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QStackedWidget, QStatusBar, QLabel, QSystemTrayIcon,
    QMenu, QMessageBox
)

from config import APP_NAME, APP_VERSION
from core.watchdog_service import FolderWatchdogService
from ui.style import KESCOLLAH_QSS
from ui.sidebar import Sidebar
from ui.view_action_center import ActionCenterView
from ui.view_gemini_sync import GeminiSyncView
from ui.view_dictionaries import DictionaryManagerView
from ui.view_size_analyzer import SizeAnalyzerView
from ui.view_network_tools import NetworkToolsView
from ui.view_duplicates import DuplicateFinderView
from ui.view_watchdog import WatchdogView
from ui.view_help import HelpView


def create_app_icon() -> QIcon:
    """Return app icon from assets/icon.ico or assets/icon.png, with programmatic fallback."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ico_path = os.path.join(base_dir, "assets", "icon.ico")
    png_path = os.path.join(base_dir, "assets", "icon.png")

    if os.path.isfile(ico_path):
        return QIcon(ico_path)
    if os.path.isfile(png_path):
        return QIcon(png_path)

    # Programmatic fallback
    pix = QPixmap(64, 64)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    # Background rounded square
    painter.setBrush(QColor("#00B4D8"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(4, 4, 56, 56, 12, 12)

    # Inner lightning bolt
    painter.setBrush(QColor("#0B0D14"))
    from PyQt6.QtGui import QPolygonF
    from PyQt6.QtCore import QPointF
    points = [
        QPointF(34, 12),
        QPointF(20, 34),
        QPointF(32, 34),
        QPointF(28, 52),
        QPointF(46, 28),
        QPointF(34, 28),
    ]
    painter.drawPolygon(QPolygonF(points))
    painter.end()
    return QIcon(pix)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.resize(1380, 860)
        self.setMinimumSize(1080, 680)

        # Set application icon
        self.app_icon = create_app_icon()
        self.setWindowIcon(self.app_icon)

        # Shared background Watchdog service
        self.watchdog_service = FolderWatchdogService(self)

        # Apply custom modern theme
        self.setStyleSheet(KESCOLLAH_QSS)

        # Build UI layout
        self._init_ui()

        # Setup System Tray
        self._init_system_tray()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Navigation Sidebar
        self.sidebar = Sidebar(self)
        self.sidebar.navigation_requested.connect(self._on_navigate)
        main_layout.addWidget(self.sidebar)

        # 2. Content Stack
        content_container = QWidget()
        content_layout = QVBoxLayout(content_container)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()

        # View 0: Action Center (Zero Loose Files)
        self.view_action = ActionCenterView(self)
        self.view_action.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_action)

        # View 1: Gemini AI Knowledge Sync (The Brain & Caching System)
        self.view_gemini = GeminiSyncView(self)
        self.view_gemini.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_gemini)

        # View 2: Context Dictionaries (Static Rules & AI-Learned Rules)
        self.view_dicts = DictionaryManagerView(self)
        self.view_dicts.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_dicts)

        # View 3: Size Analyzer (Space Hog Tree, Breadcrumbs, Parent return)
        self.view_size = SizeAnalyzerView(self)
        self.view_size.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_size)

        # View 4: Network Tools (Passive Wi-Fi Analyzer)
        self.view_network = NetworkToolsView(self)
        self.view_network.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_network)

        # View 5: Duplicate Finder (SHA-256)
        self.view_dups = DuplicateFinderView(self)
        self.view_dups.status_message.connect(self._show_status)
        self.stack.addWidget(self.view_dups)

        # View 6: Folder Watchdog (Real-time monitoring & Tray service)
        self.view_watchdog = WatchdogView(self.watchdog_service, self)
        self.view_watchdog.status_message.connect(self._show_status)
        self.view_watchdog.minimize_to_tray_requested.connect(self.hide_to_tray)
        self.stack.addWidget(self.view_watchdog)

        # View 7: Help & Architectural Guide
        self.view_help = HelpView(self)
        self.stack.addWidget(self.view_help)

        content_layout.addWidget(self.stack)
        main_layout.addWidget(content_container, 1)

        # 3. Status Bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        self.status_label = QLabel("Ready • KesCollah Zero Loose Files loaded")
        self.status_label.setStyleSheet("color: #94A3B8; font-size: 12px; padding-left: 10px;")
        self.status_bar.addWidget(self.status_label, 1)

        # Connect Watchdog status updates to sidebar
        self.watchdog_service.status_changed.connect(self.sidebar.set_watchdog_active)
        self.watchdog_service.organization_completed.connect(self._on_watchdog_cleanup)

    def _init_system_tray(self):
        """Configure Windows System Tray icon and context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.tray_icon = QSystemTrayIcon(self.app_icon, self)
        self.tray_icon.setToolTip(f"{APP_NAME} — Active Background Organizer")

        tray_menu = QMenu()

        action_show = QAction("Open KesCollah", self)
        action_show.triggered.connect(self.show_from_tray)
        tray_menu.addAction(action_show)

        action_action_center = QAction("⚡ Action Center", self)
        action_action_center.triggered.connect(lambda: self._navigate_and_show(0))
        tray_menu.addAction(action_action_center)

        action_gemini = QAction("🧠 Gemini AI Sync", self)
        action_gemini.triggered.connect(lambda: self._navigate_and_show(1))
        tray_menu.addAction(action_gemini)

        action_dicts = QAction("📚 Context Dictionaries", self)
        action_dicts.triggered.connect(lambda: self._navigate_and_show(2))
        tray_menu.addAction(action_dicts)

        tray_menu.addSeparator()

        action_quit = QAction("Exit Application", self)
        action_quit.triggered.connect(self._quit_application)
        tray_menu.addAction(action_quit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.show()

    def _on_navigate(self, index: int):
        self.stack.setCurrentIndex(index)
        # When switching to Context Dictionaries or Gemini Sync, refresh their views
        if index == 1:
            self.view_gemini.refresh_queue()
        elif index == 2:
            self.view_dicts.load_all_dictionaries()

    def _navigate_and_show(self, index: int):
        btn = self.sidebar.button_group.button(index)
        if btn:
            btn.setChecked(True)
        self.stack.setCurrentIndex(index)
        self.show_from_tray()

    def _show_status(self, msg: str):
        self.status_label.setText(msg)

    def _on_watchdog_cleanup(self, moved_count: int, summary: str):
        self._show_status(summary)
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                f"{APP_NAME} Background Cleanup",
                summary,
                QSystemTrayIcon.MessageIcon.Information,
                3000
            )

    def hide_to_tray(self):
        self.hide()
        if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
            self.tray_icon.showMessage(
                f"{APP_NAME} Minimized",
                "KesCollah is actively running in the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000
            )

    def show_from_tray(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_from_tray()

    def _quit_application(self):
        self.watchdog_service.stop_watching()
        if hasattr(self, "tray_icon"):
            self.tray_icon.hide()
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    def closeEvent(self, event):
        """If watchdog is actively running, ask if user wants to minimize to tray."""
        if self.watchdog_service.is_running:
            reply = QMessageBox.question(
                self,
                "Watchdog Active",
                "Folder Watchdog is currently running in the background.\n\n"
                "Would you like to keep KesCollah running in the system tray?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Yes
            )
            if reply == QMessageBox.StandardButton.Yes:
                event.ignore()
                self.hide_to_tray()
                return
            elif reply == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return

        self._quit_application()
        event.accept()
