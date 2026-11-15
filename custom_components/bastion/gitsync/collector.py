"""Select the files that make up a configuration snapshot.

Synchronous, run in an executor. Pure file system logic so it is easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import os
from pathlib import PurePosixPath
import re

from ..const import (
    AREA_ADDONS,
    AREA_CONFIG,
    AREA_ESPHOME,
    AREA_EXTRA,
    AREA_INVENTORY,
    AREA_STORAGE,
    AREA_Z2M,
    WORK_DIR,
)

MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_CONFIG_FILE_SIZE = 5 * 1024 * 1024
MAX_FILES_PER_AREA = 5000

PREFIX = {
    AREA_CONFIG: "homeassistant/",
    AREA_STORAGE: "homeassistant/.storage/",
    AREA_INVENTORY: "bastion/inventory/",
    AREA_ESPHOME: "esphome/",
    AREA_Z2M: "zigbee2mqtt/",
    AREA_ADDONS: "addons/",
    AREA_EXTRA: "extra/",
}

# Top level prefixes owned by Bastion. Anything else in the repository (for
# example a README written by the user) is carried over untouched.
MANAGED_PREFIXES = ("homeassistant/", "bastion/", "esphome/", "zigbee2mqtt/", "addons/", "extra/")

MANIFEST_PATH = "bastion/manifest.json"
ENC_SUFFIX = ".bastion.enc"

CONFIG_EXCLUDE_DIRS = {
    ".storage",
    WORK_DIR,
    ".cloud",
    ".git",
    ".cache",
    ".esphome",
    ".venv",
    ".vscode",
    "__pycache__",
    "backup",
    "backups",
    "custom_components",
    "deps",
    "esphome",
    "image",
    "logs",
    "media",
    "node_modules",
    "share",
    "ssl",
    "tts",
    "venv",
    "www",
    "zigbee2mqtt",
}
CONFIG_EXTENSIONS = {".yaml", ".yml", ".json", ".jinja", ".j2", ".py", ".txt", ".conf", ".sh"}
CONFIG_EXTRA_FILES = {".HA_VERSION"}
CONFIG_EXCLUDE_FILES = {"known_devices.yaml.bak"}

# Encrypted regardless of what the secret scanner says.
CONFIG_ALWAYS_ENCRYPT = {"secrets.yaml"}

STORAGE_PLAIN_PATTERNS = (
    "core.area_registry",
    "core.category_registry",
    "core.config",
    "core.device_registry",
    "core.entity_registry",
    "core.floor_registry",
    "core.label_registry",
    "lovelace",
    "lovelace.*",
    "lovelace_dashboards",
    "lovelace_resources",
    "input_boolean",
    "input_button",
    "input_datetime",
    "input_number",
    "input_select",
    "input_text",
    "counter",
    "timer",
    "schedule",
    "person",
    "zone",
    "tag",
    "homeassistant.exposed_entities",
    "assist_pipeline.pipelines",
    "energy",
    "http",
    "network",
    "frontend.system_data",
)
STORAGE_ENCRYPTED_PATTERNS = (
    "core.config_entries",
    "application_credentials",
    "backup",
)
# Never leave the instance, not even encrypted.
STORAGE_NEVER = (
    "auth",
    "auth_provider.*",
    "auth_module.*",
    "onboarding",
    "cloud",
    "core.uuid",
    "core.restore_state",
    "mobile_app",
    "bastion.*",
    "hassio",
)

ESPHOME_EXCLUDE_DIRS = {".esphome", ".pioenvs", ".piolibdeps", "build", "__pycache__", ".git"}
ESPHOME_ALWAYS_ENCRYPT = {"secrets.yaml"}

Z2M_FILES = {
    "configuration.yaml",
    "secret.yaml",
    "devices.yaml",
    "groups.yaml",
    "database.db",
    "coordinator_backup.json",
}
Z2M_ALWAYS_ENCRYPT = {"secret.yaml", "coordinator_backup.json"}

EXTRA_EXCLUDE_DIRS = {".git", "__pycache__", "node_modules"}


@dataclass(slots=True)
class SourceFile:
    """A file that becomes part of the snapshot."""

    repo_path: str
    area: str
    abs_path: str | None = None
    data: bytes | None = None
    encrypt: bool = False
    plain: bool = False  # never encrypted automatically (decoy file)

    def read(self) -> bytes:
        """Return the file content."""
        if self.data is not None:
            return self.data
        assert self.abs_path is not None
        with open(self.abs_path, "rb") as fh:
            return fh.read()


@dataclass(slots=True)
class CollectResult:
    """Collected files and problems."""

    files: list[SourceFile] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (path, reason)
    extra_labels: dict[str, str] = field(default_factory=dict)


def _match(name: str, patterns: tuple[str, ...]) -> bool:
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def _walk(base: str, exclude_dirs: set[str], *, top_exclude: set[str] | None = None):
    """Yield (rel_path, abs_path) of regular files, never following symlinks."""
    base = os.path.realpath(base)
    for root, dirs, files in os.walk(base, followlinks=False):
        rel_root = os.path.relpath(root, base)
        depth = 0 if rel_root == "." else rel_root.count(os.sep) + 1
        keep = []
        for d in dirs:
            full = os.path.join(root, d)
            if d in exclude_dirs or os.path.islink(full):
                continue
            if depth == 0 and top_exclude and d in top_exclude:
                continue
            if depth >= 10:
                continue
            keep.append(d)
        dirs[:] = sorted(keep)
        for name in sorted(files):
            full = os.path.join(root, name)
            if os.path.islink(full) or not os.path.isfile(full):
                continue
            rel = name if rel_root == "." else os.path.join(rel_root, name)
            yield rel.replace(os.sep, "/"), full


def collect_config(config_dir: str, result: CollectResult) -> None:
    """YAML and other text configuration below the HA config directory."""
    count = 0
    for rel, full in _walk(config_dir, {"__pycache__", ".git"}, top_exclude=CONFIG_EXCLUDE_DIRS):
        name = rel.rsplit("/", 1)[-1]
        ext = os.path.splitext(name)[1].lower()
        if name in CONFIG_EXCLUDE_FILES:
            continue
        if ext not in CONFIG_EXTENSIONS and rel not in CONFIG_EXTRA_FILES:
            continue
        if name.startswith("home-assistant.log") or name.endswith((".db", ".db-shm", ".db-wal")):
            continue
        if os.path.getsize(full) > MAX_CONFIG_FILE_SIZE:
            result.skipped.append((rel, "too_large"))
            continue
        count += 1
        if count > MAX_FILES_PER_AREA:
            result.skipped.append((rel, "too_many_files"))
            break
        result.files.append(
            SourceFile(
                repo_path=PREFIX[AREA_CONFIG] + rel,
                area=AREA_CONFIG,
                abs_path=full,
                encrypt=rel in CONFIG_ALWAYS_ENCRYPT,
            )
        )


def collect_storage(config_dir: str, result: CollectResult, extra_patterns: tuple[str, ...] = ()) -> None:
    """Selected UI configuration from .storage."""
    storage_dir = os.path.join(config_dir, ".storage")
    if not os.path.isdir(storage_dir):
        return
    for name in sorted(os.listdir(storage_dir)):
        full = os.path.join(storage_dir, name)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        if name.endswith((".tmp", ".bak")) or _match(name, STORAGE_NEVER):
            continue
        encrypt = _match(name, STORAGE_ENCRYPTED_PATTERNS)
        if not encrypt and not _match(name, STORAGE_PLAIN_PATTERNS + extra_patterns):
            continue
        if os.path.getsize(full) > MAX_FILE_SIZE:
            result.skipped.append((".storage/" + name, "too_large"))
            continue
        result.files.append(
            SourceFile(
                repo_path=PREFIX[AREA_STORAGE] + name,
                area=AREA_STORAGE,
                abs_path=full,
                encrypt=encrypt,
            )
        )


def collect_esphome(path: str, result: CollectResult) -> None:
    """ESPHome device configurations."""
    if not path or not os.path.isdir(path):
        return
    for rel, full in _walk(path, ESPHOME_EXCLUDE_DIRS):
        if not rel.lower().endswith((".yaml", ".yml")):
            continue
        if os.path.getsize(full) > MAX_CONFIG_FILE_SIZE:
            result.skipped.append(("esphome/" + rel, "too_large"))
            continue
        result.files.append(
            SourceFile(
                repo_path=PREFIX[AREA_ESPHOME] + rel,
                area=AREA_ESPHOME,
                abs_path=full,
                encrypt=rel.rsplit("/", 1)[-1] in ESPHOME_ALWAYS_ENCRYPT,
            )
        )


def collect_z2m(path: str, result: CollectResult) -> None:
    """Zigbee2MQTT data directory."""
    if not path or not os.path.isdir(path):
        return
    for name in sorted(os.listdir(path)):
        full = os.path.join(path, name)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        if name not in Z2M_FILES and not name.lower().endswith((".yaml", ".yml")):
            continue
        if os.path.getsize(full) > MAX_FILE_SIZE:
            result.skipped.append(("zigbee2mqtt/" + name, "too_large"))
            continue
        result.files.append(
            SourceFile(
                repo_path=PREFIX[AREA_Z2M] + name,
                area=AREA_Z2M,
                abs_path=full,
                encrypt=name in Z2M_ALWAYS_ENCRYPT,
            )
        )


def extra_label(path: str, used: set[str]) -> str:
    """Stable, filesystem safe label for an extra path."""
    base = re.sub(r"[^A-Za-z0-9._\-]", "_", PurePosixPath(path.rstrip("/")).name or "root")
    label = base
    i = 2
    while label in used:
        label = f"{base}_{i}"
        i += 1
    used.add(label)
    return label


def collect_extra(paths: list[str], result: CollectResult) -> None:
    """Additional user defined files or directories."""
    used: set[str] = set()
    for raw in paths:
        path = raw.strip()
        if not path:
            continue
        label = extra_label(path, used)
        result.extra_labels[label] = path
        if os.path.isfile(path) and not os.path.islink(path):
            if os.path.getsize(path) > MAX_FILE_SIZE:
                result.skipped.append((path, "too_large"))
                continue
            result.files.append(
                SourceFile(
                    repo_path=f"{PREFIX[AREA_EXTRA]}{label}/{os.path.basename(path)}",
                    area=AREA_EXTRA,
                    abs_path=path,
                )
            )
            continue
        if not os.path.isdir(path):
            result.skipped.append((path, "not_found"))
            continue
        count = 0
        for rel, full in _walk(path, EXTRA_EXCLUDE_DIRS):
            if os.path.getsize(full) > MAX_FILE_SIZE:
                result.skipped.append((f"{path}/{rel}", "too_large"))
                continue
            count += 1
            if count > MAX_FILES_PER_AREA:
                result.skipped.append((path, "too_many_files"))
                break
            result.files.append(
                SourceFile(
                    repo_path=f"{PREFIX[AREA_EXTRA]}{label}/{rel}",
                    area=AREA_EXTRA,
                    abs_path=full,
                )
            )


def collect(
    config_dir: str,
    areas: list[str],
    *,
    esphome_path: str = "",
    z2m_path: str = "",
    extra_paths: list[str] | None = None,
    generated: list[SourceFile] | None = None,
) -> CollectResult:
    """Collect all files of the enabled areas."""
    result = CollectResult()
    if AREA_CONFIG in areas:
        collect_config(config_dir, result)
    if AREA_STORAGE in areas:
        collect_storage(config_dir, result)
    if AREA_ESPHOME in areas:
        collect_esphome(esphome_path or os.path.join(config_dir, "esphome"), result)
    if AREA_Z2M in areas:
        collect_z2m(z2m_path or os.path.join(config_dir, "zigbee2mqtt"), result)
    if AREA_EXTRA in areas and extra_paths:
        collect_extra(extra_paths, result)
    for item in generated or []:
        if item.area in areas:
            result.files.append(item)
    return result


def area_of(repo_path: str) -> str | None:
    """Area a repository path belongs to."""
    path = repo_path.removesuffix(ENC_SUFFIX)
    if path.startswith(PREFIX[AREA_STORAGE]):
        return AREA_STORAGE
    for area in (AREA_CONFIG, AREA_INVENTORY, AREA_ESPHOME, AREA_Z2M, AREA_ADDONS, AREA_EXTRA):
        if path.startswith(PREFIX[area]):
            return area
    return None


def is_safe_relative(path: str) -> bool:
    """Reject absolute paths and any traversal in repository paths."""
    if not path or path.startswith("/") or "\\" in path or "\x00" in path:
        return False
    parts = path.split("/")
    return all(p not in ("", ".", "..") for p in parts)


def resolve_target(base: str, rel: str) -> str | None:
    """Join base and rel and make sure the result stays inside base."""
    if not is_safe_relative(rel):
        return None
    base_real = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_real, rel))
    if os.path.commonpath([base_real, target]) != base_real or target == base_real:
        return None
    return target
