import json
from pathlib import Path
from threading import Lock
from typing import Any


class OpenStackAuditStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(__file__).resolve().parents[2] / "database" / "openstack_audit.json"
        self._lock = Lock()

    def list_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def save_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            events = self._read()
            events.append(event)
            self._write(events)
            return event

    def _read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []

        with self._path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _write(self, events: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as file:
            json.dump(events, file, indent=2)
