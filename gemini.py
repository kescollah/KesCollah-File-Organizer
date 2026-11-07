import os
import re
import shutil
from collections import defaultdict


def clean_base_name(filename):
    """Extracts a clean base category name by stripping extensions,

    copy numbers like (1), version tags, and trailing numbers.
    """
    # Remove extension
    name, _ = os.path.splitext(filename)

    # Remove copy numbers like (1), (2), -1, -2 at the end
    name = re.sub(r"[\(\-_]\d+\)?$", "", name)

    # Remove trailing dates/timestamps (e.g. 2026-10-21)
    name = re.sub(r"[\-_]\d{4}[\-_]\d{2}[\-_]\d{2}.*", "", name)

    # Remove common extra spacing
    name = name.strip()
    return name


def organize_directory(target_dir="."):
    files = [
        f
        for f in os.listdir(target_dir)
        if os.path.isfile(os.path.join(target_dir, f))
    ]

    groups = defaultdict(list)

    # Group files sharing the same cleaned base name
    for file in files:
        base_name = clean_base_name(file)
        if base_name:
            groups[base_name].append(file)

    for group_name, file_list in groups.items():
        # Only create a directory if there are multiple related files
        if len(file_list) > 1:
            # Create folder safely
            folder_path = os.path.join(target_dir, group_name)
            os.makedirs(folder_path, exist_ok=True)

            # Move files into folder
            for f in file_list:
                src = os.path.join(target_dir, f)
                dst = os.path.join(folder_path, f)
                shutil.move(src, dst)
                print(f"Moved: {f} -> {group_name}/")


if __name__ == "__main__":
    import sys

    # If run with --cli, execute directly in terminal; otherwise open the modern PyQt6 desktop app
    if "--cli" in sys.argv:
        target = sys.argv[2] if len(sys.argv) > 2 else "."
        organize_directory(target)
    else:
        try:
            from main import main as launch_pyqt_app
            launch_pyqt_app()
        except ImportError:
            try:
                from app import main as launch_gui
                launch_gui()
            except ImportError:
                organize_directory(".")

