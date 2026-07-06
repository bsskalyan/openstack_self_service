import json
from pathlib import Path
from threading import Lock
from typing import Any


class OpenStackProviderConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(__file__).resolve().parents[2] / "database" / "openstack_provider_config.json"
        self._lock = Lock()

    def get_config(self) -> dict[str, Any]:
        with self._lock:
            if not self._path.exists():
                return {}

            with self._path.open("r", encoding="utf-8") as file:
                return json.load(file)

    def save_config(self, config: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as file:
                json.dump(config, file, indent=2)
            return config
