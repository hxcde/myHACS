"""Constants for Bastion."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "bastion"
NAME: Final = "Bastion"

PANEL_URL: Final = "bastion"
PANEL_COMPONENT: Final = "bastion-panel"
PANEL_STATIC_URL: Final = "/bastion_static"

STORAGE_VERSION: Final = 1
STORAGE_KEY_DATA: Final = f"{DOMAIN}.data"
STORAGE_KEY_LOGINS: Final = f"{DOMAIN}.logins"
STORAGE_KEY_GIT: Final = f"{DOMAIN}.git"
STORAGE_KEY_ANOMALY: Final = f"{DOMAIN}.anomaly"

# Directory (relative to the HA config dir) that holds local state such as
# the local git object store and staged restores. Excluded from every scan.
WORK_DIR: Final = ".bastion"

EVENT_FINDING: Final = f"{DOMAIN}_finding"
EVENT_SECURITY: Final = f"{DOMAIN}_security_event"
EVENT_ANOMALY: Final = f"{DOMAIN}_anomaly"

SIGNAL_UPDATE: Final = f"{DOMAIN}_update"


class Severity(StrEnum):
    """Finding severity."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


SEVERITY_ORDER: Final = {
    Severity.CRITICAL: 4,
    Severity.HIGH: 3,
    Severity.MEDIUM: 2,
    Severity.LOW: 1,
    Severity.INFO: 0,
}

SEVERITY_WEIGHT: Final = {
    Severity.CRITICAL: 25,
    Severity.HIGH: 10,
    Severity.MEDIUM: 4,
    Severity.LOW: 1,
    Severity.INFO: 0,
}


class Category(StrEnum):
    """Finding category."""

    ACCESS = "access"
    EXPOSURE = "exposure"
    UPDATES = "updates"
    SUPPLY_CHAIN = "supply_chain"
    CONFIG = "config"
    GIT = "git"
    ANOMALY = "anomaly"


# ---------------------------------------------------------------- options keys
CONF_AUDIT_INTERVAL: Final = "audit_interval_hours"
CONF_REPAIRS_MIN_SEVERITY: Final = "repairs_min_severity"
CONF_MAX_ADMINS: Final = "max_admins"
CONF_TOKEN_MAX_AGE_DAYS: Final = "token_max_age_days"
CONF_TOKEN_UNUSED_DAYS: Final = "token_unused_days"
CONF_GITHUB_TOKEN: Final = "github_token"
CONF_DISABLED_CHECKS: Final = "disabled_checks"

CONF_NOTIFY_TARGETS: Final = "notify_targets"
CONF_NOTIFY_MIN_SEVERITY: Final = "notify_min_severity"
CONF_NOTIFY_LOGINS: Final = "notify_logins"
CONF_NOTIFY_PUBLIC_ONLY: Final = "notify_public_ip_only"
CONF_GEOIP: Final = "geoip_lookup"
CONF_BRUTE_FORCE_THRESHOLD: Final = "brute_force_threshold"

CONF_GIT_ENABLED: Final = "git_enabled"
CONF_GIT_URL: Final = "git_url"
CONF_GIT_BRANCH: Final = "git_branch"
CONF_GIT_AUTH: Final = "git_auth"
CONF_GIT_USERNAME: Final = "git_username"
CONF_GIT_TOKEN: Final = "git_token"
CONF_GIT_PRIVATE_KEY: Final = "git_private_key"
CONF_GIT_PUBLIC_KEY: Final = "git_public_key"
CONF_GIT_HOST_KEY: Final = "git_host_key"
CONF_GIT_PASSPHRASE: Final = "git_passphrase"
CONF_GIT_SALT: Final = "git_salt"
CONF_GIT_AREAS: Final = "git_areas"
CONF_GIT_ESPHOME_PATH: Final = "git_esphome_path"
CONF_GIT_Z2M_PATH: Final = "git_z2m_path"
CONF_GIT_EXTRA_PATHS: Final = "git_extra_paths"
CONF_GIT_DEBOUNCE: Final = "git_debounce_seconds"
CONF_GIT_DAILY_TIME: Final = "git_daily_time"
CONF_GIT_AUTHOR_NAME: Final = "git_author_name"
CONF_GIT_AUTHOR_EMAIL: Final = "git_author_email"
CONF_GIT_ALLOW_UNVERIFIED_PRIVATE: Final = "git_allow_unverified_private"

CONF_PROBE_URL: Final = "probe_url"
CONF_PROBE_TOKEN: Final = "probe_token"
CONF_PROBE_INTERVAL: Final = "probe_interval_hours"

CONF_ANOMALY_ENTITIES: Final = "anomaly_entities"
CONF_ANOMALY_SENSITIVITY: Final = "anomaly_sensitivity"
CONF_ANOMALY_LOGIN_TIME: Final = "anomaly_login_time"
CONF_ANOMALY_ACTIONS: Final = "anomaly_actions"
CONF_ANOMALY_SABOTAGE: Final = "anomaly_sabotage"
CONF_SABOTAGE_COUNT: Final = "sabotage_count"
CONF_SABOTAGE_WINDOW: Final = "sabotage_window_seconds"
CONF_ANOMALY_OUTBOUND: Final = "anomaly_outbound"

