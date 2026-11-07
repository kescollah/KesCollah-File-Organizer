"""Core business logic and services for KesCollah."""
from core.file_logic import (
    clean_base_name,
    load_custom_rules,
    save_custom_rules,
    load_taxonomy,
    save_taxonomy,
    load_extension_mapping,
    save_extension_mapping,
    match_taxonomy,
    CustomRule,
    ProposedMove,
    ZeroLooseFilesEngine,
)
from core.gemini_sync import (
    load_learned_rules,
    save_learned_rules,
    load_unrecognized_files,
    save_unrecognized_files,
    clear_unrecognized_files,
    log_unrecognized_file,
    sync_knowledge_base,
    get_gemini_api_key,
    set_gemini_api_key
)
from core.size_analyzer import scan_directory_space_hogs, DiskItem
from core.duplicate_finder import find_duplicates, DuplicateGroup
from core.watchdog_service import FolderWatchdogService
from core.network_tools import scan_wifi_networks, get_connected_network_info, WifiNetwork

__all__ = [
    "clean_base_name",
    "load_custom_rules",
    "save_custom_rules",
    "load_taxonomy",
    "save_taxonomy",
    "load_learned_rules",
    "save_learned_rules",
    "load_unrecognized_files",
    "save_unrecognized_files",
    "clear_unrecognized_files",
    "log_unrecognized_file",
    "sync_knowledge_base",
    "get_gemini_api_key",
    "set_gemini_api_key",
    "load_extension_mapping",
    "save_extension_mapping",
    "match_taxonomy",
    "CustomRule",
    "ProposedMove",
    "ZeroLooseFilesEngine",
    "scan_directory_space_hogs",
    "DiskItem",
    "find_duplicates",
    "DuplicateGroup",
    "FolderWatchdogService",
    "scan_wifi_networks",
    "get_connected_network_info",
    "WifiNetwork",
]
