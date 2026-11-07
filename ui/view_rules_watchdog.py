"""Custom Rule Engine Editor, Semantic Domain Taxonomy Explorer,
and Background Watchdog / Tray Service Monitor.
"""

import os
import uuid
from typing import Dict, List
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QFileDialog, QCheckBox, QDialog, QMessageBox,
    QPlainTextEdit, QSplitter, QTabWidget, QListWidget, QListWidgetItem,
    QInputDialog
)

from config import DEFAULT_EXTENSION_MAPPING, DEFAULT_TAXONOMY
from core.file_logic import (
    CustomRule,
    load_custom_rules,
    save_custom_rules,
    load_extension_mapping,
    save_extension_mapping,
    load_taxonomy,
    save_taxonomy,
    match_taxonomy
)
from core.watchdog_service import FolderWatchdogService


class AddRuleDialog(QDialog):
    """Dialog to create a new custom sorting rule."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Custom Organization Rule")
        self.resize(440, 260)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Create Custom Sorting Rule (Pass 0)")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Evaluated before smart grouping. Matches specific patterns or extensions.")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(subtitle)

        # Pattern
        layout.addWidget(QLabel("Match Pattern or Extension (e.g. *.pkt, .iso, report_*):"))
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("*.pkt")
        layout.addWidget(self.pattern_input)

        # Target Folder
        layout.addWidget(QLabel("Destination Subfolder Name:"))
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("Networking_Projects")
        layout.addWidget(self.folder_input)

        # Description
        layout.addWidget(QLabel("Description / Notes (Optional):"))
        self.desc_input = QLineEdit()
        self.desc_input.setPlaceholderText("Cisco Packet Tracer simulation topologies")
        layout.addWidget(self.desc_input)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Save Rule")
        btn_save.setObjectName("primaryButton")
        btn_save.clicked.connect(self._validate_and_save)
        btns.addWidget(btn_save)

        layout.addLayout(btns)

    def _validate_and_save(self):
        pat = self.pattern_input.text().strip()
        fld = self.folder_input.text().strip()
        if not pat or not fld:
            QMessageBox.warning(self, "Invalid Input", "Pattern and Destination Folder cannot be empty.")
            return
        self.accept()

    def get_rule(self) -> CustomRule:
        return CustomRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            pattern=self.pattern_input.text().strip(),
            target_folder=self.folder_input.text().strip(),
            enabled=True,
            description=self.desc_input.text().strip()
        )


class RulesAndWatchdogView(QWidget):
    status_message = pyqtSignal(str)
    minimize_to_tray_requested = pyqtSignal()

    def __init__(self, watchdog_service: FolderWatchdogService, parent=None):
        super().__init__(parent)
        self.watchdog = watchdog_service
        self.rules = load_custom_rules()
        self.taxonomy: Dict[str, List[str]] = load_taxonomy()
        self.extension_mapping: Dict[str, List[str]] = load_extension_mapping()
        self.current_category: str = list(self.taxonomy.keys())[0] if self.taxonomy else ""
        self.current_extension_category: str = ""

        self._init_ui()
        self._load_rules_to_table()
        self._load_taxonomy_list()
        self._load_extension_list()

        # Connect watchdog signals
        self.watchdog.file_detected.connect(self._on_file_detected)
        self.watchdog.organization_completed.connect(self._on_org_completed)
        self.watchdog.status_changed.connect(self._on_watchdog_status)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("Rules, Domain Taxonomy & Real-Time Watchdog")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel("Configure strict rules (Pass 0), bilingual semantic rules (Pass 1.5), extension fallbacks (Pass 2), and background sorting.")
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(5)

        # -------------------------------------------------------------
        # Top Section: Tabs for Rules & Semantic Taxonomy
        # -------------------------------------------------------------
        self.tabs = QTabWidget()

        # Tab 1: Strict Custom Rules (Pass 0)
        tab_rules = QWidget()
        rules_layout = QVBoxLayout(tab_rules)
        rules_layout.setContentsMargins(12, 12, 12, 12)
        rules_layout.setSpacing(10)

        rules_top = QHBoxLayout()
        r_title = QLabel("STRICT CUSTOM OVERRIDES (PASS 0)")
        r_title.setStyleSheet("font-weight: 700; color: #00E5FF; font-size: 12px; letter-spacing: 0.5px;")
        rules_top.addWidget(r_title)
        rules_top.addStretch()

        btn_add_rule = QPushButton("➕ Add Custom Rule")
        btn_add_rule.setObjectName("primaryButton")
        btn_add_rule.clicked.connect(self.prompt_add_rule)
        rules_top.addWidget(btn_add_rule)
        rules_layout.addLayout(rules_top)

        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(4)
        self.rules_table.setHorizontalHeaderLabels(["Enabled", "Pattern / Extension", "Destination Subfolder", "Description"])
        self.rules_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.rules_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.rules_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.rules_table.setColumnWidth(1, 160)
        self.rules_table.setColumnWidth(2, 220)
        rules_layout.addWidget(self.rules_table)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_delete_rule = QPushButton("Remove Selected Rule")
        btn_delete_rule.clicked.connect(self.delete_selected_rule)
        btn_row.addWidget(btn_delete_rule)
        rules_layout.addLayout(btn_row)

        self.tabs.addTab(tab_rules, "⚙️ Strict Rules (Pass 0)")

        # Tab 2: Semantic Domain Taxonomy (Pass 1.5)
        tab_tax = QWidget()
        tax_layout = QVBoxLayout(tab_tax)
        tax_layout.setContentsMargins(12, 12, 12, 12)
        tax_layout.setSpacing(10)

        tax_top = QHBoxLayout()
        tax_title = QLabel("BILINGUAL DOMAIN TAXONOMY (PASS 1.5 • 11 CATEGORIES)")
        tax_title.setStyleSheet("font-weight: 700; color: #E879F9; font-size: 12px; letter-spacing: 0.5px;")
        tax_top.addWidget(tax_title)
        tax_top.addStretch()

        btn_reset_tax = QPushButton("🔄 Reset Taxonomy to Defaults")
        btn_reset_tax.clicked.connect(self.reset_taxonomy_defaults)
        tax_top.addWidget(btn_reset_tax)
        tax_layout.addLayout(tax_top)

        # Splitter between categories list and keyword editor
        h_splitter = QSplitter(Qt.Orientation.Horizontal)
        h_splitter.setHandleWidth(4)

        # Left: Category List
        left_box = QWidget()
        left_layout = QVBoxLayout(left_box)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        left_lbl = QLabel("Target Domain Folders:")
        left_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; font-size: 11px;")
        left_layout.addWidget(left_lbl)

        self.tax_list = QListWidget()
        self.tax_list.currentRowChanged.connect(self._on_category_selected)
        left_layout.addWidget(self.tax_list)

        tax_category_buttons = QHBoxLayout()
        for label, callback in (
            ("Add", self.add_taxonomy_category),
            ("Rename", self.rename_taxonomy_category),
            ("Delete", self.delete_taxonomy_category),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            tax_category_buttons.addWidget(button)
        left_layout.addLayout(tax_category_buttons)
        h_splitter.addWidget(left_box)

        # Right: Keyword Editor & Tester
        right_box = QWidget()
        right_layout = QVBoxLayout(right_box)
        right_layout.setContentsMargins(6, 0, 0, 0)
        right_layout.setSpacing(8)

        self.tax_cat_title = QLabel("Selected Domain: —")
        self.tax_cat_title.setStyleSheet("font-weight: 700; color: #F8FAFC; font-size: 13px;")
        right_layout.addWidget(self.tax_cat_title)

        tax_desc = QLabel("Keywords and Extension Tags (comma-separated or one per line):")
        tax_desc.setStyleSheet("color: #94A3B8; font-size: 11px;")
        right_layout.addWidget(tax_desc)

        self.tax_editor = QPlainTextEdit()
        self.tax_editor.setPlaceholderText("Enter keywords e.g. packet tracer, wireshark, .pkt")
        right_layout.addWidget(self.tax_editor, 1)

        tax_btns = QHBoxLayout()
        tax_btns.addStretch()

        btn_save_cat = QPushButton("💾 Save Domain Keywords")
        btn_save_cat.setObjectName("primaryButton")
        btn_save_cat.clicked.connect(self.save_current_category_keywords)
        tax_btns.addWidget(btn_save_cat)
        right_layout.addLayout(tax_btns)

        # Real-time Interactive Classifier Tester
        test_frame = QFrame()
        test_frame.setObjectName("elevatedCard")
        test_layout = QVBoxLayout(test_frame)
        test_layout.setContentsMargins(10, 8, 10, 8)
        test_layout.setSpacing(4)

        test_header = QLabel("🔍 Interactive Filename Classifier Tester:")
        test_header.setStyleSheet("font-weight: 700; color: #38BDF8; font-size: 11px;")
        test_layout.addWidget(test_header)

        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText("Type a sample filename e.g. lettre_de_motivation.docx or cisco_lab.pkt")
        self.test_input.textChanged.connect(self._test_classify_filename)
        test_layout.addWidget(self.test_input)

        self.test_result_lbl = QLabel("Enter a filename above to test semantic classification.")
        self.test_result_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
        test_layout.addWidget(self.test_result_lbl)

        right_layout.addWidget(test_frame)
        h_splitter.addWidget(right_box)
        h_splitter.setStretchFactor(0, 1)
        h_splitter.setStretchFactor(1, 2)

        tax_layout.addWidget(h_splitter)
        self.tabs.addTab(tab_tax, "🧠 Semantic Rules (Pass 1.5)")

        # Tab 3: Extension Mapping Catch-All
        tab_extensions = QWidget()
        ext_layout = QVBoxLayout(tab_extensions)
        ext_layout.setContentsMargins(12, 12, 12, 12)
        ext_layout.setSpacing(10)
        ext_layout.addWidget(QLabel(
            "Extensions left after custom rules, smart grouping, and semantic matching "
            "are routed by this mapping (Pass 2). Enter one extension per line."
        ))

        ext_splitter = QSplitter(Qt.Orientation.Horizontal)
        ext_left = QWidget()
        ext_left_layout = QVBoxLayout(ext_left)
        ext_left_layout.setContentsMargins(0, 0, 0, 0)
        ext_left_layout.addWidget(QLabel("Fallback Categories:"))
        self.extension_list = QListWidget()
        self.extension_list.currentRowChanged.connect(self._on_extension_category_selected)
        ext_left_layout.addWidget(self.extension_list, 1)

        ext_category_buttons = QHBoxLayout()
        for label, callback in (
            ("Add", self.add_extension_category),
            ("Rename", self.rename_extension_category),
            ("Delete", self.delete_extension_category),
        ):
            button = QPushButton(label)
            button.clicked.connect(callback)
            ext_category_buttons.addWidget(button)
        ext_left_layout.addLayout(ext_category_buttons)
        ext_splitter.addWidget(ext_left)

        ext_right = QWidget()
        ext_right_layout = QVBoxLayout(ext_right)
        ext_right_layout.setContentsMargins(0, 0, 0, 0)
        self.extension_category_title = QLabel("Selected Category: —")
        self.extension_category_title.setStyleSheet(
            "font-weight: 700; color: #F8FAFC; font-size: 13px;"
        )
        ext_right_layout.addWidget(self.extension_category_title)
        self.extension_editor = QPlainTextEdit()
        self.extension_editor.setPlaceholderText(".png\n.jpg\n.jpeg")
        ext_right_layout.addWidget(self.extension_editor, 1)

        ext_actions = QHBoxLayout()
        btn_reset_extensions = QPushButton("Reset to Defaults")
        btn_reset_extensions.clicked.connect(self.reset_extension_defaults)
        ext_actions.addWidget(btn_reset_extensions)
        ext_actions.addStretch()
        btn_save_extensions = QPushButton("Save Extensions")
        btn_save_extensions.setObjectName("primaryButton")
        btn_save_extensions.clicked.connect(self.save_current_extensions)
        ext_actions.addWidget(btn_save_extensions)
        ext_right_layout.addLayout(ext_actions)
        ext_splitter.addWidget(ext_right)
        ext_splitter.setStretchFactor(0, 1)
        ext_splitter.setStretchFactor(1, 2)
        ext_layout.addWidget(ext_splitter, 1)
        self.tabs.addTab(tab_extensions, "🗂️ Extension Mapping (Pass 2)")

        splitter.addWidget(self.tabs)

        # -------------------------------------------------------------
        # Section 2: Folder Watchdog Card
        # -------------------------------------------------------------
        watchdog_card = QFrame()
        watchdog_card.setObjectName("cardFrame")
        w_layout = QVBoxLayout(watchdog_card)
        w_layout.setContentsMargins(14, 12, 14, 12)
        w_layout.setSpacing(10)

        w_top = QHBoxLayout()
        w_title = QLabel("ACTIVE SYSTEM TRAY WATCHDOG")
        w_title.setStyleSheet("font-weight: 700; color: #8B5CF6; font-size: 12px; letter-spacing: 0.5px;")
        w_top.addWidget(w_title)
        w_top.addStretch()

        self.btn_toggle_watch = QPushButton("▶️ Start Watchdog")
        self.btn_toggle_watch.setObjectName("successButton")
        self.btn_toggle_watch.clicked.connect(self.toggle_watchdog)
        w_top.addWidget(self.btn_toggle_watch)

        btn_tray = QPushButton("📥 Minimize to System Tray")
        btn_tray.setObjectName("purpleButton")
        btn_tray.clicked.connect(self.minimize_to_tray_requested.emit)
        w_top.addWidget(btn_tray)

        w_layout.addLayout(w_top)

        # Watch Directory selector
        w_dir_layout = QHBoxLayout()
        self.btn_watch_up = QPushButton("⬆️ Up to Parent")
        self.btn_watch_up.setToolTip("Return up to the parent directory")
        self.btn_watch_up.clicked.connect(self.navigate_watch_up)
        w_dir_layout.addWidget(self.btn_watch_up)

        w_dir_layout.addWidget(QLabel("Monitored Folder:"))
        self.watch_dir_input = QLineEdit(os.path.abspath("."))
        w_dir_layout.addWidget(self.watch_dir_input, 1)

        btn_browse_watch = QPushButton("Browse...")
        btn_browse_watch.clicked.connect(self.browse_watch_dir)
        w_dir_layout.addWidget(btn_browse_watch)
        w_layout.addLayout(w_dir_layout)

        # Console Log for Watchdog
        log_header = QHBoxLayout()
        log_header.addWidget(QLabel("Live Watchdog Activity Stream:"))
        log_header.addStretch()
        btn_clear_log = QPushButton("Clear Stream")
        btn_clear_log.clicked.connect(lambda: self.log_console.clear())
        log_header.addWidget(btn_clear_log)
        w_layout.addLayout(log_header)

        self.log_console = QPlainTextEdit()
        self.log_console.setReadOnly(True)
        w_layout.addWidget(self.log_console)

        splitter.addWidget(watchdog_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root_layout.addWidget(splitter)

    # -------------------------------------------------------------
    # Custom Rules Logic
    # -------------------------------------------------------------
    def _load_rules_to_table(self):
        self.rules_table.setRowCount(len(self.rules))
        for row, r in enumerate(self.rules):
            chk = QTableWidgetItem()
            chk.setCheckState(Qt.CheckState.Checked if r.enabled else Qt.CheckState.Unchecked)
            self.rules_table.setItem(row, 0, chk)

            self.rules_table.setItem(row, 1, QTableWidgetItem(r.pattern))
            self.rules_table.setItem(row, 2, QTableWidgetItem(f"📁 {r.target_folder}/"))
            self.rules_table.setItem(row, 3, QTableWidgetItem(r.description or "—"))

    def prompt_add_rule(self):
        dialog = AddRuleDialog(self)
        if dialog.exec():
            new_rule = dialog.get_rule()
            self.rules.append(new_rule)
            save_custom_rules(self.rules)
            self._load_rules_to_table()
            self.status_message.emit(f"Added custom rule for '{new_rule.pattern}' -> '{new_rule.target_folder}/'")

    def delete_selected_rule(self):
        row = self.rules_table.currentRow()
        if 0 <= row < len(self.rules):
            r = self.rules.pop(row)
            save_custom_rules(self.rules)
            self._load_rules_to_table()
            self.status_message.emit(f"Deleted rule '{r.pattern}'")

    # -------------------------------------------------------------
    # Semantic Domain Taxonomy Logic
    # -------------------------------------------------------------
    def _load_taxonomy_list(self):
        self.tax_list.clear()
        for cat_name, kws in self.taxonomy.items():
            item = QListWidgetItem(f"📁 {cat_name} ({len(kws)} tags)")
            item.setData(Qt.ItemDataRole.UserRole, cat_name)
            self.tax_list.addItem(item)

        if self.tax_list.count() > 0:
            self.tax_list.setCurrentRow(0)

    def _save_taxonomy_data(self, taxonomy: Dict[str, List[str]]) -> bool:
        try:
            save_taxonomy(taxonomy)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save semantic rules:\n{exc}")
            return False
        self.taxonomy = taxonomy
        return True

    @staticmethod
    def _valid_category_name(name: str) -> bool:
        return bool(
            name
            and name not in {".", ".."}
            and not name.endswith((" ", "."))
            and not any(char in name for char in '<>:"/\\|?*')
        )

    def _on_category_selected(self, row: int):
        if row < 0:
            self.current_category = ""
            self.tax_cat_title.setText("Selected Domain: —")
            self.tax_editor.clear()
            return
        item = self.tax_list.item(row)
        cat_name = item.data(Qt.ItemDataRole.UserRole)
        self.current_category = cat_name
        self.tax_cat_title.setText(f"Domain Folder: 📁 {cat_name}")

        keywords = self.taxonomy.get(cat_name, [])
        self.tax_editor.setPlainText(", ".join(keywords))

    def add_taxonomy_category(self):
        name, accepted = QInputDialog.getText(self, "Add Semantic Category", "Category folder name:")
        name = name.strip()
        if not accepted:
            return
        if not self._valid_category_name(name) or any(
            name.casefold() == key.casefold() for key in self.taxonomy
        ):
            QMessageBox.warning(self, "Invalid Category", "Enter a unique, non-empty category name.")
            return
        updated = dict(self.taxonomy)
        updated[name] = []
        if self._save_taxonomy_data(updated):
            self._load_taxonomy_list()
            for row in range(self.tax_list.count()):
                if self.tax_list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                    self.tax_list.setCurrentRow(row)
                    break

    def rename_taxonomy_category(self):
        if not self.current_category:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename Semantic Category", "Category folder name:", text=self.current_category
        )
        name = name.strip()
        if not accepted:
            return
        if not self._valid_category_name(name) or (
            name.casefold() != self.current_category.casefold()
            and any(name.casefold() == key.casefold() for key in self.taxonomy)
        ):
            QMessageBox.warning(self, "Invalid Category", "Enter a unique, non-empty category name.")
            return
        updated = {
            (name if key == self.current_category else key): keywords
            for key, keywords in self.taxonomy.items()
        }
        if self._save_taxonomy_data(updated):
            self.current_category = name
            self._load_taxonomy_list()
            for row in range(self.tax_list.count()):
                if self.tax_list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                    self.tax_list.setCurrentRow(row)
                    break

    def delete_taxonomy_category(self):
        if not self.current_category:
            return
        reply = QMessageBox.question(
            self,
            "Delete Semantic Category",
            f"Delete '{self.current_category}' and all of its keywords?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        updated = {
            key: value for key, value in self.taxonomy.items()
            if key != self.current_category
        }
        if self._save_taxonomy_data(updated):
            self.current_category = ""
            self._load_taxonomy_list()

    def save_current_category_keywords(self):
        if not self.current_category:
            return
        raw = self.tax_editor.toPlainText()
        tokens = [t.strip() for t in raw.replace("\n", ",").split(",") if t.strip()]
        updated = dict(self.taxonomy)
        updated[self.current_category] = tokens
        if not self._save_taxonomy_data(updated):
            return

        # Refresh list row badge count
        curr_row = self.tax_list.currentRow()
        self._load_taxonomy_list()
        self.tax_list.setCurrentRow(curr_row)

        self.status_message.emit(f"Saved {len(tokens)} keywords for '{self.current_category}'")

    def reset_taxonomy_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset Taxonomy",
            "Are you sure you want to restore the default 11 bilingual domain categories and keywords?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            defaults = {
                category: list(keywords)
                for category, keywords in DEFAULT_TAXONOMY.items()
            }
            if self._save_taxonomy_data(defaults):
                self._load_taxonomy_list()
                self.status_message.emit("Semantic Domain Taxonomy restored to defaults.")

    def _load_extension_list(self):
        self.extension_list.clear()
        for category, extensions in self.extension_mapping.items():
            item = QListWidgetItem(f"📁 {category} ({len(extensions)} extensions)")
            item.setData(Qt.ItemDataRole.UserRole, category)
            self.extension_list.addItem(item)
        if self.extension_list.count():
            self.extension_list.setCurrentRow(0)

    def _on_extension_category_selected(self, row: int):
        if row < 0:
            self.current_extension_category = ""
            self.extension_category_title.setText("Selected Category: —")
            self.extension_editor.clear()
            return
        item = self.extension_list.item(row)
        category = item.data(Qt.ItemDataRole.UserRole)
        self.current_extension_category = category
        self.extension_category_title.setText(f"Fallback Folder: 📁 {category}")
        self.extension_editor.setPlainText(
            "\n".join(self.extension_mapping.get(category, []))
        )

    def _save_extension_data(self, mapping: Dict[str, List[str]]) -> bool:
        try:
            save_extension_mapping(mapping)
        except OSError as exc:
            QMessageBox.critical(self, "Save Failed", f"Could not save extension mapping:\n{exc}")
            return False
        self.extension_mapping = mapping
        return True

    def add_extension_category(self):
        name, accepted = QInputDialog.getText(self, "Add Fallback Category", "Category folder name:")
        name = name.strip()
        if not accepted:
            return
        if not self._valid_category_name(name) or any(
            name.casefold() == key.casefold() for key in self.extension_mapping
        ):
            QMessageBox.warning(self, "Invalid Category", "Enter a unique, non-empty category name.")
            return
        updated = dict(self.extension_mapping)
        updated[name] = []
        if self._save_extension_data(updated):
            self._load_extension_list()
            for row in range(self.extension_list.count()):
                if self.extension_list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                    self.extension_list.setCurrentRow(row)
                    break

    def rename_extension_category(self):
        if not self.current_extension_category:
            return
        name, accepted = QInputDialog.getText(
            self, "Rename Fallback Category", "Category folder name:",
            text=self.current_extension_category
        )
        name = name.strip()
        if not accepted:
            return
        if not self._valid_category_name(name) or (
            name.casefold() != self.current_extension_category.casefold()
            and any(name.casefold() == key.casefold() for key in self.extension_mapping)
        ):
            QMessageBox.warning(self, "Invalid Category", "Enter a unique, non-empty category name.")
            return
        updated = {
            (name if key == self.current_extension_category else key): extensions
            for key, extensions in self.extension_mapping.items()
        }
        if self._save_extension_data(updated):
            self.current_extension_category = name
            self._load_extension_list()
            for row in range(self.extension_list.count()):
                if self.extension_list.item(row).data(Qt.ItemDataRole.UserRole) == name:
                    self.extension_list.setCurrentRow(row)
                    break

    def delete_extension_category(self):
        if not self.current_extension_category:
            return
        reply = QMessageBox.question(
            self,
            "Delete Fallback Category",
            f"Delete '{self.current_extension_category}' and all of its extensions?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        updated = {
            key: value for key, value in self.extension_mapping.items()
            if key != self.current_extension_category
        }
        if self._save_extension_data(updated):
            self.current_extension_category = ""
            self._load_extension_list()

    def save_current_extensions(self):
        if not self.current_extension_category:
            return
        category = self.current_extension_category
        raw_extensions = self.extension_editor.toPlainText().replace(",", "\n").splitlines()
        extensions = []
        for raw in raw_extensions:
            extension = raw.strip().lower()
            if not extension:
                continue
            if not extension.startswith("."):
                extension = f".{extension}"
            if len(extension) < 2 or any(char in extension for char in "\\/"):
                QMessageBox.warning(self, "Invalid Extension", f"Invalid extension: {raw.strip()}")
                return
            if extension not in extensions:
                extensions.append(extension)

        assigned_elsewhere = {
            extension
            for other_category, other_extensions in self.extension_mapping.items()
            if other_category != category
            for extension in other_extensions
        }
        duplicates = sorted(set(extensions) & assigned_elsewhere)
        if duplicates:
            QMessageBox.warning(
                self,
                "Extension Already Assigned",
                "Each extension can belong to only one fallback category:\n"
                + ", ".join(duplicates)
            )
            return

        updated = dict(self.extension_mapping)
        updated[category] = extensions
        if self._save_extension_data(updated):
            self._load_extension_list()
            for row in range(self.extension_list.count()):
                if self.extension_list.item(row).data(Qt.ItemDataRole.UserRole) == category:
                    self.extension_list.setCurrentRow(row)
                    break
            self.status_message.emit(
                f"Saved {len(extensions)} extensions for '{category}'"
            )

    def reset_extension_defaults(self):
        reply = QMessageBox.question(
            self,
            "Reset Extension Mapping",
            "Restore the default file extension categories and mappings?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        defaults = {
            category: list(extensions)
            for category, extensions in DEFAULT_EXTENSION_MAPPING.items()
        }
        if self._save_extension_data(defaults):
            self._load_extension_list()
            self.status_message.emit("Extension Mapping restored to defaults.")

    def _test_classify_filename(self, text: str):
        fn = text.strip()
        if not fn:
            self.test_result_lbl.setText("Enter a filename above to test semantic classification.")
            self.test_result_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 600;")
            return

        res = match_taxonomy(fn, self.taxonomy)
        if res:
            cat_name, kw = res
            self.test_result_lbl.setText(f"🎯 MATCH: Routes to '{cat_name}/' via keyword '{kw}'")
            self.test_result_lbl.setStyleSheet("color: #00E5FF; font-size: 12px; font-weight: 700;")
        else:
            self.test_result_lbl.setText("⚪ NO DOMAIN MATCH: Falls back to Smart Stem Grouping or Category Extension.")
            self.test_result_lbl.setStyleSheet("color: #94A3B8; font-size: 12px; font-weight: 500;")

    # -------------------------------------------------------------
    # Watchdog Logic
    # -------------------------------------------------------------
    def navigate_watch_up(self):
        """Return up to the parent directory."""
        curr = self.watch_dir_input.text().strip()
        parent = os.path.dirname(curr)
        if parent and parent != curr and os.path.isdir(parent):
            self.set_directory(parent)

    def set_directory(self, path: str):
        self.watch_dir_input.setText(os.path.abspath(path))

    def browse_watch_dir(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Folder to Watch", self.watch_dir_input.text())
        if chosen:
            self.watch_dir_input.setText(os.path.abspath(chosen))

    def toggle_watchdog(self):
        if self.watchdog.is_running:
            self.watchdog.stop_watching()
            self.btn_toggle_watch.setText("▶️ Start Watchdog")
            self.btn_toggle_watch.setObjectName("successButton")
            self.btn_toggle_watch.setStyleSheet("")
        else:
            folder = self.watch_dir_input.text().strip()
            if not os.path.isdir(folder):
                QMessageBox.warning(self, "Invalid Directory", f"Folder does not exist:\n{folder}")
                return
            self.watchdog.start_watching(folder)
            self.btn_toggle_watch.setText("⏹️ Stop Watchdog")
            self.btn_toggle_watch.setObjectName("dangerButton")
            self.btn_toggle_watch.setStyleSheet("")

    def _on_file_detected(self, filename: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_console.appendPlainText(f"{ts} [DETECTED] New file arrived: '{filename}'")

    def _on_org_completed(self, count: int, summary: str):
        from datetime import datetime
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_console.appendPlainText(f"{ts} [ORGANIZED] {summary}")

    def _on_watchdog_status(self, active: bool, msg: str):
        self.status_message.emit(msg)
