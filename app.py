"""File Organizer GUI Application
A graphical user interface built with Tkinter for organizing files by base name,
integrating with the logic from gemini.py.
"""

import os
import re
import shutil
import subprocess
import threading
from collections import defaultdict
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Import base cleaning logic from gemini.py if available
try:
    from gemini import clean_base_name
except ImportError:
    def clean_base_name(filename):
        """Extracts a clean base category name by stripping extensions,
        copy numbers like (1), version tags, and trailing numbers.
        """
        name, _ = os.path.splitext(filename)
        name = re.sub(r"[\(\-_]\d+\)?$", "", name)
        name = re.sub(r"[\-_]\d{4}[\-_]\d{2}[\-_]\d{2}.*", "", name)
        return name.strip()


class FileOrganizerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("File Organizer - Desktop App")
        self.geometry("820x640")
        self.minsize(700, 500)

        # Center the window on screen
        self._center_window()

        # State tracking
        self.current_dir = tk.StringVar(value=os.path.abspath("."))
        self.min_files_var = tk.IntVar(value=2)
        self.skip_scripts_var = tk.BooleanVar(value=True)
        self.groups_to_move = {}
        self.ignored_files = []
        self.undo_history = []  # Stores list of (original_path, new_path, created_folder)

        # Setup ttk styles
        self._configure_styles()

        # Build UI layout
        self._create_widgets()

        # Initial scan of the current directory
        self.after(200, self.scan_directory)

    def _center_window(self):
        self.update_idletasks()
        w = 820
        h = 640
        ws = self.winfo_screenwidth()
        hs = self.winfo_screenheight()
        x = max(0, (ws - w) // 2)
        y = max(0, (hs - h) // 2)
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _configure_styles(self):
        self.style = ttk.Style()
        available_themes = self.style.theme_names()
        if "vista" in available_themes:
            self.style.theme_use("vista")
        elif "clam" in available_themes:
            self.style.theme_use("clam")

        self.style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        self.style.configure("Subheader.TLabel", font=("Segoe UI", 9), foreground="#555555")
        self.style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), padding=6)
        self.style.configure("Primary.TButton", font=("Segoe UI", 9, "bold"), padding=6)

    def _create_widgets(self):
        # Main container with padding
        container = ttk.Frame(self, padding="16 14 16 14")
        container.pack(fill=tk.BOTH, expand=True)

        # 1. Header Section
        header_frame = ttk.Frame(container)
        header_frame.pack(fill=tk.X, pady=(0, 12))

        title_lbl = ttk.Label(header_frame, text="📁 Smart File Organizer", style="Header.TLabel")
        title_lbl.pack(anchor=tk.W)
        subtitle_lbl = ttk.Label(
            header_frame,
            text="Automatically group related files (e.g., invoices, photos, reports) into neat subfolders.",
            style="Subheader.TLabel",
        )
        subtitle_lbl.pack(anchor=tk.W, pady=(2, 0))

        # 2. Directory Selector Frame
        dir_frame = ttk.LabelFrame(container, text=" Target Directory ", padding="10 8 10 10")
        dir_frame.pack(fill=tk.X, pady=(0, 10))

        dir_entry = ttk.Entry(dir_frame, textvariable=self.current_dir, font=("Segoe UI", 9))
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        browse_btn = ttk.Button(dir_frame, text="Browse...", command=self.browse_directory)
        browse_btn.pack(side=tk.LEFT, padx=(0, 4))

        open_folder_btn = ttk.Button(dir_frame, text="Open in Explorer", command=self.open_current_directory)
        open_folder_btn.pack(side=tk.LEFT)

        # 3. Settings & Options
        options_frame = ttk.Frame(container)
        options_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(options_frame, text="Min files per group:").pack(side=tk.LEFT, padx=(0, 6))
        min_spin = ttk.Spinbox(
            options_frame,
            from_=2,
            to=50,
            width=5,
            textvariable=self.min_files_var,
            command=self.scan_directory,
        )
        min_spin.pack(side=tk.LEFT, padx=(0, 16))

        skip_chk = ttk.Checkbutton(
            options_frame,
            text="Protect Python & Script files (.py, .bat, .exe, .sh)",
            variable=self.skip_scripts_var,
            command=self.scan_directory,
        )
        skip_chk.pack(side=tk.LEFT)

        # 4. Action Buttons Toolbar
        btn_frame = ttk.Frame(container)
        btn_frame.pack(fill=tk.X, pady=(0, 10))

        self.preview_btn = ttk.Button(
            btn_frame,
            text="🔍 Scan / Preview",
            style="Action.TButton",
            command=self.scan_directory,
        )
        self.preview_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.organize_btn = ttk.Button(
            btn_frame,
            text="✨ Organize Files Now",
            style="Primary.TButton",
            command=self.confirm_and_organize,
        )
        self.organize_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.undo_btn = ttk.Button(
            btn_frame,
            text="↩️ Undo Last Move",
            state=tk.DISABLED,
            command=self.undo_organization,
        )
        self.undo_btn.pack(side=tk.LEFT)

        self.status_summary_var = tk.StringVar(value="Ready.")
        status_lbl = ttk.Label(btn_frame, textvariable=self.status_summary_var, font=("Segoe UI", 9, "italic"))
        status_lbl.pack(side=tk.RIGHT, padx=4)

        # 5. Notebook (Tabs for Preview and Logs)
        self.notebook = ttk.Notebook(container)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        # Tab 1: Preview Treeview
        tree_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tree_tab, text="  📋 Proposed Groups & Preview  ")

        columns = ("count", "details")
        self.tree = ttk.Treeview(tree_tab, columns=columns, show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Group Name / File Name", anchor=tk.W)
        self.tree.heading("count", text="Files", anchor=tk.CENTER)
        self.tree.heading("details", text="Destination Action", anchor=tk.W)

        self.tree.column("#0", width=400, stretch=True)
        self.tree.column("count", width=90, stretch=False, anchor=tk.CENTER)
        self.tree.column("details", width=250, stretch=True)

        tree_scroll_y = ttk.Scrollbar(tree_tab, orient=tk.VERTICAL, command=self.tree.yview)
        tree_scroll_x = ttk.Scrollbar(tree_tab, orient=tk.HORIZONTAL, command=self.tree.xview)
        self.tree.configure(yscrollcommand=tree_scroll_y.set, xscrollcommand=tree_scroll_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        tree_scroll_y.grid(row=0, column=1, sticky="ns")
        tree_scroll_x.grid(row=1, column=0, sticky="ew")

        tree_tab.rowconfigure(0, weight=1)
        tree_tab.columnconfigure(0, weight=1)

        # Tab 2: Activity Log
        log_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(log_tab, text="  📜 Activity Log  ")

        self.log_text = tk.Text(
            log_tab,
            wrap=tk.WORD,
            font=("Consolas", 9),
            bg="#ffffff",
            fg="#222222",
            relief=tk.FLAT,
        )
        log_scroll = ttk.Scrollbar(log_tab, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)

        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")

        log_tab.rowconfigure(0, weight=1)
        log_tab.columnconfigure(0, weight=1)

        # 6. Bottom Status Bar & Progress
        bottom_frame = ttk.Frame(container)
        bottom_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(bottom_frame, mode="determinate")
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=False, padx=(8, 0), ipadx=40)

        self.status_var = tk.StringVar(value="Select a directory and click 'Scan / Preview' to review.")
        self.status_bar = ttk.Label(bottom_frame, textvariable=self.status_var, font=("Segoe UI", 8), foreground="#444444")
        self.status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

    def log(self, message):
        """Append text to the Activity Log tab."""
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)

    def browse_directory(self):
        chosen = filedialog.askdirectory(initialdir=self.current_dir.get(), title="Select Target Folder")
        if chosen:
            self.current_dir.set(os.path.abspath(chosen))
            self.scan_directory()

    def open_current_directory(self):
        target = self.current_dir.get()
        if os.path.isdir(target):
            try:
                os.startfile(target)
            except Exception as e:
                messagebox.showerror("Error", f"Could not open directory:\n{e}")
        else:
            messagebox.showwarning("Warning", "Directory does not exist.")

    def scan_directory(self):
        """Scan the directory and populate the treeview with proposed groups."""
        target_dir = self.current_dir.get().strip()
        if not os.path.isdir(target_dir):
            self.status_var.set("Error: Target directory does not exist.")
            return

        min_files = self.min_files_var.get()
        skip_scripts = self.skip_scripts_var.get()
        script_exts = {".py", ".pyw", ".exe", ".bat", ".cmd", ".sh"}

        # Clear existing items in Treeview
        for item in self.tree.get_children():
            self.tree.delete(item)

        try:
            entries = os.listdir(target_dir)
        except Exception as e:
            self.status_var.set(f"Cannot read directory: {e}")
            return

        files = []
        for f in entries:
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                # Don't move the application itself or script files if protection is checked
                _, ext = os.path.splitext(f)
                if skip_scripts and ext.lower() in script_exts:
                    continue
                files.append(f)

        groups = defaultdict(list)
        for f in files:
            base = clean_base_name(f)
            if base:
                groups[base].append(f)

        self.groups_to_move = {}
        self.ignored_files = []

        total_files_to_move = 0
        total_groups_count = 0

        # Populate groups
        for group_name, file_list in sorted(groups.items()):
            if len(file_list) >= min_files:
                self.groups_to_move[group_name] = file_list
                total_files_to_move += len(file_list)
                total_groups_count += 1

                # Add parent node for this folder
                parent_id = self.tree.insert(
                    "",
                    tk.END,
                    text=f"📁 {group_name}/",
                    values=(f"{len(file_list)} files", f"Will create folder '{group_name}' and move"),
                    open=True,
                )
                # Add child items for each file
                for f in sorted(file_list):
                    self.tree.insert(
                        parent_id,
                        tk.END,
                        text=f"  📄 {f}",
                        values=("", f"-> {group_name}/{f}"),
                    )
            else:
                self.ignored_files.extend(file_list)

        # Also list files that won't be moved (single files)
        if self.ignored_files:
            ignored_parent = self.tree.insert(
                "",
                tk.END,
                text=f"⚪ Unchanged Files ({len(self.ignored_files)})",
                values=(f"{len(self.ignored_files)} files", f"Ignored (fewer than {min_files} files)"),
                open=False,
            )
            for f in sorted(self.ignored_files):
                self.tree.insert(
                    ignored_parent,
                    tk.END,
                    text=f"  📄 {f}",
                    values=("", "Kept in current directory"),
                )

        summary_msg = f"{total_files_to_move} files to organize into {total_groups_count} folders."
        self.status_summary_var.set(summary_msg)
        self.status_var.set(f"Scan complete. {summary_msg} ({len(self.ignored_files)} files untouched).")

        self.log(f"[Scan] {target_dir}: Found {total_files_to_move} files across {total_groups_count} groups to organize.")

    def confirm_and_organize(self):
        """Ask confirmation and run the file organization in a background thread."""
        if not self.groups_to_move:
            messagebox.showinfo("No Files", "No file groups found to organize. Try lowering the 'Min files' setting or selecting another folder.")
            return

        total_files = sum(len(flist) for flist in self.groups_to_move.values())
        num_folders = len(self.groups_to_move)

        confirmed = messagebox.askyesno(
            "Confirm Organization",
            f"Are you sure you want to organize {total_files} files into {num_folders} subfolders in:\n\n{self.current_dir.get()}?\n\n(You can undo this immediately afterwards)",
            icon="question",
        )
        if not confirmed:
            return

        # Disable buttons during operation
        self.organize_btn.config(state=tk.DISABLED)
        self.preview_btn.config(state=tk.DISABLED)
        self.undo_btn.config(state=tk.DISABLED)
        self.progress["maximum"] = total_files
        self.progress["value"] = 0

        # Switch to log tab so user can see progress in real time
        self.notebook.select(1)

        threading.Thread(target=self._run_organization, daemon=True).start()

    def _run_organization(self):
        target_dir = self.current_dir.get()
        history_batch = []
        moved_count = 0
        error_count = 0

        self.log(f"\n--- Starting Organization: {target_dir} ---")

        for group_name, file_list in self.groups_to_move.items():
            folder_path = os.path.join(target_dir, group_name)
            folder_created_by_us = not os.path.exists(folder_path)

            try:
                os.makedirs(folder_path, exist_ok=True)
            except Exception as e:
                self.log(f"Error creating folder '{group_name}': {e}")
                error_count += len(file_list)
                continue

            for f in file_list:
                src = os.path.join(target_dir, f)
                dst = os.path.join(folder_path, f)

                if not os.path.exists(src):
                    self.log(f"Skipping (not found): {f}")
                    continue

                if os.path.exists(dst):
                    self.log(f"Conflict: Destination already exists for '{f}', skipped.")
                    error_count += 1
                    continue

                try:
                    shutil.move(src, dst)
                    history_batch.append((src, dst, folder_created_by_us))
                    moved_count += 1
                    self.log(f"Moved: '{f}' -> '{group_name}/'")
                except Exception as e:
                    self.log(f"Failed to move '{f}': {e}")
                    error_count += 1

                # Update progress in UI
                self.after(0, self._step_progress, moved_count)

        self.undo_history = history_batch
        self.log(f"--- Finished! Successfully moved {moved_count} files ({error_count} errors/conflicts). ---\n")

        # Re-enable UI on main thread
        self.after(0, self._finish_organization, moved_count, error_count)

    def _step_progress(self, val):
        self.progress["value"] = val
        self.status_var.set(f"Moving files... ({val} done)")

    def _finish_organization(self, moved_count, error_count):
        self.organize_btn.config(state=tk.NORMAL)
        self.preview_btn.config(state=tk.NORMAL)
        if self.undo_history:
            self.undo_btn.config(state=tk.NORMAL)

        self.status_var.set(f"Done! Moved {moved_count} files. {error_count} skipped/errors.")
        self.scan_directory()

        messagebox.showinfo(
            "Organization Complete",
            f"Successfully moved {moved_count} files into folders!\n\nIf you made a mistake, click '↩️ Undo Last Move' to restore them.",
        )

    def undo_organization(self):
        """Move all files back to their original locations and remove empty created folders."""
        if not self.undo_history:
            messagebox.showinfo("Undo", "No previous actions to undo.")
            return

        confirmed = messagebox.askyesno(
            "Confirm Undo",
            f"Restore {len(self.undo_history)} files back to their original folder?",
            icon="question",
        )
        if not confirmed:
            return

        self.undo_btn.config(state=tk.DISABLED)
        self.notebook.select(1)
        self.log("\n--- Undoing Last Organization ---")

        restored = 0
        folders_to_check = set()

        # Revert in reverse order
        for src, dst, created_folder in reversed(self.undo_history):
            if os.path.exists(dst):
                try:
                    shutil.move(dst, src)
                    restored += 1
                    self.log(f"Restored: '{os.path.basename(dst)}' -> original directory")
                    folders_to_check.add(os.path.dirname(dst))
                except Exception as e:
                    self.log(f"Could not restore '{dst}': {e}")

        # Clean up empty folders that were created
        for folder in folders_to_check:
            try:
                if os.path.isdir(folder) and not os.listdir(folder):
                    os.rmdir(folder)
                    self.log(f"Removed empty folder: '{os.path.basename(folder)}/'")
            except Exception as e:
                self.log(f"Could not remove folder '{folder}': {e}")

        self.undo_history = []
        self.log(f"--- Undo finished! Restored {restored} files. ---\n")
        self.status_var.set(f"Undo completed: {restored} files restored.")
        self.scan_directory()
        messagebox.showinfo("Undo Finished", f"Restored {restored} files to their original location.")


def main():
    app = FileOrganizerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
