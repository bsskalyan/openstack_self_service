from typing import Any

from app.providers.base import CloudProvider


class ProxmoxProvider(CloudProvider):
    """Future Proxmox implementation of the common cloud provider contract."""

    def status(self) -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def list_images(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def list_flavors(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def list_networks(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def list_servers(self) -> list[dict[str, Any]]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def create_server(
        self,
        *,
        name: str,
        image_id: str,
        flavor_id: str,
        network_id: str,
        key_name: str | None = None,
        security_group_id: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def start_server(self, server_id: str) -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def stop_server(self, server_id: str) -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def reboot_server(self, server_id: str, reboot_type: str = "SOFT") -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")

    def delete_server(self, server_id: str) -> dict[str, Any]:
        raise NotImplementedError("Proxmox provider is not implemented yet")
