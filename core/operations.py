"""File operations engine: Dry-run simulation, background QThread move worker,
and Undo management.
"""

import os
import shutil
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from PyQt6.QtCore import QThread, pyqtSignal


@dataclass
class PlanItem:
    filename: str
    group_name: str
    source_path: str
    destination_dir: str
    destination_path: str
    will_create_dir: bool
    has_conflict: bool
    conflict_resolution: str = ""


@dataclass
class DryRunReport:
    items: List[PlanItem]
    total_files: int
    folders_to_create: int
    conflicts_count: int
    total_bytes: int


def generate_dry_run(target_dir: str, groups: Dict[str, List[str]]) -> DryRunReport:
    """Simulate file organization and generate a detailed dry-run report."""
    items: List[PlanItem] = []
    folders_to_create = set()
    conflicts_count = 0
    total_bytes = 0

    for group_name, files in groups.items():
        dest_dir = os.path.join(target_dir, group_name)
        dir_exists = os.path.exists(dest_dir)
        if not dir_exists:
            folders_to_create.add(dest_dir)

        for f in files:
            src = os.path.join(target_dir, f)
            dst = os.path.join(dest_dir, f)

            try:
                sz = os.path.getsize(src)
            except OSError:
                sz = 0
            total_bytes += sz

            conflict = os.path.exists(dst)
            res = ""
            if conflict:
                conflicts_count += 1
                res = "Destination file already exists (will auto-rename safely or skip)"

            items.append(
                PlanItem(
                    filename=f,
                    group_name=group_name,
                    source_path=src,
                    destination_dir=dest_dir,
                    destination_path=dst,
                    will_create_dir=not dir_exists,
                    has_conflict=conflict,
                    conflict_resolution=res,
                )
            )

    return DryRunReport(
        items=items,
        total_files=len(items),
        folders_to_create=len(folders_to_create),
        conflicts_count=conflicts_count,
        total_bytes=total_bytes,
    )


class FileMoveWorker(QThread):
    """Background thread to execute file moves safely without freezing UI."""
    progress_updated = pyqtSignal(int, int, str, str)  # current, total, filename, group
    log_message = pyqtSignal(str, str)                 # message, level ("info", "success", "warning", "error")
    finished_success = pyqtSignal(int, int, list)       # moved_count, skipped_count, history_batch
    error_occurred = pyqtSignal(str)                   # error message

    def __init__(self, target_dir: str, groups: Dict[str, List[str]], parent=None):
        super().__init__(parent)
        self.target_dir = target_dir
        self.groups = groups
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        try:
            total_files = sum(len(flist) for flist in self.groups.values())
            current = 0
            moved = 0
            skipped = 0
            history_batch: List[Tuple[str, str, bool]] = []

            self.log_message.emit(
                f"Starting move operation for {total_files} files across {len(self.groups)} groups...",
                "info"
            )

            for group_name, file_list in self.groups.items():
                if self._is_cancelled:
                    self.log_message.emit("Operation cancelled by user.", "warning")
                    break

                folder_path = os.path.join(self.target_dir, group_name)
                created_by_us = not os.path.exists(folder_path)

                if created_by_us:
                    try:
                        os.makedirs(folder_path, exist_ok=True)
                        self.log_message.emit(f"Created folder: '{group_name}/'", "info")
                    except Exception as e:
                        self.log_message.emit(f"Failed to create directory '{group_name}': {e}", "error")
                        skipped += len(file_list)
                        current += len(file_list)
                        continue

                for f in file_list:
                    if self._is_cancelled:
                        break

                    current += 1
                    src = os.path.join(self.target_dir, f)
                    dst = os.path.join(folder_path, f)

                    if not os.path.exists(src):
                        self.log_message.emit(f"Source file not found: {f}", "warning")
                        skipped += 1
                        self.progress_updated.emit(current, total_files, f, group_name)
                        continue

                    # Handle name collision by appending a safe suffix if needed
                    actual_dst = dst
                    if os.path.exists(actual_dst):
                        base, ext = os.path.splitext(f)
                        counter = 1
                        while os.path.exists(actual_dst):
                            actual_dst = os.path.join(folder_path, f"{base}_copy{counter}{ext}")
                            counter += 1
                        self.log_message.emit(
                            f"Collision detected for '{f}'. Saving as '{os.path.basename(actual_dst)}'",
                            "warning"
                        )

                    try:
                        shutil.move(src, actual_dst)
                        history_batch.append((src, actual_dst, created_by_us))
                        moved += 1
                        self.log_message.emit(f"Moved: '{f}' -> '{group_name}/'", "success")
                    except Exception as ex:
                        self.log_message.emit(f"Failed to move '{f}': {ex}", "error")
                        skipped += 1

                    self.progress_updated.emit(current, total_files, f, group_name)

            self.log_message.emit(
                f"Batch completed: {moved} files moved successfully ({skipped} skipped/errors).",
                "success" if skipped == 0 else "warning"
            )
            self.finished_success.emit(moved, skipped, history_batch)

        except Exception as e:
            self.error_occurred.emit(str(e))


class UndoManager:
    """Manages transaction history for reversing file movements."""
    def __init__(self):
        # Stack of batches: each batch is a list of (orig_src, new_dst, folder_created)
        self.history_batches: List[List[Tuple[str, str, bool]]] = []

    def record_batch(self, batch: List[Tuple[str, str, bool]]):
        if batch:
            self.history_batches.append(batch)

    def can_undo(self) -> bool:
        return len(self.history_batches) > 0

    def undo_last(self, log_callback=None) -> Tuple[int, int, List[str]]:
        """Reverses the most recent batch.
        Returns (restored_count, removed_folders_count, errors)
        """
        if not self.history_batches:
            return 0, 0, ["No actions in history to undo."]

        batch = self.history_batches.pop()
        restored = 0
        folders_to_check = set()
        errors = []

        # Reverse moves in LIFO order
        for orig_src, current_dst, was_created in reversed(batch):
            if os.path.exists(current_dst):
                try:
                    # Ensure parent dir exists
                    os.makedirs(os.path.dirname(orig_src), exist_ok=True)
                    shutil.move(current_dst, orig_src)
                    restored += 1
                    if log_callback:
                        log_callback(f"Restored: '{os.path.basename(current_dst)}' -> original directory", "info")
                    folders_to_check.add(os.path.dirname(current_dst))
                except Exception as e:
                    err = f"Failed to restore '{current_dst}': {e}"
                    errors.append(err)
                    if log_callback:
                        log_callback(err, "error")
            else:
                errors.append(f"File not found to restore: '{current_dst}'")

        # Cleanup created folders if they are now empty
        removed_folders = 0
        for folder in folders_to_check:
            try:
                if os.path.isdir(folder) and not os.listdir(folder):
                    os.rmdir(folder)
                    removed_folders += 1
                    if log_callback:
                        log_callback(f"Cleaned up empty directory: '{os.path.basename(folder)}/'", "info")
            except Exception as e:
                errors.append(f"Failed to remove empty folder '{folder}': {e}")

        return restored, removed_folders, errors
