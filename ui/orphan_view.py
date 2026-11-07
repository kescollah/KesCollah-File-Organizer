"""Review Workspace for Untouched and Orphan Files.
Provides automated quick-sort options (Extension, Date, Size) and drag-and-drop source.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData, QByteArray, QPoint
from PyQt6.QtGui import QDrag, QCursor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame, QAbstractItemView
)
from core.file_utils import get_file_metadata


class DraggableTableWidget(QTableWidget):
    """Table widget that allows dragging rows out as individual filenames."""
    file_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.itemClicked.connect(self._handle_clicked)

    def _handle_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.file_selected.emit(path)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            super().mouseMoveEvent(event)
            return

        selected_items = self.selectedItems()
        if not selected_items:
            super().mouseMoveEvent(event)
            return

        # Pick the filename from the first column of the selected row
        row = selected_items[0].row()
        fn_item = self.item(row, 0)
        if not fn_item:
            return

        filename = fn_item.text()
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData("application/x-file-name", QByteArray(filename.encode("utf-8")))
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.MoveAction)


class OrphanReviewWorkspace(QWidget):
    """Dedicated workspace tab for orphaned/untouched files."""
    quick_sort_requested = pyqtSignal(str)  # "extension", "date", "size"
    file_selected = pyqtSignal(str)
    move_to_group_requested = pyqtSignal(list, str)  # filenames, group_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir = ""
        self.orphan_files = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Top Quick-Sort Action Bar
        action_bar = QFrame()
        action_bar.setObjectName("cardFrame")
        bar_layout = QHBoxLayout(action_bar)
        bar_layout.setContentsMargins(12, 10, 12, 10)
        bar_layout.setSpacing(10)

        info_layout = QVBoxLayout()
        self.count_badge = QLabel("0 Untouched Files")
        self.count_badge.setObjectName("badgeLabel")
        info_layout.addWidget(self.count_badge)

        hint = QLabel("💡 Drag files into left groups, or use 1-click Quick-Sort:")
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        info_layout.addWidget(hint)
        bar_layout.addLayout(info_layout)

        bar_layout.addStretch()

        # Quick Sort Buttons
        self.btn_sort_ext = QPushButton("📂 By Extension")
        self.btn_sort_ext.setObjectName("actionButton")
        self.btn_sort_ext.setToolTip("Auto-group into Documents, Images, Code, etc.")
        self.btn_sort_ext.clicked.connect(lambda: self.quick_sort_requested.emit("extension"))
        bar_layout.addWidget(self.btn_sort_ext)

        self.btn_sort_date = QPushButton("📅 By Month/Date")
        self.btn_sort_date.setObjectName("actionButton")
        self.btn_sort_date.setToolTip("Auto-group by creation month (e.g. 2026-10)")
        self.btn_sort_date.clicked.connect(lambda: self.quick_sort_requested.emit("date"))
        bar_layout.addWidget(self.btn_sort_date)

        self.btn_sort_size = QPushButton("⚖️ By Size")
        self.btn_sort_size.setObjectName("actionButton")
        self.btn_sort_size.setToolTip("Auto-group by size tiers (<1MB, 1-50MB, >50MB)")
        self.btn_sort_size.clicked.connect(lambda: self.quick_sort_requested.emit("size"))
        bar_layout.addWidget(self.btn_sort_size)

        layout.addWidget(action_bar)

        # 2. Table of Untouched Files
        self.table = DraggableTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Filename (Drag to Group)", "Category", "Size", "Created Date"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.file_selected.connect(self.file_selected.emit)

        layout.addWidget(self.table)

    def load_orphans(self, target_dir: str, orphan_files: list):
        self.target_dir = target_dir
        self.orphan_files = orphan_files
        self.count_badge.setText(f"{len(orphan_files)} Untouched Files")

        self.table.setRowCount(len(orphan_files))
        for row, f in enumerate(orphan_files):
            full_path = os.path.join(target_dir, f)
            meta = get_file_metadata(full_path)

            item_name = QTableWidgetItem(f)
            item_name.setData(Qt.ItemDataRole.UserRole, full_path)

            item_cat = QTableWidgetItem(meta.get("category", "Other"))
            item_cat.setData(Qt.ItemDataRole.UserRole, full_path)

            item_size = QTableWidgetItem(meta.get("size_formatted", "—"))
            item_size.setData(Qt.ItemDataRole.UserRole, full_path)

            item_date = QTableWidgetItem(meta.get("created_date", "—"))
            item_date.setData(Qt.ItemDataRole.UserRole, full_path)

            self.table.setItem(row, 0, item_name)
            self.table.setItem(row, 1, item_cat)
            self.table.setItem(row, 2, item_size)
            self.table.setItem(row, 3, item_date)

        has_files = len(orphan_files) > 0
        self.btn_sort_ext.setEnabled(has_files)
        self.btn_sort_date.setEnabled(has_files)
        self.btn_sort_size.setEnabled(has_files)
