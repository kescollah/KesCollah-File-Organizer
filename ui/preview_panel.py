"""Preview and Metadata Inspector Panel.
Provides live metadata cards and instant image / text previews.
"""

import os
import subprocess
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap, QImageReader
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPlainTextEdit, QPushButton, QScrollArea, QGridLayout
)
from core.file_utils import get_file_metadata, read_text_preview


class PreviewPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path = None
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # Header
        header_layout = QHBoxLayout()
        title = QLabel("INSPECTOR & PREVIEW")
        title.setObjectName("sectionHeader")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.category_badge = QLabel("None")
        self.category_badge.setObjectName("badgeLabel")
        header_layout.addWidget(self.category_badge)
        main_layout.addLayout(header_layout)

        # Scroll area for the preview content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        self.content_layout = QVBoxLayout(container)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(10)

        # 1. Preview Box (Image or Text)
        self.preview_card = QFrame()
        self.preview_card.setObjectName("cardFrame")
        self.preview_card_layout = QVBoxLayout(self.preview_card)
        self.preview_card_layout.setContentsMargins(8, 8, 8, 8)

        self.image_preview_lbl = QLabel()
        self.image_preview_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_preview_lbl.setMinimumHeight(150)
        self.image_preview_lbl.setMaximumHeight(260)
        self.image_preview_lbl.setStyleSheet("background-color: #0E1017; border-radius: 6px;")
        self.preview_card_layout.addWidget(self.image_preview_lbl)

        self.text_preview_edit = QPlainTextEdit()
        self.text_preview_edit.setReadOnly(True)
        self.text_preview_edit.setMaximumHeight(240)
        self.text_preview_edit.setVisible(False)
        self.preview_card_layout.addWidget(self.text_preview_edit)

        self.placeholder_lbl = QLabel("Select a file to preview details")
        self.placeholder_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder_lbl.setStyleSheet("color: #64748B; font-size: 12px; padding: 40px 10px;")
        self.preview_card_layout.addWidget(self.placeholder_lbl)

        self.content_layout.addWidget(self.preview_card)

        # 2. Metadata Grid Card
        self.meta_card = QFrame()
        self.meta_card.setObjectName("cardFrame")
        grid = QGridLayout(self.meta_card)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(6)

        def add_meta_row(row_idx, label_text):
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #94A3B8; font-weight: 500; font-size: 11px;")
            val = QLabel("—")
            val.setStyleSheet("color: #F1F5F9; font-weight: 600; font-size: 12px;")
            val.setWordWrap(True)
            grid.addWidget(lbl, row_idx, 0)
            grid.addWidget(val, row_idx, 1)
            return val

        self.val_name = add_meta_row(0, "Name:")
        self.val_size = add_meta_row(1, "Size:")
        self.val_ext = add_meta_row(2, "Type:")
        self.val_created = add_meta_row(3, "Created:")
        self.val_modified = add_meta_row(4, "Modified:")
        self.val_path = add_meta_row(5, "Path:")

        grid.setColumnStretch(1, 1)
        self.content_layout.addWidget(self.meta_card)

        # 3. Actions Toolbar
        actions_frame = QFrame()
        actions_layout = QHBoxLayout(actions_frame)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(6)

        self.btn_open_file = QPushButton("Open File")
        self.btn_open_file.setObjectName("actionButton")
        self.btn_open_file.clicked.connect(self._open_file)
        self.btn_open_file.setEnabled(False)
        actions_layout.addWidget(self.btn_open_file)

        self.btn_reveal_explorer = QPushButton("Show in Explorer")
        self.btn_reveal_explorer.setObjectName("actionButton")
        self.btn_reveal_explorer.clicked.connect(self._reveal_explorer)
        self.btn_reveal_explorer.setEnabled(False)
        actions_layout.addWidget(self.btn_reveal_explorer)

        self.content_layout.addWidget(actions_frame)
        self.content_layout.addStretch()

        scroll.setWidget(container)
        main_layout.addWidget(scroll)

    def display_file(self, file_path: str):
        """Update inspector with file info and preview."""
        if not file_path or not os.path.isfile(file_path):
            self.clear_preview()
            return

        self.current_file_path = file_path
        meta = get_file_metadata(file_path)

        self.category_badge.setText(meta.get("category", "File"))
        self.val_name.setText(meta.get("filename", "—"))
        self.val_size.setText(meta.get("size_formatted", "—"))
        self.val_ext.setText(f"{meta.get('extension', '')} ({meta.get('category', '')})")
        self.val_created.setText(meta.get("created_date", "—"))
        self.val_modified.setText(meta.get("modified_date", "—"))
        self.val_path.setText(meta.get("path", "—"))

        self.btn_open_file.setEnabled(True)
        self.btn_reveal_explorer.setEnabled(True)

        # Image preview
        if meta.get("is_image", False):
            self.placeholder_lbl.setVisible(False)
            self.text_preview_edit.setVisible(False)
            self.image_preview_lbl.setVisible(True)

            pix = QPixmap(file_path)
            if not pix.isNull():
                scaled = pix.scaled(
                    260, 220,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_preview_lbl.setPixmap(scaled)
            else:
                self.image_preview_lbl.setText("Image preview unavailable")

        # Text file preview
        elif meta.get("is_text", False):
            self.placeholder_lbl.setVisible(False)
            self.image_preview_lbl.setVisible(False)
            self.text_preview_edit.setVisible(True)
            txt = read_text_preview(file_path)
            self.text_preview_edit.setPlainText(txt or "(Empty file)")

        # Generic / binary file
        else:
            self.image_preview_lbl.setVisible(False)
            self.text_preview_edit.setVisible(False)
            self.placeholder_lbl.setVisible(True)
            self.placeholder_lbl.setText(f"📄 {meta.get('category', 'Binary')} File\n(Preview not supported)")

    def clear_preview(self):
        self.current_file_path = None
        self.category_badge.setText("None")
        self.val_name.setText("—")
        self.val_size.setText("—")
        self.val_ext.setText("—")
        self.val_created.setText("—")
        self.val_modified.setText("—")
        self.val_path.setText("—")
        self.image_preview_lbl.clear()
        self.image_preview_lbl.setVisible(False)
        self.text_preview_edit.clear()
        self.text_preview_edit.setVisible(False)
        self.placeholder_lbl.setVisible(True)
        self.placeholder_lbl.setText("Select a file to preview details")
        self.btn_open_file.setEnabled(False)
        self.btn_reveal_explorer.setEnabled(False)

    def _open_file(self):
        if self.current_file_path and os.path.exists(self.current_file_path):
            try:
                os.startfile(self.current_file_path)
            except Exception as e:
                print(f"Error opening file: {e}")

    def _reveal_explorer(self):
        if self.current_file_path and os.path.exists(self.current_file_path):
            try:
                subprocess.Popen(f'explorer /select,"{os.path.abspath(self.current_file_path)}"')
            except Exception as e:
                print(f"Error revealing in explorer: {e}")
