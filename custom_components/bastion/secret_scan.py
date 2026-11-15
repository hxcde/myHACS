"""Pattern based detection of credentials in text files.

Pure functions, no Home Assistant imports, so the scanner can be used by the
audit (plain text secrets in YAML) and by the git sync (never push clear text
credentials) alike. Findings never contain the secret value itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

# Key names that usually carry a credential.
_KEY_WORDS = (
    "password",
    "passwd",
    "pwd",
    "token",
    "secret",
    "api_key",
    "apikey",
    "access_key",
    "auth_key",
    "private_key",
    "client_secret",
    "psk",
    "encryption_key",
    "network_key",
    "credentials",
)

_KEY_RE = re.compile(
    r"^(?P<indent>\s*-?\s*)(?P<key>[\"']?[A-Za-z0-9_.\-]*?(?:"
    + "|".join(re.escape(w) for w in _KEY_WORDS)
    + r")[A-Za-z0-9_.\-]*[\"']?)\s*:\s*(?P<value>.*)$",
    re.IGNORECASE,
)

# Values that are clearly not a literal secret.
_SAFE_VALUE_RE = re.compile(
    r"""^(
        !secret\b.*            |   # HA secret reference
        !env_var\b.*           |   # environment variable
        !include\b.*           |   # include
        !input\b.*             |   # blueprint input
        \{\{.*                 |   # template
        \{%.*                  |
        \$\{.*\}               |   # ESPHome substitution
        \$[A-Za-z_][A-Za-z0-9_]*|  # ESPHome substitution short form
        true|false|yes|no|on|off|null|none|~ |
        [\[\{]\s*[\]\}]        |   # empty list / dict
        [|>][-+]?              |   # block scalar marker (value follows)
        ""|''                  |
        \d{1,6}                    # short numbers (ports, lengths, pins in tests)
    )\s*(\#.*)?$""",
    re.IGNORECASE | re.VERBOSE,
)

# Keys that contain one of the key words but never hold a secret.
_SAFE_KEYS = {
    "password_entity",
    "token_entity",
    "show_password",
    "password_required",
    "require_password",
    "pin_entity",
    "pin_required",
    "code_format",
    "secret_file",
    "pass_through",
    "passive",
    "passive_scan",
    "bypass",
    "pinned",
    "pin_mode",
    "spin",
    "spinner",
    "pinout",
    "tokenizer",
    "max_tokens",
    "token_limit",
}

# Well known token formats, matched anywhere in a line.
_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("private_key_block", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("github_token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("github_pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{60,}\b")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{20,}\b")),
    ("aws_access_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("slack_token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b")),
    ("telegram_bot_token", re.compile(r"\b\d{8,10}:[A-Za-z0-9_\-]{35}\b")),
    ("google_api_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}\b")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{32,}\b")),
    ("anthropic_key", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{32,}\b")),
    ("cloudflare_token", re.compile(r"\bcf[a-z]{2}_[A-Za-z0-9]{40,}\b")),
    (
        # Home Assistant long-lived access tokens are JWTs.
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.eyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"),
    ),
    ("url_credentials", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^\s:/@]+:[^\s@/]{3,}@[^\s]+", re.I)),
)

# ESPHome API encryption key: 32 bytes base64 (44 characters ending in "=").
_BARE_KEY_RE = re.compile(r"^\s*-?\s*key\s*:\s*[\"']?[A-Za-z0-9+/]{43}=[\"']?\s*(#.*)?$")

TEXT_EXTENSIONS = {
    ".yaml",
    ".yml",
    ".json",
    ".conf",
    ".cfg",
    ".ini",
    ".txt",
    ".py",
    ".js",
    ".jinja",
    ".j2",
    ".env",
    ".toml",
    ".xml",
    ".sh",
}


@dataclass(frozen=True, slots=True)
class SecretHit:
    """A potential secret. Only location and kind, never the value."""

    line: int
    kind: str
    key: str | None = None


def _clean_key(raw: str) -> str:
    return raw.strip().strip("\"'").lower()


def scan_text(text: str, *, max_hits: int = 50) -> list[SecretHit]:
    """Return potential secrets found in text."""
    hits: list[SecretHit] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if len(hits) >= max_hits:
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        matched = False
        for kind, pattern in _TOKEN_PATTERNS:
            if pattern.search(line):
                hits.append(SecretHit(lineno, kind))
                matched = True
                break
        if matched:
            continue
        if (m := _KEY_RE.match(line)) is None:
            # ESPHome style "key: <base64>" (API encryption key).
            if _BARE_KEY_RE.match(line):
                hits.append(SecretHit(lineno, "encryption_key", "key"))
            continue
        key = _clean_key(m.group("key"))
        leaf = key.rsplit(".", 1)[-1]
        if leaf in _SAFE_KEYS or leaf.endswith("_entity") or leaf.endswith("_id_entity"):
            continue
        value = m.group("value").strip()
        if not value or _SAFE_VALUE_RE.match(value):
            continue
        # A JSON line such as "token": "..." is handled the same way.
        unquoted = value.rstrip(",").strip().strip("\"'")
        if not unquoted or unquoted.lower() in {"true", "false", "null", "none"}:
            continue
        if _SAFE_VALUE_RE.match(unquoted):
            continue
        # Entity ids and service references are not secrets.
        if re.fullmatch(r"[a-z_]+\.[a-z0-9_]+", unquoted):
            continue
        hits.append(SecretHit(lineno, "credential_key", leaf))
    return hits


def scan_bytes(data: bytes, *, max_hits: int = 50) -> list[SecretHit]:
    """Scan raw bytes. Binary data is not scanned."""
    if b"\x00" in data[:8192]:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return scan_text(text, max_hits=max_hits)


def is_text_path(path: str) -> bool:
    """Return True if a file name looks like a text file worth scanning."""
    lower = path.lower()
    return any(lower.endswith(ext) for ext in TEXT_EXTENSIONS)
