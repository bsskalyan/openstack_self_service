from typing import Any

from app.providers.base import CloudProvider
from app.providers.openstack.service import OpenStackService


class OpenStackProvider(CloudProvider):
    """OpenStack implementation of the common cloud provider contract."""

    def __init__(self, service: OpenStackService) -> None:
        self._service = service

    @property
    def service(self) -> OpenStackService:
        """Expose OpenStack-specific workflows that are not in the common contract yet."""
        return self._service

    def status(self) -> dict[str, Any]:
        return self._service.verify_authentication()

    def list_images(self) -> list[dict[str, Any]]:
        return self._service.list_images()

    def list_flavors(self) -> list[dict[str, Any]]:
        return self._service.list_flavors()

    def list_networks(self) -> list[dict[str, Any]]:
        return self._service.list_networks()

    def list_servers(self) -> list[dict[str, Any]]:
        return self._service.list_servers()

    def create_server(
        self,
        *,
        name: str,
        image_id: str,
        flavor_id: str,
        network_id: str,
        key_name: str | None = None,
        security_group_id: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._service.create_server(
            name=name,
            image_id=image_id,
            flavor_id=flavor_id,
            network_id=network_id,
            key_name=key_name,
            security_group_id=security_group_id,
            metadata=metadata,
        )

    def start_server(self, server_id: str) -> dict[str, Any]:
        return self._service.start_server(server_id)

    def stop_server(self, server_id: str) -> dict[str, Any]:
        return self._service.stop_server(server_id)

    def reboot_server(self, server_id: str, reboot_type: str = "SOFT") -> dict[str, Any]:
        return self._service.reboot_server(server_id, reboot_type=reboot_type)

    def delete_server(self, server_id: str) -> dict[str, Any]:
        return self._service.delete_server(server_id)
