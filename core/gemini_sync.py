"""Gemini AI Knowledge Sync: The Brain & Self-Learning Caching System.
Batches unrecognized filenames from Pass 1.5, asks Gemini (default: gemini-3.8-flash, thinking
level "medium") to propose a category + keyword stem for each, lets the user review the
proposals, and appends the approved keywords to learned_rules.json with thread-safe locking.

Transport: the Gemini REST API (v1beta) via the standard library. This is the exact wire format
the official google-genai SDK produces, it has no third-party dependencies, and it is the code path
the bundled PyInstaller .exe runs.
"""

import os
import json
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import unicodedata
import threading
from typing import Callable, Dict, List, Tuple, Optional, Any
from datetime import datetime

from config import (
    TAXONOMY_FILE,
    LEARNED_RULES_FILE,
    UNRECOGNIZED_LOG_FILE,
    SETTINGS_FILE,
    EXTENSION_MAPPING_FILE,
    DEFAULT_TAXONOMY,
    DEFAULT_EXTENSION_MAPPING,
    DEFAULT_GEMINI_MODEL,
    DEFAULT_THINKING_LEVEL,
    FALLBACK_GEMINI_MODEL,
    THINKING_LEVELS
)

# Global thread lock for learned_rules.json and unrecognized_files.json
_cache_lock = threading.Lock()
_unrecognized_lock = threading.Lock()
_settings_lock = threading.Lock()


def normalize_keyword(val: str) -> str:
    """Case-insensitive and unaccented string normalization."""
    decomposed = unicodedata.normalize("NFKD", val.strip().casefold())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


# ---------------------------------------------------------------------------
# Unrecognized Files Batch Logging (Offline Queue)
# ---------------------------------------------------------------------------

def log_unrecognized_file(filename: str, source_path: str = "", category_hint: str = ""):
    """Quietly log an unrecognized file that fell through Pass 1.5.
    Thread-safe and avoids duplicates.
    """
    clean_name = os.path.basename(filename).strip()
    if not clean_name:
        return

    with _unrecognized_lock:
        items = load_unrecognized_files()
        existing_names = {item["filename"].casefold() for item in items}

        if clean_name.casefold() not in existing_names:
            items.append({
                "filename": clean_name,
                "source_path": source_path,
                "category_hint": category_hint,
                "timestamp": datetime.now().isoformat()
            })
            save_unrecognized_files(items)


