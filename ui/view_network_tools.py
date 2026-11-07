"""Network Tools view: Passive Wi-Fi analyzer with live scan, signal bars,
and current connection inspector panel.
"""

import os
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QProgressBar, QSplitter
)
from core.network_tools import scan_wifi_networks, get_connected_network_info, WifiNetwork


class WifiScanWorker(QThread):
    scan_finished = pyqtSignal(list)
    scan_failed = pyqtSignal(str)

    def run(self):
        try:
            nets = scan_wifi_networks()
            self.scan_finished.emit(nets)
        except Exception as e:
            self.scan_failed.emit(str(e))


class SignalBar(QWidget):
    """Custom inline signal strength bar widget."""
    def __init__(self, pct: int, color: str, parent=None):
        super().__init__(parent)
        self.pct = pct
        self.color = color
        self.setFixedHeight(28)
        self.setMinimumWidth(80)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QPen, QBrush
        p = QPainter(self)
        p.setRenderHint(p.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        bar_w = int(w * self.pct / 100)
        # Background track
        p.setBrush(QColor("#1A202E"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, h // 3, w, h // 3, 3, 3)
        # Filled portion
        if bar_w > 0:
            p.setBrush(QColor(self.color))
            p.drawRoundedRect(0, h // 3, bar_w, h // 3, 3, 3)
        # Percentage text
        p.setPen(QColor("#E2E8F0"))
        p.setFont(self.font())
        p.drawText(0, 0, w, h, Qt.AlignmentFlag.AlignCenter, f"{self.pct}%")
        p.end()


class InfoCard(QFrame):
    """Small label+value card for the connection info panel."""
    def __init__(self, label: str, value: str = "—", accent: str = "#00E5FF", parent=None):
        super().__init__(parent)
        self.setObjectName("cardFrame")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        lbl = QLabel(label.upper())
        lbl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: 700; letter-spacing: 0.5px;")
        self.val = QLabel(value)
        self.val.setStyleSheet(f"color: {accent}; font-size: 14px; font-weight: 700;")
        self.val.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addWidget(self.val)

    def set_value(self, v: str):
        self.val.setText(v or "—")


class NetworkToolsView(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.networks = []
        self.worker: WifiScanWorker = None
        self.auto_refresh_timer = QTimer(self)
        self.auto_refresh_timer.timeout.connect(self.start_scan)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QVBoxLayout()
        title = QLabel("Network Tools — Wi-Fi Analyzer")
        title.setObjectName("viewTitle")
        hdr.addWidget(title)
        sub = QLabel("Passive scan of nearby Wi-Fi networks. Signal, channel, band, and security at a glance.")
        sub.setObjectName("viewSubtitle")
        hdr.addWidget(sub)
        layout.addLayout(hdr)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setObjectName("cardFrame")
        t_lay = QHBoxLayout(toolbar)
        t_lay.setContentsMargins(14, 10, 14, 10)
        t_lay.setSpacing(10)

        self.btn_scan = QPushButton("📡  Scan Networks")
        self.btn_scan.setObjectName("primaryButton")
        self.btn_scan.clicked.connect(self.start_scan)
        t_lay.addWidget(self.btn_scan)

        self.btn_auto = QPushButton("▶  Auto-Refresh (15s)")
        self.btn_auto.setCheckable(True)
        self.btn_auto.clicked.connect(self._toggle_auto)
        t_lay.addWidget(self.btn_auto)

        t_lay.addStretch()

        self.lbl_last_scan = QLabel("Last scan: —")
        self.lbl_last_scan.setStyleSheet("color: #64748B; font-size: 11px;")
        t_lay.addWidget(self.lbl_last_scan)
        layout.addWidget(toolbar)

        # ── Main Splitter: Table | Connection Info ────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)

        # Left: Networks Table
        table_container = QWidget()
        t_cont_layout = QVBoxLayout(table_container)
        t_cont_layout.setContentsMargins(0, 0, 0, 0)
        t_cont_layout.setSpacing(6)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "  Network Name (SSID)", "Signal", "Band", "Channel", "Radio", "Security", "BSSID"
        ])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setColumnWidth(1, 130)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        t_cont_layout.addWidget(self.table)
        splitter.addWidget(table_container)

        # Right: Live Connection Inspector Panel
        inspector = QWidget()
        insp_layout = QVBoxLayout(inspector)
        insp_layout.setContentsMargins(0, 0, 0, 0)
        insp_layout.setSpacing(8)

        insp_title = QLabel("CURRENT CONNECTION")
        insp_title.setStyleSheet("color: #00E5FF; font-weight: 700; font-size: 11px; letter-spacing: 1px;")
        insp_layout.addWidget(insp_title)

        # Connected network signal ring / badge
        self.conn_ssid_lbl = QLabel("Not Connected")
        self.conn_ssid_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #F8FAFC;")
        self.conn_ssid_lbl.setWordWrap(True)
        insp_layout.addWidget(self.conn_ssid_lbl)

        self.conn_signal_bar = QProgressBar()
        self.conn_signal_bar.setRange(0, 100)
        self.conn_signal_bar.setValue(0)
        self.conn_signal_bar.setFixedHeight(14)
        self.conn_signal_bar.setFormat("Signal: %p%")
        insp_layout.addWidget(self.conn_signal_bar)

        # Info cards grid (2-col)
        self.card_band = InfoCard("Band", "—", "#00E5FF")
        self.card_channel = InfoCard("Channel", "—", "#8B5CF6")
        self.card_radio = InfoCard("Radio", "—", "#38BDF8")
        self.card_auth = InfoCard("Security", "—", "#F59E0B")
        self.card_rx = InfoCard("Receive", "—", "#10B981")
        self.card_tx = InfoCard("Transmit", "—", "#10B981")
        self.card_bssid = InfoCard("BSSID", "—", "#94A3B8")
        self.card_iface = InfoCard("Interface", "—", "#94A3B8")

        cards_1 = QHBoxLayout()
        cards_1.addWidget(self.card_band)
        cards_1.addWidget(self.card_channel)
        insp_layout.addLayout(cards_1)

        cards_2 = QHBoxLayout()
        cards_2.addWidget(self.card_radio)
        cards_2.addWidget(self.card_auth)
        insp_layout.addLayout(cards_2)

        cards_3 = QHBoxLayout()
        cards_3.addWidget(self.card_rx)
        cards_3.addWidget(self.card_tx)
        insp_layout.addLayout(cards_3)

        insp_layout.addWidget(self.card_bssid)
        insp_layout.addWidget(self.card_iface)

        # Selected network detail section
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("background-color: #1C2332; max-height: 1px;")
        insp_layout.addWidget(sep)

        sel_title = QLabel("SELECTED NETWORK")
        sel_title.setStyleSheet("color: #8B5CF6; font-weight: 700; font-size: 11px; letter-spacing: 1px; margin-top: 4px;")
        insp_layout.addWidget(sel_title)

        self.sel_detail = QLabel("Click a row to inspect")
        self.sel_detail.setWordWrap(True)
        self.sel_detail.setStyleSheet("color: #94A3B8; font-size: 12px; line-height: 1.6;")
        insp_layout.addWidget(self.sel_detail)

        insp_layout.addStretch()
        inspector.setFixedWidth(300)
        splitter.addWidget(inspector)
        splitter.setSizes([800, 300])

        layout.addWidget(splitter, 1)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

    # ── Scan Logic ─────────────────────────────────────────────────────────

    def start_scan(self):
        self.btn_scan.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_message.emit("Scanning Wi-Fi networks...")
        self.table.setRowCount(0)

        self.worker = WifiScanWorker(self)
        self.worker.scan_finished.connect(self._on_scan_finished)
        self.worker.scan_failed.connect(self._on_scan_failed)
        self.worker.start()

    def _on_scan_finished(self, networks: list):
        from datetime import datetime
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.networks = networks
        self.lbl_last_scan.setText(f"Last scan: {datetime.now().strftime('%H:%M:%S')} — {len(networks)} network(s) found")

        self.table.setRowCount(len(networks))
        for row, net in enumerate(networks):
            # SSID with connected badge
            ssid_text = f"{'★ ' if net.is_connected else ''}  {net.ssid}"
            ssid_item = QTableWidgetItem(ssid_text)
            ssid_item.setData(Qt.ItemDataRole.UserRole, row)
            if net.is_connected:
                ssid_item.setForeground(QColor("#00E5FF"))
                font = ssid_item.font()
                font.setBold(True)
                ssid_item.setFont(font)
            self.table.setItem(row, 0, ssid_item)

            # Signal bar widget
            bar = SignalBar(net.signal_pct, net.signal_color)
            self.table.setCellWidget(row, 1, bar)

            # Remaining text columns
            for col, text in enumerate([net.band, net.channel, net.radio_type, net.auth, net.bssid], start=2):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(row, col, item)

        # Refresh connection inspector panel
        self._refresh_connection_panel()
        self.status_message.emit(f"Wi-Fi scan complete: {len(networks)} network(s) found.")

    def _on_scan_failed(self, err: str):
        self.progress_bar.setVisible(False)
        self.btn_scan.setEnabled(True)
        self.status_message.emit(f"Scan failed: {err}")

    def _refresh_connection_panel(self):
        info = get_connected_network_info()
        self.conn_ssid_lbl.setText(info.get("ssid", "—"))
        try:
            sig = int(info.get("signal", "0 %").replace("%", "").strip())
        except Exception:
            sig = 0
        self.conn_signal_bar.setValue(sig)
        self.card_band.set_value(info.get("band", "—"))
        self.card_channel.set_value(info.get("channel", "—"))
        self.card_radio.set_value(info.get("radio", "—"))
        self.card_auth.set_value(info.get("auth", "—"))
        self.card_rx.set_value(info.get("rx_mbps", "—") + " Mbps" if info.get("rx_mbps") != "—" else "—")
        self.card_tx.set_value(info.get("tx_mbps", "—") + " Mbps" if info.get("tx_mbps") != "—" else "—")
        self.card_bssid.set_value(info.get("bssid", "—").upper())
        self.card_iface.set_value(info.get("interface", "—"))

    def _on_selection_changed(self):
        rows = self.table.selectedItems()
        if not rows:
            self.sel_detail.setText("Click a row to inspect")
            return
        row = rows[0].row()
        if row >= len(self.networks):
            return
        net = self.networks[row]
        status = "★ Currently Connected" if net.is_connected else "Not Connected"
        self.sel_detail.setText(
            f"<b>SSID:</b> {net.ssid}<br>"
            f"<b>BSSID:</b> {net.bssid}<br>"
            f"<b>Signal:</b> {net.signal_pct}%  {net.signal_bars}  <i>{net.signal_level_text}</i><br>"
            f"<b>Band:</b> {net.band}  •  <b>Channel:</b> {net.channel}<br>"
            f"<b>Radio:</b> {net.radio_type}<br>"
            f"<b>Authentication:</b> {net.auth}<br>"
            f"<b>Encryption:</b> {net.encryption}<br>"
            f"<b>Status:</b> {status}"
        )

    def _toggle_auto(self, checked: bool):
        if checked:
            self.btn_auto.setText("⏹  Stop Auto-Refresh")
            self.auto_refresh_timer.start(15000)
            self.start_scan()
        else:
            self.btn_auto.setText("▶  Auto-Refresh (15s)")
            self.auto_refresh_timer.stop()
