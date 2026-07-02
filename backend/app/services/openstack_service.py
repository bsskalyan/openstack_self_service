import logging
from typing import Any

import openstack
from openstack.connection import Connection
from openstack.exceptions import SDKException

from app.core.config import Settings


logger = logging.getLogger(__name__)


class OpenStackServiceError(Exception):
    """Raised when OpenStack operations fail."""


class OpenStackConfigurationError(OpenStackServiceError):
    """Raised when required OpenStack configuration is missing."""


class OpenStackService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Connection | None = None

    def get_connection(self) -> Connection:
        if self._connection is None:
            self._connection = self._create_connection()

        return self._connection

    def verify_authentication(self) -> dict[str, Any]:
        connection = self.get_connection()

        try:
            token = connection.authorize()
            current_project = connection.get_project(self._settings.os_project_name)
            logger.info(
                "Verified OpenStack authentication for user '%s'",
                self._settings.os_username,
            )
            return {
                "authenticated": True,
                "auth_url": self._settings.os_auth_url,
                "region": self._settings.os_region_name,
                "project_id": getattr(current_project, "id", None),
                "project_name": getattr(current_project, "name", self._settings.os_project_name),
                "user_name": self._settings.os_username,
                "token_expires_at": getattr(token, "expires_at", None),
            }
        except SDKException as exc:
            logger.exception("OpenStack authentication failed")
            self._connection = None
            raise OpenStackServiceError("OpenStack authentication failed") from exc

    def list_images(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "id": image.id,
                    "name": image.name,
                    "status": image.status,
                    "visibility": getattr(image, "visibility", None),
                    "disk_format": getattr(image, "disk_format", None),
                    "size": getattr(image, "size", None),
                }
                for image in self.get_connection().image.images()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack images")
            raise OpenStackServiceError("Failed to list OpenStack images") from exc

    def list_flavors(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "id": flavor.id,
                    "name": flavor.name,
                    "vcpus": getattr(flavor, "vcpus", None),
                    "ram": getattr(flavor, "ram", None),
                    "disk": getattr(flavor, "disk", None),
                    "ephemeral": getattr(flavor, "ephemeral", None),
                    "swap": getattr(flavor, "swap", None),
                    "is_public": getattr(flavor, "is_public", None),
                }
                for flavor in self.get_connection().compute.flavors()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack flavors")
            raise OpenStackServiceError("Failed to list OpenStack flavors") from exc

    def list_networks(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "id": network.id,
                    "name": network.name,
                    "status": getattr(network, "status", None),
                    "admin_state_up": getattr(network, "admin_state_up", None),
                    "is_shared": getattr(network, "is_shared", None),
                    "is_router_external": getattr(network, "is_router_external", None),
                    "project_id": getattr(network, "project_id", None),
                }
                for network in self.get_connection().network.networks()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack networks")
            raise OpenStackServiceError("Failed to list OpenStack networks") from exc

    def list_keypairs(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "name": keypair.name,
                    "type": getattr(keypair, "type", None),
                    "fingerprint": getattr(keypair, "fingerprint", None),
                    "public_key": getattr(keypair, "public_key", None),
                }
                for keypair in self.get_connection().compute.keypairs()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack keypairs")
            raise OpenStackServiceError("Failed to list OpenStack keypairs") from exc

    def list_security_groups(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "id": security_group.id,
                    "name": security_group.name,
                    "description": getattr(security_group, "description", None),
                    "project_id": getattr(security_group, "project_id", None),
                    "rules": [
                        self._serialize_security_group_rule(rule)
                        for rule in getattr(security_group, "security_group_rules", [])
                    ],
                }
                for security_group in self.get_connection().network.security_groups()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack security groups")
            raise OpenStackServiceError("Failed to list OpenStack security groups") from exc

    def list_servers(self) -> list[dict[str, Any]]:
        try:
            return [
                {
                    "id": server.id,
                    "name": server.name,
                    "status": getattr(server, "status", None),
                    "flavor_id": self._extract_server_flavor_id(server),
                    "image_id": self._extract_server_image_id(server),
                    "addresses": getattr(server, "addresses", None),
                    "project_id": getattr(server, "project_id", None),
                    "created_at": self._serialize_value(getattr(server, "created_at", None)),
                    "updated_at": self._serialize_value(getattr(server, "updated_at", None)),
                    "vm_state": getattr(server, "vm_state", None),
                }
                for server in self.get_connection().compute.servers(details=True)
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack servers")
            raise OpenStackServiceError("Failed to list OpenStack servers") from exc

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
        try:
            connection = self.get_connection()
            image = connection.image.find_image(image_id, ignore_missing=False)
            flavor = connection.compute.find_flavor(flavor_id, ignore_missing=False)
            network = connection.network.find_network(network_id, ignore_missing=False)

            server_payload: dict[str, Any] = {
                "name": name,
                "image_id": image.id,
                "flavor_id": flavor.id,
                "networks": [{"uuid": network.id}],
            }

            if key_name:
                server_payload["key_name"] = key_name

            if security_group_id:
                security_group = connection.network.find_security_group(
                    security_group_id,
                    ignore_missing=False,
                )
                server_payload["security_groups"] = [{"name": security_group.name}]

            logger.info(
                "Creating OpenStack server name='%s', image_id='%s', flavor_id='%s', "
                "network_id='%s'",
                name,
                image_id,
                flavor_id,
                network_id,
            )
            server = connection.compute.create_server(**server_payload)
            logger.info("Created OpenStack server id='%s', name='%s'", server.id, server.name)
            return self._serialize_server_summary(server)
        except SDKException as exc:
            logger.exception("Failed to create OpenStack server name='%s'", name)
            raise OpenStackServiceError(
                f"Failed to create OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def delete_server(self, server_id: str) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Deleting OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.delete_server(server, ignore_missing=False)
            return self._serialize_lifecycle_response(
                server=server,
                action="delete",
            )
        except SDKException as exc:
            logger.exception("Failed to delete OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to delete OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def start_server(self, server_id: str) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Starting OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.start_server(server)
            return self._serialize_lifecycle_response(
                server=server,
                action="start",
            )
        except SDKException as exc:
            logger.exception("Failed to start OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to start OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def stop_server(self, server_id: str) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Stopping OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.stop_server(server)
            return self._serialize_lifecycle_response(
                server=server,
                action="stop",
            )
        except SDKException as exc:
            logger.exception("Failed to stop OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to stop OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def reboot_server(self, server_id: str) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Rebooting OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.reboot_server(server, reboot_type="SOFT")
            return self._serialize_lifecycle_response(
                server=server,
                action="reboot",
            )
        except SDKException as exc:
            logger.exception("Failed to reboot OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to reboot OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def _create_connection(self) -> Connection:
        self._validate_configuration()

        try:
            connection = openstack.connection.Connection(
                auth_url=self._settings.os_auth_url,
                username=self._settings.os_username,
                password=self._settings.os_password.get_secret_value()
                if self._settings.os_password
                else None,
                project_name=self._settings.os_project_name,
                user_domain_id=self._settings.os_user_domain_id,
                project_domain_id=self._settings.os_project_domain_id,
                region_name=self._settings.os_region_name,
                app_name=self._settings.app_name,
                app_version=self._settings.app_version,
            )
            logger.info(
                "Created OpenStack connection for auth_url='%s', project='%s', region='%s'",
                self._settings.os_auth_url,
                self._settings.os_project_name,
                self._settings.os_region_name,
            )
            return connection
        except SDKException as exc:
            logger.exception("Failed to create OpenStack connection")
            raise OpenStackServiceError("Failed to create OpenStack connection") from exc

    def _validate_configuration(self) -> None:
        missing_settings = [
            name
            for name, value in {
                "OS_AUTH_URL": self._settings.os_auth_url,
                "OS_USERNAME": self._settings.os_username,
                "OS_PASSWORD": self._settings.os_password,
                "OS_PROJECT_NAME": self._settings.os_project_name,
            }.items()
            if value is None or value == ""
        ]

        if missing_settings:
            message = f"Missing OpenStack configuration: {', '.join(missing_settings)}"
            logger.error(message)
            raise OpenStackConfigurationError(message)

    @staticmethod
    def _extract_resource_id(resource: Any) -> str | None:
        if resource is None:
            return None

        if isinstance(resource, dict):
            return resource.get("id")

        return getattr(resource, "id", None)

    @staticmethod
    def _serialize_security_group_rule(rule: Any) -> dict[str, Any]:
        return {
            "id": OpenStackService._get_resource_field(rule, "id"),
            "direction": OpenStackService._get_resource_field(rule, "direction"),
            "ethertype": OpenStackService._get_resource_field(rule, "ethertype"),
            "protocol": OpenStackService._get_resource_field(rule, "protocol"),
            "port_range_min": OpenStackService._get_resource_field(rule, "port_range_min"),
            "port_range_max": OpenStackService._get_resource_field(rule, "port_range_max"),
            "remote_ip_prefix": OpenStackService._get_resource_field(
                rule,
                "remote_ip_prefix",
            ),
            "remote_group_id": OpenStackService._get_resource_field(rule, "remote_group_id"),
        }

    @staticmethod
    def _get_resource_field(resource: Any, field_name: str) -> Any:
        if isinstance(resource, dict):
            return resource.get(field_name)

        return getattr(resource, field_name, None)

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            return value.isoformat()

        return value

    @staticmethod
    def _serialize_server_summary(server: Any) -> dict[str, Any]:
        return {
            "id": server.id,
            "name": server.name,
            "status": getattr(server, "status", None),
            "addresses": getattr(server, "addresses", None),
            "image_id": OpenStackService._extract_server_image_id(server),
            "flavor_id": OpenStackService._extract_server_flavor_id(server),
        }

    @staticmethod
    def _serialize_lifecycle_response(
        *,
        server: Any,
        action: str,
    ) -> dict[str, Any]:
        return {
            "id": server.id,
            "action": action,
            "status": "accepted",
        }

    @staticmethod
    def _extract_server_image_id(server: Any) -> str | None:
        return getattr(server, "image_id", None) or OpenStackService._extract_resource_id(
            getattr(server, "image", None),
        )

    @staticmethod
    def _extract_server_flavor_id(server: Any) -> str | None:
        return getattr(server, "flavor_id", None) or OpenStackService._extract_resource_id(
            getattr(server, "flavor", None),
        )

    @staticmethod
    def _format_openstack_error(exc: SDKException) -> str:
        return str(exc) or exc.__class__.__name__
