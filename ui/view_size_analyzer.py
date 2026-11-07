"""Folder Size Analyzer: Identify space hogs sorted in descending order by default.
Features clickable navigation breadcrumbs, dedicated 'Up to Parent Directory' button,
Back/Forward history, and columns for Name, Size (dynamic KB/MB/GB), Type, and Last Modified.
"""

import os
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog, QProgressBar, QMessageBox, QScrollArea
)

from core.size_analyzer import scan_directory_space_hogs, DiskItem
from config import format_bytes, get_windows_profile_directories


class SizeScanWorker(QThread):
    progress_updated = pyqtSignal(int, int, str)
    scan_finished = pyqtSignal(list, int)

    def __init__(self, target_dir: str, parent=None):
        super().__init__(parent)
        self.target_dir = target_dir

    def run(self):
        items, total_bytes = scan_directory_space_hogs(
            self.target_dir,
            progress_callback=lambda cur, tot, name: self.progress_updated.emit(cur, tot, name)
        )
        self.scan_finished.emit(items, total_bytes)


class BreadcrumbBar(QWidget):
    """Clickable breadcrumbs bar for quick folder hierarchy navigation."""
    path_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(4, 4, 4, 4)
        self.layout.setSpacing(4)

    def set_path(self, full_path: str):
        # Clear existing buttons
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        norm_path = os.path.abspath(full_path)
        parts = Path(norm_path).parts

        accum = ""
        for idx, part in enumerate(parts):
            if idx == 0:
                accum = part
            else:
                accum = os.path.join(accum, part)

            btn = QPushButton(part.replace("\\", "") or "Root")
            btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
            target_p = accum
            btn.clicked.connect(lambda checked, p=target_p: self.path_selected.emit(p))

            if idx == len(parts) - 1:
                # Active leaf segment
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #1E293B;
                        color: #00E5FF;
                        border: 1px solid #00B4D8;
                        border-radius: 5px;
                        padding: 3px 8px;
                        font-weight: 700;
                        font-size: 11px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #94A3B8;
                        border: none;
                        padding: 3px 6px;
                        font-size: 11px;
                    }
                    QPushButton:hover {
                        color: #F8FAFC;
                        background-color: #171D28;
                        border-radius: 4px;
                    }
                """)
            self.layout.addWidget(btn)

            if idx < len(parts) - 1:
                sep = QLabel("›")
                sep.setStyleSheet("color: #64748B; font-weight: bold;")
                self.layout.addWidget(sep)

        self.layout.addStretch()


class SizeAnalyzerView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir = os.path.abspath(".")
        self.history_back = []
        self.history_forward = []
        self.items: list[DiskItem] = []
        self.total_bytes = 0
        self.worker: SizeScanWorker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Folder Size Analyzer — Disk Space Explorer")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "Scans directory items and displays them sorted descending by size (largest at top). "
            "Double-click any folder to drill down; use clickable breadcrumbs or Up button to navigate."
        )
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Directory Selector Card with Navigation Controls
        dir_card = QFrame()
        dir_card.setObjectName("cardFrame")
        dir_layout = QHBoxLayout(dir_card)
        dir_layout.setContentsMargins(14, 8, 14, 8)
        dir_layout.setSpacing(8)

        # Navigation Buttons
        self.btn_back = QPushButton("◀ Back")
        self.btn_back.setToolTip("Go back to previous directory in history")
        self.btn_back.setEnabled(False)
        self.btn_back.clicked.connect(self.navigate_back)
        dir_layout.addWidget(self.btn_back)

        self.btn_forward = QPushButton("▶ Forward")
        self.btn_forward.setToolTip("Go forward in history")
        self.btn_forward.setEnabled(False)
        self.btn_forward.clicked.connect(self.navigate_forward)
        dir_layout.addWidget(self.btn_forward)

        self.btn_up = QPushButton("⬆️ Up to Parent Directory")
        self.btn_up.setObjectName("actionButton")
        self.btn_up.setToolTip("Go up one level to the parent directory")
        self.btn_up.clicked.connect(self.navigate_up)
        dir_layout.addWidget(self.btn_up)

        dir_lbl = QLabel("Directory:")
        dir_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; margin-left: 4px;")
        dir_layout.addWidget(dir_lbl)

        self.dir_input = QLineEdit(self.target_dir)
        self.dir_input.returnPressed.connect(self.start_scan)
        dir_layout.addWidget(self.dir_input, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)

        self.btn_scan = QPushButton("🔍 Scan Folder")
        self.btn_scan.setObjectName("primaryButton")
        self.btn_scan.clicked.connect(self.start_scan)
        dir_layout.addWidget(self.btn_scan)

        layout.addWidget(dir_card)

        # 3. Clickable Breadcrumb Bar Card
        bc_card = QFrame()
        bc_card.setObjectName("cardFrame")
        bc_card.setStyleSheet("background-color: #10141F; border: 1px solid #1C2436; border-radius: 6px;")
        bc_layout = QHBoxLayout(bc_card)
        bc_layout.setContentsMargins(8, 2, 8, 2)

        lbl_bc = QLabel("Path:")
        lbl_bc.setStyleSheet("color: #64748B; font-weight: 700; font-size: 11px;")
        bc_layout.addWidget(lbl_bc)

        self.breadcrumbs = BreadcrumbBar(self)
        self.breadcrumbs.path_selected.connect(self.set_directory)
        bc_layout.addWidget(self.breadcrumbs, 1)

        layout.addWidget(bc_card)

        # 4. Metric Strip
        stats_frame = QFrame()
        stats_frame.setObjectName("elevatedCard")
        stat_layout = QHBoxLayout(stats_frame)
        stat_layout.setContentsMargins(16, 10, 16, 10)

        def make_stat(lbl, initial="0", color="#00E5FF"):
            box = QVBoxLayout()
            l = QLabel(lbl)
            l.setObjectName("statLabel")
            v = QLabel(initial)
            v.setObjectName("statNumber")
            v.setStyleSheet(f"color: {color};")
            box.addWidget(l)
            box.addWidget(v)
            stat_layout.addLayout(box)
            return v

        self.stat_items = make_stat("Scanned Items", "0", "#00E5FF")
        self.stat_total_size = make_stat("Total Directory Volume", "0 B", "#8B5CF6")
        self.stat_largest = make_stat("Top Space Hog", "—", "#F59E0B")
        stat_layout.addStretch()

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.start_scan)
        stat_layout.addWidget(btn_refresh)

        layout.addWidget(stats_frame)

        # 5. Tree / Table View
        # Required columns: Name, Size (dynamic KB/MB/GB), Type, Last Modified
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "Size", "Type", "Last Modified"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 160)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

        # 6. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Sync initial path
        self.set_directory(self.target_dir)

    def browse_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Folder to Analyze", self.target_dir)
        if chosen:
            self.set_directory(chosen)

    def set_directory(self, path: str, record_history: bool = True):
        norm = os.path.abspath(path)
        if record_history and norm != self.target_dir and os.path.isdir(self.target_dir):
            self.history_back.append(self.target_dir)
            self.history_forward.clear()

        self.target_dir = norm
        self.dir_input.setText(self.target_dir)
        self.breadcrumbs.set_path(self.target_dir)

        # Enable/Disable Up button
        parent = os.path.dirname(self.target_dir)
        self.btn_up.setEnabled(bool(parent and parent != self.target_dir and os.path.isdir(parent)))
        self.btn_back.setEnabled(len(self.history_back) > 0)
        self.btn_forward.setEnabled(len(self.history_forward) > 0)

        self.start_scan()

    def navigate_up(self):
        parent = os.path.dirname(self.target_dir)
        if parent and parent != self.target_dir and os.path.isdir(parent):
            self.set_directory(parent)

    def navigate_back(self):
        if self.history_back:
            prev = self.history_back.pop()
            self.history_forward.append(self.target_dir)
            self.set_directory(prev, record_history=False)

    def navigate_forward(self):
        if self.history_forward:
            nxt = self.history_forward.pop()
            self.history_back.append(self.target_dir)
            self.set_directory(nxt, record_history=False)

    def start_scan(self):
        target = self.dir_input.text().strip()
        if not os.path.isdir(target):
            self.status_message.emit(f"Invalid directory: {target}")
            return

        self.target_dir = os.path.abspath(target)
        self.breadcrumbs.set_path(self.target_dir)
        self.btn_scan.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self.status_message.emit(f"Scanning directory: {self.target_dir}...")

        self.worker = SizeScanWorker(self.target_dir, self)
        self.worker.progress_updated.connect(self._on_scan_progress)
        self.worker.scan_finished.connect(self._on_scan_finished)
        self.worker.start()

    def _on_scan_progress(self, current: int, total: int, item_name: str):
        self.status_message.emit(f"Analyzing sizes ({current}/{total}): {item_name}")

    def _on_scan_finished(self, items: list, total_bytes: int):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.items = items
        self.total_bytes = total_bytes

        # Strict descending sort by size_bytes (largest at top)
        self.items.sort(key=lambda x: x.size_bytes, reverse=True)

        self.stat_items.setText(str(len(self.items)))
        self.stat_total_size.setText(format_bytes(total_bytes))
        top_name = self.items[0].name if self.items else "—"
        self.stat_largest.setText(top_name[:20] + ("..." if len(top_name) > 20 else ""))

        # Populate table
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            icon = "📁 " if item.is_dir else "📄 "
            name_item = QTableWidgetItem(f"{icon}{item.name}")
            name_item.setData(Qt.ItemDataRole.UserRole, item)
            self.table.setItem(row, 0, name_item)

            # Formatted size
            pct = (item.size_bytes / total_bytes * 100) if total_bytes > 0 else 0
            size_item = QTableWidgetItem(f"{item.size_formatted} ({pct:.1f}%)")
            size_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 1, size_item)

            type_item = QTableWidgetItem(item.item_type)
            self.table.setItem(row, 2, type_item)

            mod_item = QTableWidgetItem(item.modified_str)
            self.table.setItem(row, 3, mod_item)

        self.status_message.emit(
            f"Size scan complete: {len(self.items)} items in {self.target_dir} ({format_bytes(total_bytes)} total)."
        )

    def _on_row_double_clicked(self, row: int, col: int):
        item_widget = self.table.item(row, 0)
        if not item_widget:
            return
        disk_item: DiskItem = item_widget.data(Qt.ItemDataRole.UserRole)
        if disk_item and disk_item.is_dir and os.path.isdir(disk_item.full_path):
            self.set_directory(disk_item.full_path)
