"""High-performance hash-based duplicate file finder (SHA-256 / MD5)
with two-stage hashing (size filter -> header hash -> full hash).
"""

import os
import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import List, Dict, Tuple
from config import format_bytes


@dataclass
class DuplicateGroup:
    file_hash: str
    size_bytes: int
    size_formatted: str
    file_paths: List[str]
    wasted_bytes: int


def calculate_chunk_hash(file_path: str, chunk_size: int = 4096) -> str:
    """Hash the first chunk of a file for fast pre-filtering."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        h.update(f.read(chunk_size))
    return h.hexdigest()


def calculate_full_hash(file_path: str, chunk_size: int = 65536) -> str:
    """Compute complete SHA-256 hash for byte-exact identity verification."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def find_duplicates(
    target_dir: str,
    recursive: bool = True,
    progress_callback=None
) -> List[DuplicateGroup]:
    """Finds byte-identical duplicate files using a 3-stage pipeline:
    1. Filter by identical size in bytes.
    2. Filter by 4KB header hash.
    3. Compute full SHA-256 hash.
    """
    if not os.path.isdir(target_dir):
        return []

    # Stage 1: Gather all files and group by exact size in bytes
    size_map = defaultdict(list)
    all_files = []

    if recursive:
        for root, _, files in os.walk(target_dir):
            for f in files:
                all_files.append(os.path.join(root, f))
    else:
        for f in os.listdir(target_dir):
            p = os.path.join(target_dir, f)
            if os.path.isfile(p):
                all_files.append(p)

    total_files = len(all_files)
    for idx, path in enumerate(all_files):
        if progress_callback:
            progress_callback(idx + 1, total_files, "Stage 1/3: Indexing file sizes...")
        try:
            sz = os.path.getsize(path)
            if sz > 0:  # Ignore 0-byte files
                size_map[sz].append(path)
        except OSError:
            continue

    # Keep only sizes that have 2 or more files
    potential_duplicates = [paths for sz, paths in size_map.items() if len(paths) > 1]
    total_potential = sum(len(p) for p in potential_duplicates)

    # Stage 2: Quick Header Hash
    header_map = defaultdict(list)
    processed = 0
    for paths in potential_duplicates:
        for path in paths:
            processed += 1
            if progress_callback:
                progress_callback(processed, total_potential, f"Stage 2/3: Pre-hashing {os.path.basename(path)}")
            try:
                ch = calculate_chunk_hash(path)
                header_map[(os.path.getsize(path), ch)].append(path)
            except OSError:
                continue

    # Stage 3: Full SHA-256 on matched headers
    candidates = [paths for key, paths in header_map.items() if len(paths) > 1]
    total_candidates = sum(len(p) for p in candidates)

    full_hash_map = defaultdict(list)
    processed = 0
    for paths in candidates:
        for path in paths:
            processed += 1
            if progress_callback:
                progress_callback(processed, total_candidates, f"Stage 3/3: Verifying {os.path.basename(path)}")
            try:
                fh = calculate_full_hash(path)
                full_hash_map[fh].append(path)
            except OSError:
                continue

    # Construct final results
    results: List[DuplicateGroup] = []
    for f_hash, paths in full_hash_map.items():
        if len(paths) > 1:
            try:
                sz = os.path.getsize(paths[0])
            except OSError:
                sz = 0
            wasted = (len(paths) - 1) * sz
            results.append(
                DuplicateGroup(
                    file_hash=f_hash,
                    size_bytes=sz,
                    size_formatted=format_bytes(sz),
                    file_paths=sorted(paths),
                    wasted_bytes=wasted
                )
            )

    # Sort groups by wasted bytes descending (biggest waste first)
    results.sort(key=lambda x: x.wasted_bytes, reverse=True)
    return results
