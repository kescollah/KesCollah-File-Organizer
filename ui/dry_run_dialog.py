"""Dry Run Simulation Modal Dialog.
Presents a complete breakdown of proposed directories, file moves, and conflict checks.
"""

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QPushButton, QFrame, QGridLayout
)
from core.operations import DryRunReport
from core.file_utils import format_file_size


class DryRunDialog(QDialog):
    def __init__(self, report: DryRunReport, parent=None):
        super().__init__(parent)
        self.report = report
        self.setWindowTitle("Dry Run Simulation — Proposed Move Plan")
        self.resize(860, 560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Title & Subtitle
        header_layout = QVBoxLayout()
        title = QLabel("Proposed Organization Plan (Simulation)")
        title.setObjectName("titleLabel")
        header_layout.addWidget(title)

        subtitle = QLabel("Review all planned folder creations and file moves before applying changes to disk.")
        subtitle.setObjectName("subtitleLabel")
        header_layout.addWidget(subtitle)
        layout.addLayout(header_layout)

        # Metric Summary Cards
        summary_card = QFrame()
        summary_card.setObjectName("cardFrame")
        grid = QGridLayout(summary_card)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setSpacing(16)

        def make_stat_box(title, value, color="#FFFFFF"):
            box = QVBoxLayout()
            t_lbl = QLabel(title)
            t_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase;")
            v_lbl = QLabel(str(value))
            v_lbl.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: 700;")
            box.addWidget(t_lbl)
            box.addWidget(v_lbl)
            return box

        grid.addLayout(make_stat_box("Files to Move", self.report.total_files, "#818CF8"), 0, 0)
        grid.addLayout(make_stat_box("New Folders to Create", self.report.folders_to_create, "#34D399"), 0, 1)
        grid.addLayout(make_stat_box("Total Data Size", format_file_size(self.report.total_bytes), "#67E8F9"), 0, 2)
        conflict_color = "#F87171" if self.report.conflicts_count > 0 else "#94A3B8"
        grid.addLayout(make_stat_box("Potential Conflicts", self.report.conflicts_count, conflict_color), 0, 3)

        layout.addWidget(summary_card)

        # Detailed Move Table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Filename", "Target Folder", "Folder Creation", "Status / Conflicts"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        table.setColumnWidth(0, 240)
        table.setColumnWidth(1, 180)

        table.setRowCount(len(self.report.items))
        for row, item in enumerate(self.report.items):
            fn_item = QTableWidgetItem(f"📄 {item.filename}")
            folder_item = QTableWidgetItem(f"📁 {item.group_name}/")

            dir_text = "New Folder" if item.will_create_dir else "Existing"
            dir_item = QTableWidgetItem(dir_text)
            if item.will_create_dir:
                dir_item.setForeground(Qt.GlobalColor.green)

            status_text = "Ready to move"
            if item.has_conflict:
                status_text = f"⚠️ {item.conflict_resolution}"
            status_item = QTableWidgetItem(status_text)
            if item.has_conflict:
                status_item.setForeground(Qt.GlobalColor.yellow)

            table.setItem(row, 0, fn_item)
            table.setItem(row, 1, folder_item)
            table.setItem(row, 2, dir_item)
            table.setItem(row, 3, status_item)

        layout.addWidget(table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        btn_proceed = QPushButton("Execute Move Now")
        btn_proceed.setObjectName("successButton")
        btn_proceed.clicked.connect(self.accept)
        btn_layout.addWidget(btn_proceed)

        layout.addLayout(btn_layout)
