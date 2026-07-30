import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand_env(value: Any) -> Any:
    if isinstance(value, str):
        return ENV_PATTERN.sub(lambda match: os.getenv(match.group(1), ""), value)
    if isinstance(value, list):
        return [_expand_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _expand_env(item) for key, item in value.items()}
    return value


@dataclass(frozen=True)
class AppConfig:
    raw: dict[str, Any]
    path: Path

    @property
    def db(self) -> dict[str, Any]:
        return self.raw.get("ghostfolio", {}).get("db", {})

    @property
    def market_data(self) -> dict[str, Any]:
        return self.raw.get("market_data", {})

    @property
    def dashboard(self) -> dict[str, Any]:
        return self.raw.get("dashboard", {})

    @property
    def alerts(self) -> dict[str, Any]:
        return self.raw.get("alerts", {})


def load_config() -> AppConfig:
    configured = Path(os.getenv("CONFIG_PATH", "config.yaml"))
    fallback = Path("config.example.yaml")
    path = configured if configured.exists() else fallback
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    return AppConfig(raw=_expand_env(data or {}), path=path)


def data_dir() -> Path:
    path = Path(os.getenv("DATA_DIR", "data"))
    path.mkdir(parents=True, exist_ok=True)
    return path

