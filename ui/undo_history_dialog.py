"""Undo History ("Time Machine"): browse and reverse any of the last 30 organize operations,
manual or Watchdog, not just the most recent one."""

import os
from datetime import datetime

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox, QAbstractItemView
)

from core.file_logic import ZeroLooseFilesEngine


class UndoHistoryDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Undo History")
        self.resize(900, 460)
        self.changed = False
        self._init_ui()
        self._load()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Undo History")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        subtitle = QLabel(
            "Every manual and Watchdog cleanup is recorded separately (last 30). Undo any of them, in any order. "
            "A file is never overwritten: if something new sits at its original path, it is restored as "
            "'name (restored 1).ext'. Only folders KesCollah created are removed, and only when empty."
        )
        subtitle.setObjectName("viewSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["When", "Source", "Folder", "Files", "Still in Place"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda _i: self._show_details())
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.btn_details = QPushButton("📄 Show Files")
        self.btn_details.clicked.connect(self._show_details)
        buttons.addWidget(self.btn_details)
        buttons.addStretch()

        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        buttons.addWidget(btn_close)

        self.btn_undo = QPushButton("↩️ Undo Selected Operation")
        self.btn_undo.setObjectName("dangerButton")
        self.btn_undo.clicked.connect(self._undo_selected)
        buttons.addWidget(self.btn_undo)
        layout.addLayout(buttons)

    def _load(self):
        self.history = ZeroLooseFilesEngine.get_undo_history()
        self.table.setRowCount(len(self.history))
        for row, op in enumerate(self.history):
            try:
                when = datetime.fromisoformat(op.get("timestamp", "")).strftime("%Y-%m-%d  %H:%M:%S")
            except ValueError:
                when = op.get("timestamp", "?")
            moves = op.get("moves", [])
            in_place = sum(1 for m in moves if m.get("target_dst") and os.path.exists(m["target_dst"]))

            self.table.setItem(row, 0, QTableWidgetItem(when))
            source = op.get("source", "Manual")
            src_item = QTableWidgetItem(("🛡️ " if source == "Watchdog" else "⚡ ") + source)
            self.table.setItem(row, 1, src_item)
            self.table.setItem(row, 2, QTableWidgetItem(op.get("target_dir", "")))
            self.table.setItem(row, 3, QTableWidgetItem(str(op.get("count", len(moves)))))

            status = QTableWidgetItem(f"{in_place}/{len(moves)}")
            status.setToolTip("Files still at the location this operation moved them to (restorable).")
            if in_place < len(moves):
                status.setForeground(QColor("#F59E0B"))
            self.table.setItem(row, 4, status)

        if self.history:
            self.table.selectRow(0)
        self._update_buttons()

    def _selected_op(self):
        rows = self.table.selectionModel().selectedRows()
        return self.history[rows[0].row()] if rows else None

    def _update_buttons(self):
        has = self._selected_op() is not None
        self.btn_undo.setEnabled(has)
        self.btn_details.setEnabled(has)

    def _show_details(self):
        op = self._selected_op()
        if not op:
            return
        lines = []
        for m in op.get("moves", [])[:300]:
            mark = "✓" if os.path.exists(m.get("target_dst", "")) else "✗ (gone)"
            lines.append(f"{mark}  {m.get('target_dst', '')}\n      ← {m.get('orig_src', '')}")
        extra = len(op.get("moves", [])) - 300
        if extra > 0:
            lines.append(f"... and {extra} more")
        box = QMessageBox(self)
        box.setWindowTitle("Files in This Operation")
        box.setText(f"{op.get('count', 0)} files moved by this {op.get('source', 'Manual').lower()} operation.")
        box.setDetailedText("\n".join(lines))
        box.exec()

    def _undo_selected(self):
        op = self._selected_op()
        if not op:
            return
        is_latest = self.history and op is self.history[0]
        warning = "" if is_latest else (
            "\n\nThis is not the most recent operation. Files that a later operation moved again "
            "will be skipped and reported."
        )
        confirm = QMessageBox.question(
            self, "Confirm Undo",
            f"Restore {op.get('count', 0)} files from this {op.get('source', 'Manual').lower()} operation "
            f"back to their original locations?{warning}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        restored, cleaned, errors = ZeroLooseFilesEngine.undo_operation(op.get("id"))
        self.changed = True
        msg = f"Restored {restored} files.\nRemoved {cleaned} empty folders KesCollah had created."
        if errors:
            msg += f"\n\n{len(errors)} file(s) could not be restored:\n" + "\n".join(errors[:8])
            if len(errors) > 8:
                msg += f"\n... and {len(errors) - 8} more"
        QMessageBox.information(self, "Undo Complete", msg)
        self._load()
