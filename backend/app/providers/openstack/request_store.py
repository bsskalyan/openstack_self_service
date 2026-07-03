import json
from pathlib import Path
from threading import Lock
from typing import Any


class OpenStackRequestStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or Path(__file__).resolve().parents[2] / "database" / "openstack_requests.json"
        self._lock = Lock()

    def list_requests(self) -> list[dict[str, Any]]:
        with self._lock:
            return self._read()

    def get_request(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            return next(
                (record for record in self._read() if record["id"] == request_id),
                None,
            )

    def save_request(self, record: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            records = self._read()
            records.append(record)
            self._write(records)
            return record

    def update_request(self, request_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            records = self._read()
            for index, record in enumerate(records):
                if record["id"] == request_id:
                    records[index] = {**record, **updates}
                    self._write(records)
                    return records[index]

        return None

    def _read(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []

        with self._path.open("r", encoding="utf-8") as file:
            records = json.load(file)

        return [self._normalize_record(record) for record in records]

    @classmethod
    def _normalize_record(cls, record: dict[str, Any]) -> dict[str, Any]:
        request = dict(record.get("request") or {})
        request.setdefault(
            "project_name",
            request.get("catalog_service_name") or request.get("app_tag") or request.get("name") or "Legacy Request",
        )
        request.setdefault("request_owner", record.get("owner") or request.get("cost_center") or "Legacy Owner")
        request.setdefault("business_unit", None)
        request.setdefault("team_name", None)
        request.setdefault("application_name", request.get("app_tag") or request.get("name") or "Legacy Application")
        request.setdefault("application_type", None)
        request.setdefault("purpose_description", None)
        request.setdefault("lifetime", cls._normalize_lifetime(request.get("lifetime_days")))
        request["packages"] = cls._normalize_packages(request.get("packages"))

        return {**record, "request": request, "expires_at": record.get("expires_at")}

    @staticmethod
    def _normalize_lifetime(lifetime_days: Any) -> str:
        try:
            days = int(lifetime_days)
        except (TypeError, ValueError):
            days = 30

        if days == 0:
            return "permanent"

        return {
            1: "1_day",
            7: "7_days",
            30: "30_days",
            90: "90_days",
        }.get(days, "30_days")

    @staticmethod
    def _normalize_packages(packages: Any) -> list[str]:
        if isinstance(packages, str):
            values = [item.strip() for item in packages.split(",")]
        elif isinstance(packages, list):
            values = [str(item).strip() for item in packages]
        else:
            values = []

        aliases = {
            "docker": "Docker",
            "podman": "Podman",
            "nginx": "Nginx",
            "apache": "Apache",
            "nodejs": "Node.js",
            "node.js": "Node.js",
            "node": "Node.js",
            "python": "Python",
            "postgresql": "PostgreSQL",
            "postgres": "PostgreSQL",
            "mysql": "MySQL",
            "git": "Git",
            "ansible": "Ansible",
        }

        normalized: list[str] = []
        for value in values:
            package = aliases.get(value.lower().replace("-", "").replace("_", ""))
            if package and package not in normalized:
                normalized.append(package)

        return normalized

    def _write(self, records: list[dict[str, Any]]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as file:
            json.dump(records, file, indent=2)
