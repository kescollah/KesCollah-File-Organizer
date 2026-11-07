"""Modern sidebar navigation menu for KesCollah File Organizer.
Features pill-shaped active buttons, glowing indicators, category badges, and live status monitor.
"""

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QButtonGroup, QScrollArea
)
from config import APP_NAME, APP_SUBTITLE, APP_VERSION


class NavButton(QPushButton):
    """Pill-styled navigation button with active accent line."""
    def __init__(self, icon_text: str, label_text: str, view_index: int, parent=None):
        super().__init__(f"  {icon_text}   {label_text}", parent)
        self.view_index = view_index
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(44)
        self.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-left: 3px solid transparent;
                border-radius: 8px;
                text-align: left;
                padding-left: 14px;
                font-size: 13px;
                font-weight: 600;
                color: #94A3B8;
            }
            QPushButton:hover {
                background-color: #171C28;
                color: #F8FAFC;
            }
            QPushButton:checked {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E2638, stop:1 #141926);
                border-left: 3px solid #00E5FF;
                color: #00E5FF;
                font-weight: 700;
            }
        """)


class Sidebar(QWidget):
    navigation_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(246)
        self.setStyleSheet("background-color: #0E1119; border-right: 1px solid #1C2332;")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 16, 12, 14)
        layout.setSpacing(4)

        # 1. Brand Header
        brand_frame = QFrame()
        brand_frame.setStyleSheet("background: transparent; border: none;")
        brand_layout = QVBoxLayout(brand_frame)
        brand_layout.setContentsMargins(4, 0, 4, 12)
        brand_layout.setSpacing(2)

        app_title = QLabel("⚡ KesCollah")
        app_title.setObjectName("appTitle")
        brand_layout.addWidget(app_title)

        app_sub = QLabel(f"v{APP_VERSION} • FILE ORGANIZER")
        app_sub.setObjectName("appSubtitle")
        brand_layout.addWidget(app_sub)

        layout.addWidget(brand_frame)

        # Subtle separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1C2332; max-height: 1px; border: none; margin-bottom: 6px;")
        layout.addWidget(sep)

        # Section Label
        nav_lbl = QLabel("MODULES")
        nav_lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 700; letter-spacing: 1px; padding-left: 8px; margin-bottom: 2px;")
        layout.addWidget(nav_lbl)

        # 2. Navigation Items
        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        self.btn_action = NavButton("⚡", "Action Center", 0)
        self.btn_gemini = NavButton("🧠", "Gemini AI Sync", 1)
        self.btn_dicts = NavButton("📚", "Context Dictionaries", 2)
        self.btn_size = NavButton("📊", "Size Analyzer", 3)
        self.btn_network = NavButton("📡", "Network Tools", 4)
        self.btn_dups = NavButton("🔍", "Duplicate Finder", 5)
        self.btn_watchdog = NavButton("🛡️", "Folder Watchdog", 6)
        self.btn_help = NavButton("📖", "Help & Guide", 7)

        buttons = [
            self.btn_action,
            self.btn_gemini,
            self.btn_dicts,
            self.btn_size,
            self.btn_network,
            self.btn_dups,
            self.btn_watchdog,
            self.btn_help,
        ]

        for btn in buttons:
            self.button_group.addButton(btn, btn.view_index)
            btn.clicked.connect(lambda checked, idx=btn.view_index: self.navigation_requested.emit(idx))
            layout.addWidget(btn)

        # Default selection
        self.btn_action.setChecked(True)

        layout.addStretch()

        # 3. Bottom System Status Card
        status_card = QFrame()
        status_card.setStyleSheet("""
            QFrame {
                background-color: #131722;
                border: 1px solid #1F2637;
                border-radius: 8px;
                padding: 8px;
            }
        """)
        s_layout = QVBoxLayout(status_card)
        s_layout.setContentsMargins(8, 8, 8, 8)
        s_layout.setSpacing(4)

        status_title = QLabel("SYSTEM STATUS")
        status_title.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        s_layout.addWidget(status_title)

        # Mode Indicator
        self.lbl_mode = QLabel("⚡ 100% Offline Core")
        self.lbl_mode.setStyleSheet("color: #34D399; font-size: 11px; font-weight: 600;")
        s_layout.addWidget(self.lbl_mode)

        # Watchdog status
        self.lbl_watchdog = QLabel("🛡️ Watchdog: Idle")
        self.lbl_watchdog.setStyleSheet("color: #94A3B8; font-size: 11px;")
        s_layout.addWidget(self.lbl_watchdog)

        layout.addWidget(status_card)

    def set_watchdog_active(self, active: bool, status_text: str = ""):
        if active:
            self.lbl_watchdog.setText("🛡️ Watchdog: Active")
            self.lbl_watchdog.setStyleSheet("color: #00E5FF; font-weight: 600;")
        else:
            self.lbl_watchdog.setText("🛡️ Watchdog: Idle")
            self.lbl_watchdog.setStyleSheet("color: #94A3B8;")
