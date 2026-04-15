"""Configuration loading for the CUCM exporter."""

import os
import logging

import yaml

from cucm_exporter.constants import DEFAULT_PERFMON_OBJECTS

logger = logging.getLogger(__name__)


class ServerConfig:
    """Configuration for a single CUCM server."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int = 8443,
        username: str = "",
        password: str = "",
        verify_ssl: bool = False,
    ):
        self.name = name
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

    def __repr__(self):
        return f"ServerConfig(name={self.name!r}, host={self.host!r})"


class Config:
    """Exporter configuration loaded from YAML file with env var overrides."""

    def __init__(
        self,
        servers: list[ServerConfig],
        exporter_port: int = 9100,
        log_level: str = "INFO",
        scrape_timeout: float = 55.0,
        perfmon_enabled: bool = True,
        perfmon_objects: list | None = None,
        risport_enabled: bool = True,
        risport_max_devices: int = 2000,
        risport_device_info_enabled: bool = True,
    ):
        self.servers = servers
        self.exporter_port = exporter_port
        self.log_level = log_level
        self.scrape_timeout = scrape_timeout
        self.perfmon_enabled = perfmon_enabled
        self.perfmon_objects = perfmon_objects or list(DEFAULT_PERFMON_OBJECTS)
        self.risport_enabled = risport_enabled
        self.risport_max_devices = risport_max_devices
        self.risport_device_info_enabled = risport_device_info_enabled

    @classmethod
    def load(cls, config_path: str | None = None) -> "Config":
        """Load config from YAML file, then apply env var overrides.

        Supports two YAML formats:
          1. Multi-server: a top-level ``servers`` list
          2. Single-server (legacy): a top-level ``cucm`` section

        If both are present, ``servers`` takes priority. Environment variables
        CUCM_HOST / CUCM_USERNAME / CUCM_PASSWORD still work for the
        single-server case.
        """
        data = {}
        path = config_path or os.environ.get("CUCM_CONFIG_FILE")
        if path and os.path.exists(path):
            logger.info("Loading config from %s", path)
            with open(path) as f:
                data = yaml.safe_load(f) or {}

        exporter = data.get("exporter", {})
        perfmon = data.get("perfmon", {})
        risport = data.get("risport", {})

        # Build server list
        servers = _load_servers(data)

        return cls(
            servers=servers,
            exporter_port=_env_int(
                "EXPORTER_PORT", exporter.get("port", 9100)
            ),
            log_level=_env_str(
                "LOG_LEVEL", exporter.get("log_level", "INFO")
            ),
            scrape_timeout=float(
                os.environ.get(
                    "SCRAPE_TIMEOUT", exporter.get("scrape_timeout", 55.0)
                )
            ),
            perfmon_enabled=_env_bool(
                "PERFMON_ENABLED", perfmon.get("enabled", True)
            ),
            perfmon_objects=_env_list(
                "PERFMON_OBJECTS", perfmon.get("objects")
            ),
            risport_enabled=_env_bool(
                "RISPORT_ENABLED", risport.get("enabled", True)
            ),
            risport_max_devices=_env_int(
                "RISPORT_MAX_DEVICES", risport.get("max_devices", 2000)
            ),
            risport_device_info_enabled=_env_bool(
                "RISPORT_DEVICE_INFO",
                risport.get("device_info_enabled", True),
            ),
        )


def _load_servers(data: dict) -> list[ServerConfig]:
    """Build the server list from YAML data and/or env vars.

    Priority:
      1. ``servers`` list in YAML (multi-server)
      2. ``cucm`` section in YAML with env var overrides (single-server, legacy)
      3. Pure env vars CUCM_HOST / CUCM_USERNAME / CUCM_PASSWORD (no YAML)
    """
    servers_raw = data.get("servers")
    if servers_raw and isinstance(servers_raw, list):
        servers = []
        for entry in servers_raw:
            servers.append(
                ServerConfig(
                    name=entry.get("name", entry.get("host", "")),
                    host=entry["host"],
                    port=entry.get("port", 8443),
                    username=entry.get("username", ""),
                    password=entry.get("password", ""),
                    verify_ssl=entry.get("verify_ssl", False),
                )
            )
        return servers

    # Legacy single-server fallback
    cucm = data.get("cucm", {})
    host = _env_str("CUCM_HOST", cucm.get("host", ""))
    if not host:
        return []

    return [
        ServerConfig(
            name=host,
            host=host,
            port=_env_int("CUCM_PORT", cucm.get("port", 8443)),
            username=_env_str("CUCM_USERNAME", cucm.get("username", "")),
            password=_env_str("CUCM_PASSWORD", cucm.get("password", "")),
            verify_ssl=_env_bool(
                "CUCM_VERIFY_SSL", cucm.get("verify_ssl", False)
            ),
        )
    ]


def _env_str(key: str, default: str) -> str:
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    val = os.environ.get(key)
    if val is not None:
        return int(val)
    return default


def _env_bool(key: str, default: bool) -> bool:
    val = os.environ.get(key)
    if val is not None:
        return val.lower() in ("true", "1", "yes")
    return default


def _env_list(key: str, default: list | None) -> list | None:
    val = os.environ.get(key)
    if val is not None:
        return [s.strip() for s in val.split(",") if s.strip()]
    return default
