"""Global configuration, constants, paths, and default JSON structures for KesCollah File Organizer.
"""

import os
import sys
from pathlib import Path

APP_NAME = "KesCollah File Organizer"
APP_SHORT_NAME = "KesCollah"
APP_VERSION = "2.1.0"
APP_SUBTITLE = "Zero Loose Files Desktop Organizer & AI Disk Intelligence"

# Data Storage paths in User Profile directory (~/.kescollah)
USER_DATA_DIR = Path.home() / ".kescollah"
USER_DATA_DIR.mkdir(parents=True, exist_ok=True)

# JSON files
RULES_FILE = USER_DATA_DIR / "kescollah_rules.json"           # Pass 0 user rules
UNDO_FILE = USER_DATA_DIR / "kescollah_undo.json"             # Transaction journal for undo
SETTINGS_FILE = USER_DATA_DIR / "kescollah_settings.json"     # Settings & API keys
TAXONOMY_FILE = USER_DATA_DIR / "semantic_rules.json"         # Static semantic rules
LEARNED_RULES_FILE = USER_DATA_DIR / "learned_rules.json"     # AI-learned rules cache
EXTENSION_MAPPING_FILE = USER_DATA_DIR / "extension_mapping.json"  # Pass 2 extension fallback
UNRECOGNIZED_LOG_FILE = USER_DATA_DIR / "unrecognized_files.json"  # Batched queue for Gemini sync

# Subfolder name when a category folder already exists in root
NESTED_GATHERED_DIRNAME = "Gathered_Loose_Files"

# Gemini AI Model & Thinking Level Configuration
DEFAULT_GEMINI_MODEL = "gemini-3.8-flash"
DEFAULT_THINKING_LEVEL = "medium"
# Levels gemini-3.8-flash accepts ("minimal" is rejected; thinking cannot be switched off on 3.x)
THINKING_LEVELS = ["low", "medium", "high"]
# Google-maintained alias that always points at the current Flash model.
# Used automatically when the configured model returns 404 (retired / renamed).
FALLBACK_GEMINI_MODEL = "gemini-flash-latest"
# Offline defaults for the model picker; "Fetch Live Models" replaces these with what the key can use.
SUPPORTED_GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]

# Exact default semantic_rules.json as specified
DEFAULT_TAXONOMY = {
  "Networking_and_Infrastructure": [
    "packet tracer", "wireshark", "pcap", "pcapng", ".pkt", ".pka",
    "dhcp", "vlan", "subnetting", "ipv6", "routing", "cisco",
    "router", "switch", "rdp", "anydesk", "remote desktop", "vnc"
  ],
  "Cloud_and_Virtualization": [
    "aws", "azure", "proxmox", "virtualbox", "vbox", "vm",
    "cloud", "terraform", "server 2022", "windows 11",
    "linux deployment", "kali"
  ],
  "Programming_and_Scripts": [
    "python", "sql", "bash", "vscode", "script", "pseudocode", "mermaid"
  ],
  "Career_and_Applications_EN_FR": [
    "resume", "cv", "lettre de motivation", "cover letter", "transcript",
    "diplome", "diploma", "certificate", "certificat", "recommendation",
    "curriculum vitae", "portfolio"
  ],
  "Academics_and_Assignments_EN_FR": [
    "assignment", "project", "homework", "worksheet", "essay",
    "rapport", "etude", "pc102", "pc103", "it143", "it210", "it335",
    "eng 101", "byu", "ensign", "study guide", "learning journal", "peer review"
  ],
  "Legal_and_Immigration_EN_FR": [
    "constitution", "loi", "adaptation", "immigration", "imm5",
    "visa", "passport", "contrat", "contract", "serment", "legal", "droit"
  ],
  "Finance_and_Business_EN_FR": [
    "invoice", "facture", "receipt", "recu", "reçu", "budget",
    "cloture", "caisse", "transactions", "bank", "finance",
    "accounting", "journal general", "sales", "ventes", "inventaire"
  ],
  "Esoteric_and_Philosophy_EN_FR": [
    "rosicrucian", "amorc", "rosae crucis", "qabalah", "tarot",
    "hermetic", "meditation", "spirituel", "kabbalah", "grimoire", "magie"
  ],
  "Automotive_and_Mechanical": [
    "jeep", "liberty", "nissan", "xterra", "fsm", "haynes",
    "manual", "mechanic", "engine", "obd", "telemetry"
  ],
  "Games_and_Repacks": [
    "fitgirl", "repack", "skidrow", "codex", "torrent",
    "game", "setup", "black mesa", "half-life", "splinter cell"
  ],
  "Media_and_Audio_EN_FR": [
    "audio", "video", "recording", "enregistrement",
    "clipchamp", "episode", "saison", "webrip", "hdrip"
  ]
}

# Exact default extension_mapping.json as specified
DEFAULT_EXTENSION_MAPPING = {
  "Images": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".tiff", ".bmp", ".svg"],
  "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".csv", ".xlsx", ".xls", ".pptx", ".ppt"],
  "Audio": [".mp3", ".wav", ".flac", ".m4a", ".ogg", ".wma"],
  "Video": [".mp4", ".mkv", ".avi", ".mov", ".wmv"],
  "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".pkg"],
  "Executables_and_Installers": [".exe", ".msi", ".apk", ".bat", ".cmd", ".ps1", ".sh", ".iso", ".torrent"],
  "Web_and_Misc": [".html", ".htm", ".css", ".js", ".json", ".xml", ".sql", ".md"]
}

# Standard Windows profile directories helper
def get_windows_profile_directories() -> dict[str, str]:
    home = Path.home()
    dirs = {
        "Desktop": str(home / "Desktop"),
        "Downloads": str(home / "Downloads"),
        "Documents": str(home / "Documents"),
        "Pictures": str(home / "Pictures"),
        "Music": str(home / "Music"),
        "Videos": str(home / "Videos"),
    }
    # Keep only those that exist
    return {name: path for name, path in dirs.items() if os.path.isdir(path)}

# Human readable size formatting helper
def format_bytes(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
