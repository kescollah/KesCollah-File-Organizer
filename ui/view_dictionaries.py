"""Context Dictionary Manager UI:
Provides a dual-list editor for 'Static Rules' (semantic_rules.json) and
'AI-Learned Rules' (learned_rules.json) allowing viewing, adding, editing, and deleting rules.
Also provides full editing for extension_mapping.json and Custom Rules (Pass 0).
"""

import os
import json
import uuid
from typing import Dict, List, Optional
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QListWidget, QListWidgetItem, QTableWidget,
    QTableWidgetItem, QHeaderView, QFrame, QMessageBox,
    QInputDialog, QTabWidget, QSplitter
)

from config import (
    DEFAULT_TAXONOMY,
    DEFAULT_EXTENSION_MAPPING,
    TAXONOMY_FILE,
    LEARNED_RULES_FILE,
    EXTENSION_MAPPING_FILE
)
from core.file_logic import (
    CustomRule,
    load_custom_rules,
    save_custom_rules,
    load_taxonomy,
    save_taxonomy,
    load_extension_mapping,
    save_extension_mapping
)
from core.gemini_sync import (
    load_learned_rules,
    save_learned_rules,
    normalize_keyword
)


class DictionaryManagerView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.static_taxonomy: Dict[str, List[str]] = {}
        self.learned_taxonomy: Dict[str, List[str]] = {}
        self.extension_mapping: Dict[str, List[str]] = {}
        self.custom_rules: List[CustomRule] = []
        self.current_semantic_cat: Optional[str] = None
        self.current_ext_cat: Optional[str] = None
        self._init_ui()
        self.load_all_dictionaries()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Context Dictionary Manager — Rules & Taxonomies")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "Inspect and manage offline dictionary rules. Review AI-learned keywords side-by-side with static rules, "
            "edit or delete associations, and customize extension fallbacks."
        )
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Main Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setObjectName("customTabWidget")

        # Tab 1: Semantic Rules (Static vs AI-Learned)
        self.tab_semantic = self._build_semantic_rules_tab()
        self.tabs.addTab(self.tab_semantic, "🧠 Semantic Rules (Static vs AI-Learned)")

        # Tab 2: Extension Mapping
        self.tab_extensions = self._build_extension_mapping_tab()
        self.tabs.addTab(self.tab_extensions, "📁 Extension Fallback (extension_mapping.json)")

        # Tab 3: Custom Rules (Pass 0)
        self.tab_custom = self._build_custom_rules_tab()
        self.tabs.addTab(self.tab_custom, "⚡ Custom Rules (Pass 0)")

        layout.addWidget(self.tabs)

    # -----------------------------------------------------------------------
    # TAB 1: Semantic Rules (Static vs AI-Learned)
    # -----------------------------------------------------------------------
    def _build_semantic_rules_tab(self) -> QWidget:
        widget = QWidget()
        v_layout = QVBoxLayout(widget)
        v_layout.setContentsMargins(8, 10, 8, 8)
        v_layout.setSpacing(10)

        # Top Bar: Search & Stats
        top_bar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Filter keyword across categories...")
        self.search_input.textChanged.connect(self._filter_semantic_keywords)
        top_bar.addWidget(self.search_input, 1)

        btn_reload = QPushButton("🔄 Reload from Disk")
        btn_reload.clicked.connect(self.load_all_dictionaries)
        top_bar.addWidget(btn_reload)

        btn_reset_static = QPushButton("Factory Default Static Rules")
        btn_reset_static.clicked.connect(self._reset_static_defaults)
        top_bar.addWidget(btn_reset_static)

        v_layout.addLayout(top_bar)

        # Main Splitter: Left = Categories, Right = Dual List (Static vs Learned)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel: Category Selector
        left_frame = QFrame()
        left_frame.setObjectName("cardFrame")
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(10, 10, 10, 10)
        l_layout.setSpacing(6)

        cat_lbl = QLabel("TAXONOMY CATEGORIES")
        cat_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; font-size: 11px;")
        l_layout.addWidget(cat_lbl)

        self.list_categories = QListWidget()
        self.list_categories.itemClicked.connect(self._on_category_selected)
        l_layout.addWidget(self.list_categories, 1)

        splitter.addWidget(left_frame)

        # Right Panel: Dual Lists (Static Rules vs AI-Learned Rules)
        right_frame = QFrame()
        right_frame.setObjectName("cardFrame")
        r_layout = QHBoxLayout(right_frame)
        r_layout.setContentsMargins(12, 10, 12, 10)
        r_layout.setSpacing(16)

        # Col A: Static Rules (semantic_rules.json)
        col_static = QVBoxLayout()
        lbl_static = QLabel("📋 Static Rules (semantic_rules.json)")
        lbl_static.setStyleSheet("font-weight: 700; color: #00E5FF; font-size: 12px;")
        col_static.addWidget(lbl_static)

        self.list_static = QListWidget()
        col_static.addWidget(self.list_static, 1)

        btns_static = QHBoxLayout()
        btn_add_s = QPushButton("➕ Add")
        btn_add_s.clicked.connect(self._add_static_keyword)
        btns_static.addWidget(btn_add_s)

        btn_edit_s = QPushButton("✏️ Edit")
        btn_edit_s.clicked.connect(self._edit_static_keyword)
        btns_static.addWidget(btn_edit_s)

        btn_del_s = QPushButton("🗑️ Delete")
        btn_del_s.setObjectName("dangerButton")
        btn_del_s.clicked.connect(self._delete_static_keyword)
        btns_static.addWidget(btn_del_s)
        col_static.addLayout(btns_static)
        r_layout.addLayout(col_static)

        # Col B: AI-Learned Rules (learned_rules.json)
        col_learned = QVBoxLayout()
        lbl_learned = QLabel("🧠 AI-Learned Rules (learned_rules.json)")
        lbl_learned.setStyleSheet("font-weight: 700; color: #E879F9; font-size: 12px;")
        col_learned.addWidget(lbl_learned)

        self.list_learned = QListWidget()
        col_learned.addWidget(self.list_learned, 1)

        btns_learned = QHBoxLayout()
        btn_add_l = QPushButton("➕ Add")
        btn_add_l.clicked.connect(self._add_learned_keyword)
        btns_learned.addWidget(btn_add_l)

        btn_edit_l = QPushButton("✏️ Edit")
        btn_edit_l.clicked.connect(self._edit_learned_keyword)
        btns_learned.addWidget(btn_edit_l)

        btn_del_l = QPushButton("🗑️ Delete")
        btn_del_l.setObjectName("dangerButton")
        btn_del_l.setToolTip("Delete a rule if Gemini made a bad association")
        btn_del_l.clicked.connect(self._delete_learned_keyword)
        btns_learned.addWidget(btn_del_l)
        col_learned.addLayout(btns_learned)
        r_layout.addLayout(col_learned)

        splitter.addWidget(right_frame)
        splitter.setSizes([260, 680])
        v_layout.addWidget(splitter, 1)

        return widget

    # -----------------------------------------------------------------------
    # TAB 2: Extension Mapping
    # -----------------------------------------------------------------------
    def _build_extension_mapping_tab(self) -> QWidget:
        widget = QWidget()
        v_layout = QVBoxLayout(widget)
        v_layout.setContentsMargins(8, 10, 8, 8)
        v_layout.setSpacing(10)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Extension Categories
        left_frame = QFrame()
        left_frame.setObjectName("cardFrame")
        l_layout = QVBoxLayout(left_frame)
        l_layout.setContentsMargins(10, 10, 10, 10)

        l_lbl = QLabel("EXTENSION CATEGORIES")
        l_lbl.setStyleSheet("font-weight: 700; color: #94A3B8; font-size: 11px;")
        l_layout.addWidget(l_lbl)

        self.list_ext_cats = QListWidget()
        self.list_ext_cats.itemClicked.connect(self._on_ext_cat_selected)
        l_layout.addWidget(self.list_ext_cats, 1)

        btn_reset_ext = QPushButton("Reset to Factory Defaults")
        btn_reset_ext.clicked.connect(self._reset_ext_defaults)
        l_layout.addWidget(btn_reset_ext)
        splitter.addWidget(left_frame)

        # Right: Extensions in Category
        right_frame = QFrame()
        right_frame.setObjectName("cardFrame")
        r_layout = QVBoxLayout(right_frame)
        r_layout.setContentsMargins(12, 10, 12, 10)

        self.lbl_ext_title = QLabel("Configured Extensions")
        self.lbl_ext_title.setStyleSheet("font-weight: 700; color: #00E5FF; font-size: 13px;")
        r_layout.addWidget(self.lbl_ext_title)

        self.list_ext_items = QListWidget()
        r_layout.addWidget(self.list_ext_items, 1)

        ext_btns = QHBoxLayout()
        btn_add_ext = QPushButton("➕ Add Extension")
        btn_add_ext.clicked.connect(self._add_extension)
        ext_btns.addWidget(btn_add_ext)

        btn_edit_ext = QPushButton("✏️ Edit Extension")
        btn_edit_ext.clicked.connect(self._edit_extension)
        ext_btns.addWidget(btn_edit_ext)

        btn_del_ext = QPushButton("🗑️ Remove Extension")
        btn_del_ext.setObjectName("dangerButton")
        btn_del_ext.clicked.connect(self._delete_extension)
        ext_btns.addWidget(btn_del_ext)
        r_layout.addLayout(ext_btns)

        splitter.addWidget(right_frame)
        splitter.setSizes([260, 680])
        v_layout.addWidget(splitter, 1)

        return widget

    # -----------------------------------------------------------------------
    # TAB 3: Custom Rules (Pass 0)
    # -----------------------------------------------------------------------
    def _build_custom_rules_tab(self) -> QWidget:
        widget = QWidget()
        v_layout = QVBoxLayout(widget)
        v_layout.setContentsMargins(8, 10, 8, 8)
        v_layout.setSpacing(10)

        # Toolbar
        t_layout = QHBoxLayout()
        btn_add_rule = QPushButton("➕ Add Custom Rule")
        btn_add_rule.setObjectName("primaryButton")
        btn_add_rule.clicked.connect(self._add_custom_rule)
        t_layout.addWidget(btn_add_rule)

        btn_del_rule = QPushButton("🗑️ Delete Selected Rule")
        btn_del_rule.setObjectName("dangerButton")
        btn_del_rule.clicked.connect(self._delete_custom_rule)
        t_layout.addWidget(btn_del_rule)

        t_layout.addStretch()
        v_layout.addLayout(t_layout)

        # Rules Table
        self.table_custom = QTableWidget()
        self.table_custom.setColumnCount(4)
        self.table_custom.setHorizontalHeaderLabels(["Pattern / Glob", "Target Subfolder", "Enabled", "Description"])
        self.table_custom.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_custom.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        self.table_custom.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_custom.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table_custom.setColumnWidth(0, 180)
        self.table_custom.setColumnWidth(1, 200)
        v_layout.addWidget(self.table_custom, 1)

        return widget

    # -----------------------------------------------------------------------
    # Loading & Syncing Data
    # -----------------------------------------------------------------------
    def load_all_dictionaries(self):
        self.static_taxonomy = load_taxonomy()
        self.learned_taxonomy = load_learned_rules()
        self.extension_mapping = load_extension_mapping()
        self.custom_rules = load_custom_rules()

        # Populate Category lists
        self._populate_category_lists()
        self._populate_extension_categories()
        self._populate_custom_rules_table()
        self.status_message.emit("Context dictionaries loaded successfully.")

    def _populate_category_lists(self):
        self.list_categories.clear()
        all_cats = sorted(set(list(self.static_taxonomy.keys()) + list(self.learned_taxonomy.keys())))
        for cat in all_cats:
            static_cnt = len(self.static_taxonomy.get(cat, []))
            learned_cnt = len(self.learned_taxonomy.get(cat, []))
            item = QListWidgetItem(f"📁 {cat}  ({static_cnt} / +{learned_cnt} AI)")
            item.setData(Qt.ItemDataRole.UserRole, cat)
            self.list_categories.addItem(item)

        if all_cats:
            self.list_categories.setCurrentRow(0)
            self._on_category_selected(self.list_categories.item(0))

    def _populate_extension_categories(self):
        self.list_ext_cats.clear()
        for cat, exts in self.extension_mapping.items():
            item = QListWidgetItem(f"📦 {cat}  ({len(exts)})")
            item.setData(Qt.ItemDataRole.UserRole, cat)
            self.list_ext_cats.addItem(item)

        if self.extension_mapping:
            self.list_ext_cats.setCurrentRow(0)
            self._on_ext_cat_selected(self.list_ext_cats.item(0))

    def _populate_custom_rules_table(self):
        self.table_custom.setRowCount(len(self.custom_rules))
        for row, rule in enumerate(self.custom_rules):
            self.table_custom.setItem(row, 0, QTableWidgetItem(rule.pattern))
            self.table_custom.setItem(row, 1, QTableWidgetItem(rule.target_folder))
            status_item = QTableWidgetItem("Active" if rule.enabled else "Disabled")
            status_item.setForeground(QColor("#10B981" if rule.enabled else "#94A3B8"))
            self.table_custom.setItem(row, 2, status_item)
            self.table_custom.setItem(row, 3, QTableWidgetItem(rule.description or "—"))

    def _on_category_selected(self, item: QListWidgetItem):
        if not item:
            return
        cat = item.data(Qt.ItemDataRole.UserRole)
        self.current_semantic_cat = cat
        self._refresh_semantic_lists(cat)

    def _refresh_semantic_lists(self, cat: str):
        self.list_static.clear()
        for kw in sorted(self.static_taxonomy.get(cat, [])):
            self.list_static.addItem(f"•  {kw}")

        self.list_learned.clear()
        for kw in sorted(self.learned_taxonomy.get(cat, [])):
            self.list_learned.addItem(f"✨ {kw}")

    def _filter_semantic_keywords(self, query: str):
        q = query.strip().lower()
        if not q:
            if self.current_semantic_cat:
                self._refresh_semantic_lists(self.current_semantic_cat)
            return

        self.list_static.clear()
        self.list_learned.clear()

        for cat, kws in self.static_taxonomy.items():
            for kw in kws:
                if q in kw.lower():
                    self.list_static.addItem(f"[{cat}] {kw}")

        for cat, kws in self.learned_taxonomy.items():
            for kw in kws:
                if q in kw.lower():
                    self.list_learned.addItem(f"[{cat}] {kw}")

    # -----------------------------------------------------------------------
    # CRUD Operations on Semantic Rules
    # -----------------------------------------------------------------------
    def _add_static_keyword(self):
        if not self.current_semantic_cat:
            return
        text, ok = QInputDialog.getText(
            self, "Add Static Rule Keyword",
            f"Enter new keyword or extension for '{self.current_semantic_cat}':"
        )
        if ok and text.strip():
            kw = text.strip()
            self.static_taxonomy.setdefault(self.current_semantic_cat, []).append(kw)
            save_taxonomy(self.static_taxonomy)
            self._populate_category_lists()
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _edit_static_keyword(self):
        curr_row = self.list_static.currentRow()
        if curr_row < 0 or not self.current_semantic_cat:
            return
        old_val = self.static_taxonomy[self.current_semantic_cat][curr_row]
        new_val, ok = QInputDialog.getText(
            self, "Edit Static Keyword",
            "Modify keyword:",
            text=old_val
        )
        if ok and new_val.strip():
            self.static_taxonomy[self.current_semantic_cat][curr_row] = new_val.strip()
            save_taxonomy(self.static_taxonomy)
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _delete_static_keyword(self):
        curr_row = self.list_static.currentRow()
        if curr_row < 0 or not self.current_semantic_cat:
            return
        val = self.static_taxonomy[self.current_semantic_cat][curr_row]
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Remove static rule keyword '{val}' from category '{self.current_semantic_cat}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.static_taxonomy[self.current_semantic_cat].pop(curr_row)
            save_taxonomy(self.static_taxonomy)
            self._populate_category_lists()
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _add_learned_keyword(self):
        if not self.current_semantic_cat:
            return
        text, ok = QInputDialog.getText(
            self, "Add AI-Learned Keyword",
            f"Enter keyword to cache in learned_rules.json for '{self.current_semantic_cat}':"
        )
        if ok and text.strip():
            kw = text.strip()
            self.learned_taxonomy.setdefault(self.current_semantic_cat, []).append(kw)
            save_learned_rules(self.learned_taxonomy)
            self._populate_category_lists()
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _edit_learned_keyword(self):
        curr_row = self.list_learned.currentRow()
        if curr_row < 0 or not self.current_semantic_cat:
            return
        old_val = self.learned_taxonomy[self.current_semantic_cat][curr_row]
        new_val, ok = QInputDialog.getText(
            self, "Edit AI-Learned Keyword",
            "Modify AI-learned keyword:",
            text=old_val
        )
        if ok and new_val.strip():
            self.learned_taxonomy[self.current_semantic_cat][curr_row] = new_val.strip()
            save_learned_rules(self.learned_taxonomy)
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _delete_learned_keyword(self):
        """Allows deleting bad associations made by Gemini AI."""
        curr_row = self.list_learned.currentRow()
        if curr_row < 0 or not self.current_semantic_cat:
            return
        val = self.learned_taxonomy[self.current_semantic_cat][curr_row]
        reply = QMessageBox.question(
            self, "Prune AI Association",
            f"Delete AI-learned keyword '{val}' from '{self.current_semantic_cat}'?\n\n"
            "This fixes incorrect associations taught by the AI.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.learned_taxonomy[self.current_semantic_cat].pop(curr_row)
            save_learned_rules(self.learned_taxonomy)
            self._populate_category_lists()
            self._refresh_semantic_lists(self.current_semantic_cat)

    def _reset_static_defaults(self):
        reply = QMessageBox.question(
            self, "Reset Static Rules",
            "Reset semantic_rules.json to the factory default 11 bilingual domains?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.static_taxonomy = dict(DEFAULT_TAXONOMY)
            save_taxonomy(self.static_taxonomy)
            self._populate_category_lists()
            QMessageBox.information(self, "Reset Complete", "Static rules restored to factory defaults.")

    # -----------------------------------------------------------------------
    # Extension Mapping CRUD
    # -----------------------------------------------------------------------
    def _on_ext_cat_selected(self, item: QListWidgetItem):
        if not item:
            return
        cat = item.data(Qt.ItemDataRole.UserRole)
        self.current_ext_cat = cat
        self.lbl_ext_title.setText(f"📁 Extensions for Category: {cat}")
        self.list_ext_items.clear()
        for ext in self.extension_mapping.get(cat, []):
            self.list_ext_items.addItem(f"•  {ext}")

    def _add_extension(self):
        if not self.current_ext_cat:
            return
        text, ok = QInputDialog.getText(
            self, "Add Extension",
            f"Enter file extension for '{self.current_ext_cat}' (e.g. .webp):"
        )
        if ok and text.strip():
            ext = text.strip().lower()
            if not ext.startswith("."):
                ext = f".{ext}"
            if ext not in self.extension_mapping[self.current_ext_cat]:
                self.extension_mapping[self.current_ext_cat].append(ext)
                save_extension_mapping(self.extension_mapping)
                self._populate_extension_categories()

    def _edit_extension(self):
        row = self.list_ext_items.currentRow()
        if row < 0 or not self.current_ext_cat:
            return
        old = self.extension_mapping[self.current_ext_cat][row]
        new_val, ok = QInputDialog.getText(
            self, "Edit Extension", "Modify extension:", text=old
        )
        if ok and new_val.strip():
            val = new_val.strip().lower()
            if not val.startswith("."):
                val = f".{val}"
            self.extension_mapping[self.current_ext_cat][row] = val
            save_extension_mapping(self.extension_mapping)
            self._populate_extension_categories()

    def _delete_extension(self):
        row = self.list_ext_items.currentRow()
        if row < 0 or not self.current_ext_cat:
            return
        ext = self.extension_mapping[self.current_ext_cat][row]
        reply = QMessageBox.question(
            self, "Remove Extension",
            f"Remove extension '{ext}' from '{self.current_ext_cat}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.extension_mapping[self.current_ext_cat].pop(row)
            save_extension_mapping(self.extension_mapping)
            self._populate_extension_categories()

    def _reset_ext_defaults(self):
        reply = QMessageBox.question(
            self, "Reset Extensions",
            "Reset extension_mapping.json to factory defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.extension_mapping = {k: list(v) for k, v in DEFAULT_EXTENSION_MAPPING.items()}
            save_extension_mapping(self.extension_mapping)
            self._populate_extension_categories()

    # -----------------------------------------------------------------------
    # Custom Rules (Pass 0) CRUD
    # -----------------------------------------------------------------------
    def _add_custom_rule(self):
        pat, ok1 = QInputDialog.getText(self, "New Rule", "Enter pattern or extension (e.g. *.pkt, .iso):")
        if not ok1 or not pat.strip():
            return
        folder, ok2 = QInputDialog.getText(self, "Target Folder", "Enter destination subfolder name:")
        if not ok2 or not folder.strip():
            return

        rule = CustomRule(
            id=f"rule_{uuid.uuid4().hex[:8]}",
            pattern=pat.strip(),
            target_folder=folder.strip(),
            enabled=True,
            description="User custom rule"
        )
        self.custom_rules.append(rule)
        save_custom_rules(self.custom_rules)
        self._populate_custom_rules_table()

    def _delete_custom_rule(self):
        row = self.table_custom.currentRow()
        if row < 0 or row >= len(self.custom_rules):
            QMessageBox.warning(self, "Selection", "Please select a custom rule row to delete.")
            return

        rule = self.custom_rules[row]
        reply = QMessageBox.question(
            self, "Delete Rule",
            f"Delete rule for pattern '{rule.pattern}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.custom_rules.pop(row)
            save_custom_rules(self.custom_rules)
            self._populate_custom_rules_table()