def load_unrecognized_files() -> List[Dict[str, Any]]:
    """Load pending unrecognized files from disk."""
    if not UNRECOGNIZED_LOG_FILE.exists():
        return []
    try:
        with open(UNRECOGNIZED_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def save_unrecognized_files(items: List[Dict[str, Any]]):
    """Save pending unrecognized files list to disk."""
    try:
        with open(UNRECOGNIZED_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving unrecognized files log: {e}")


def clear_unrecognized_files(processed_filenames: Optional[List[str]] = None):
    """Remove processed items or clear the entire queue."""
    with _unrecognized_lock:
        if processed_filenames is None:
            save_unrecognized_files([])
            return

        processed_set = {f.casefold() for f in processed_filenames}
        current = load_unrecognized_files()
        remaining = [item for item in current if item["filename"].casefold() not in processed_set]
        save_unrecognized_files(remaining)


# ---------------------------------------------------------------------------
# Learned Rules JSON Cache (Self-Learning Dictionary)
# ---------------------------------------------------------------------------

def load_learned_rules() -> Dict[str, List[str]]:
    """Load AI-learned rules dictionary. Thread-safe."""
    with _cache_lock:
        if not LEARNED_RULES_FILE.exists():
            initial = {cat: [] for cat in DEFAULT_TAXONOMY.keys()}
            try:
                with open(LEARNED_RULES_FILE, "w", encoding="utf-8") as f:
                    json.dump(initial, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
            return initial

        try:
            with open(LEARNED_RULES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return {
                        str(cat): [str(k) for k in kws if str(k).strip()]
                        for cat, kws in data.items()
                        if isinstance(kws, list)
                    }
        except Exception:
            pass
        return {cat: [] for cat in DEFAULT_TAXONOMY.keys()}


def save_learned_rules(rules: Dict[str, List[str]]):
    """Persist AI-learned rules dictionary to disk. Thread-safe."""
    with _cache_lock:
        try:
            with open(LEARNED_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(rules, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving learned rules: {e}")


def append_learned_keywords(new_mappings: Dict[str, List[str]]) -> Dict[str, List[str]]:
    """Thread-safely append new keywords to learned_rules.json, guaranteeing no duplicates.
    Checks against existing learned keywords AND static semantic rules.
    Returns the dictionary of newly added keywords per category.
    """
    with _cache_lock:
        # Load existing learned rules
        learned = {}
        if LEARNED_RULES_FILE.exists():
            try:
                with open(LEARNED_RULES_FILE, "r", encoding="utf-8") as f:
                    learned = json.load(f)
            except Exception:
                learned = {}

        if not isinstance(learned, dict):
            learned = {}

        # Load static rules to avoid duplicating words already in static rules
        static_rules = {}
        if TAXONOMY_FILE.exists():
            try:
                with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
                    static_rules = json.load(f)
            except Exception:
                static_rules = {}
        if not isinstance(static_rules, dict):
            static_rules = DEFAULT_TAXONOMY

        # Build existing normalized set for fast comparison
        existing_normalized = set()
        for cat, kws in static_rules.items():
            for kw in kws:
                existing_normalized.add(normalize_keyword(kw))
        for cat, kws in learned.items():
            for kw in kws:
                existing_normalized.add(normalize_keyword(kw))

        added_summary: Dict[str, List[str]] = {}

        for category, keywords in new_mappings.items():
            if category not in learned:
                learned[category] = []
            if category not in added_summary:
                added_summary[category] = []

            for kw in keywords:
                clean_kw = kw.strip()
                if not clean_kw:
                    continue
                norm = normalize_keyword(clean_kw)
                if norm not in existing_normalized:
                    learned[category].append(clean_kw)
                    existing_normalized.add(norm)
                    added_summary[category].append(clean_kw)

        # Write back to disk
        try:
            with open(LEARNED_RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(learned, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Failed to write learned rules: {e}")

        return added_summary


# ---------------------------------------------------------------------------
# Settings (API Key, Model, Thinking Level, Privacy Shield, cached model list)
# ---------------------------------------------------------------------------

def _read_settings() -> Dict[str, Any]:
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def _write_setting(key: str, value: Any):
    with _settings_lock:
        settings = _read_settings()
        settings[key] = value
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            print(f"Error saving setting '{key}': {e}")


def get_gemini_api_key() -> str:
    """Retrieve Gemini API key from environment or settings file."""
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key
    return str(_read_settings().get("gemini_api_key", "")).strip()


def set_gemini_api_key(api_key: str):
    """Save Gemini API key to settings file."""
    _write_setting("gemini_api_key", api_key.strip())


def get_gemini_model() -> str:
    """Retrieve configured Gemini model name, defaulting to gemini-3.8-flash."""
    env_model = os.environ.get("GEMINI_MODEL", "").strip()
    if env_model:
        return env_model
    return str(_read_settings().get("gemini_model", "")).strip() or DEFAULT_GEMINI_MODEL


def set_gemini_model(model_name: str):
    """Save selected Gemini model name to settings file."""
    _write_setting("gemini_model", model_name.strip())


def normalize_thinking_level(tier: Optional[str]) -> str:
    """Map any stored/legacy tier to one Gemini 3.x accepts (low | medium | high).
    Gemini 3.x models cannot switch thinking off and gemini-3.8-flash rejects "minimal",
    so the legacy "off" setting maps to "low", the cheapest accepted level.
    """
    t = (tier or "").strip().lower()
    if t in THINKING_LEVELS:
        return t
    if t in ("off", "none", "minimal", "disabled"):
        return "low"
    return DEFAULT_THINKING_LEVEL


def get_thinking_tier() -> str:
    """Retrieve configured thinking level (low | medium | high)."""
    env_tier = os.environ.get("GEMINI_THINKING_TIER", "").strip()
    raw = env_tier or str(_read_settings().get("thinking_tier", "")).strip()
    return normalize_thinking_level(raw)


def set_thinking_tier(tier: str):
    """Save thinking level to settings file."""
    _write_setting("thinking_tier", normalize_thinking_level(tier))


def get_privacy_shield() -> bool:
    """Whether personal data is masked out of filenames before they are sent to Gemini (default ON)."""
    return bool(_read_settings().get("privacy_shield", True))


def set_privacy_shield(enabled: bool):
    _write_setting("privacy_shield", bool(enabled))


def get_cached_model_list() -> List[str]:
    """Model IDs last fetched live from the API (empty until the user fetches once)."""
    models = _read_settings().get("available_models", [])
    return [str(m) for m in models] if isinstance(models, list) else []


def set_cached_model_list(models: List[str]):
    _write_setting("available_models", list(models))


# ---------------------------------------------------------------------------
# Gemini REST Client (retries, thinking level, schema enforcement, model fallback)
# ---------------------------------------------------------------------------

API_BASE = "https://generativelanguage.googleapis.com/v1beta"
RETRYABLE_STATUS = {0, 429, 500, 502, 503, 504}   # 0 = network error / timeout
MAX_RETRIES = 3
SYNC_BATCH_SIZE = 40


class GeminiAPIError(RuntimeError):
    """Normalized API failure carrying the HTTP status (0 for network errors)."""

    def __init__(self, status: int, message: str, model: str = ""):
        super().__init__(message)
        self.status = status
        self.api_message = message
        self.model = model

    def __str__(self) -> str:
        if self.status:
            where = f" on model '{self.model}'" if self.model else ""
            return f"Gemini API HTTP Error {self.status}{where}: {self.api_message}"
        return f"Gemini API error: {self.api_message}"


def _http_json(method: str, url: str, api_key: str, body: Optional[dict] = None, timeout: int = 60) -> dict:
    """Send a JSON request. The key travels in the x-goog-api-key header, never in the URL,
    so it cannot leak into proxy logs or error messages."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        raw = he.read().decode("utf-8", errors="replace")
        try:
            msg = json.loads(raw).get("error", {}).get("message", raw)
        except Exception:
            msg = raw
        raise GeminiAPIError(he.code, str(msg).strip()) from None
    except urllib.error.URLError as ue:
        raise GeminiAPIError(0, f"Network error: {ue.reason}") from None
    except TimeoutError:
        raise GeminiAPIError(0, f"Request timed out after {timeout}s.") from None


def _extract_text(resp: dict, model: str) -> str:
    candidates = resp.get("candidates") or []
    if not candidates:
        reason = (resp.get("promptFeedback") or {}).get("blockReason")
        raise GeminiAPIError(0, "No response returned" + (f" (blocked: {reason})." if reason else "."), model)
    parts = (candidates[0].get("content") or {}).get("parts") or []
    # Gemini 3.x may interleave thought parts; only the answer text is JSON.
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    if not text.strip():
        finish = candidates[0].get("finishReason", "unknown")
        raise GeminiAPIError(0, f"Empty response from model (finishReason={finish}).", model)
    return text


def _generate_json(
    api_key: str,
    model: str,
    prompt: str,
    thinking_level: str,
    response_schema: Optional[dict],
    status_callback: Optional[Callable[[str], None]] = None
) -> str:
    """One generateContent call with:
    - thinkingConfig.thinkingLevel (Gemini 3.x); dropped automatically if a model rejects it
    - responseSchema (category enum) for guaranteed-valid JSON; dropped if a model rejects it
    - exponential backoff on 429 / 5xx / network errors
    """
    use_thinking = True
    use_schema = response_schema is not None
    attempt = 0
    url = f"{API_BASE}/models/{urllib.parse.quote(model)}:generateContent"

    while True:
        gen_config: Dict[str, Any] = {"responseMimeType": "application/json"}
        if use_thinking:
            gen_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
        if use_schema:
            gen_config["responseSchema"] = response_schema
        body = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config
        }
        try:
            resp = _http_json("POST", url, api_key, body, timeout=120)
        except GeminiAPIError as e:
            e.model = model
            msg = e.api_message.lower()
            if e.status == 400 and use_thinking and "thinking" in msg:
                use_thinking = False      # e.g. older 2.x model without thinkingLevel support
                continue
            if e.status == 400 and use_schema and "schema" in msg:
                use_schema = False
                continue
            # Overload/rate limits are retried up to MAX_RETRIES; network errors/timeouts only once,
            # since each timeout already cost up to 120s.
            retry_limit = 1 if e.status == 0 else MAX_RETRIES
            if e.status in RETRYABLE_STATUS and attempt < retry_limit:
                delay = 2 * (2 ** attempt)   # 2s, 4s, 8s
                attempt += 1
                if status_callback:
                    reason = f"HTTP {e.status}" if e.status else "network error"
                    status_callback(f"{model} is busy ({reason}); retry {attempt}/{retry_limit} in {delay}s...")
                time.sleep(delay)
                continue
            raise
        return _extract_text(resp, model)


def _generate_with_fallback(
    api_key: str,
    model: str,
    prompt: str,
    thinking_level: str,
    response_schema: Optional[dict],
    status_callback: Optional[Callable[[str], None]] = None
) -> Tuple[str, str]:
    """Call `model`; if Google reports it does not exist (404, e.g. a retired model ID),
    retry once on the always-current alias. Returns (text, model_actually_used)."""
    try:
        return _generate_json(api_key, model, prompt, thinking_level, response_schema, status_callback), model
    except GeminiAPIError as e:
        if e.status == 404 and model != FALLBACK_GEMINI_MODEL:
            if status_callback:
                status_callback(f"'{model}' is not available; falling back to '{FALLBACK_GEMINI_MODEL}'...")
            text = _generate_json(api_key, FALLBACK_GEMINI_MODEL, prompt, thinking_level, response_schema, status_callback)
            return text, FALLBACK_GEMINI_MODEL
        raise


# ---------------------------------------------------------------------------
# Live Model Discovery
# ---------------------------------------------------------------------------

_NON_TEXT_MODEL_MARKERS = (
    "tts", "image", "robotics", "computer-use", "customtools", "transcribe",
    "embedding", "aqa", "native-audio", "live", "nano-banana"
)


def _model_sort_key(name: str):
    m = re.match(r"gemini-(\d+(?:\.\d+)?)", name)
    version = float(m.group(1)) if m else 0.0
    is_flash = "flash" in name and "lite" not in name
    return (0 if name.endswith("-latest") else 1, -version, 0 if is_flash else 1, "preview" in name, name)


def list_available_models(api_key: str) -> List[str]:
    """Ask the API which text models this key can call with generateContent, newest first."""
    if not api_key:
        raise ValueError("An API key is required to list models.")
    found: List[str] = []
    page_token = ""
    while True:
        url = f"{API_BASE}/models?pageSize=200"
        if page_token:
            url += f"&pageToken={urllib.parse.quote(page_token)}"
        data = _http_json("GET", url, api_key, timeout=20)
        for m in data.get("models", []):
            name = str(m.get("name", "")).removeprefix("models/")
            if "generateContent" not in m.get("supportedGenerationMethods", []):
                continue
            if not name.startswith("gemini-") or any(x in name for x in _NON_TEXT_MODEL_MARKERS):
                continue
            found.append(name)
        page_token = data.get("nextPageToken", "")
        if not page_token:
            break
    return sorted(set(found), key=_model_sort_key)


# ---------------------------------------------------------------------------
# Privacy Shield & Keyword Quality Guard
# ---------------------------------------------------------------------------

# "_" is excluded from both sides: in filenames it is a word separator, not part of an address.
_EMAIL_RE = re.compile(r"[A-Za-z0-9.+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,24}(?![A-Za-z])")
_NUMBER_RUN_RE = re.compile(r"\+?\d[\d ()._-]*\d")
_MIN_DIGITS_TO_MASK = 6


def redact_filename(filename: str) -> str:
    """Mask personal data before a filename leaves the machine:
    emails -> [email]; digit runs with >= 6 digits (account / passport / phone / ID numbers,
    full timestamps) -> [number]. Short numbers such as years or course codes are kept,
    since they carry category meaning (e.g. 'Server 2022', 'IT335')."""
    stem, ext = os.path.splitext(filename)   # the extension is never masked
    out = _EMAIL_RE.sub("[email]", stem)

    def _mask(m: re.Match) -> str:
        digits = sum(c.isdigit() for c in m.group())
        return "[number]" if digits >= _MIN_DIGITS_TO_MASK else m.group()

    return _NUMBER_RUN_RE.sub(_mask, out) + ext


_GENERIC_KEYWORDS = {
    # English filler
    "file", "files", "doc", "docs", "document", "documents", "new", "old", "copy", "final",
    "draft", "scan", "scanned", "img", "image", "images", "photo", "photos", "pic", "download",
    "downloads", "untitled", "temp", "tmp", "test", "version", "misc", "other", "data", "backup",
    "the", "and", "for", "with", "from", "page", "part", "report", "notes", "screenshot", "edited",
    # French filler
    "fichier", "fichiers", "nouveau", "nouvelle", "copie", "les", "des", "une", "pour", "avec", "sans",
}


def _keyword_extension_set() -> set:
    exts = set()
    try:
        if EXTENSION_MAPPING_FILE.exists():
            with open(EXTENSION_MAPPING_FILE, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        else:
            mapping = DEFAULT_EXTENSION_MAPPING
        for values in mapping.values():
            exts.update(str(v).lower().lstrip(".") for v in values)
    except Exception:
        pass
    return exts


def keyword_issue(keyword: str, original_filename: str, extension_set: Optional[set] = None) -> str:
    """Return why a proposed keyword would make a bad rule ('' if it is fine).
    A learned keyword is applied to EVERY future file, so a generic stem like 'pdf' or 'new'
    would hijack sorting. It must also occur in its own filename under the same word-boundary
    matching Pass 1.5 uses, otherwise the rule would never fire."""
    kw = normalize_keyword(keyword)
    if not kw:
        return "empty keyword"
    if "[" in kw or "]" in kw:
        return "privacy placeholder, not a real word"
    if len(kw) < 3:
        return "too short (matches too many files)"
    if re.fullmatch(r"[\d\W_]+", kw):
        return "only numbers/symbols"
    if kw in _GENERIC_KEYWORDS:
        return "too generic"
    exts = extension_set if extension_set is not None else _keyword_extension_set()
    if kw.lstrip(".") in exts:
        return "file extension (use Extension Mapping instead)"
    fname = normalize_keyword(original_filename)
    parts = [re.escape(p) for p in re.split(r"[\s\-_.]+", kw) if p]
    pattern = r"(?<![a-z0-9])" + r"[\s\-_.]+".join(parts) + r"(?![a-z0-9])"
    if not re.search(pattern, fname):
        return "does not appear as a whole word in the filename"
    return ""


# ---------------------------------------------------------------------------
# Knowledge Sync: fetch suggestions -> user review -> apply
# ---------------------------------------------------------------------------

def load_sync_categories() -> List[str]:
    """Categories Gemini is allowed to choose from (semantic_rules.json keys)."""
    if TAXONOMY_FILE.exists():
        try:
            with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
                tax = json.load(f)
                if isinstance(tax, dict) and tax:
                    return list(tax.keys())
        except Exception:
            pass
    return list(DEFAULT_TAXONOMY.keys())


def build_sync_payload(filenames: List[str], privacy_shield: bool) -> List[Dict[str, Any]]:
    """Exactly what is sent to Gemini for each file: a numeric id and the (optionally masked) name."""
    return [
        {"id": i, "name": redact_filename(name) if privacy_shield else name}
        for i, name in enumerate(filenames)
    ]


def _build_response_schema(categories: List[str]) -> dict:
    return {
        "type": "ARRAY",
        "items": {
            "type": "OBJECT",
            "properties": {
                "id": {"type": "INTEGER"},
                "category": {"type": "STRING", "enum": categories},
                "keyword": {"type": "STRING"},
                "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
                "reasoning": {"type": "STRING"}
            },
            "required": ["id", "category", "keyword", "confidence", "reasoning"]
        }
    }


def _build_prompt(payload: List[Dict[str, Any]], categories: List[str]) -> str:
    return f"""You are the categorization engine of a desktop file organizer.
For EACH file below, choose exactly one category from VALID CATEGORIES and extract ONE keyword
that justifies the choice and will be reused as an offline matching rule for future files.

Keyword rules:
- It MUST appear in the filename as a whole word (between separators such as space, _, -, .).
- Lowercase, unaccented, at least 3 characters.
- Specific and meaningful (a product, tool, topic, institution or document type such as
  'aws', 'wireshark', 'invoice', 'homework'), never generic filler ('file', 'new', 'final',
  'copy', 'scan', 'document'), a number, a file extension, or a bracketed placeholder.
- If no good keyword exists, still answer, and set confidence to "low".

Text such as [email] or [number] marks personal data that was masked for privacy; ignore it.

VALID CATEGORIES:
{json.dumps(categories, indent=2, ensure_ascii=False)}

FILES (use the same "id" in your answer):
{json.dumps(payload, indent=2, ensure_ascii=False)}

Return a JSON array with one object per file:
[{{"id": 0, "category": "...", "keyword": "...", "confidence": "high|medium|low", "reasoning": "one short sentence"}}]
"""


def _parse_json_response(text_json: str) -> List[Dict[str, Any]]:
    """Clean markdown code blocks and parse structured JSON response."""
    text_json = text_json.strip()
    if text_json.startswith("```json"):
        text_json = text_json[7:]
    if text_json.startswith("```"):
        text_json = text_json[3:]
    if text_json.endswith("```"):
        text_json = text_json[:-3]
    text_json = text_json.strip()

    try:
        parsed = json.loads(text_json)
        if isinstance(parsed, list):
            return [p for p in parsed if isinstance(p, dict)]
        if isinstance(parsed, dict) and isinstance(parsed.get("files"), list):
            return [p for p in parsed["files"] if isinstance(p, dict)]
        if isinstance(parsed, dict):
            return [parsed]
    except Exception:
        pass
    return []


def fetch_suggestions(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    thinking_tier: Optional[str] = None,
    privacy_shield: Optional[bool] = None,
    filenames: Optional[List[str]] = None,
    status_callback: Optional[Callable[[str], None]] = None
) -> Tuple[List[Dict[str, Any]], str]:
    """Ask Gemini for a category + keyword per queued file, in batches. Nothing is written to disk.

    Returns (suggestions, model_actually_used). Each suggestion:
      filename, sent_as, category, keyword, confidence, reasoning,
      issue  ('' or why the keyword would be a bad rule),
      accept (default selection for the review step: no issue and confidence != low).
    Files the model skipped are simply absent, so they stay in the queue.
    """
    key = (api_key or get_gemini_api_key()).strip()
    if not key:
        raise ValueError("Missing Gemini API key. Please configure your API key in the Gemini Sync tab.")

    if filenames is None:
        filenames = [item["filename"] for item in load_unrecognized_files()]
    if not filenames:
        return [], (model_name or get_gemini_model())

    model = (model_name or get_gemini_model()).strip() or DEFAULT_GEMINI_MODEL
    level = normalize_thinking_level(thinking_tier or get_thinking_tier())
    shield = get_privacy_shield() if privacy_shield is None else privacy_shield
    categories = load_sync_categories()
    schema = _build_response_schema(categories)
    ext_set = _keyword_extension_set()

    suggestions: List[Dict[str, Any]] = []
    batches = [filenames[i:i + SYNC_BATCH_SIZE] for i in range(0, len(filenames), SYNC_BATCH_SIZE)]

    for b_idx, chunk in enumerate(batches, start=1):
        if status_callback:
            status_callback(f"Batch {b_idx}/{len(batches)}: asking {model} (thinking: {level}) about {len(chunk)} files...")
        payload = build_sync_payload(chunk, shield)
        text, model = _generate_with_fallback(key, model, _build_prompt(payload, categories), level, schema, status_callback)

        seen_ids = set()
        for row in _parse_json_response(text):
            try:
                idx = int(row.get("id"))
            except (TypeError, ValueError):
                continue
            if idx < 0 or idx >= len(chunk) or idx in seen_ids:
                continue
            seen_ids.add(idx)

            original = chunk[idx]
            category = str(row.get("category", "")).strip()
            keyword = normalize_keyword(str(row.get("keyword", "")))
            confidence = str(row.get("confidence", "low")).strip().lower()
            if confidence not in ("high", "medium", "low"):
                confidence = "low"

            issue = "unknown category" if category not in categories else keyword_issue(keyword, original, ext_set)
            suggestions.append({
                "filename": original,
                "sent_as": payload[idx]["name"],
                "category": category if category in categories else categories[0],
                "keyword": keyword,
                "confidence": confidence,
                "reasoning": str(row.get("reasoning", "")).strip(),
                "issue": issue,
                "accept": not issue and confidence != "low",
            })

    return suggestions, model


def apply_suggestions(accepted: List[Dict[str, Any]], reviewed_filenames: List[str]) -> Dict[str, List[str]]:
    """Persist approved keywords and remove every reviewed file from the queue
    (approved or rejected: the user has made a decision on them)."""
    mappings: Dict[str, List[str]] = {}
    for s in accepted:
        cat = str(s.get("category", "")).strip()
        kw = str(s.get("keyword", "")).strip()
        if cat and kw:
            mappings.setdefault(cat, []).append(kw)
    added = append_learned_keywords(mappings) if mappings else {}
    clear_unrecognized_files(reviewed_filenames)
    return added


def sync_knowledge_base(
    api_key: Optional[str] = None,
    model_name: Optional[str] = None,
    thinking_tier: Optional[str] = None
) -> Tuple[int, Dict[str, List[str]], str]:
    """Non-interactive sync (no review step): learns every suggestion that passes the quality
    guard with high/medium confidence. Returns (num_files_synced, added_keywords, summary)."""
    suggestions, used_model = fetch_suggestions(api_key, model_name, thinking_tier)
    if not suggestions:
        return 0, {}, "No unrecognized files pending in the batch queue."

    added = apply_suggestions(
        [s for s in suggestions if s["accept"]],
        [s["filename"] for s in suggestions]
    )
    total_new = sum(len(k) for k in added.values())
    summary = (
        f"Successfully synchronized {len(suggestions)} files with {used_model}. "
        f"Learned {total_new} new keywords cached into learned_rules.json."
    )
    return len(suggestions), added, summary


def test_connection(api_key: str, model_name: str, thinking_tier: str) -> Tuple[bool, str]:
    """Run one real classification end to end, without touching the queue or learned rules."""
    try:
        suggestions, used = fetch_suggestions(
            api_key=api_key,
            model_name=model_name,
            thinking_tier=thinking_tier,
            privacy_shield=True,
            filenames=["AWS_Invoice_2026.pdf"]
        )
    except Exception as e:
        return False, str(e)
    if not suggestions:
        return False, f"{used} responded but returned no usable structured data."
    s = suggestions[0]
    note = f" (requested '{model_name}' was not found, so the alias was used)" if used != model_name else ""
    return True, (
        f"Connection successful! {used} is active{note}.\n\n"
        f"Sample: AWS_Invoice_2026.pdf → {s['category']} • keyword '{s['keyword']}' ({s['confidence']} confidence)"
    )
