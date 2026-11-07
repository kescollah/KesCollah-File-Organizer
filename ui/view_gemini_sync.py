"""Gemini AI Knowledge Sync: The Brain & Self-Learning Caching System.
Sends batched unrecognized filenames to Gemini (structured JSON, default gemini-3.8-flash with
"medium" thinking), lets the user review every proposed rule, then updates learned_rules.json.
"""

import json
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QProgressBar, QInputDialog, QCheckBox,
    QDialog, QPlainTextEdit
)

from config import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_THINKING_LEVEL,
    SUPPORTED_GEMINI_MODELS,
    THINKING_LEVELS,
    FALLBACK_GEMINI_MODEL
)
from core.gemini_sync import (
    load_unrecognized_files,
    clear_unrecognized_files,
    log_unrecognized_file,
    load_learned_rules,
    get_gemini_api_key,
    set_gemini_api_key,
    get_gemini_model,
    set_gemini_model,
    get_thinking_tier,
    set_thinking_tier,
    get_privacy_shield,
    set_privacy_shield,
    get_cached_model_list,
    set_cached_model_list,
    list_available_models,
    load_sync_categories,
    build_sync_payload,
    fetch_suggestions,
    apply_suggestions,
    test_connection,
    SYNC_BATCH_SIZE
)
from ui.ai_review_dialog import AIReviewDialog


