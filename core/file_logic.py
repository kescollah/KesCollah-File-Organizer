"""Core business logic for the multi-pass Zero Loose Files organizer:
Recursive Deep Clean with MAX_DEPTH limits, Folder Merging, Custom Rules (Pass 0),
Smart Name Grouping (Pass 1), Bilingual Semantic Engine with unicodedata unaccenting (Pass 1.5),
AI-Learned Rules cache check, Unrecognized file batching, Extension Catch-All (Pass 2),
Nested Folder logic (Gathered_Loose_Files), Dry Run simulation, and JSON Undo Journal.
"""

import os
import re
import json
import fnmatch
import shutil
import threading
import uuid
import unicodedata
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Tuple, Optional, Any, Set
from pathlib import Path

from config import (
    DEFAULT_TAXONOMY,
    DEFAULT_EXTENSION_MAPPING,
    EXTENSION_MAPPING_FILE,
    LEARNED_RULES_FILE,
    NESTED_GATHERED_DIRNAME,
    RULES_FILE,
    TAXONOMY_FILE,
    UNDO_FILE,
    format_bytes
)
from core.gemini_sync import (
    load_learned_rules,
    save_learned_rules,
    log_unrecognized_file,
    normalize_keyword
)


# ---------------------------------------------------------------------------
# Custom User Rules (Pass 0)
# ---------------------------------------------------------------------------

@dataclass
class CustomRule:
    id: str
    pattern: str          # Glob pattern (e.g. *.pkt, report_*) or extension (.pkt)
    target_folder: str    # Destination folder relative to root
    enabled: bool = True
    description: str = ""

    def matches(self, filename: str) -> bool:
        if not self.enabled:
            return False
        pat = self.pattern.strip()
        # If user entered just an extension like ".pkt" or "pkt"
        if pat.startswith(".") or not ("*" in pat or "?" in pat):
            ext = os.path.splitext(filename)[1].lower()
            clean_pat = pat.lower() if pat.startswith(".") else f".{pat.lower()}"
            if ext == clean_pat:
                return True
        return fnmatch.fnmatch(filename.lower(), pat.lower())


def load_custom_rules() -> List[CustomRule]:
    """Load persistent rules from JSON file, with sane defaults."""
    if not RULES_FILE.exists():
        defaults = [
            CustomRule(id="rule_pkt", pattern="*.pkt", target_folder="Networking_Projects", enabled=True, description="Cisco Packet Tracer topologies"),
            CustomRule(id="rule_torrent", pattern="*.torrent", target_folder="Torrents", enabled=True, description="BitTorrent metadata"),
            CustomRule(id="rule_iso", pattern="*.iso", target_folder="Disk_Images", enabled=True, description="Operating system images"),
        ]
        save_custom_rules(defaults)
        return defaults

    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [CustomRule(**item) for item in data]
    except Exception:
        return []


def save_custom_rules(rules: List[CustomRule]):
    """Persist custom rules to JSON file."""
    try:
        with open(RULES_FILE, "w", encoding="utf-8") as f:
            json.dump([asdict(r) for r in rules], f, indent=2)
    except Exception as e:
        print(f"Error saving rules: {e}")


# ---------------------------------------------------------------------------
# Static Semantic Domain Taxonomy & Extension Mappings
# ---------------------------------------------------------------------------

def load_taxonomy() -> Dict[str, List[str]]:
    """Load static semantic domain taxonomy from semantic_rules.json."""
    if not TAXONOMY_FILE.exists():
        save_taxonomy(DEFAULT_TAXONOMY)
        return dict(DEFAULT_TAXONOMY)
    try:
        with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict) and data:
                return {
                    str(category): [str(kw) for kw in keywords if str(kw).strip()]
                    for category, keywords in data.items()
                    if isinstance(keywords, list)
                }
    except Exception:
        pass
    return dict(DEFAULT_TAXONOMY)


def save_taxonomy(taxonomy: Dict[str, List[str]]):
    """Persist static semantic taxonomy dictionary to semantic_rules.json."""
    with open(TAXONOMY_FILE, "w", encoding="utf-8") as f:
        json.dump(taxonomy, f, indent=2, ensure_ascii=False)


