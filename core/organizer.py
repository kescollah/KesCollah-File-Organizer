"""Smart Auto-Grouping and Orphan File Sorting Engine.
"""

import os
import re
from collections import defaultdict
from typing import Dict, List, Tuple
from core.file_utils import get_file_metadata, EXTENSION_CATEGORIES

SCRIPT_EXTENSIONS = {".py", ".pyw", ".exe", ".bat", ".cmd", ".sh", ".msi", ".dll"}


def clean_base_name(filename: str) -> str:
    """Extracts a clean base category name by stripping:
    - Extensions
    - Copy numbers like (1), (2), -1, _2
    - Version tags like _v1, -v2.0, _final, _draft
    - Date and timestamp patterns (e.g., 2026-10-21, 2026_10_21, 20261021)
    - Trailing numbers and delimiters
    """
    # 1. Strip extension
    name, _ = os.path.splitext(filename)

    # 2. Strip copy indicators like (1), (2), [1]
    name = re.sub(r"[\(\[]\s*\d+\s*[\)\]]$", "", name)

    # 3. Strip version tags (e.g., _v1, -v2.3, _final, _draft, _copy)
    name = re.sub(r"[\-_](v\d+(\.\d+)*|final|draft|copy|rev\d*)$", "", name, flags=re.IGNORECASE)

    # 4. Strip trailing ISO dates (e.g. 2026-10-21 or 2026_10_21)
    name = re.sub(r"[\-_]\d{4}[\-_]\d{2}[\-_]\d{2}.*", "", name)

    # 5. Strip 8-digit compact dates (e.g., _20261021)
    name = re.sub(r"[\-_](19|20)\d{6}.*", "", name)

    # 6. Strip trailing copy numbers with hyphens/underscores (e.g. -1, _02)
    name = re.sub(r"[\-_]\d+$", "", name)

    # 7. Strip trailing punctuation or spaces
    name = re.sub(r"[\s\-_.]+$", "", name)

    return name.strip()


def scan_and_group_directory(
    target_dir: str,
    min_files_per_group: int = 2,
    protect_scripts: bool = True
) -> Tuple[Dict[str, List[str]], List[str], List[str]]:
    """Scans target_dir and separates files into:
    1. groups: Dict[group_name, list of filenames] that meet min_files_per_group
    2. orphans: list of filenames that didn't form a group
    3. protected: list of filenames skipped due to script protection
    """
    if not os.path.isdir(target_dir):
        return {}, [], []

    try:
        entries = os.listdir(target_dir)
    except Exception:
        return {}, [], []

    files = []
    protected = []

    for entry in entries:
        full_path = os.path.join(target_dir, entry)
        if os.path.isfile(full_path):
            ext = os.path.splitext(entry)[1].lower()
            if protect_scripts and ext in SCRIPT_EXTENSIONS:
                protected.append(entry)
                continue
            files.append(entry)

    # Group by cleaned base name
    candidates = defaultdict(list)
    for f in files:
        base = clean_base_name(f)
        if base:
            candidates[base].append(f)
        else:
            candidates[os.path.splitext(f)[0]].append(f)

    groups = {}
    orphans = []

    for base, flist in sorted(candidates.items()):
        if len(flist) >= min_files_per_group:
            groups[base] = sorted(flist)
        else:
            orphans.extend(flist)

    return groups, sorted(orphans), sorted(protected)


def quick_group_by_extension(target_dir: str, file_list: List[str]) -> Dict[str, List[str]]:
    """Group untouched/orphan files by high-level category (Documents, Images, etc.)
    or by specific extension.
    """
    groups = defaultdict(list)
    for f in file_list:
        full_path = os.path.join(target_dir, f)
        meta = get_file_metadata(full_path)
        cat = meta.get("category", "Other")
        ext = meta.get("extension", "").lstrip(".").upper()
        if not ext:
            group_name = "No Extension"
        elif cat != "Other":
            group_name = f"{cat} ({ext})"
        else:
            group_name = f"Files_{ext}"
        groups[group_name].append(f)
    return dict(sorted(groups.items()))


def quick_group_by_date(target_dir: str, file_list: List[str]) -> Dict[str, List[str]]:
    """Group untouched/orphan files by year and month (e.g. 2026-10)."""
    groups = defaultdict(list)
    for f in file_list:
        full_path = os.path.join(target_dir, f)
        meta = get_file_metadata(full_path)
        month_str = meta.get("created_month", "Unknown Date")
        groups[f"Created_{month_str}"].append(f)
    return dict(sorted(groups.items()))


def quick_group_by_size(target_dir: str, file_list: List[str]) -> Dict[str, List[str]]:
    """Group untouched/orphan files by size tier:
    - Small (< 1 MB)
    - Medium (1 MB - 50 MB)
    - Large (> 50 MB)
    """
    groups = defaultdict(list)
    for f in file_list:
        full_path = os.path.join(target_dir, f)
        try:
            sz = os.path.getsize(full_path)
        except OSError:
            sz = 0

        if sz < 1024 * 1024:
            tier = "Size_Small (< 1MB)"
        elif sz <= 50 * 1024 * 1024:
            tier = "Size_Medium (1-50MB)"
        else:
            tier = "Size_Large (> 50MB)"

        groups[tier].append(f)
    return dict(sorted(groups.items()))
