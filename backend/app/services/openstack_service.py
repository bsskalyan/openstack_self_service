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
                    "flavor_id": self._extract_resource_id(getattr(server, "flavor", None)),
                    "image_id": self._extract_resource_id(getattr(server, "image", None)),
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
