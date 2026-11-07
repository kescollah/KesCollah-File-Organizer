"""Folder Watchdog & System Tray View:
Monitors directories in the background using the offline JSON dictionaries,
provides options to minimize to system tray, and logs real-time file detection.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QFrame, QFileDialog,
    QPlainTextEdit, QMessageBox
)

from config import get_windows_profile_directories
from core.watchdog_service import FolderWatchdogService


class WatchdogView(QWidget):
    status_message = pyqtSignal(str)
    minimize_to_tray_requested = pyqtSignal()

    def __init__(self, watchdog_service: FolderWatchdogService, parent=None):
        super().__init__(parent)
        self.watchdog = watchdog_service
        self.target_dir = os.path.abspath(".")
        self._init_ui()

        # Connect watchdog signals
        self.watchdog.status_changed.connect(self._on_status_changed)
        self.watchdog.file_detected.connect(self._on_file_detected)
        self.watchdog.organization_completed.connect(self._on_cleanup_done)

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Folder Watchdog — Real-Time Background Automation")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "Monitors designated folders for incoming files and automatically executes offline "
            "Zero Loose Files organization using local semantic & learned rules. Can run quietly in the System Tray."
        )
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Windows Profile Quick Access
        p_card = QFrame()
        p_card.setObjectName("cardFrame")
        p_layout = QHBoxLayout(p_card)
        p_layout.setContentsMargins(12, 8, 12, 8)
        p_layout.setSpacing(8)

        p_lbl = QLabel("Watch Folder Shortcut:")
        p_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; font-size: 11px;")
        p_layout.addWidget(p_lbl)

        for name, path in get_windows_profile_directories().items():
            btn = QPushButton(f"📁 {name}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #171D2A;
                    border: 1px solid #263349;
                    border-radius: 6px;
                    padding: 4px 10px;
                    font-size: 11px;
                    color: #CBD5E1;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background-color: #212B3E;
                    border-color: #00E5FF;
                    color: #00E5FF;
                }
            """)
            btn.clicked.connect(lambda checked, p=path: self.set_directory(p))
            p_layout.addWidget(btn)

        p_layout.addStretch()
        layout.addWidget(p_card)

        # 3. Watchdog Controls Card
        dir_card = QFrame()
        dir_card.setObjectName("cardFrame")
        dir_layout = QHBoxLayout(dir_card)
        dir_layout.setContentsMargins(14, 10, 14, 10)
        dir_layout.setSpacing(10)

        dir_lbl = QLabel("Directory to Monitor:")
        dir_lbl.setStyleSheet("font-weight: 700; color: #94A3B8;")
        dir_layout.addWidget(dir_lbl)

        self.dir_input = QLineEdit(self.target_dir)
        dir_layout.addWidget(self.dir_input, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)

        self.btn_toggle_watch = QPushButton("▶ Start Watching")
        self.btn_toggle_watch.setObjectName("primaryButton")
        self.btn_toggle_watch.clicked.connect(self._toggle_watching)
        dir_layout.addWidget(self.btn_toggle_watch)

        self.btn_tray = QPushButton("🗔 Minimize to Tray")
        self.btn_tray.setToolTip("Keep KesCollah monitoring in the Windows system tray")
        self.btn_tray.clicked.connect(self.minimize_to_tray_requested.emit)
        dir_layout.addWidget(self.btn_tray)

        layout.addWidget(dir_card)

        # 4. Settings Card
        s_card = QFrame()
        s_card.setObjectName("cardFrame")
        s_layout = QHBoxLayout(s_card)
        s_layout.setContentsMargins(14, 8, 14, 8)
        s_layout.setSpacing(14)

        s_layout.addWidget(QLabel("Min Smart Group files:"))
        self.spin_min_smart = QSpinBox()
        self.spin_min_smart.setRange(2, 20)
        self.spin_min_smart.setValue(2)
        s_layout.addWidget(self.spin_min_smart)

        self.chk_dates = QCheckBox("Organize into Year/Month subfolders")
        self.chk_dates.setChecked(True)
        s_layout.addWidget(self.chk_dates)

        s_layout.addStretch()
        layout.addWidget(s_card)

        # 5. Live Activity Monitor / Event Log
        log_header = QHBoxLayout()
        lbl_log = QLabel("📜 Live Watchdog Activity Journal:")
        lbl_log.setStyleSheet("font-weight: 700; color: #CBD5E1; font-size: 12px;")
        log_header.addWidget(lbl_log)
        log_header.addStretch()

        btn_clear_log = QPushButton("Clear Log")
        btn_clear_log.clicked.connect(lambda: self.log_box.clear())
        log_header.addWidget(btn_clear_log)
        layout.addLayout(log_header)

        self.log_box = QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0B0E17;
                color: #A5F3FC;
                border: 1px solid #1C2332;
                border-radius: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                padding: 10px;
            }
        """)
        self.log_box.appendPlainText("Watchdog Service initialized. Idle.")
        layout.addWidget(self.log_box, 1)

    def set_directory(self, path: str):
        self.target_dir = os.path.abspath(path)
        self.dir_input.setText(self.target_dir)

    def browse_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Directory to Watch", self.target_dir)
        if chosen:
            self.set_directory(chosen)

    def _toggle_watching(self):
        if self.watchdog.is_running:
            self.watchdog.stop_watching()
        else:
            path = self.dir_input.text().strip()
            if not os.path.isdir(path):
                QMessageBox.warning(self, "Invalid Path", "Please select a valid folder to monitor.")
                return
            self.watchdog.start_watching(
                path,
                use_date_subfolders=self.chk_dates.isChecked(),
                min_smart_group=self.spin_min_smart.value()
            )

    def _on_status_changed(self, running: bool, msg: str):
        if running:
            self.btn_toggle_watch.setText("⏹ Stop Watching")
            self.btn_toggle_watch.setObjectName("dangerButton")
            self.btn_toggle_watch.setStyle(self.btn_toggle_watch.style())
            self.log_box.appendPlainText(f"[STATUS] 🟢 {msg}")
        else:
            self.btn_toggle_watch.setText("▶ Start Watching")
            self.btn_toggle_watch.setObjectName("primaryButton")
            self.btn_toggle_watch.setStyle(self.btn_toggle_watch.style())
            self.log_box.appendPlainText(f"[STATUS] ⚪ {msg}")
        self.status_message.emit(msg)

    def _on_file_detected(self, filename: str):
        self.log_box.appendPlainText(f"[DETECTED] New arrival: '{filename}' (debouncing...)")

    def _on_cleanup_done(self, count: int, summary: str):
        self.log_box.appendPlainText(f"[ORGANIZED] ⚡ {summary}")
