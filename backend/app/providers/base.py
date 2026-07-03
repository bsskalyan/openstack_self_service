from typing import Any, Protocol


class CloudProvider(Protocol):
    """Common cloud provider contract for self-service operations."""

    def status(self) -> dict[str, Any]:
        """Return provider connectivity and cloud identity information."""

    def list_images(self) -> list[dict[str, Any]]:
        """Return available VM images."""

    def list_flavors(self) -> list[dict[str, Any]]:
        """Return available compute sizes."""

    def list_networks(self) -> list[dict[str, Any]]:
        """Return available networks."""

    def list_servers(self) -> list[dict[str, Any]]:
        """Return provisioned servers."""

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
        """Create a server."""

    def start_server(self, server_id: str) -> dict[str, Any]:
        """Start a server by provider ID."""

    def stop_server(self, server_id: str) -> dict[str, Any]:
        """Stop a server by provider ID."""

    def reboot_server(self, server_id: str, reboot_type: str = "SOFT") -> dict[str, Any]:
        """Reboot a server by provider ID."""

    def delete_server(self, server_id: str) -> dict[str, Any]:
        """Delete a server by provider ID."""