class FetchSuggestionsWorker(QThread):
    progress_status = pyqtSignal(str)
    suggestions_ready = pyqtSignal(list, str)   # suggestions, model actually used
    failed = pyqtSignal(str)

    def __init__(self, api_key: str, model_name: str, thinking_tier: str, privacy_shield: bool, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.thinking_tier = thinking_tier
        self.privacy_shield = privacy_shield

    def run(self):
        try:
            suggestions, used = fetch_suggestions(
                api_key=self.api_key,
                model_name=self.model_name,
                thinking_tier=self.thinking_tier,
                privacy_shield=self.privacy_shield,
                status_callback=self.progress_status.emit
            )
            self.suggestions_ready.emit(suggestions, used)
        except Exception as e:
            self.failed.emit(str(e))


class TestKeyWorker(QThread):
    test_result = pyqtSignal(bool, str)

    def __init__(self, api_key: str, model_name: str, thinking_tier: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key
        self.model_name = model_name
        self.thinking_tier = thinking_tier

    def run(self):
        ok, message = test_connection(self.api_key, self.model_name, self.thinking_tier)
        self.test_result.emit(ok, message)


class ModelListWorker(QThread):
    models_ready = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, api_key: str, parent=None):
        super().__init__(parent)
        self.api_key = api_key

    def run(self):
        try:
            self.models_ready.emit(list_available_models(self.api_key))
        except Exception as e:
            self.failed.emit(str(e))


class GeminiSyncView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.test_worker = None
        self.models_worker = None
        self._loading = True
        self._init_ui()
        self._loading = False

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # 1. Header
        header = QVBoxLayout()
        title = QLabel("Gemini AI Knowledge Sync — The Brain & Self-Learning Cache")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel(
            "100% Offline-First Speed: Gemini is NEVER called during real-time sorting. "
            "Instead, unrecognized files are queued here to teach the offline semantic engine new keywords."
        )
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        layout.addLayout(header)

        # 2. Configuration Card (API Key, Model, Thinking Level, Privacy)
        key_card = QFrame()
        key_card.setObjectName("cardFrame")
        k_layout = QVBoxLayout(key_card)
        k_layout.setContentsMargins(14, 12, 14, 12)
        k_layout.setSpacing(10)

        k_title = QLabel("🔑 Gemini API Key & Model Configuration")
        k_title.setStyleSheet("font-weight: 700; color: #00E5FF; font-size: 13px;")
        k_layout.addWidget(k_title)

        # Row 1: API Key Input & Action Buttons
        key_row = QHBoxLayout()
        key_row.setSpacing(10)

        self.key_input = QLineEdit()
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.key_input.setPlaceholderText("Enter your Google Gemini API key from Google AI Studio")
        existing_key = get_gemini_api_key()
        if existing_key:
            self.key_input.setText(existing_key)
        key_row.addWidget(self.key_input, 1)

        self.btn_toggle_key = QPushButton("👁️ Show")
        self.btn_toggle_key.setFixedWidth(75)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_row.addWidget(self.btn_toggle_key)

        btn_save_key = QPushButton("Save Settings")
        btn_save_key.clicked.connect(self._save_settings)
        key_row.addWidget(btn_save_key)

        self.btn_test_key = QPushButton("Test API")
        self.btn_test_key.setObjectName("primaryButton")
        self.btn_test_key.clicked.connect(self._test_api)
        key_row.addWidget(self.btn_test_key)

        k_layout.addLayout(key_row)

        # Row 2: Model & Thinking Level Selection
        model_row = QHBoxLayout()
        model_row.setSpacing(14)

        lbl_model = QLabel("Target Active Model:")
        lbl_model.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px;")
        model_row.addWidget(lbl_model)

        self.combo_model = QComboBox()
        self.combo_model.setEditable(True)   # any model ID can be typed in
        self.combo_model.setMinimumWidth(230)
        self._populate_models(get_cached_model_list() or SUPPORTED_GEMINI_MODELS, get_gemini_model())
        self.combo_model.currentTextChanged.connect(self._on_setting_changed)
        model_row.addWidget(self.combo_model)

        self.btn_fetch_models = QPushButton("🔄 Fetch Live Models")
        self.btn_fetch_models.setToolTip(
            "Ask Google which models your key can use right now, so a retired model ID can never break sync."
        )
        self.btn_fetch_models.clicked.connect(self._fetch_models)
        model_row.addWidget(self.btn_fetch_models)

        lbl_thinking = QLabel("Thinking Level:")
        lbl_thinking.setStyleSheet("color: #94A3B8; font-weight: 600; font-size: 12px; margin-left: 10px;")
        model_row.addWidget(lbl_thinking)

        self.combo_thinking = QComboBox()
        self.combo_thinking.addItems(THINKING_LEVELS)
        self.combo_thinking.setCurrentText(get_thinking_tier())
        self.combo_thinking.setToolTip(
            "How much Gemini reasons before answering. 'medium' balances accuracy and speed; "
            "Gemini 3.x models cannot switch thinking off."
        )
        self.combo_thinking.currentIndexChanged.connect(self._on_setting_changed)
        model_row.addWidget(self.combo_thinking)

        model_row.addStretch()
        k_layout.addLayout(model_row)

        # Row 3: Privacy Shield
        privacy_row = QHBoxLayout()
        self.chk_privacy = QCheckBox(
            "🛡️ Privacy Shield: mask emails and long numbers (account, passport, phone, ID) before filenames leave this PC"
        )
        self.chk_privacy.setChecked(get_privacy_shield())
        self.chk_privacy.toggled.connect(self._on_setting_changed)
        privacy_row.addWidget(self.chk_privacy)
        privacy_row.addStretch()

        btn_preview = QPushButton("👁 Preview What Gets Sent")
        btn_preview.setToolTip("Show the exact data that would be sent to Google for the current queue.")
        btn_preview.clicked.connect(self._preview_payload)
        privacy_row.addWidget(btn_preview)
        k_layout.addLayout(privacy_row)

        k_hint = QLabel(
            f"Default: {DEFAULT_GEMINI_MODEL} with '{DEFAULT_THINKING_LEVEL}' thinking. If the selected model is ever "
            f"retired (HTTP 404), sync automatically falls back to '{FALLBACK_GEMINI_MODEL}'. "
            "Get a free key from Google AI Studio (aistudio.google.com)."
        )
        k_hint.setWordWrap(True)
        k_hint.setStyleSheet("color: #64748B; font-size: 11px;")
        k_layout.addWidget(k_hint)

        layout.addWidget(key_card)

        # 3. Status Metric Strip
        stats_frame = QFrame()
        stats_frame.setObjectName("elevatedCard")
        s_layout = QHBoxLayout(stats_frame)
        s_layout.setContentsMargins(16, 10, 16, 10)

        def make_stat(lbl, initial="0", color="#00E5FF"):
            box = QVBoxLayout()
            l = QLabel(lbl)
            l.setObjectName("statLabel")
            v = QLabel(initial)
            v.setObjectName("statNumber")
            v.setStyleSheet(f"color: {color};")
            box.addWidget(l)
            box.addWidget(v)
            s_layout.addLayout(box)
            return v

        self.stat_queue_count = make_stat("Unrecognized Files Queued", "0", "#F59E0B")
        self.stat_learned_count = make_stat("AI-Learned Keywords", "0", "#00E5FF")
        self.stat_active_model = make_stat("Active Model", self.combo_model.currentText(), "#8B5CF6")
        self.stat_status = make_stat("Sync Engine Status", "Idle", "#10B981")
        s_layout.addStretch()

        self.btn_sync = QPushButton("⚡ Sync & Review AI Suggestions")
        self.btn_sync.setObjectName("successButton")
        self.btn_sync.setToolTip("Ask Gemini about the queued files, then approve which keywords to learn.")
        self.btn_sync.clicked.connect(self.start_sync)
        s_layout.addWidget(self.btn_sync)

        layout.addWidget(stats_frame)

        # 4. Batch Queue Table
        queue_header = QHBoxLayout()
        q_label = QLabel("📋 Pending Unrecognized Files (Fell through Pass 1.5):")
        q_label.setStyleSheet("font-weight: 700; color: #CBD5E1;")
        queue_header.addWidget(q_label)
        queue_header.addStretch()

        btn_add = QPushButton("➕ Add File Manually")
        btn_add.clicked.connect(self._add_file_manually)
        queue_header.addWidget(btn_add)

        btn_clear = QPushButton("🗑️ Clear Queue")
        btn_clear.clicked.connect(self._clear_queue)
        queue_header.addWidget(btn_clear)

        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_queue)
        queue_header.addWidget(btn_refresh)
        layout.addLayout(queue_header)

        self.table_queue = QTableWidget()
        self.table_queue.setColumnCount(3)
        self.table_queue.setHorizontalHeaderLabels(["Filename", "Source Path", "Queued At"])
        self.table_queue.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.table_queue.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table_queue.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table_queue.setColumnWidth(0, 260)
        layout.addWidget(self.table_queue)

        # 5. Progress Bar & Live Status Label
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.status_step = QLabel(
            f"Ready • Configured for {self.combo_model.currentText()} (Thinking: {self.combo_thinking.currentText()})."
        )
        self.status_step.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(self.status_step)

        # Initial load
        self.refresh_queue()

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _populate_models(self, models, current: str):
        self.combo_model.blockSignals(True)
        self.combo_model.clear()
        self.combo_model.addItems(models)
        if current and self.combo_model.findText(current) < 0:
            self.combo_model.addItem(current)
        self.combo_model.setCurrentText(current or DEFAULT_GEMINI_MODEL)
        self.combo_model.blockSignals(False)

    def _toggle_key_visibility(self):
        if self.key_input.echoMode() == QLineEdit.EchoMode.Password:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Normal)
            self.btn_toggle_key.setText("🙈 Hide")
        else:
            self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
            self.btn_toggle_key.setText("👁️ Show")

    def _on_setting_changed(self, *_):
        if not self._loading:
            self._save_settings()

    def _save_settings(self):
        key = self.key_input.text().strip()
        set_gemini_api_key(key)
        model = self.combo_model.currentText().strip() or DEFAULT_GEMINI_MODEL
        set_gemini_model(model)
        tier = self.combo_thinking.currentText().strip()
        set_thinking_tier(tier)
        set_privacy_shield(self.chk_privacy.isChecked())
        self.stat_active_model.setText(model)
        shield = "on" if self.chk_privacy.isChecked() else "off"
        self.status_step.setText(f"Settings saved: model '{model}', thinking '{tier}', privacy shield {shield}.")

    def _fetch_models(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter a Gemini API key first.")
            return
        self.btn_fetch_models.setEnabled(False)
        self.status_step.setText("Fetching the models your key can use...")
        self.models_worker = ModelListWorker(key, self)
        self.models_worker.models_ready.connect(self._on_models_ready)
        self.models_worker.failed.connect(self._on_models_failed)
        self.models_worker.start()

    def _on_models_ready(self, models: list):
        self.btn_fetch_models.setEnabled(True)
        if not models:
            self.status_step.setText("The API returned no text models for this key.")
            return
        set_cached_model_list(models)
        current = self.combo_model.currentText().strip()
        self._populate_models(models, current)
        if current in models:
            self.status_step.setText(f"Found {len(models)} live models. '{current}' is available ✓")
        else:
            self.status_step.setText(
                f"Found {len(models)} live models. ⚠ '{current}' is NOT available to this key; pick one from the list."
            )
            QMessageBox.warning(
                self, "Model Not Available",
                f"'{current}' is not offered for your key.\n\nSync would fall back to '{FALLBACK_GEMINI_MODEL}'. "
                "Pick a model from the refreshed list to choose explicitly."
            )

    def _on_models_failed(self, error: str):
        self.btn_fetch_models.setEnabled(True)
        self.status_step.setText(f"Could not fetch models: {error}")
        QMessageBox.critical(self, "Fetch Models Failed", error)

    def _preview_payload(self):
        filenames = [item["filename"] for item in load_unrecognized_files()]
        if not filenames:
            QMessageBox.information(self, "Nothing Queued", "The queue is empty, so nothing would be sent.")
            return
        payload = build_sync_payload(filenames[:SYNC_BATCH_SIZE], self.chk_privacy.isChecked())
        masked = sum(1 for p, original in zip(payload, filenames) if p["name"] != original)

        dlg = QDialog(self)
        dlg.setWindowTitle("Exactly What Gets Sent to Google")
        dlg.resize(720, 520)
        v = QVBoxLayout(dlg)
        info = QLabel(
            f"Only filenames are sent. Never file contents, folders or paths. "
            f"Privacy Shield is {'ON' if self.chk_privacy.isChecked() else 'OFF'}: {masked} of {len(payload)} names masked. "
            f"Your category names are sent too. Showing the first batch ({len(payload)} of {len(filenames)} files)."
        )
        info.setWordWrap(True)
        v.addWidget(info)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(json.dumps(payload, indent=2, ensure_ascii=False))
        v.addWidget(text)
        btn = QPushButton("Close")
        btn.clicked.connect(dlg.accept)
        v.addWidget(btn)
        dlg.exec()

    def _test_api(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please enter a Gemini API Key first.")
            return

        model = self.combo_model.currentText().strip()
        tier = self.combo_thinking.currentText().strip()

        self.btn_test_key.setEnabled(False)
        self.status_step.setText(f"Testing Gemini API connection using {model} (thinking: {tier})...")
        self.test_worker = TestKeyWorker(key, model, tier, self)
        self.test_worker.test_result.connect(self._on_test_finished)
        self.test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.btn_test_key.setEnabled(True)
        self.status_step.setText(message.splitlines()[0] if message else "")
        if success:
            QMessageBox.information(self, "API Test Success", message)
        else:
            QMessageBox.critical(self, "API Test Error", f"Connection failed:\n\n{message}")

    # ------------------------------------------------------------------
    # Queue
    # ------------------------------------------------------------------

    def refresh_queue(self):
        items = load_unrecognized_files()
        learned = load_learned_rules()
        total_learned = sum(len(kws) for kws in learned.values())

        self.stat_queue_count.setText(str(len(items)))
        self.stat_learned_count.setText(str(total_learned))
        self.stat_active_model.setText(self.combo_model.currentText())

        self.table_queue.setRowCount(len(items))
        for row, item in enumerate(items):
            self.table_queue.setItem(row, 0, QTableWidgetItem(f"📄 {item.get('filename', '')}"))
            self.table_queue.setItem(row, 1, QTableWidgetItem(item.get("source_path", "—")))
            self.table_queue.setItem(row, 2, QTableWidgetItem(item.get("timestamp", "—")[:19]))

        self.btn_sync.setEnabled(len(items) > 0 and not (self.worker and self.worker.isRunning()))

    def _add_file_manually(self):
        text, ok = QInputDialog.getText(
            self,
            "Add Filename to Queue",
            "Enter a sample filename to categorize (e.g. AWS_Billing_Report.pdf):"
        )
        if ok and text.strip():
            log_unrecognized_file(text.strip(), "Manual Entry")
            self.refresh_queue()

    def _clear_queue(self):
        reply = QMessageBox.question(
            self,
            "Clear Queue",
            "Clear all pending unrecognized filenames from the batch queue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            clear_unrecognized_files()
            self.refresh_queue()

    # ------------------------------------------------------------------
    # Sync -> Review -> Learn
    # ------------------------------------------------------------------

    def start_sync(self):
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Missing Key", "Please configure your Gemini API Key above.")
            return

        if not load_unrecognized_files():
            QMessageBox.information(self, "Empty Queue", "No unrecognized files pending in the queue.")
            return

        model = self.combo_model.currentText().strip() or DEFAULT_GEMINI_MODEL
        tier = self.combo_thinking.currentText().strip()

        self.btn_sync.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)
        self._set_engine_status("Syncing...", "#F59E0B")

        self.worker = FetchSuggestionsWorker(key, model, tier, self.chk_privacy.isChecked(), self)
        self.worker.progress_status.connect(self._on_worker_progress)
        self.worker.suggestions_ready.connect(self._on_suggestions_ready)
        self.worker.failed.connect(self._on_worker_failed)
        self.worker.start()

    def _set_engine_status(self, text: str, color: str):
        self.stat_status.setText(text)
        self.stat_status.setStyleSheet(f"color: {color};")

    def _on_worker_progress(self, msg: str):
        self.status_step.setText(msg)
        self.status_message.emit(msg)

    def _on_suggestions_ready(self, suggestions: list, used_model: str):
        self.progress_bar.setVisible(False)
        requested = self.combo_model.currentText().strip()

        if not suggestions:
            self._set_engine_status("Idle", "#10B981")
            self.refresh_queue()
            QMessageBox.information(self, "No Suggestions", f"{used_model} returned no usable suggestions. Files remain queued.")
            return

        if used_model != requested:
            QMessageBox.warning(
                self, "Model Fallback Used",
                f"'{requested}' is not available (HTTP 404), so '{used_model}' was used instead.\n\n"
                "Click 'Fetch Live Models' to pick a current model."
            )

        self._set_engine_status("Review...", "#8B5CF6")
        dialog = AIReviewDialog(suggestions, load_sync_categories(), used_model, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self._set_engine_status("Idle", "#10B981")
            self.status_step.setText("Review cancelled. Nothing was learned and all files remain queued.")
            self.refresh_queue()
            return

        accepted = dialog.accepted_suggestions()
        added = apply_suggestions(accepted, dialog.reviewed_filenames())
        total_new = sum(len(k) for k in added.values())
        unanswered = len(load_unrecognized_files())

        self._set_engine_status("Synced", "#10B981")
        already_known = len(accepted) - total_new
        summary = f"Reviewed {len(suggestions)} files with {used_model}. Learned {total_new} new keywords"
        summary += f" ({already_known} were already known)." if already_known > 0 else "."
        self.status_step.setText(summary)
        self.status_message.emit(summary)
        self.refresh_queue()

        details = [
            f"• {cat}: +{len(kws)} ({', '.join(kws[:5])}{'...' if len(kws) > 5 else ''})"
            for cat, kws in added.items() if kws
        ]
        msg = summary + "\n\n" + ("\n".join(details) if details else "No new keywords were added.")
        if unanswered:
            msg += f"\n\n{unanswered} file(s) remain queued (not answered by the model, or added during sync)."
        QMessageBox.information(self, "Gemini Knowledge Sync Complete", msg)

    def _on_worker_failed(self, error_msg: str):
        self.progress_bar.setVisible(False)
        self._set_engine_status("Error", "#EF4444")
        self.refresh_queue()
        self.status_step.setText(f"Sync failed: {error_msg}")
        QMessageBox.critical(
            self, "Sync Failed",
            f"Gemini Knowledge Sync failed:\n\n{error_msg}\n\nNothing was learned; all files remain queued."
        )
