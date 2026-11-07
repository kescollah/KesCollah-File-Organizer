"""File utility functions for metadata extraction, size formatting, and previewing.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional

TEXT_EXTENSIONS = {
    ".txt", ".py", ".md", ".json", ".csv", ".log", ".xml", ".yaml", ".yml",
    ".html", ".css", ".js", ".ts", ".ini", ".conf", ".sql", ".sh", ".bat",
    ".env", ".gitignore", ".c", ".cpp", ".h", ".rs", ".go", ".toml"
}

IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".ico", ".tiff", ".svg"
}

EXTENSION_CATEGORIES = {
    "Documents": {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".odt", ".rtf", ".csv"},
    "Images": {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico", ".raw", ".psd"},
    "Audio & Video": {".mp4", ".mkv", ".mov", ".avi", ".mp3", ".wav", ".flac", ".aac", ".m4a"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "Code & Scripts": {".py", ".js", ".ts", ".html", ".css", ".json", ".sql", ".cpp", ".c", ".h", ".sh", ".bat"},
}


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable string (e.g. 14.2 MB)."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def get_file_metadata(file_path: str) -> Dict[str, Any]:
    """Retrieve comprehensive metadata for a given file."""
    if not os.path.exists(file_path):
        return {}

    stat = os.stat(file_path)
    ext = os.path.splitext(file_path)[1].lower()
    
    # Categorize extension
    category = "Other"
    for cat_name, extensions in EXTENSION_CATEGORIES.items():
        if ext in extensions:
            category = cat_name
            break

    created_dt = datetime.fromtimestamp(stat.st_ctime)
    modified_dt = datetime.fromtimestamp(stat.st_mtime)

    return {
        "filename": os.path.basename(file_path),
        "path": file_path,
        "size_bytes": stat.st_size,
        "size_formatted": format_file_size(stat.st_size),
        "extension": ext or "(none)",
        "category": category,
        "created_date": created_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "created_month": created_dt.strftime("%Y-%m"),
        "modified_date": modified_dt.strftime("%Y-%m-%d %H:%M:%S"),
        "is_image": ext in IMAGE_EXTENSIONS,
        "is_text": ext in TEXT_EXTENSIONS,
    }


def read_text_preview(file_path: str, max_lines: int = 120, max_bytes: int = 65536) -> Optional[str]:
    """Read a truncated preview of a text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = []
            bytes_read = 0
            for i, line in enumerate(f):
                if i >= max_lines or bytes_read >= max_bytes:
                    lines.append("\n... [Preview truncated] ...")
                    break
                lines.append(line)
                bytes_read += len(line.encode("utf-8"))
            return "".join(lines)
    except Exception as e:
        return f"Error reading text preview: {e}"
