"""Action Center: The 'Zero Loose Files' Automated Organizer.
Implements Multi-Pass sorting (Pass 0 Custom Rules, Pass 1 Smart Name Grouping,
Pass 1.5 Semantic Engine with French accent tolerance, Pass 2 Extension Catch-All),
Nested Folder protection (Gathered_Loose_Files), Recursive Deep Clean with MAX_DEPTH limit,
Folder Merging, Quick Windows Profile selectors, Dry Run simulation, and JSON Undo Journal.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QSpinBox, QCheckBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QFileDialog, QMessageBox, QDialog, QProgressBar
)

from config import (
    format_bytes,
    get_windows_profile_directories,
    NESTED_GATHERED_DIRNAME
)
from core.file_logic import (
    ZeroLooseFilesEngine,
    ProposedMove,
    load_custom_rules,
    load_taxonomy,
    load_learned_rules,
    load_extension_mapping
)
from ui.undo_history_dialog import UndoHistoryDialog


class MoveWorkerThread(QThread):
    progress_updated = pyqtSignal(int, int, str, str)  # current, total, filename, dest
    operation_finished = pyqtSignal(int, int, list)     # moved, skipped, errors

    def __init__(self, engine: ZeroLooseFilesEngine, plan: list, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.plan = plan

    def run(self):
        moved, skipped, errors = self.engine.execute_plan(
            self.plan,
            progress_callback=lambda c, t, f, d: self.progress_updated.emit(c, t, f, d)
        )
        self.operation_finished.emit(moved, skipped, errors)


class DryRunModal(QDialog):
    """Modern modal dialog showing planned directory creations, moves, and deep-clean relocations."""
    def __init__(self, plan: list, target_dir: str, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.target_dir = target_dir
        self.setWindowTitle("Dry Run Simulation — Zero Loose Files Plan")
        self.resize(960, 600)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("Proposed Organization Plan (Dry Run Preview)")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(f"Simulation of 100% loose file cleanup and deep clean for: {self.target_dir}")
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # Stats Card
        stats_frame = QFrame()
        stats_frame.setObjectName("elevatedCard")
        s_layout = QHBoxLayout(stats_frame)
        s_layout.setContentsMargins(16, 12, 16, 12)

        def add_stat(label, val, color="#00E5FF"):
            box = QVBoxLayout()
            l = QLabel(label)
            l.setObjectName("statLabel")
            v = QLabel(str(val))
            v.setObjectName("statNumber")
            v.setStyleSheet(f"color: {color};")
            box.addWidget(l)
            box.addWidget(v)
            s_layout.addLayout(box)

        total_files = len(self.plan)
        dirs_to_create = len({item.dest_dir_abs for item in self.plan if item.will_create_dir})
        total_size = sum(item.size_bytes for item in self.plan)
        conflicts = sum(1 for item in self.plan if item.has_conflict)
        deep_count = sum(1 for item in self.plan if item.is_deep_clean)

        add_stat("Total Items", total_files, "#00E5FF")
        add_stat("Folders to Create", dirs_to_create, "#10B981")
        add_stat("Deep Clean Files", deep_count, "#F59E0B")
        add_stat("Total Volume", format_bytes(total_size), "#8B5CF6")
        add_stat("Conflicts", conflicts, "#FB7185" if conflicts > 0 else "#94A3B8")
        s_layout.addStretch()
        layout.addWidget(stats_frame)

        # Table
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Filename", "Destination Folder", "Pass Origin", "Action / Status"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        table.setColumnWidth(0, 260)

        table.setRowCount(len(self.plan))
        for row, item in enumerate(self.plan):
            table.setItem(row, 0, QTableWidgetItem(f"📄 {item.filename}"))
            table.setItem(row, 1, QTableWidgetItem(f"📁 {item.dest_dir_rel}/"))

            pass_item = QTableWidgetItem(item.pass_origin)
            table.setItem(row, 2, pass_item)

            status = "New Directory" if item.will_create_dir else "Existing Folder"
            if item.has_conflict:
                status += " (Auto-suffix duplicate)"
            table.setItem(row, 3, QTableWidgetItem(status))

        layout.addWidget(table)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()

        btn_cancel = QPushButton("Close")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_execute = QPushButton("⚡ Execute Cleanup Now")
        btn_execute.setObjectName("primaryButton")
        btn_execute.clicked.connect(self.accept)
        btns.addWidget(btn_execute)

        layout.addLayout(btns)


class ActionCenterView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir = os.path.abspath(".")
        self.current_plan: list[ProposedMove] = []
        self.worker_thread: MoveWorkerThread = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # 1. Header & Title
        header = QVBoxLayout()
        title = QLabel("Action Center — Zero Loose Files Organizer")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "100% Offline Multi-Pass Sorting: Custom Rules (Pass 0) ➔ Smart Name Groups (Pass 1) "
            "➔ Bilingual Semantic Engine (Pass 1.5) ➔ Extension Catch-All (Pass 2)."
        )
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Windows Profile Quick Access Bar
        profile_card = QFrame()
        profile_card.setObjectName("cardFrame")
        p_layout = QHBoxLayout(profile_card)
        p_layout.setContentsMargins(12, 8, 12, 8)
        p_layout.setSpacing(8)

        p_lbl = QLabel("Quick Profile Folders:")
        p_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; font-size: 11px;")
        p_layout.addWidget(p_lbl)

        profile_dirs = get_windows_profile_directories()
        icon_map = {
            "Desktop": "🖥️",
            "Downloads": "📥",
            "Documents": "📄",
            "Pictures": "🖼️",
            "Music": "🎵",
            "Videos": "🎬"
        }

        for name, path in profile_dirs.items():
            ico = icon_map.get(name, "📁")
            btn = QPushButton(f"{ico} {name}")
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
        layout.addWidget(profile_card)

        # 3. Directory Selector Card
        dir_card = QFrame()
        dir_card.setObjectName("cardFrame")
        dir_layout = QHBoxLayout(dir_card)
        dir_layout.setContentsMargins(14, 10, 14, 10)
        dir_layout.setSpacing(10)

        self.btn_up = QPushButton("⬆️ Up to Parent")
        self.btn_up.setToolTip("Return up to the parent directory")
        self.btn_up.clicked.connect(self.navigate_up)
        dir_layout.addWidget(self.btn_up)

        dir_lbl = QLabel("Active Target:")
        dir_lbl.setStyleSheet("font-weight: 700; color: #94A3B8;")
        dir_layout.addWidget(dir_lbl)

        self.dir_input = QLineEdit(self.target_dir)
        self.dir_input.returnPressed.connect(self.scan_and_plan)
        dir_layout.addWidget(self.dir_input, 1)

        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(btn_browse)

        btn_explorer = QPushButton("Open in Explorer")
        btn_explorer.clicked.connect(self.open_explorer)
        dir_layout.addWidget(btn_explorer)
        layout.addWidget(dir_card)

        # 4. Multi-Pass & Deep Clean Controls Card
        settings_card = QFrame()
        settings_card.setObjectName("cardFrame")
        s_layout = QVBoxLayout(settings_card)
        s_layout.setContentsMargins(14, 10, 14, 10)
        s_layout.setSpacing(8)

        # Row 1: Pipeline Flags
        row1 = QHBoxLayout()
        row1.setSpacing(14)

        row1.addWidget(QLabel("Min Smart Group files:"))
        self.spin_min_smart = QSpinBox()
        self.spin_min_smart.setRange(2, 20)
        self.spin_min_smart.setValue(2)
        self.spin_min_smart.valueChanged.connect(self.scan_and_plan)
        row1.addWidget(self.spin_min_smart)

        self.chk_taxonomy = QCheckBox("Semantic Engine (Pass 1.5)")
        self.chk_taxonomy.setChecked(True)
        self.chk_taxonomy.setToolTip("Classifies loose files matching static & AI-learned keywords (French accent insensitive).")
        self.chk_taxonomy.stateChanged.connect(self.scan_and_plan)
        row1.addWidget(self.chk_taxonomy)

        self.chk_date_subfolders = QCheckBox("Year/Month Subfolders")
        self.chk_date_subfolders.setChecked(True)
        self.chk_date_subfolders.setToolTip("Sub-sorts loose category files by creation date (e.g. 2026/11_Nov).")
        self.chk_date_subfolders.stateChanged.connect(self.scan_and_plan)
        row1.addWidget(self.chk_date_subfolders)

        self.chk_protect_scripts = QCheckBox("Protect Scripts (.py, .exe, .bat)")
        self.chk_protect_scripts.setChecked(False)
        self.chk_protect_scripts.stateChanged.connect(self.scan_and_plan)
        row1.addWidget(self.chk_protect_scripts)

        row1.addStretch()
        s_layout.addLayout(row1)

        # Row 2: Deep Clean & Recursive Depth Limits
        row2 = QHBoxLayout()
        row2.setSpacing(14)

        self.chk_deep_clean = QCheckBox("Recursive Deep Clean (Relocate wrongly placed files)")
        self.chk_deep_clean.setChecked(False)
        self.chk_deep_clean.setToolTip("Scans inside existing folders up to MAX_DEPTH to reorganize misplaced files.")
        self.chk_deep_clean.stateChanged.connect(self.scan_and_plan)
        row2.addWidget(self.chk_deep_clean)

        row2.addWidget(QLabel("Max Scan Depth:"))
        self.spin_max_depth = QSpinBox()
        self.spin_max_depth.setRange(1, 3)
        self.spin_max_depth.setValue(2)
        self.spin_max_depth.setToolTip("Strict depth limit (max 3) to prevent infinite loops.")
        self.spin_max_depth.valueChanged.connect(self.scan_and_plan)
        row2.addWidget(self.spin_max_depth)

        self.chk_merge_folders = QCheckBox("Merge Semantically Related Folders")
        self.chk_merge_folders.setChecked(True)
        self.chk_merge_folders.setToolTip("Merges loose files into Gathered_Loose_Files if a domain folder already exists.")
        self.chk_merge_folders.stateChanged.connect(self.scan_and_plan)
        row2.addWidget(self.chk_merge_folders)

        row2.addStretch()
        s_layout.addLayout(row2)

        layout.addWidget(settings_card)

        # 5. Metric Stat Strip
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("elevatedCard")
        stat_layout = QHBoxLayout(self.stats_frame)
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

        self.stat_total_loose = make_stat("Total Items to Move", "0", "#00E5FF")
        self.stat_custom_rules = make_stat("Pass 0: Rules", "0", "#8B5CF6")
        self.stat_smart_groups = make_stat("Pass 1: Groups", "0", "#38BDF8")
        self.stat_taxonomy = make_stat("Pass 1.5: Semantic", "0", "#E879F9")
        self.stat_fallback = make_stat("Pass 2: Extension", "0", "#34D399")
        stat_layout.addStretch()

        # Action Buttons on right side of stat strip
        self.btn_dry_run = QPushButton("🧪 Dry Run (Preview)")
        self.btn_dry_run.setObjectName("primaryButton")
        self.btn_dry_run.clicked.connect(self.open_dry_run)
        stat_layout.addWidget(self.btn_dry_run)

        self.btn_execute = QPushButton("⚡ Execute Zero Loose Files")
        self.btn_execute.setObjectName("successButton")
        self.btn_execute.clicked.connect(self.confirm_and_execute)
        stat_layout.addWidget(self.btn_execute)

        self.btn_history = QPushButton("🕘 History")
        self.btn_history.setToolTip("Browse and undo any of the last 30 operations (manual and Watchdog).")
        self.btn_history.clicked.connect(self.open_undo_history)

        self.btn_undo = QPushButton("↩️ Undo Last Operation")
        self.btn_undo.setObjectName("dangerButton")
        self.btn_undo.clicked.connect(self.execute_undo)
        self._update_undo_button_state()
        stat_layout.addWidget(self.btn_undo)
        stat_layout.addWidget(self.btn_history)

        layout.addWidget(self.stats_frame)

        # 6. Planned Moves Table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Target Subfolder (Zero Loose Files)", "Pass Origin", "Size", "Folder Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(0, 260)
        layout.addWidget(self.table)

        # 7. Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    def navigate_up(self):
        """Return up to the parent directory."""
        parent = os.path.dirname(self.target_dir)
        if parent and parent != self.target_dir and os.path.isdir(parent):
            self.set_directory(parent)

    def set_directory(self, path: str):
        self.target_dir = os.path.abspath(path)
        self.dir_input.setText(self.target_dir)
        parent = os.path.dirname(self.target_dir)
        self.btn_up.setEnabled(bool(parent and parent != self.target_dir and os.path.isdir(parent)))
        self.scan_and_plan()

    def browse_directory(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Directory to Clean", self.target_dir)
        if chosen:
            self.set_directory(chosen)

    def open_explorer(self):
        if os.path.isdir(self.target_dir):
            os.startfile(self.target_dir)

    def scan_and_plan(self):
        """Scans the directory and executes the multi-pass Zero Loose Files plan."""
        target = self.dir_input.text().strip()
        if not os.path.isdir(target):
            self.status_message.emit(f"Invalid directory: {target}")
            return

        self.target_dir = os.path.abspath(target)
        min_smart = self.spin_min_smart.value()
        use_dates = self.chk_date_subfolders.isChecked()
        protect_scripts = self.chk_protect_scripts.isChecked()
        use_tax = self.chk_taxonomy.isChecked()
        deep_clean = self.chk_deep_clean.isChecked()
        max_depth = self.spin_max_depth.value()
        merge_folders = self.chk_merge_folders.isChecked()

        rules = load_custom_rules()
        engine = ZeroLooseFilesEngine(self.target_dir, rules)

        self.current_plan = engine.plan_organization(
            min_smart_group=min_smart,
            use_date_subfolders=use_dates,
            skip_scripts=protect_scripts,
            enable_taxonomy=use_tax,
            deep_clean=deep_clean,
            max_depth=max_depth,
            merge_folders=merge_folders
        )

        # Calculate counts
        p0 = sum(1 for item in self.current_plan if "Pass 0" in item.pass_origin)
        p1 = sum(1 for item in self.current_plan if "Pass 1:" in item.pass_origin)
        p15 = sum(1 for item in self.current_plan if "Pass 1.5:" in item.pass_origin)
        p2 = sum(1 for item in self.current_plan if "Pass 2:" in item.pass_origin)

        self.stat_total_loose.setText(str(len(self.current_plan)))
        self.stat_custom_rules.setText(str(p0))
        self.stat_smart_groups.setText(str(p1))
        self.stat_taxonomy.setText(str(p15))
        self.stat_fallback.setText(str(p2))

        # Populate table
        self.table.setRowCount(len(self.current_plan))
        for row, item in enumerate(self.current_plan):
            self.table.setItem(row, 0, QTableWidgetItem(f"📄 {item.filename}"))
            self.table.setItem(row, 1, QTableWidgetItem(f"📁 {item.dest_dir_rel}/"))

            # Pass badge column
            pass_item = QTableWidgetItem(item.pass_origin)
            if "Pass 0" in item.pass_origin:
                pass_item.setForeground(QColor("#A78BFA"))  # purple
            elif "Pass 1.5" in item.pass_origin:
                pass_item.setForeground(QColor("#E879F9"))  # neon magenta for semantic context
            elif "Pass 1" in item.pass_origin:
                pass_item.setForeground(QColor("#38BDF8"))  # sky blue for smart group
            else:
                pass_item.setForeground(QColor("#34D399"))  # mint green for fallback
            self.table.setItem(row, 2, pass_item)

            self.table.setItem(row, 3, QTableWidgetItem(item.size_formatted))

            stat_str = "Create Directory" if item.will_create_dir else "Existing Folder"
            if item.has_conflict:
                stat_str += " (Duplicate Safe)"
            if item.is_deep_clean:
                stat_str += " • Deep Clean"
            self.table.setItem(row, 4, QTableWidgetItem(stat_str))

        has_files = len(self.current_plan) > 0
        self.btn_dry_run.setEnabled(has_files)
        self.btn_execute.setEnabled(has_files)
        self._update_undo_button_state()

        mode_str = "Deep Clean Scan" if deep_clean else "Zero Loose Files Scan"
        self.status_message.emit(
            f"{mode_str}: {len(self.current_plan)} items planned for organization."
        )

    def _update_undo_button_state(self):
        info = ZeroLooseFilesEngine.get_last_undo_info()
        self.btn_undo.setEnabled(info is not None)
        if hasattr(self, "btn_history"):
            self.btn_history.setEnabled(info is not None)
        if info:
            source = " • Watchdog" if info.get("source") == "Watchdog" else ""
            self.btn_undo.setText(f"↩️ Undo Last Operation ({info.get('count', 0)} files{source})")
        else:
            self.btn_undo.setText("↩️ Undo Last Operation")

    def open_undo_history(self):
        dialog = UndoHistoryDialog(self)
        dialog.exec()
        if dialog.changed:
            self.scan_and_plan()
        self._update_undo_button_state()

    def open_dry_run(self):
        if not self.current_plan:
            QMessageBox.information(self, "No Files", "No items detected to organize.")
            return

        modal = DryRunModal(self.current_plan, self.target_dir, self)
        if modal.exec():
            self.execute_plan_direct()

    def confirm_and_execute(self):
        if not self.current_plan:
            QMessageBox.information(self, "No Files", "No items detected to organize.")
            return

        total = len(self.current_plan)
        confirm = QMessageBox.question(
            self,
            "Confirm Zero Loose Files Execution",
            f"Are you sure you want to organize all {total} files in:\n\n{self.target_dir}\n\n"
            f"This will leave ZERO loose files in the root folder. You can safely undo this action afterwards.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.execute_plan_direct()

    def execute_plan_direct(self):
        """Run move operations in a worker thread."""
        self.btn_execute.setEnabled(False)
        self.btn_dry_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self.current_plan))
        self.progress_bar.setValue(0)

        rules = load_custom_rules()
        engine = ZeroLooseFilesEngine(self.target_dir, rules)

        self.worker_thread = MoveWorkerThread(engine, self.current_plan, self)
        self.worker_thread.progress_updated.connect(self._on_progress)
        self.worker_thread.operation_finished.connect(self._on_finished)
        self.worker_thread.start()

    def _on_progress(self, current: int, total: int, filename: str, dest: str):
        self.progress_bar.setValue(current)
        self.status_message.emit(f"Moving ({current}/{total}): {filename} -> {dest}/")

    def _on_finished(self, moved: int, skipped: int, errors: list):
        self.progress_bar.setVisible(False)
        self.scan_and_plan()
        self._update_undo_button_state()

        msg = f"Zero Loose Files Complete!\n\nSuccessfully moved {moved} files into organized subfolders."
        if skipped > 0:
            msg += f"\nSkipped / Errors: {skipped}"
        QMessageBox.information(self, "Cleanup Complete", msg)

    def execute_undo(self):
        if not ZeroLooseFilesEngine.can_undo():
            QMessageBox.information(self, "Undo", "No previous actions found in Undo Journal.")
            return

        confirm = QMessageBox.question(
            self,
            "Confirm Undo",
            "Restore all organized files back to their original locations and clean up newly created empty folders?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        restored, cleaned_dirs, errors = ZeroLooseFilesEngine.undo_last_operation()
        self.scan_and_plan()
        self._update_undo_button_state()

        msg = f"Undo Operation Finished!\n\n• Restored {restored} files back to original locations.\n• Removed {cleaned_dirs} empty subfolders."
        if errors:
            msg += f"\n• Could not restore {len(errors)}:\n  " + "\n  ".join(errors[:5])
        QMessageBox.information(self, "Undo Complete", msg)
