"""Help & Documentation View: In-app guide explaining KesCollah's
Multi-Pass sorting, Deep Clean, Gemini AI Knowledge Sync, Context Dictionaries,
Size Analyzer, Passive Wi-Fi, Duplicate Finder, and Safety/Undo mechanics.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea
)


class HelpCard(QFrame):
    def __init__(self, icon: str, title: str, subtitle: str, body_html: str, parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        # Header
        h_row = QHBoxLayout()
        ic_lbl = QLabel(icon)
        ic_lbl.setStyleSheet("font-size: 22px;")
        h_row.addWidget(ic_lbl)

        title_box = QVBoxLayout()
        t_lbl = QLabel(title)
        t_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #F8FAFC;")
        sub_lbl = QLabel(subtitle)
        sub_lbl.setStyleSheet("font-size: 12px; color: #00E5FF; font-weight: 600;")
        title_box.addWidget(t_lbl)
        title_box.addWidget(sub_lbl)
        h_row.addLayout(title_box)
        h_row.addStretch()
        layout.addLayout(h_row)

        # Body
        body = QLabel(body_html)
        body.setWordWrap(True)
        body.setStyleSheet("color: #CBD5E1; font-size: 13px; line-height: 1.6;")
        layout.addWidget(body)


class HelpView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        header = QVBoxLayout()
        title = QLabel("KesCollah Documentation & Architectural Guide")
        title.setObjectName("viewTitle")
        header.addWidget(title)

        subtitle = QLabel("Complete technical guide on the offline multi-pass pipeline, Gemini AI knowledge sync, and core safety systems.")
        subtitle.setObjectName("viewSubtitle")
        header.addWidget(subtitle)
        root_layout.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(14)

        # Card 1: Zero Loose Files & Multi-Pass Architecture
        layout.addWidget(
            HelpCard(
                "⚡",
                "1. The 'Zero Loose Files' Multi-Pass Sorting Architecture",
                "100% Offline Speed & Guaranteed Zero Clutter",
                """
                <p>KesCollah enforces a strict <b>Multi-Stage Sorting Pipeline</b> entirely offline to guarantee zero loose files remain in root directories:</p>
                <ul>
                    <li><b>Pass 0 (Custom User Rules):</b> Evaluates user-defined pattern rules first (e.g. <code>*.pkt</code> &rarr; <code>Networking_Projects/</code>).</li>
                    <li><b>Pass 1 (Smart Name Grouping):</b> Groups related files sharing a common base name after stripping copy tags (<code>(1)</code>, <code>[2]</code>), version markers (<code>_v1</code>, <code>-final</code>), and timestamps.</li>
                    <li><b>Pass 1.5 (Semantic Engine):</b> Checks filenames against local <code>semantic_rules.json</code> AND <code>learned_rules.json</code>.
                        <br><b>Crucial:</b> Matching is case-insensitive and normalizes French/Latin accents using <code>unicodedata</code> NFKD (e.g., <code>reçu</code> matches <code>recu</code>, <code>diplôme</code> matches <code>diplome</code>).</li>
                    <li><b>Pass 2 (Extension Catch-All):</b> Categorizes any remaining files using <code>extension_mapping.json</code> (e.g. <code>Images</code>, <code>Documents</code>, <code>Archives</code>).</li>
                </ul>
                <p><b>🛡️ Nested Folder Protection:</b> If a generic category folder like <code>Images</code> already exists, KesCollah does <i>not</i> dump files directly into it. Instead, it creates <code>Images/Gathered_Loose_Files/</code> (optionally sub-sorted by Year/Month like <code>2026/11_Nov</code>) so your manually organized albums stay pristine.</p>
                <p><b>🔄 Recursive Deep Clean:</b> Enable Deep Clean to scan subfolders up to a strict <code>MAX_DEPTH</code> (default 2, max 3) to relocate misplaced files back to their semantic homes.</p>
                """
            )
        )

        # Card 2: Gemini AI Knowledge Sync
        layout.addWidget(
            HelpCard(
                "🧠",
                "2. The Gemini AI Knowledge Sync (Brain & Caching System)",
                "Offline-First File Organization with Cloud Learning",
                """
                <p>To preserve maximum performance and avoid API quotas, KesCollah follows an <b>offline-first architecture</b>:</p>
                <ul>
                    <li><b>No Live API Calls:</b> Real-time file organization runs 100% locally with zero latency.</li>
                    <li><b>Batch Logging:</b> New, unrecognized filenames that fall through Pass 1.5 are quietly added to <code>unrecognized_files.json</code>.</li>
                    <li><b>Sync &amp; Review:</b> Open the <b>Gemini AI Sync</b> tab and click <i>"Sync &amp; Review AI Suggestions"</i>. Queued filenames are sent in batches of 40 to Gemini (default <code>gemini-3.8-flash</code>, thinking level <code>medium</code>) with a JSON schema that forces a valid category for every answer. Busy-server errors (429/503) are retried automatically.</li>
                    <li><b>Stem Extraction:</b> Gemini categorizes each file into one of your existing categories and extracts the keyword that justifies it (e.g., <code>AWS_Billing_2026.pdf</code> &rarr; Category: <code>Cloud_and_Virtualization</code>, Stem: <code>aws</code>).</li>
                    <li><b>Review Before Learning:</b> Nothing is learned until you approve it. Each suggestion shows Gemini's confidence and reasoning; you can edit the keyword or category. A quality guard unchecks keywords that would hijack sorting (too generic, numbers, file extensions, or words not actually in the filename).</li>
                    <li><b>Privacy Shield:</b> Emails and long numbers (account, passport, phone and ID numbers) are masked before a filename leaves your PC. <i>"Preview What Gets Sent"</i> shows the exact payload. Only filenames are ever sent: never file contents or paths.</li>
                    <li><b>Model Safety Net:</b> <i>"Fetch Live Models"</i> lists the models your key can use right now. If the selected model is retired (HTTP 404), sync falls back to <code>gemini-flash-latest</code> automatically.</li>
                    <li><b>Self-Learning Cache:</b> Approved keywords are thread-safely appended to <code>learned_rules.json</code> with automatic deduplication. All subsequent offline scans immediately recognize these files!</li>
                </ul>
                """
            )
        )

        # Card 3: Context Dictionary Manager
        layout.addWidget(
            HelpCard(
                "📚",
                "3. Context Dictionary Manager UI",
                "Dual-List Rule Inspection, Pruning & Customization",
                """
                <p>In the <b>Context Dictionaries</b> module, you have complete governance over your sorting rules:</p>
                <ul>
                    <li><b>Dual-List View:</b> Compare <b>Static Rules</b> (from <code>semantic_rules.json</code>) side-by-side with <b>AI-Learned Rules</b> (from <code>learned_rules.json</code>).</li>
                    <li><b>Pruning Bad Associations:</b> If Gemini ever makes an inaccurate association, simply select the keyword and click <i>"Delete"</i> to eliminate it.</li>
                    <li><b>Extension Mapping:</b> View and customize the 7 primary extension categories (Images, Documents, Audio, Video, Archives, Executables, Web/Misc) or reset to defaults.</li>
                    <li><b>Custom Rules (Pass 0):</b> Add or toggle pattern-based rules evaluated before any grouping.</li>
                </ul>
                """
            )
        )

        # Card 4: Folder Size Analyzer
        layout.addWidget(
            HelpCard(
                "📊",
                "4. Folder Size Analyzer (Space Hog Hunter)",
                "Descending Tree View, Clickable Breadcrumbs & Parent Navigation",
                """
                <p>The <b>Size Analyzer</b> performs deep directory size calculations:</p>
                <ul>
                    <li><b>Descending Sort:</b> Folders and files are strictly sorted largest-first so space hogs are immediately visible at the top.</li>
                    <li><b>Navigation Controls:</b> Features a dedicated <i>"Up to Parent Directory"</i> button, Back/Forward browser-style history, and interactive clickable breadcrumbs.</li>
                    <li><b>Drill-Down:</b> Double-click any folder row to dive inside it instantly.</li>
                </ul>
                """
            )
        )

        # Card 5: Network Tools
        layout.addWidget(
            HelpCard(
                "📡",
                "5. Passive Wi-Fi Analyzer (Network Tools)",
                "Native OS Telemetry via Netsh",
                """
                <p>Uses Windows native <code>netsh wlan</code> commands to passively scan nearby wireless networks without installing packet capture drivers:</p>
                <ul>
                    <li>Displays SSID, Signal Strength (percentage and colored visual bars), Channel, Band (2.4 GHz, 5 GHz, 6 GHz), and Security Type (WPA2, WPA3).</li>
                    <li>Inspects active connection details including BSSID, RX/TX link speeds, and interface state.</li>
                </ul>
                """
            )
        )

        # Card 6: Safety, Duplicate Finder & Undo Journal
        layout.addWidget(
            HelpCard(
                "🛡️",
                "6. Core Safety, Duplicate Finder & JSON Undo Journal",
                "Zero Risk of Data Loss & Atomic Reversals",
                """
                <p>Safety is the foundational principle of KesCollah:</p>
                <ul>
                    <li><b>Dry Run Simulation:</b> Test any cleanup operation in preview mode before a single byte moves on disk.</li>
                    <li><b>Duplicate Finder:</b> Employs a 3-stage SHA-256 hash pipeline (Size filter &rarr; 4KB header hash &rarr; Full SHA-256) to identify byte-identical duplicates with one-click smart selection.</li>
                    <li><b>Multi-Level Undo History:</b> Every manual and Watchdog cleanup is recorded separately in <code>kescollah_undo.json</code> (last 30). <i>"Undo Last Operation"</i> reverses the newest one; <i>"🕘 History"</i> lets you undo any of them, in any order.</li>
                    <li><b>Never-Overwrite Restore:</b> If a new file now sits at an original location, the restored file is saved as <code>name (restored 1).ext</code>. Only folders KesCollah created are removed, and only when empty.</li>
                    <li><b>Collision Protection:</b> When moving files, KesCollah automatically suffixes <code>_copy1</code>, <code>_copy2</code> to prevent accidental overwrites.</li>
                </ul>
                """
            )
        )

        layout.addStretch()
        scroll.setWidget(container)
        root_layout.addWidget(scroll)
