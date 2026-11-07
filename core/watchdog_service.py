"""Watchdog background service for real-time folder monitoring
and automated zero-loose-files organization.
Supports watchdog native OS hooks when installed, with seamless standard-library
polling fallback so the app NEVER fails to start.
"""

import os
import time
import threading
from typing import Optional, Set
from PyQt6.QtCore import QObject, pyqtSignal

# Optional watchdog import with graceful fallback
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False
    Observer = None
    FileSystemEventHandler = object

from core.file_logic import ZeroLooseFilesEngine, load_custom_rules


if HAS_WATCHDOG:
    class AutoSortHandler(FileSystemEventHandler):
        def __init__(self, service: "FolderWatchdogService"):
            super().__init__()
            self.service = service

        def on_created(self, event):
            if not event.is_directory:
                self.service.schedule_file_check(event.src_path)

        def on_moved(self, event):
            if not event.is_directory:
                self.service.schedule_file_check(event.dest_path)


class FolderWatchdogService(QObject):
    """Background service that watches a target directory and triggers
    sorting when new files arrive. Works with or without 'watchdog' library installed.
    """
    file_detected = pyqtSignal(str)
    organization_completed = pyqtSignal(int, str)
    status_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.target_dir: Optional[str] = None
        self.observer = None
        self.is_running = False
        self._debounce_timer: Optional[threading.Timer] = None
        self._poll_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self.use_date_subfolders = True
        self.min_smart_group = 2

    def start_watching(self, directory: str, use_date_subfolders: bool = True, min_smart_group: int = 2):
        self.stop_watching()

        if not os.path.isdir(directory):
            self.status_changed.emit(False, f"Invalid directory: {directory}")
            return

        self.target_dir = os.path.abspath(directory)
        self.use_date_subfolders = use_date_subfolders
        self.min_smart_group = min_smart_group
        self._stop_event.clear()

        # Strategy A: Use watchdog library if available
        if HAS_WATCHDOG:
            try:
                self.observer = Observer()
                handler = AutoSortHandler(self)
                self.observer.schedule(handler, path=self.target_dir, recursive=False)
                self.observer.start()
                self.is_running = True
                self.status_changed.emit(True, f"Actively watching '{os.path.basename(self.target_dir)}' (Native)")
                return
            except Exception as e:
                print(f"Watchdog native observer failed: {e}. Falling back to polling.")

        # Strategy B: Seamless standard-library polling (works on ANY machine without pip packages)
        try:
            self._poll_thread = threading.Thread(target=self._run_poll_loop, daemon=True)
            self.is_running = True
            self._poll_thread.start()
            self.status_changed.emit(True, f"Actively watching '{os.path.basename(self.target_dir)}' (Standard)")
        except Exception as e:
            self.is_running = False
            self.status_changed.emit(False, f"Watcher failed to start: {e}")

    def _run_poll_loop(self):
        """Standard-library filesystem polling thread (1.5s interval)."""
        known_files: Set[str] = set()
        try:
            if self.target_dir and os.path.isdir(self.target_dir):
                known_files = {
                    f for f in os.listdir(self.target_dir)
                    if os.path.isfile(os.path.join(self.target_dir, f))
                }
        except Exception:
            pass

        while not self._stop_event.is_set():
            time.sleep(1.5)
            if self._stop_event.is_set():
                break

            if not self.target_dir or not os.path.isdir(self.target_dir):
                continue

            try:
                current_files = {
                    f for f in os.listdir(self.target_dir)
                    if os.path.isfile(os.path.join(self.target_dir, f))
                }
                new_files = current_files - known_files
                for f in new_files:
                    full_p = os.path.join(self.target_dir, f)
                    self.schedule_file_check(full_p)
                known_files = current_files
            except Exception:
                continue

    def stop_watching(self):
        self._stop_event.set()

        if self.observer and self.is_running:
            try:
                self.observer.stop()
                self.observer.join(timeout=2)
            except Exception:
                pass
            self.observer = None

        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(timeout=2)
            self._poll_thread = None

        self.is_running = False
        self.status_changed.emit(False, "Folder Watchdog is Idle")

    def schedule_file_check(self, file_path: str):
        """Debounce file arrival (wait 1.5s for write completion)."""
        filename = os.path.basename(file_path)
        # Ignore temporary download and lock files
        if (filename.endswith(".tmp") or
            filename.endswith(".crdownload") or
            filename.endswith(".part") or
            filename.startswith(".~")):
            return

        self.file_detected.emit(filename)

        with self._lock:
            if self._debounce_timer:
                self._debounce_timer.cancel()
            self._debounce_timer = threading.Timer(1.5, self._run_auto_sort)
            self._debounce_timer.start()

    def _run_auto_sort(self):
        """Execute automated Zero-Loose-Files organization with Semantic Taxonomy on the monitored directory."""
        if not self.target_dir or not os.path.isdir(self.target_dir):
            return

        rules = load_custom_rules()
        engine = ZeroLooseFilesEngine(self.target_dir, rules)

        plan = engine.plan_organization(
            min_smart_group=self.min_smart_group,
            use_date_subfolders=self.use_date_subfolders,
            skip_scripts=True
        )

        if not plan:
            return

        moved, skipped, errors = engine.execute_plan(plan, source="Watchdog")
        if moved > 0:
            summary = f"Watchdog organized {moved} newly added files."
            self.organization_completed.emit(moved, summary)
