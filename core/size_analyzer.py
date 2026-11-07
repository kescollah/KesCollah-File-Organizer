"""Folder Size Analyzer logic for inspecting directory sizes, calculating disk hogs,
and delivering descending sorted metrics.
"""

import os
from datetime import datetime
from dataclasses import dataclass
from typing import List, Tuple
from config import format_bytes


@dataclass
class DiskItem:
    name: str
    full_path: str
    is_dir: bool
    size_bytes: int
    size_formatted: str
    item_type: str
    modified_str: str
    item_count: int
    percentage: float = 0.0


def calculate_folder_size(folder_path: str) -> Tuple[int, int]:
    """Recursively calculate total bytes and file count of a folder."""
    total_size = 0
    file_count = 0
    try:
        with os.scandir(folder_path) as it:
            for entry in it:
                try:
                    if entry.is_file(follow_symlinks=False):
                        total_size += entry.stat().st_size
                        file_count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        sub_sz, sub_cnt = calculate_folder_size(entry.path)
                        total_size += sub_sz
                        file_count += sub_cnt
                except (PermissionError, FileNotFoundError, OSError):
                    continue
    except (PermissionError, FileNotFoundError, OSError):
        pass
    return total_size, file_count


def scan_directory_space_hogs(target_dir: str, progress_callback=None) -> Tuple[List[DiskItem], int]:
    """Scans the immediate children (files and subfolders) of target_dir,
    recursively computes subfolder sizes, and sorts in descending order (largest first).
    """
    if not os.path.isdir(target_dir):
        return [], 0

    items: List[DiskItem] = []
    total_scanned_bytes = 0

    try:
        entries = list(os.scandir(target_dir))
    except Exception:
        return [], 0

    total_entries = len(entries)
    for idx, entry in enumerate(entries):
        if progress_callback:
            progress_callback(idx + 1, total_entries, entry.name)

        try:
            stat = entry.stat()
            mod_dt = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")

            if entry.is_dir(follow_symlinks=False):
                folder_bytes, file_cnt = calculate_folder_size(entry.path)
                items.append(
                    DiskItem(
                        name=entry.name,
                        full_path=entry.path,
                        is_dir=True,
                        size_bytes=folder_bytes,
                        size_formatted=format_bytes(folder_bytes),
                        item_type="📁 Folder",
                        modified_str=mod_dt,
                        item_count=file_cnt
                    )
                )
                total_scanned_bytes += folder_bytes
            else:
                sz = stat.st_size
                ext = os.path.splitext(entry.name)[1].lower() or "File"
                items.append(
                    DiskItem(
                        name=entry.name,
                        full_path=entry.path,
                        is_dir=False,
                        size_bytes=sz,
                        size_formatted=format_bytes(sz),
                        item_type=f"📄 {ext.upper()}",
                        modified_str=mod_dt,
                        item_count=1
                    )
                )
                total_scanned_bytes += sz
        except (PermissionError, FileNotFoundError, OSError):
            continue

    # Calculate percentages and sort descending by size
    for it in items:
        if total_scanned_bytes > 0:
            it.percentage = (it.size_bytes / total_scanned_bytes) * 100.0
        else:
            it.percentage = 0.0

    # Default sort MUST be size descending (largest space hogs at top)
    items.sort(key=lambda x: x.size_bytes, reverse=True)

    return items, total_scanned_bytes
