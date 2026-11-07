"""Review-before-learn dialog for Gemini Knowledge Sync.

Every learned keyword becomes a permanent offline rule applied to all future files, so the
user approves each one first. Shows the masked name actually sent to Gemini, the model's
confidence and reasoning, and flags keywords the quality guard considers unsafe.
"""

from typing import Any, Dict, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox
)

from core.gemini_sync import keyword_issue

COL_CHECK, COL_FILE, COL_SENT, COL_CATEGORY, COL_KEYWORD, COL_CONF, COL_NOTE = range(7)
CONFIDENCE_COLORS = {"high": "#10B981", "medium": "#F59E0B", "low": "#EF4444"}


class AIReviewDialog(QDialog):
    def __init__(self, suggestions: List[Dict[str, Any]], categories: List[str], model_used: str, parent=None):
        super().__init__(parent)
        self.suggestions = suggestions
        self.categories = categories
        self.setWindowTitle(f"Review AI Suggestions — {model_used}")
        self.resize(1180, 620)
        self._updating = False
        self._init_ui(model_used)

    def _init_ui(self, model_used: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Review What KesCollah Will Learn")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        flagged = sum(1 for s in self.suggestions if s["issue"])
        subtitle = QLabel(
            f"{model_used} proposed {len(self.suggestions)} rules. Each approved keyword becomes a permanent offline "
            f"rule for ALL future files. Low-confidence and flagged rows ({flagged} flagged) start unchecked. "
            "You can edit the category or keyword before approving. Hover a row to read Gemini's reasoning."
        )
        subtitle.setObjectName("viewSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        self.table = QTableWidget(len(self.suggestions), 7)
        self.table.setHorizontalHeaderLabels(
            ["Learn", "File", "Sent to Gemini As", "Category", "Keyword (editable)", "Confidence", "Note"]
        )
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(COL_CHECK, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_FILE, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_SENT, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(COL_CATEGORY, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_KEYWORD, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_CONF, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_NOTE, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(COL_FILE, 230)
        self.table.setColumnWidth(COL_SENT, 200)

        self._updating = True
        for row, s in enumerate(self.suggestions):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Checked if s["accept"] else Qt.CheckState.Unchecked)
            self.table.setItem(row, COL_CHECK, check)

            tip = s.get("reasoning") or ""
            self.table.setItem(row, COL_FILE, self._readonly(s["filename"], tip))
            sent = self._readonly(s["sent_as"], "Exactly what left this computer.")
            if s["sent_as"] != s["filename"]:
                sent.setForeground(QColor("#38BDF8"))
            self.table.setItem(row, COL_SENT, sent)

            combo = QComboBox()
            combo.addItems(self.categories)
            combo.setCurrentText(s["category"])
            combo.currentTextChanged.connect(lambda _t, r=row: self._row_edited(r))
            self.table.setCellWidget(row, COL_CATEGORY, combo)

            self.table.setItem(row, COL_KEYWORD, QTableWidgetItem(s["keyword"]))

            conf = self._readonly(s["confidence"], tip)
            conf.setForeground(QColor(CONFIDENCE_COLORS.get(s["confidence"], "#94A3B8")))
            self.table.setItem(row, COL_CONF, conf)

            self.table.setItem(row, COL_NOTE, self._readonly("", tip))
            self._refresh_note(row)
        self._updating = False

        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        btn_valid = QPushButton("✔ Select All Safe")
        btn_valid.setToolTip("Check every row without a warning, including low-confidence ones.")
        btn_valid.clicked.connect(self._select_safe)
        buttons.addWidget(btn_valid)

        btn_none = QPushButton("Select None")
        btn_none.clicked.connect(lambda: self._set_all(False))
        buttons.addWidget(btn_none)

        buttons.addStretch()
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet("color: #94A3B8;")
        buttons.addWidget(self.lbl_count)

        btn_cancel = QPushButton("Cancel (keep files queued)")
        btn_cancel.clicked.connect(self.reject)
        buttons.addWidget(btn_cancel)

        self.btn_learn = QPushButton("🧠 Learn Selected")
        self.btn_learn.setObjectName("successButton")
        self.btn_learn.clicked.connect(self.accept)
        buttons.addWidget(self.btn_learn)
        layout.addLayout(buttons)

        self._update_count()

    @staticmethod
    def _readonly(text: str, tooltip: str = "") -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
        if tooltip:
            item.setToolTip(tooltip)
        return item

    def _refresh_note(self, row: int):
        keyword = self.table.item(row, COL_KEYWORD).text()
        issue = keyword_issue(keyword, self.suggestions[row]["filename"])
        note = self.table.item(row, COL_NOTE)
        if issue:
            note.setText(f"⚠ {issue}")
            note.setForeground(QColor("#F59E0B"))
        else:
            note.setText(self.suggestions[row].get("reasoning") or "OK")
            note.setForeground(QColor("#94A3B8"))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._updating:
            return
        if item.column() == COL_KEYWORD:
            self._row_edited(item.row())
        self._update_count()

    def _row_edited(self, row: int):
        self._updating = True
        self._refresh_note(row)
        self._updating = False

    def _set_all(self, checked: bool):
        self._updating = True
        for row in range(self.table.rowCount()):
            self.table.item(row, COL_CHECK).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._updating = False
        self._update_count()

    def _select_safe(self):
        self._updating = True
        for row in range(self.table.rowCount()):
            safe = not keyword_issue(self.table.item(row, COL_KEYWORD).text(), self.suggestions[row]["filename"])
            self.table.item(row, COL_CHECK).setCheckState(Qt.CheckState.Checked if safe else Qt.CheckState.Unchecked)
        self._updating = False
        self._update_count()

    def _update_count(self):
        n = sum(
            1 for row in range(self.table.rowCount())
            if self.table.item(row, COL_CHECK).checkState() == Qt.CheckState.Checked
        )
        self.lbl_count.setText(f"{n} of {self.table.rowCount()} selected")
        self.btn_learn.setText(f"🧠 Learn {n} Selected" if n else "Done (learn nothing)")

    def accepted_suggestions(self) -> List[Dict[str, Any]]:
        """Approved rows with the user's edits applied. A user-edited keyword is the user's call,
        so it is accepted even if the guard flags it."""
        result = []
        for row, s in enumerate(self.suggestions):
            if self.table.item(row, COL_CHECK).checkState() != Qt.CheckState.Checked:
                continue
            keyword = self.table.item(row, COL_KEYWORD).text().strip()
            if not keyword:
                continue
            combo: QComboBox = self.table.cellWidget(row, COL_CATEGORY)
            result.append({**s, "category": combo.currentText(), "keyword": keyword})
        return result

    def reviewed_filenames(self) -> List[str]:
        return [s["filename"] for s in self.suggestions]
