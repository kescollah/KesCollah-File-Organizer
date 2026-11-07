"""Wi-Fi / Network scanner using netsh (Windows) with cross-platform stub fallback.
Parses netsh output with locale-agnostic regex so it works on English and French Windows.
"""

import re
import subprocess
import platform
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class WifiNetwork:
    ssid: str
    bssid: str
    signal_pct: int           # 0-100
    signal_bars: str          # e.g. "████░"
    radio_type: str
    band: str
    channel: str
    auth: str
    encryption: str
    is_connected: bool = False

    @property
    def signal_level_text(self) -> str:
        if self.signal_pct >= 80:
            return "Excellent"
        elif self.signal_pct >= 60:
            return "Good"
        elif self.signal_pct >= 40:
            return "Fair"
        elif self.signal_pct >= 20:
            return "Weak"
        return "Very Weak"

    @property
    def signal_color(self) -> str:
        if self.signal_pct >= 80:
            return "#10B981"   # emerald
        elif self.signal_pct >= 60:
            return "#00E5FF"   # teal
        elif self.signal_pct >= 40:
            return "#F59E0B"   # amber
        return "#EF4444"       # red

    def _make_bars(pct: int) -> str:  # noqa: N805
        filled = round(pct / 20)
        return "█" * filled + "░" * (5 - filled)


def _run_netsh(args: List[str]) -> str:
    """Run a netsh command and return stdout as text."""
    try:
        result = subprocess.run(
            ["netsh"] + args,
            capture_output=True,
            timeout=10,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except Exception as e:
        return ""


def _extract(pattern: str, text: str, default: str = "—") -> str:
    """Case-insensitive single-group regex extraction."""
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else default


def scan_wifi_networks() -> List[WifiNetwork]:
    """Scan nearby Wi-Fi networks. Returns list of WifiNetwork objects."""
    if platform.system() != "Windows":
        return _mock_wifi_data()

    raw = _run_netsh(["wlan", "show", "networks", "mode=bssid"])
    if not raw:
        return []

    # Find out which SSID is currently connected
    iface_raw = _run_netsh(["wlan", "show", "interfaces"])
    connected_bssid = _extract(r"BSSID\s*:\s*([0-9a-f:]{17})", iface_raw, "").lower()

    networks: List[WifiNetwork] = []

    # Split the output into per-SSID blocks by looking for "SSID N :" lines
    ssid_blocks = re.split(r"(?=^SSID\s+\d+\s*:)", raw, flags=re.MULTILINE)

    for block in ssid_blocks:
        block = block.strip()
        if not block or not re.match(r"^SSID\s+\d+\s*:", block, re.IGNORECASE):
            continue

        # SSID name (everything after the colon on the first line)
        ssid_match = re.match(r"^SSID\s+\d+\s*:\s*(.+)", block, re.IGNORECASE)
        if not ssid_match:
            continue
        ssid = ssid_match.group(1).strip()
        if not ssid:
            ssid = "(Hidden Network)"

        # Find each BSSID sub-block inside this SSID block
        bssid_blocks = re.split(r"(?=^\s+BSSID\s+\d+\s*:)", block, flags=re.MULTILINE)
        for b_block in bssid_blocks:
            if not re.search(r"BSSID\s+\d+\s*:", b_block, re.IGNORECASE):
                continue

            bssid = _extract(r"BSSID\s+\d+\s*:\s*([0-9a-f:]{17})", b_block)
            signal_str = _extract(r"Signal\s*[:/]\s*(\d+)\s*%", b_block, "0")
            radio = _extract(r"(?:Radio\s+type|Type\s+de\s+radio)\s*[:/]+\s*(.+)", b_block)
            band = _extract(r"(?:Band|Bande)\s*[:/]+\s*(.+)", b_block)
            channel = _extract(r"(?:Channel|Canal)\s*[:/]+\s*(\d+)", b_block)

            # Auth and Encryption from parent SSID block
            auth = _extract(r"(?:Authentication|Authentification)\s*[:/]+\s*(.+)", block)
            enc = _extract(r"(?:Encryption|Chiffrement)\s*[:/]+\s*(.+)", block)

            try:
                pct = int(signal_str)
            except ValueError:
                pct = 0

            bars = "█" * round(pct / 20) + "░" * (5 - round(pct / 20))
            is_connected = bssid.lower() == connected_bssid

            networks.append(
                WifiNetwork(
                    ssid=ssid,
                    bssid=bssid.upper(),
                    signal_pct=pct,
                    signal_bars=bars,
                    radio_type=radio,
                    band=band,
                    channel=channel,
                    auth=auth,
                    encryption=enc,
                    is_connected=is_connected,
                )
            )

    # Sort: connected first, then by signal descending
    networks.sort(key=lambda n: (not n.is_connected, -n.signal_pct))
    return networks


def get_connected_network_info() -> dict:
    """Return current connection details from netsh wlan show interfaces."""
    if platform.system() != "Windows":
        return {}

    raw = _run_netsh(["wlan", "show", "interfaces"])
    return {
        "ssid": _extract(r"(?:^|\n)\s+SSID\s*:\s*(.+)", raw),
        "bssid": _extract(r"BSSID\s*:\s*([0-9a-f:]{17})", raw),
        "signal": _extract(r"Signal\s*:\s*(\d+\s*%)", raw),
        "radio": _extract(r"(?:Radio\s+type|Type\s+de\s+radio)\s*:\s*(.+)", raw),
        "band": _extract(r"(?:Band|Bande)\s*:\s*(.+)", raw),
        "channel": _extract(r"(?:Channel|Canal)\s*:\s*(\d+)", raw),
        "rx_mbps": _extract(r"(?:Receive|Réception)\s*\([^)]+\)\s*:\s*(.+)", raw),
        "tx_mbps": _extract(r"(?:Transmit|Transmission)\s*\([^)]+\)\s*:\s*(.+)", raw),
        "auth": _extract(r"(?:Authentication|Authentification)\s*:\s*(.+)", raw),
        "interface": _extract(r"(?:^|\n)\s+(?:Name|Nom)\s*:\s*(.+)", raw),
    }


def _mock_wifi_data() -> List[WifiNetwork]:
    """Provides placeholder data on non-Windows platforms."""
    return [
        WifiNetwork("Demo_Network_5G", "AA:BB:CC:DD:EE:FF", 85, "█████", "802.11ax", "5 GHz", "36", "WPA2", "CCMP", True),
        WifiNetwork("Neighbor_2.4G", "11:22:33:44:55:66", 55, "███░░", "802.11n", "2.4 GHz", "6", "WPA2", "CCMP", False),
        WifiNetwork("Guest_WiFi", "AA:11:BB:22:CC:33", 30, "██░░░", "802.11g", "2.4 GHz", "11", "Open", "None", False),
    ]
