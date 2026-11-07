"""Duplicate File Finder: SHA-256 hash-based byte-exact duplicate detection,
smart selection rules, and safe deletion.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTreeWidget, QTreeWidgetItem, QHeaderView,
    QFrame, QFileDialog, QCheckBox, QProgressBar, QMessageBox
)

from core.duplicate_finder import find_duplicates, DuplicateGroup
from config import format_bytes


class DuplicateScanWorker(QThread):
    progress_updated = pyqtSignal(int, int, str)
    scan_finished = pyqtSignal(list)

    def __init__(self, target_dir: str, recursive: bool, parent=None):
        super().__init__(parent)
        self.target_dir = target_dir
        self.recursive = recursive

    def run(self):
        groups = find_duplicates(
            self.target_dir,
            recursive=self.recursive,
            progress_callback=lambda cur, tot, msg: self.progress_updated.emit(cur, tot, msg)
        )
        self.scan_finished.emit(groups)


class DuplicateFinderView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir = os.path.abspath(".")
        self.groups: list[DuplicateGroup] = []
        self.worker: DuplicateScanWorker = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # Header
        header = QVBoxLayout()
        title = QLabel("Duplicate Finder — SHA-256 Identity Engine")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel("Finds completely identical files regardless of filename using byte-exact SHA-256 hashes.")
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Directory Card
        dir_card = QFrame()
        dir_card.setObjectName("cardFrame")
        dir_layout = QHBoxLayout(dir_card)
        dir_layout.setContentsMargins(14, 10, 14, 10)
        dir_layout.setSpacing(10)

        self.btn_up = QPushButton("⬆️ Up to Parent")
        self.btn_up.setToolTip("Return up to the parent directory")
        self.btn_up.clicked.connect(self.navigate_up)
        dir_layout.addWidget(self.btn_up)

        dir_lbl = QLabel("Directory:")
        dir_lbl.setStyleSheet("font-weight: 700; color: #94A3B8;")
        dir_layout.addWidget(dir_lbl)

        self.dir_input = QLineEdit(self.target_dir)
        self.dir_input.returnPressed.connect(self.start_scan)
        dir_layout.addWidget(self.dir_input, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)

        self.chk_recursive = QCheckBox("Include Subfolders")
        self.chk_recursive.setChecked(True)
        dir_layout.addWidget(self.chk_recursive)

        self.btn_scan = QPushButton("🔍 Find Duplicates")
        self.btn_scan.setObjectName("primaryButton")
        self.btn_scan.clicked.connect(self.start_scan)
        dir_layout.addWidget(self.btn_scan)

        layout.addWidget(dir_card)

        # Metric Stats Strip
        stats_frame = QFrame()
        stats_frame.setObjectName("elevatedCard")
        s_layout = QHBoxLayout(stats_frame)
        s_layout.setContentsMargins(16, 10, 16, 10)

        def make_stat(lbl, val="0", color="#00E5FF"):
            box = QVBoxLayout()
            l = QLabel(lbl)
            l.setObjectName("statLabel")
            v = QLabel(val)
            v.setObjectName("statNumber")
            v.setStyleSheet(f"color: {color};")
            box.addWidget(l)
            box.addWidget(v)
            s_layout.addLayout(box)
            return v

        self.stat_groups = make_stat("Duplicate Clusters", "0", "#00E5FF")
        self.stat_wasted = make_stat("Wasted Disk Space", "0 B", "#FB7185")
        self.stat_redundant = make_stat("Redundant Files", "0", "#8B5CF6")
        s_layout.addStretch()

        # Selection tools
        btn_sel_newest = QPushButton("Keep Newest")
        btn_sel_newest.setToolTip("Mark older duplicates for deletion, keeping the newest copy")
        btn_sel_newest.clicked.connect(lambda: self.smart_select(keep="newest"))
        s_layout.addWidget(btn_sel_newest)

        btn_sel_oldest = QPushButton("Keep Oldest")
        btn_sel_oldest.setToolTip("Mark newer duplicates for deletion, keeping the original oldest copy")
        btn_sel_oldest.clicked.connect(lambda: self.smart_select(keep="oldest"))
        s_layout.addWidget(btn_sel_oldest)

        btn_desel = QPushButton("Deselect All")
        btn_desel.clicked.connect(self.deselect_all)
        s_layout.addWidget(btn_desel)

        self.btn_delete = QPushButton("🗑️ Delete Selected")
        self.btn_delete.setObjectName("dangerButton")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_delete.setEnabled(False)
        s_layout.addWidget(self.btn_delete)

        layout.addWidget(stats_frame)

        # Tree View of Duplicate Clusters
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["File Path / Hash Cluster", "Size", "Date Modified"])
        self.tree.header().resizeSection(0, 520)
        self.tree.header().resizeSection(1, 100)
        self.tree.itemChanged.connect(self._on_item_checked)
        layout.addWidget(self.tree)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def navigate_up(self):
        """Return up to the parent directory."""
        parent = os.path.dirname(self.target_dir)
        if parent and parent != self.target_dir and os.path.isdir(parent):
            self.set_directory(parent)
            self.start_scan()

    def set_directory(self, path: str):
        self.target_dir = os.path.abspath(path)
        self.dir_input.setText(self.target_dir)
        parent = os.path.dirname(self.target_dir)
        self.btn_up.setEnabled(bool(parent and parent != self.target_dir and os.path.isdir(parent)))

    def browse_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Folder to Scan for Duplicates", self.target_dir)
        if chosen:
            self.set_directory(chosen)

    def start_scan(self):
        target = self.dir_input.text().strip()
        if not os.path.isdir(target):
            self.status_message.emit(f"Invalid directory: {target}")
            return

        self.target_dir = os.path.abspath(target)
        self.btn_scan.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        self.worker = DuplicateScanWorker(self.target_dir, self.chk_recursive.isChecked(), self)
        self.worker.progress_updated.connect(self._on_progress)
        self.worker.scan_finished.connect(self._on_finished)
        self.worker.start()

    def _on_progress(self, cur: int, tot: int, msg: str):
        self.progress_bar.setRange(0, tot)
        self.progress_bar.setValue(cur)
        self.status_message.emit(msg)

    def _on_finished(self, groups: list):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.groups = groups

        total_wasted = sum(g.wasted_bytes for g in groups)
        total_redundant = sum(len(g.file_paths) - 1 for g in groups)

        self.stat_groups.setText(str(len(groups)))
        self.stat_wasted.setText(format_bytes(total_wasted))
        self.stat_redundant.setText(str(total_redundant))

        self.tree.clear()

        # Block signals temporarily to prevent early check callbacks
        self.tree.blockSignals(True)

        for g in groups:
            cluster_item = QTreeWidgetItem(self.tree)
            hash_snippet = g.file_hash[:12]
            cluster_item.setText(0, f"🧬 Cluster {hash_snippet}... ({len(g.file_paths)} copies)")
            cluster_item.setText(1, f"Waste: {format_bytes(g.wasted_bytes)}")
            cluster_item.setText(2, f"Each: {g.size_formatted}")
            cluster_item.setExpanded(True)

            for path in g.file_paths:
                child = QTreeWidgetItem(cluster_item)
                child.setText(0, path)
                child.setText(1, g.size_formatted)
                try:
                    mtime = os.path.getmtime(path)
                    from datetime import datetime
                    dt_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S")
                except OSError:
                    dt_str = "—"
                    mtime = 0
                child.setText(2, dt_str)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, path)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, mtime)

        self.tree.blockSignals(False)
        self.status_message.emit(
            f"Duplicate scan complete: Found {len(groups)} clusters ({format_bytes(total_wasted)} reclaimable)."
        )

    def _on_item_checked(self, item: QTreeWidgetItem, col: int):
        # Update delete button state
        has_checked = self._has_any_checked()
        self.btn_delete.setEnabled(has_checked)

    def _has_any_checked(self) -> bool:
        for i in range(self.tree.topLevelItemCount()):
            cluster = self.tree.topLevelItem(i)
            for j in range(cluster.childCount()):
                if cluster.child(j).checkState(0) == Qt.CheckState.Checked:
                    return True
        return False

    def smart_select(self, keep: str = "newest"):
        """Automatically select duplicate copies for deletion while preserving one copy."""
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            cluster = self.tree.topLevelItem(i)
            children = [cluster.child(j) for j in range(cluster.childCount())]
            if not children:
                continue

            # Sort children by mtime
            children.sort(key=lambda c: c.data(0, Qt.ItemDataRole.UserRole + 1) or 0)

            if keep == "newest":
                # Keep the newest (last item), check all others for deletion
                for c in children[:-1]:
                    c.setCheckState(0, Qt.CheckState.Checked)
                children[-1].setCheckState(0, Qt.CheckState.Unchecked)
            else:
                # Keep the oldest (first item), check all others for deletion
                children[0].setCheckState(0, Qt.CheckState.Unchecked)
                for c in children[1:]:
                    c.setCheckState(0, Qt.CheckState.Checked)

        self.tree.blockSignals(False)
        self.btn_delete.setEnabled(self._has_any_checked())

    def deselect_all(self):
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            cluster = self.tree.topLevelItem(i)
            for j in range(cluster.childCount()):
                cluster.child(j).setCheckState(0, Qt.CheckState.Unchecked)
        self.tree.blockSignals(False)
        self.btn_delete.setEnabled(False)

    def delete_selected(self):
        files_to_delete = []
        for i in range(self.tree.topLevelItemCount()):
            cluster = self.tree.topLevelItem(i)
            for j in range(cluster.childCount()):
                child = cluster.child(j)
                if child.checkState(0) == Qt.CheckState.Checked:
                    path = child.data(0, Qt.ItemDataRole.UserRole)
                    if path:
                        files_to_delete.append(path)

        if not files_to_delete:
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Duplicate Deletion",
            f"Are you sure you want to permanently delete {len(files_to_delete)} duplicate files?\n\n"
            f"This will remove the selected redundant files and free up disk space.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        errors = []
        for path in files_to_delete:
            try:
                os.remove(path)
                deleted += 1
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        msg = f"Successfully deleted {deleted} duplicate files."
        if errors:
            msg += f"\n\nErrors encountered:\n" + "\n".join(errors[:5])
        QMessageBox.information(self, "Deletion Complete", msg)

        # Refresh
        self.start_scan()
