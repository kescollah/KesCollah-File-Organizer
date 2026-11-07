"""Interactive drag-and-drop TreeWidget for auto-grouped and custom directories.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QMimeData
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QMenu, QInputDialog, QMessageBox
)


class GroupTreeWidget(QTreeWidget):
    """Tree widget displaying folders/groups and their contained files.
    Accepts drops of loose files dragged from other views.
    """
    file_dropped_to_group = pyqtSignal(str, str)  # filename, target_group
    file_selected = pyqtSignal(str)               # full_path
    group_created = pyqtSignal(str)               # new_group_name
    group_renamed = pyqtSignal(str, str)          # old_name, new_name
    group_deleted = pyqtSignal(str)               # group_name

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setColumnCount(2)
        self.setHeaderLabels(["Folder / File", "Items / Size"])
        self.header().resizeSection(0, 220)
        self.header().resizeSection(1, 90)
        self.setAnimated(True)

        # Enable Drag & Drop
        self.setAcceptDrops(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragDrop)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)

        # Context Menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

        # Selection change
        self.itemClicked.connect(self._handle_item_clicked)

    def _handle_item_clicked(self, item: QTreeWidgetItem, column: int):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if path and os.path.isfile(path):
            self.file_selected.emit(path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-file-name"):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item:
            # Highlight folder drop targets
            group_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if group_name:
                event.acceptProposedAction()
                return
        event.ignore()

    def dropEvent(self, event):
        pos = event.position().toPoint()
        target_item = self.itemAt(pos)

        if not target_item:
            event.ignore()
            return

        # Determine target group
        target_group = target_item.data(0, Qt.ItemDataRole.UserRole + 1)
        if not target_group:
            # If dropped on a child item, find its parent group
            parent = target_item.parent()
            if parent:
                target_group = parent.data(0, Qt.ItemDataRole.UserRole + 1)

        if target_group and event.mimeData().hasFormat("application/x-file-name"):
            filename = str(event.mimeData().data("application/x-file-name"), "utf-8")
            self.file_dropped_to_group.emit(filename, target_group)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    def _show_context_menu(self, pos):
        item = self.itemAt(pos)
        menu = QMenu(self)

        action_new = QAction("➕ Create New Custom Group", self)
        action_new.triggered.connect(self._prompt_create_group)
        menu.addAction(action_new)

        if item:
            group_name = item.data(0, Qt.ItemDataRole.UserRole + 1)
            if group_name:
                menu.addSeparator()
                action_rename = QAction(f"✏️ Rename Group '{group_name}'", self)
                action_rename.triggered.connect(lambda: self._prompt_rename_group(group_name))
                menu.addAction(action_rename)

                action_del = QAction(f"❌ Dissolve Group '{group_name}'", self)
                action_del.triggered.connect(lambda: self.group_deleted.emit(group_name))
                menu.addAction(action_del)

        menu.exec(self.viewport().mapToGlobal(pos))

    def _prompt_create_group(self):
        text, ok = QInputDialog.getText(self, "Create Group", "Enter new folder/group name:")
        if ok and text.strip():
            self.group_created.emit(text.strip())

    def _prompt_rename_group(self, old_name: str):
        text, ok = QInputDialog.getText(self, "Rename Group", "Enter new folder name:", text=old_name)
        if ok and text.strip() and text.strip() != old_name:
            self.group_renamed.emit(old_name, text.strip())
