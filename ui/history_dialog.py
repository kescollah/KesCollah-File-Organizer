"""Action History and Audit Log Viewer.
"""

from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCursor, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPlainTextEdit, QPushButton, QFrame
)


class ActivityLogWidget(QWidget):
    """Real-time scrolling log displaying file movements and audit history."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Header bar
        header = QHBoxLayout()
        title = QLabel("ACTION LOG & AUDIT HISTORY")
        title.setObjectName("sectionHeader")
        header.addWidget(title)
        header.addStretch()

        btn_clear = QPushButton("Clear Log")
        btn_clear.setObjectName("actionButton")
        btn_clear.clicked.connect(self.clear_log)
        header.addWidget(btn_clear)
        layout.addLayout(header)

        # Text Console
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        layout.addWidget(self.text_edit)

    def log(self, message: str, level: str = "info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        prefix = {
            "info": "[INFO]",
            "success": "[SUCCESS]",
            "warning": "[WARN]",
            "error": "[ERROR]",
        }.get(level, "[INFO]")

        line = f"{timestamp} {prefix} {message}"
        self.text_edit.appendPlainText(line)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.End)

    def clear_log(self):
        self.text_edit.clear()