CONF_NOTIFY_ACTIONS: Final = "notify_actions"
CONF_CANARY_ENABLED: Final = "canary_enabled"
CONF_CANARY_GIT: Final = "canary_in_git"
CONF_REPORT_ENABLED: Final = "report_enabled"
CONF_REPORT_WEEKDAY: Final = "report_weekday"
CONF_REPORT_TIME: Final = "report_time"

GIT_AUTH_SSH: Final = "ssh"
GIT_AUTH_TOKEN: Final = "token"
GIT_AUTH_NONE: Final = "none"

AREA_CONFIG: Final = "config"
AREA_STORAGE: Final = "storage"
AREA_INVENTORY: Final = "inventory"
AREA_ESPHOME: Final = "esphome"
AREA_Z2M: Final = "zigbee2mqtt"
AREA_ADDONS: Final = "addons"
AREA_EXTRA: Final = "extra"

ALL_AREAS: Final = [
    AREA_CONFIG,
    AREA_STORAGE,
    AREA_INVENTORY,
    AREA_ESPHOME,
    AREA_Z2M,
    AREA_ADDONS,
    AREA_EXTRA,
]

DEFAULT_OPTIONS: Final = {
    CONF_AUDIT_INTERVAL: 6,
    CONF_REPAIRS_MIN_SEVERITY: Severity.HIGH.value,
    CONF_MAX_ADMINS: 2,
    CONF_TOKEN_MAX_AGE_DAYS: 365,
    CONF_TOKEN_UNUSED_DAYS: 90,
    CONF_GITHUB_TOKEN: "",
    CONF_DISABLED_CHECKS: [],
    CONF_NOTIFY_TARGETS: [],
    CONF_NOTIFY_MIN_SEVERITY: Severity.HIGH.value,
    CONF_NOTIFY_LOGINS: True,
    CONF_NOTIFY_PUBLIC_ONLY: True,
    CONF_GEOIP: False,
    CONF_BRUTE_FORCE_THRESHOLD: 5,
    CONF_GIT_ENABLED: False,
    CONF_GIT_URL: "",
    CONF_GIT_BRANCH: "main",
    CONF_GIT_AUTH: GIT_AUTH_SSH,
    CONF_GIT_USERNAME: "",
    CONF_GIT_TOKEN: "",
    CONF_GIT_PRIVATE_KEY: "",
    CONF_GIT_PUBLIC_KEY: "",
    CONF_GIT_HOST_KEY: "",
    CONF_GIT_PASSPHRASE: "",
    CONF_GIT_SALT: "",
    CONF_GIT_AREAS: [AREA_CONFIG, AREA_STORAGE, AREA_INVENTORY, AREA_ESPHOME, AREA_Z2M],
    CONF_GIT_ESPHOME_PATH: "",
    CONF_GIT_Z2M_PATH: "",
    CONF_GIT_EXTRA_PATHS: [],
    CONF_GIT_DEBOUNCE: 120,
    CONF_GIT_DAILY_TIME: "03:17:00",
    CONF_GIT_AUTHOR_NAME: "Home Assistant (Bastion)",
    CONF_GIT_AUTHOR_EMAIL: "bastion@homeassistant.local",
    CONF_GIT_ALLOW_UNVERIFIED_PRIVATE: False,
    CONF_PROBE_URL: "",
    CONF_PROBE_TOKEN: "",
    CONF_PROBE_INTERVAL: 24,
    CONF_ANOMALY_ENTITIES: [],
    CONF_ANOMALY_SENSITIVITY: 3.5,
    CONF_ANOMALY_LOGIN_TIME: True,
    CONF_ANOMALY_ACTIONS: True,
    CONF_ANOMALY_SABOTAGE: True,
    CONF_SABOTAGE_COUNT: 3,
    CONF_SABOTAGE_WINDOW: 120,
    CONF_ANOMALY_OUTBOUND: False,
    CONF_NOTIFY_ACTIONS: True,
    CONF_CANARY_ENABLED: False,
    CONF_CANARY_GIT: True,
    CONF_REPORT_ENABLED: True,
    CONF_REPORT_WEEKDAY: "0",
    CONF_REPORT_TIME: "08:13:00",
}

# Options that hold secrets and must never leave HA in clear text.
SECRET_OPTIONS: Final = {
    CONF_GITHUB_TOKEN,
    CONF_GIT_TOKEN,
    CONF_GIT_PRIVATE_KEY,
    CONF_GIT_PASSPHRASE,
    CONF_PROBE_TOKEN,
}

ADVISORY_REPOS: Final = (
    "home-assistant/core",
    "home-assistant/frontend",
    "home-assistant/android",
    "home-assistant/iOS",
)

VERSION_URL: Final = "https://version.home-assistant.io/stable.json"
GITHUB_API: Final = "https://api.github.com"