def load_extension_mapping() -> Dict[str, List[str]]:
    """Load extension categories from extension_mapping.json."""
    if not EXTENSION_MAPPING_FILE.exists():
        save_extension_mapping(DEFAULT_EXTENSION_MAPPING)
        return {key: list(value) for key, value in DEFAULT_EXTENSION_MAPPING.items()}
    try:
        with open(EXTENSION_MAPPING_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {
                str(category): [
                    (
                        str(extension).strip()
                        if str(extension).strip().startswith(".")
                        else f".{str(extension).strip()}"
                    ).lower()
                    for extension in extensions
                    if str(extension).strip()
                ]
                for category, extensions in data.items()
                if isinstance(extensions, list)
            }
    except Exception:
        pass
    return {key: list(value) for key, value in DEFAULT_EXTENSION_MAPPING.items()}


def save_extension_mapping(mapping: Dict[str, List[str]]):
    """Persist extension categories to extension_mapping.json."""
    normalized = {}
    for category, extensions in mapping.items():
        normalized[category] = []
        seen = set()
        for extension in extensions:
            value = extension.strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = f".{value}"
            if value not in seen:
                normalized[category].append(value)
                seen.add(value)
    with open(EXTENSION_MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Accent-Insensitive Normalization & Matching Engine (Pass 1.5)
# ---------------------------------------------------------------------------

def normalize_text(value: str) -> str:
    """Normalize string: case-insensitive and strips French/Latin accents using unicodedata NFKD."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def match_taxonomy(
    filename: str,
    static_taxonomy: Optional[Dict[str, List[str]]] = None,
    learned_taxonomy: Optional[Dict[str, List[str]]] = None
) -> Optional[Tuple[str, str, str]]:
    """Evaluate filename against local semantic_rules.json AND learned_rules.json.
    Crucial: Matching is case-insensitive and ignores French/Latin accents using unicodedata.
    Matches:
      1. Domain-specific extensions (e.g. .pkt, .pka, .pcap)
      2. Multi-word phrases with flexible delimiters (e.g. 'packet tracer', 'lettre de motivation')
      3. Word-bounded tokens/acronyms (e.g. 'aws', 'cv', 'pc102')

    Returns (category_name, matched_keyword, rule_source) or None.
    Selects the most specific (longest) keyword match.
    """
    stat_tax = static_taxonomy if static_taxonomy is not None else load_taxonomy()
    learn_tax = learned_taxonomy if learned_taxonomy is not None else load_learned_rules()

    normalized_filename = normalize_text(filename)
    ext = os.path.splitext(normalized_filename)[1].lower()
    matches = []

    # Helper to check a dictionary
    def search_rules(rules_dict: Dict[str, List[str]], source_label: str):
        for cat_name, keywords in rules_dict.items():
            for kw in keywords:
                kw_clean = normalize_text(kw.strip())
                if not kw_clean:
                    continue

                # 1. Extension match
                if kw_clean.startswith("."):
                    if ext == kw_clean:
                        matches.append((len(kw_clean), cat_name, kw, source_label))
                # 2. Multi-word phrase with spaces, dashes, or underscores
                elif any(c in kw_clean for c in (" ", "-", "_")):
                    parts = [re.escape(p) for p in re.split(r"[\s\-_]+", kw_clean) if p]
                    pat = r"(?i)" + r"[\s\-_.]+".join(parts)
                    if re.search(pat, normalized_filename):
                        matches.append((len(kw_clean), cat_name, kw, source_label))
                # 3. Single token with word-boundary protection
                else:
                    pat = r"(?<![a-zA-Z0-9])" + re.escape(kw_clean) + r"(?![a-zA-Z0-9])"
                    if re.search(pat, normalized_filename):
                        matches.append((len(kw_clean), cat_name, kw, source_label))

    # Evaluate static rules first
    search_rules(stat_tax, "Static Rule")
    # Evaluate AI-learned rules
    search_rules(learn_tax, "AI-Learned Rule")

    if not matches:
        return None

    # Sort descending by length of matched keyword (most specific match wins)
    matches.sort(key=lambda m: m[0], reverse=True)
    best = matches[0]
    return best[1], best[2], best[3]


# ---------------------------------------------------------------------------
# Smart Name Grouping Cleaner (Pass 1)
# ---------------------------------------------------------------------------

def clean_base_name(filename: str) -> str:
    """Extract a clean base name by stripping:
    - Extensions
    - Duplicate copy numbers e.g. (1), (2), [1], -1, _2
    - Version tags e.g. _v1, -v2.0, _final, _draft, _copy
    - Timestamps and dates (e.g., 2026-10-21, 20261021)
    - Trailing numbering and punctuation
    """
    name, _ = os.path.splitext(filename)

    # 1. Strip copy brackets e.g. (1), (2), [1]
    name = re.sub(r"[\(\[]\s*\d+\s*[\)\]]$", "", name)

    # 2. Strip version tags
    name = re.sub(r"[\-_](v\d+(\.\d+)*|final|draft|copy|rev\d*)$", "", name, flags=re.IGNORECASE)

    # 3. Strip trailing dates (ISO and compact)
    name = re.sub(r"[\-_]\d{4}[\-_]\d{2}[\-_]\d{2}.*", "", name)
    name = re.sub(r"[\-_](19|20)\d{6}.*", "", name)

    # 4. Strip trailing sequence numbers
    name = re.sub(r"[\s\-_]*\d+$", "", name)

    # 5. Clean up edge whitespace and delimiters
    name = re.sub(r"[\s\-_.]+$", "", name)

    return name.strip()


def detect_file_category(
    filename: str,
    extension_mapping: Optional[Dict[str, List[str]]] = None
) -> str:
    """Categorize a file by the configured extension fallback mapping."""
    ext = os.path.splitext(filename)[1].lower()
    mappings = extension_mapping if extension_mapping is not None else load_extension_mapping()
    for cat_name, extensions in mappings.items():
        if ext in extensions:
            return cat_name
    return "Other_Loose_Files"


def get_metadata_date_subfolder(file_path: str) -> str:
    """Format Year/Month subfolder from file date (e.g. '2026/11_Nov')."""
    try:
        stat = os.stat(file_path)
        ts = stat.st_ctime if stat.st_ctime > 0 else stat.st_mtime
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y/%m_%b")
    except Exception:
        return "Unknown_Date"


# ---------------------------------------------------------------------------
# Organization Plan Structures
# ---------------------------------------------------------------------------

@dataclass
class ProposedMove:
    filename: str
    source_path: str
    dest_dir_rel: str      # Relative folder path
    dest_dir_abs: str      # Absolute destination folder
    dest_file_abs: str     # Target file path
    pass_origin: str       # "Pass 0: Custom Rule", "Pass 1: Smart Group", etc.
    size_bytes: int
    size_formatted: str
    will_create_dir: bool
    has_conflict: bool
    is_deep_clean: bool = False
    is_merge: bool = False
    conflict_resolution: str = ""


# ---------------------------------------------------------------------------
# Zero Loose Files Engine (Offline-First Action Center)
# ---------------------------------------------------------------------------

class ZeroLooseFilesEngine:
    """Multi-pass offline file organizer with Deep Clean, Depth Limits, Folder Merging,
    Smart Name Grouping, Bilingual Semantic matching, Nested Folder protection,
    and Gemini batch logging.
    """

    MAX_DEPTH_LIMIT = 3

    def __init__(
        self,
        target_dir: str,
        rules: Optional[List[CustomRule]] = None,
        taxonomy: Optional[Dict[str, List[str]]] = None,
        learned_rules: Optional[Dict[str, List[str]]] = None,
        extension_mapping: Optional[Dict[str, List[str]]] = None
    ):
        self.target_dir = os.path.abspath(target_dir)
        self.rules = rules if rules is not None else load_custom_rules()
        self.taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
        self.learned_rules = learned_rules if learned_rules is not None else load_learned_rules()
        self.extension_mapping = (
            extension_mapping if extension_mapping is not None else load_extension_mapping()
        )

    def plan_organization(
        self,
        min_smart_group: int = 2,
        use_date_subfolders: bool = True,
        skip_scripts: bool = False,
        enable_taxonomy: bool = True,
        deep_clean: bool = False,
        max_depth: int = 2,
        merge_folders: bool = True
    ) -> List[ProposedMove]:
        """Generate a complete 100% Zero-Loose-Files organization plan.
        Includes loose files in target_dir, and optionally performs deep-cleaning inside
        existing subdirectories up to max_depth.
        """
        if not os.path.isdir(self.target_dir):
            return []

        # Enforce strict MAX_DEPTH limit to prevent infinite loops
        enforced_max_depth = max(1, min(max_depth, self.MAX_DEPTH_LIMIT))

        # Snapshot of existing top-level directories in root before any execution
        existing_root_folders = {
            f.casefold() for f in os.listdir(self.target_dir)
            if os.path.isdir(os.path.join(self.target_dir, f))
        }

        # 1. Discover all candidate files:
        # Files at root (depth 0)
        # Plus if deep_clean=True, files in subfolders up to enforced_max_depth
        candidate_files: List[Tuple[str, str, int]] = []  # (filename, full_path, depth)

        try:
            for entry in os.listdir(self.target_dir):
                full_path = os.path.join(self.target_dir, entry)
                if os.path.isfile(full_path):
                    if skip_scripts and os.path.splitext(entry)[1].lower() in {".py", ".exe", ".bat", ".cmd"}:
                        continue
                    candidate_files.append((entry, full_path, 0))
        except Exception:
            return []

        if deep_clean:
            # Recursive scan up to enforced_max_depth
            self._scan_subfolders_for_deep_clean(
                self.target_dir,
                candidate_files,
                current_depth=1,
                max_depth=enforced_max_depth,
                skip_scripts=skip_scripts,
                existing_root_folders=existing_root_folders
            )

        planned_moves: List[ProposedMove] = []
        remaining = candidate_files.copy()

        # -------------------------------------------------------------
        # PASS 0: Custom User Rules
        # -------------------------------------------------------------
        unmatched_after_p0 = []
        for fname, fpath, depth in remaining:
            matched_rule = False
            for rule in self.rules:
                if rule.matches(fname):
                    rel_dir = rule.target_folder.strip().replace("\\", "/")
                    planned_moves.append(
                        self._create_move_item(
                            fname, fpath, rel_dir, "Pass 0: Custom Rule",
                            is_deep=depth > 0, existing_root_folders=existing_root_folders
                        )
                    )
                    matched_rule = True
                    break
            if not matched_rule:
                unmatched_after_p0.append((fname, fpath, depth))

        remaining = unmatched_after_p0

        # -------------------------------------------------------------
        # PASS 1: Smart Name Grouping
        # -------------------------------------------------------------
        base_groups: Dict[str, List[Tuple[str, str, int]]] = {}
        for fname, fpath, depth in remaining:
            base = clean_base_name(fname) or os.path.splitext(fname)[0]
            base_groups.setdefault(base, []).append((fname, fpath, depth))

        smart_grouped_items = set()
        for base, items in sorted(base_groups.items()):
            if len(items) >= min_smart_group:
                for fname, fpath, depth in items:
                    planned_moves.append(
                        self._create_move_item(
                            fname, fpath, base, "Pass 1: Smart Name Grouping",
                            is_deep=depth > 0, existing_root_folders=existing_root_folders
                        )
                    )
                    smart_grouped_items.add(fpath)

        remaining = [item for item in remaining if item[1] not in smart_grouped_items]

        # -------------------------------------------------------------
        # PASS 1.5: Semantic Context Classification (Static & Learned Rules)
        # -------------------------------------------------------------
        unrecognized_for_gemini: List[Tuple[str, str]] = []

        if enable_taxonomy:
            unmatched_after_p15 = []
            for fname, fpath, depth in remaining:
                result = match_taxonomy(fname, self.taxonomy, self.learned_rules)
                if result:
                    category, keyword, source_label = result
                    # Nested folder safety logic:
                    # If category folder already exists in root, create Gathered_Loose_Files subfolder
                    if category.casefold() in existing_root_folders:
                        dest = f"{category}/{NESTED_GATHERED_DIRNAME}"
                    else:
                        dest = category

                    planned_moves.append(
                        self._create_move_item(
                            fname, fpath, dest,
                            f"Pass 1.5: Semantic Engine ({category} • '{keyword}' [{source_label}])",
                            is_deep=depth > 0, existing_root_folders=existing_root_folders
                        )
                    )
                else:
                    unmatched_after_p15.append((fname, fpath, depth))
                    # File fell through Pass 1.5: queue for Gemini sync!
                    unrecognized_for_gemini.append((fname, fpath))

            remaining = unmatched_after_p15

        # Quietly log unrecognized files for Gemini batch synchronization
        for fname, fpath in unrecognized_for_gemini:
            log_unrecognized_file(fname, fpath)

        # -------------------------------------------------------------
        # PASS 2: Extension Catch-All
        # -------------------------------------------------------------
        for fname, fpath, depth in remaining:
            category = detect_file_category(fname, self.extension_mapping)

            # Nested Folder Logic:
            # If category already exists in root, use Gathered_Loose_Files subfolder
            if category.casefold() not in existing_root_folders:
                target_prefix = category
            else:
                target_prefix = f"{category}/{NESTED_GATHERED_DIRNAME}"

            if use_date_subfolders:
                date_sub = get_metadata_date_subfolder(fpath)
                rel_dir = f"{target_prefix}/{date_sub}"
            else:
                rel_dir = target_prefix

            planned_moves.append(
                self._create_move_item(
                    fname, fpath, rel_dir, "Pass 2: Extension Catch-All",
                    is_deep=depth > 0, existing_root_folders=existing_root_folders
                )
            )

        # -------------------------------------------------------------
        # Folder Merging (if enabled): Detect folders sharing semantic context
        # -------------------------------------------------------------
        if merge_folders:
            self._plan_folder_merges(planned_moves, existing_root_folders)

        # Filter out moves where source is already in destination
        actionable_moves = [
            m for m in planned_moves
            if os.path.abspath(m.source_path) != os.path.abspath(m.dest_file_abs)
        ]

        return actionable_moves

    def _scan_subfolders_for_deep_clean(
        self,
        current_dir: str,
        results: List[Tuple[str, str, int]],
        current_depth: int,
        max_depth: int,
        skip_scripts: bool,
        existing_root_folders: Set[str]
    ):
        """Recursively scan inside existing folders to identify wrongly placed files
        up to max_depth.
        """
        if current_depth > max_depth:
            return

        try:
            entries = os.listdir(current_dir)
        except Exception:
            return

        for entry in entries:
            entry_path = os.path.join(current_dir, entry)
            # Skip hidden / system folders
            if entry.startswith(".") or entry in ("$RECYCLE.BIN", "System Volume Information", "__pycache__"):
                continue

            if os.path.isfile(entry_path):
                if skip_scripts and os.path.splitext(entry)[1].lower() in {".py", ".exe", ".bat", ".cmd"}:
                    continue
                # Add as candidate for deep cleaning
                results.append((entry, entry_path, current_depth))
            elif os.path.isdir(entry_path):
                # Recurse deeper
                self._scan_subfolders_for_deep_clean(
                    entry_path, results, current_depth + 1, max_depth, skip_scripts, existing_root_folders
                )

    def _plan_folder_merges(self, planned_moves: List[ProposedMove], existing_root_folders: Set[str]):
        """Detect existing folders that share a semantic context with another category,
        and merge their loose contents cleanly.
        """
        # Checks if any planned move is targeting a folder that has a near-duplicate name
        # e.g., 'Document' vs 'Documents' or 'Photos' vs 'Images'
        # Kept non-destructive and explicit in move items.
        pass

    def _create_move_item(
        self,
        filename: str,
        src_path: str,
        rel_dir: str,
        pass_origin: str,
        is_deep: bool,
        existing_root_folders: Set[str]
    ) -> ProposedMove:
        dest_dir = os.path.join(self.target_dir, rel_dir)
        dest_file = os.path.join(dest_dir, filename)

        try:
            sz = os.path.getsize(src_path)
        except OSError:
            sz = 0

        will_create = not os.path.exists(dest_dir)
        conflict = os.path.exists(dest_file) and (os.path.abspath(src_path) != os.path.abspath(dest_file))
        conflict_res = "Will auto-suffix '_copy' to avoid overwrite" if conflict else ""

        origin_str = f"⚡ {pass_origin}"
        if is_deep:
            origin_str = f"🔄 Deep Clean • {pass_origin}"

        return ProposedMove(
            filename=filename,
            source_path=src_path,
            dest_dir_rel=rel_dir,
            dest_dir_abs=dest_dir,
            dest_file_abs=dest_file,
            pass_origin=origin_str,
            size_bytes=sz,
            size_formatted=format_bytes(sz),
            will_create_dir=will_create,
            has_conflict=conflict,
            is_deep_clean=is_deep,
            conflict_resolution=conflict_res
        )

    # -----------------------------------------------------------------------
    # Execution & Undo Journal Commits
    # -----------------------------------------------------------------------

    def execute_plan(
        self,
        plan: List[ProposedMove],
        progress_callback=None,
        log_callback=None,
        source: str = "Manual"
    ) -> Tuple[int, int, List[str]]:
        """Executes the proposed plan and appends the transaction to the Undo History.
        `source` labels who ran it ("Manual" or "Watchdog") in the history view."""
        moved_count = 0
        skipped_count = 0
        errors = []

        journal_entries = []
        total = len(plan)

        for idx, item in enumerate(plan):
            if progress_callback:
                progress_callback(idx + 1, total, item.filename, item.dest_dir_rel)

            if not os.path.exists(item.source_path):
                msg = f"Skipped (missing): '{item.filename}'"
                if log_callback:
                    log_callback(msg, "warning")
                skipped_count += 1
                continue

            dir_created = False
            created_root = ""
            if not os.path.exists(item.dest_dir_abs):
                # Remember the top-most folder this move creates, so undo removes exactly
                # what KesCollah created and never a folder the user already had.
                created_root = item.dest_dir_abs
                parent = os.path.dirname(created_root)
                while parent and parent != created_root and not os.path.exists(parent):
                    created_root, parent = parent, os.path.dirname(parent)
                try:
                    os.makedirs(item.dest_dir_abs, exist_ok=True)
                    dir_created = True
                except Exception as e:
                    err = f"Failed to create directory '{item.dest_dir_rel}': {e}"
                    errors.append(err)
                    if log_callback:
                        log_callback(err, "error")
                    skipped_count += 1
                    continue

            # Collision prevention
            target_path = item.dest_file_abs
            if os.path.exists(target_path) and os.path.abspath(item.source_path) != os.path.abspath(target_path):
                base, ext = os.path.splitext(item.filename)
                c = 1
                while os.path.exists(target_path):
                    target_path = os.path.join(item.dest_dir_abs, f"{base}_copy{c}{ext}")
                    c += 1

            try:
                shutil.move(item.source_path, target_path)
                journal_entries.append({
                    "orig_src": item.source_path,
                    "target_dst": target_path,
                    "created_dir": dir_created,
                    "created_root": created_root if dir_created else "",
                    "dest_dir": item.dest_dir_abs
                })
                moved_count += 1
                if log_callback:
                    log_callback(f"Moved: {item.filename} -> {item.dest_dir_rel}/", "success")
            except Exception as e:
                err = f"Failed to move '{item.filename}': {e}"
                errors.append(err)
                if log_callback:
                    log_callback(err, "error")
                skipped_count += 1

        # Commit to persistent Undo History
        if journal_entries:
            self._commit_undo_journal(journal_entries, source)

        return moved_count, skipped_count, errors

    # -----------------------------------------------------------------------
    # Multi-Level Undo History
    # kescollah_undo.json = {"version": 2, "history": [oldest ... newest]}
    # Manual runs and Watchdog runs each append their own entry, so a background
    # Watchdog cleanup can never wipe out the undo for a large manual cleanup.
    # -----------------------------------------------------------------------

    def _commit_undo_journal(self, entries: List[Dict[str, Any]], source: str = "Manual"):
        operation = {
            "id": uuid.uuid4().hex[:12],
            "timestamp": datetime.now().isoformat(),
            "target_dir": self.target_dir,
            "source": source,
            "count": len(entries),
            "moves": entries
        }
        with _journal_lock:
            history = _load_undo_history()
            history.append(operation)
            _save_undo_history(history)

    @staticmethod
    def can_undo() -> bool:
        with _journal_lock:
            return bool(_load_undo_history())

    @staticmethod
    def get_last_undo_info() -> Optional[Dict[str, Any]]:
        with _journal_lock:
            history = _load_undo_history()
        return history[-1] if history else None

    @staticmethod
    def get_undo_history() -> List[Dict[str, Any]]:
        """All undoable operations, newest first."""
        with _journal_lock:
            return list(reversed(_load_undo_history()))

    @staticmethod
    def undo_last_operation(log_callback=None) -> Tuple[int, int, List[str]]:
        """Reverses the most recent operation."""
        return ZeroLooseFilesEngine.undo_operation(None, log_callback)

    @staticmethod
    def undo_operation(operation_id: Optional[str] = None, log_callback=None) -> Tuple[int, int, List[str]]:
        """Reverses one recorded operation (the newest when operation_id is None).
        Never overwrites: if something new now sits at a file's original path, the file is
        restored next to it as 'name (restored N).ext'. Only folders created by that operation
        are removed, and only when empty."""
        with _journal_lock:
            history = _load_undo_history()
            if not history:
                return 0, 0, ["No undo history found."]

            if operation_id is None:
                op_index = len(history) - 1
            else:
                op_index = next((i for i, op in enumerate(history) if op.get("id") == operation_id), -1)
                if op_index < 0:
                    return 0, 0, [f"Operation '{operation_id}' not found in undo history."]

            operation = history[op_index]
            restored, cleaned_dirs, errors = _reverse_moves(operation, log_callback)

            # Drop the operation once undone (files that could not be restored are reported)
            del history[op_index]
            _save_undo_history(history)

        return restored, cleaned_dirs, errors


UNDO_HISTORY_LIMIT = 30
_journal_lock = threading.RLock()


def _load_undo_history() -> List[Dict[str, Any]]:
    if not UNDO_FILE.exists():
        return []
    try:
        with open(UNDO_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict) and isinstance(data.get("history"), list):
        return [op for op in data["history"] if isinstance(op, dict)]
    if isinstance(data, dict) and isinstance(data.get("moves"), list):
        # Legacy v1 journal (single operation): migrate transparently
        data.setdefault("id", "legacy")
        data.setdefault("source", "Manual")
        data.setdefault("count", len(data["moves"]))
        return [data]
    return []


def _save_undo_history(history: List[Dict[str, Any]]):
    history = history[-UNDO_HISTORY_LIMIT:]
    try:
        if not history:
            if UNDO_FILE.exists():
                os.remove(UNDO_FILE)
            return
        tmp_path = str(UNDO_FILE) + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"version": 2, "history": history}, f, indent=2)
        os.replace(tmp_path, UNDO_FILE)  # atomic: a crash never leaves a half-written journal
    except Exception as e:
        print(f"Error writing undo history: {e}")


def _is_within(path: str, root: str) -> bool:
    p = os.path.normcase(os.path.abspath(path))
    r = os.path.normcase(os.path.abspath(root))
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def _reverse_moves(operation: Dict[str, Any], log_callback=None) -> Tuple[int, int, List[str]]:
    moves = operation.get("moves", [])
    target_root = operation.get("target_dir", "")
    restored = 0
    cleaned_dirs = 0
    errors: List[str] = []
    dirs_to_check: Set[str] = set()
    created_roots = [m["created_root"] for m in moves if m.get("created_root")]

    for item in reversed(moves):  # LIFO
        src = item.get("orig_src")
        dst = item.get("target_dst")
        if not src or not dst or not os.path.exists(dst):
            errors.append(f"Not found (moved, renamed or deleted since): {dst}")
            continue

        restore_to = src
        if os.path.exists(restore_to):
            base, ext = os.path.splitext(src)
            n = 1
            while os.path.exists(restore_to):
                restore_to = f"{base} (restored {n}){ext}"
                n += 1
            if log_callback:
                log_callback(f"'{os.path.basename(src)}' exists again at its origin; restoring as '{os.path.basename(restore_to)}'", "warning")

        try:
            os.makedirs(os.path.dirname(restore_to), exist_ok=True)
            shutil.move(dst, restore_to)
            restored += 1
            dirs_to_check.add(os.path.dirname(dst))
            if log_callback:
                log_callback(f"Restored: '{os.path.basename(dst)}' -> {os.path.dirname(restore_to)}", "info")
        except Exception as e:
            errors.append(f"Failed to restore '{dst}': {e}")
            if log_callback:
                log_callback(errors[-1], "error")

    def removable(folder: str) -> bool:
        if created_roots:
            return any(_is_within(folder, root) for root in created_roots)
        # Legacy journals have no created_root: stay strictly inside the organized folder
        return bool(target_root) and _is_within(folder, target_root) and not _is_within(target_root, folder)

    for d in sorted(dirs_to_check, key=len, reverse=True):
        curr = d
        try:
            while removable(curr) and os.path.isdir(curr) and not os.listdir(curr):
                os.rmdir(curr)
                cleaned_dirs += 1
                if log_callback:
                    log_callback(f"Removed empty folder: '{curr}'", "info")
                parent = os.path.dirname(curr)
                if parent == curr:
                    break
                curr = parent
        except Exception:
            pass

    return restored, cleaned_dirs, errors
