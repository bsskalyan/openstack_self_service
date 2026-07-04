import logging
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import openstack
from openstack.connection import Connection
from openstack.exceptions import SDKException

from app.core.config import Settings
from app.providers.openstack.audit_store import OpenStackAuditStore
from app.providers.openstack.policy import evaluate_vm_request
from app.providers.openstack.request_store import OpenStackRequestStore
from app.providers.openstack.schemas import OpenStackRejectRequest, OpenStackVMRequest


logger = logging.getLogger(__name__)


class OpenStackServiceError(Exception):
    """Raised when OpenStack operations fail."""

    def __init__(
        self,
        message: str,
        *,
        failure_details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.failure_details = failure_details


class OpenStackConfigurationError(OpenStackServiceError):
    """Raised when required OpenStack configuration is missing."""


class OpenStackValidationError(OpenStackServiceError):
    """Raised when request data is invalid before calling OpenStack."""


class OpenStackRequestNotFoundError(OpenStackServiceError):
    """Raised when a stored request cannot be found."""


class OpenStackService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: Connection | None = None
        self._request_store = OpenStackRequestStore()
        self._audit_store = OpenStackAuditStore()

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
                    "label": self._format_network_label(network),
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
                    "metadata": getattr(server, "metadata", None),
                    "failure_details": self._extract_server_failure_details(server),
                }
                for server in self.get_connection().compute.servers(details=True)
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack servers")
            raise OpenStackServiceError("Failed to list OpenStack servers") from exc

    def list_floating_ips(self) -> list[dict[str, Any]]:
        try:
            return [
                self._serialize_floating_ip(floating_ip)
                for floating_ip in self.get_connection().network.ips()
            ]
        except SDKException as exc:
            logger.exception("Failed to list OpenStack floating IPs")
            raise OpenStackServiceError(
                f"Failed to list OpenStack floating IPs: {self._format_openstack_error(exc)}",
            ) from exc

    def get_server_console(self, server_id: str, console_type: str = "novnc") -> dict[str, str]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            console = connection.compute.create_server_remote_console(
                server,
                protocol="vnc",
                type=console_type,
            )
            console_url = self._extract_console_url(console)
            if not console_url:
                raise OpenStackServiceError("OpenStack did not return a console URL.")

            logger.info(
                "Created OpenStack console URL for server id='%s', type='%s'",
                server_id,
                console_type,
            )
            return {
                "server_id": server_id,
                "console_type": console_type,
                "console_url": console_url,
            }
        except OpenStackServiceError:
            raise
        except SDKException as exc:
            logger.exception("Failed to create OpenStack console for server id='%s'", server_id)
            failure_details = self._build_failure_details(exc)
            if failure_details["user_message"] == "OpenStack could not provision this VM.":
                failure_details["user_message"] = "Unable to open OpenStack web console."
                failure_details["suggested_action"] = (
                    "Verify the server is available and the OpenStack console service is enabled."
                )
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def get_server_ssh_console_metadata(self, server_id: str) -> dict[str, Any]:
        try:
            server = self.get_connection().compute.get_server(server_id)
            addresses = getattr(server, "addresses", None)
            private_ip, floating_ip = self._extract_server_ips(addresses)
            username = self._suggest_ssh_username(server)
            return {
                "server_id": server_id,
                "server_name": getattr(server, "name", None),
                "private_ip": private_ip,
                "floating_ip": floating_ip,
                "username_suggestion": username,
                "connection_status": "reachable" if floating_ip else "requires_floating_ip",
            }
        except SDKException as exc:
            logger.exception("Failed to get SSH console metadata for server id='%s'", server_id)
            failure_details = self._build_failure_details(exc)
            if failure_details["user_message"] == "OpenStack could not provision this VM.":
                failure_details["user_message"] = "Unable to load CLI console metadata."
                failure_details["suggested_action"] = (
                    "Verify the server exists and try again after OpenStack is reachable."
                )
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def prepare_ssh_console_session(self, server_id: str) -> dict[str, Any]:
        try:
            server = self.get_connection().compute.get_server(server_id)
            status = str(getattr(server, "status", "") or "").upper()
            if status != "ACTIVE":
                raise OpenStackValidationError(
                    "VM is not active. Start the VM before opening CLI console.",
                    failure_details={
                        "user_message": "VM is not active.",
                        "technical_reason": f"Server status is {status or 'unknown'}",
                        "suggested_action": "Start the VM and try opening CLI console again.",
                        "raw_error": {"server_id": server_id, "status": status or None},
                    },
                )

            addresses = getattr(server, "addresses", None)
            private_ip, floating_ip = self._extract_server_ips(addresses)
            host = floating_ip or private_ip
            if not host:
                raise OpenStackValidationError(
                    "No reachable IP address is available for CLI console.",
                    failure_details={
                        "user_message": "No reachable IP.",
                        "technical_reason": (
                            "Server has no floating IP or private IP in OpenStack addresses."
                        ),
                        "suggested_action": (
                            "Attach a floating IP first or verify tenant network reachability."
                        ),
                        "raw_error": {"server_id": server_id, "addresses": addresses},
                    },
                )

            return {
                "server_id": server_id,
                "server_name": getattr(server, "name", None),
                "host": host,
                "private_ip": private_ip,
                "floating_ip": floating_ip,
                "username": self._suggest_ssh_username(server),
            }
        except OpenStackServiceError:
            raise
        except SDKException as exc:
            logger.exception("Failed to prepare SSH console session for server id='%s'", server_id)
            failure_details = self._build_failure_details(exc)
            if failure_details["user_message"] == "OpenStack could not provision this VM.":
                failure_details["user_message"] = "Unable to prepare CLI console."
                failure_details["suggested_action"] = "Verify the VM exists and try again."
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def record_console_audit_event(
        self,
        *,
        actor: str,
        role: str,
        action: str,
        server_id: str,
        status: str,
        message: str,
    ) -> None:
        self._record_audit_event(
            actor=actor,
            role=role,
            action=action,
            resource_type="server",
            resource_id=server_id,
            request_id=None,
            status=status,
            message=message,
        )

    def create_server_snapshot(
        self,
        server_id: str,
        *,
        name: str,
        description: str | None,
        actor: str,
        role: str,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            metadata = {
                "cms_snapshot": "true",
                "cms_snapshot_server_id": server_id,
                "cms_snapshot_server_name": getattr(server, "name", "") or "",
                "description": description or "",
            }
            snapshot_ref = connection.compute.create_server_image(
                server,
                name=name,
                metadata=metadata,
            )
            snapshot_id = self._extract_resource_id(snapshot_ref) or str(snapshot_ref)
            snapshot = connection.image.get_image(snapshot_id)
            serialized = self._serialize_snapshot(snapshot)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_created",
                resource_type="snapshot",
                resource_id=snapshot_id,
                request_id=None,
                status="accepted",
                message=f"Snapshot '{name}' created for server '{server_id}'.",
            )
            return serialized
        except SDKException as exc:
            logger.exception("Failed to create snapshot for server id='%s'", server_id)
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def list_server_snapshots(self, server_id: str) -> list[dict[str, Any]]:
        try:
            return [
                self._serialize_snapshot(image)
                for image in self.get_connection().image.images()
                if self._snapshot_belongs_to_server(image, server_id)
            ]
        except SDKException as exc:
            logger.exception("Failed to list snapshots for server id='%s'", server_id)
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def get_snapshot_server_id(self, snapshot_id: str) -> str | None:
        try:
            snapshot = self.get_connection().image.get_image(snapshot_id)
            return self._extract_snapshot_server_id(snapshot)
        except SDKException as exc:
            logger.exception("Failed to resolve server id for snapshot id='%s'", snapshot_id)
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def delete_snapshot(
        self,
        snapshot_id: str,
        *,
        actor: str,
        role: str,
    ) -> dict[str, Any]:
        try:
            self.get_connection().image.delete_image(snapshot_id, ignore_missing=False)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_deleted",
                resource_type="snapshot",
                resource_id=snapshot_id,
                request_id=None,
                status="succeeded",
                message=f"Snapshot '{snapshot_id}' deleted.",
            )
            return {
                "id": snapshot_id,
                "action": "delete",
                "status": "accepted",
                "message": "Snapshot deletion accepted.",
                "server": None,
            }
        except SDKException as exc:
            logger.exception("Failed to delete snapshot id='%s'", snapshot_id)
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def restore_server_snapshot(
        self,
        server_id: str,
        snapshot_id: str,
        *,
        mode: str = "new_vm",
        new_vm_name: str | None = None,
        actor: str,
        role: str,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            original_server = connection.compute.get_server(server_id)
            snapshot = connection.image.get_image(snapshot_id)
            snapshot_server_id = self._extract_snapshot_server_id(snapshot)
            if snapshot_server_id and snapshot_server_id != server_id:
                raise OpenStackValidationError(
                    "Snapshot does not belong to this server.",
                    failure_details={
                        "user_message": "Snapshot does not belong to this server.",
                        "technical_reason": (
                            f"Snapshot server id '{snapshot_server_id}' does not match '{server_id}'."
                        ),
                        "suggested_action": "Choose a snapshot created from the selected VM.",
                        "raw_error": {
                            "server_id": server_id,
                            "snapshot_id": snapshot_id,
                            "snapshot_server_id": snapshot_server_id,
                        },
                    },
                )

            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_restore_mode_selected",
                resource_type="snapshot",
                resource_id=snapshot_id,
                request_id=None,
                status="accepted",
                message=f"Snapshot restore mode selected: {mode}.",
            )

            if mode == "same_vm":
                return self._restore_snapshot_to_same_vm(
                    connection=connection,
                    original_server=original_server,
                    snapshot_id=snapshot_id,
                    actor=actor,
                    role=role,
                )

            flavor_id = self._extract_server_flavor_id(original_server)
            network_id = self._extract_primary_server_network_id(connection, original_server)
            if not flavor_id or not network_id:
                raise OpenStackValidationError(
                    "Unable to restore snapshot because server flavor or network could not be resolved.",
                    failure_details={
                        "user_message": "Unable to restore snapshot.",
                        "technical_reason": "Original server flavor or attached network was not available.",
                        "suggested_action": "Verify the original server still has flavor and interface details.",
                        "raw_error": {
                            "server_id": server_id,
                            "flavor_id": flavor_id,
                            "network_id": network_id,
                        },
                    },
                )

            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_restore_requested",
                resource_type="snapshot",
                resource_id=snapshot_id,
                request_id=None,
                status="accepted",
                message="Snapshot restore requested with mode 'new_vm'.",
            )
            restored_server = self.create_server(
                name=new_vm_name or f"{getattr(original_server, 'name', 'server')}-restored",
                image_id=snapshot_id,
                flavor_id=flavor_id,
                network_id=network_id,
                key_name=getattr(original_server, "key_name", None),
                metadata={
                    "managed_by": "openstack-self-service",
                    "restored_from_snapshot_id": snapshot_id,
                    "restored_from_server_id": server_id,
                    "owner": actor,
                    "owner_role": role,
                },
            )
            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_restore_new_vm_completed",
                resource_type="server",
                resource_id=restored_server.get("id"),
                request_id=None,
                status="accepted",
                message="Snapshot restore creates a new VM from the selected snapshot.",
            )
            return {
                "id": snapshot_id,
                "action": "restore",
                "status": "accepted",
                "message": "Snapshot restore creates a new VM from the selected snapshot.",
                "server": restored_server,
            }
        except OpenStackServiceError:
            raise
        except SDKException as exc:
            logger.exception(
                "Failed to restore snapshot id='%s' for server id='%s'",
                snapshot_id,
                server_id,
            )
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def _restore_snapshot_to_same_vm(
        self,
        *,
        connection: Connection,
        original_server: Any,
        snapshot_id: str,
        actor: str,
        role: str,
    ) -> dict[str, Any]:
        server_id = getattr(original_server, "id", None)
        self._record_audit_event(
            actor=actor,
            role=role,
            action="snapshot_restore_existing_vm_attempted",
            resource_type="server",
            resource_id=server_id,
            request_id=None,
            status="accepted",
            message="Snapshot restore to existing VM attempted.",
        )
        try:
            rebuilt_server = connection.compute.rebuild_server(
                original_server,
                image=snapshot_id,
                name=getattr(original_server, "name", None),
            )
            serialized_server = self._serialize_server_summary(rebuilt_server)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_restore_existing_vm_succeeded",
                resource_type="server",
                resource_id=server_id,
                request_id=None,
                status="accepted",
                message="Existing VM rebuild from snapshot was accepted.",
            )
            return {
                "id": snapshot_id,
                "action": "restore",
                "status": "accepted",
                "message": "Existing VM rebuild from snapshot was accepted.",
                "server": serialized_server,
            }
        except (AttributeError, TypeError, SDKException) as exc:
            logger.exception(
                "Failed to restore snapshot id='%s' to existing server id='%s'",
                snapshot_id,
                server_id,
            )
            self._record_audit_event(
                actor=actor,
                role=role,
                action="snapshot_restore_existing_vm_failed",
                resource_type="server",
                resource_id=server_id,
                request_id=None,
                status="failed",
                message="Restore to same VM failed or is unsupported.",
            )
            raise OpenStackValidationError(
                "Restore to same VM is not supported in this OpenStack environment. Please restore as a new VM.",
                failure_details={
                    "user_message": (
                        "Restore to same VM is not supported in this OpenStack environment. "
                        "Please restore as a new VM."
                    ),
                    "technical_reason": self._format_openstack_error(exc)
                    if isinstance(exc, SDKException)
                    else str(exc),
                    "suggested_action": "Choose Restore as New VM and try again.",
                    "raw_error": {
                        "server_id": server_id,
                        "snapshot_id": snapshot_id,
                        "mode": "same_vm",
                    },
                },
            ) from exc

    def create_floating_ip(self, public_network_id: str | None = None) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            public_network = self._resolve_public_network(connection, public_network_id)
            logger.info(
                "Creating OpenStack floating IP from network id='%s', name='%s'",
                public_network.id,
                getattr(public_network, "name", None),
            )
            floating_ip = connection.network.create_ip(
                floating_network_id=public_network.id,
            )
            logger.info(
                "Created OpenStack floating IP id='%s', address='%s'",
                floating_ip.id,
                getattr(floating_ip, "floating_ip_address", None),
            )
            return self._serialize_floating_ip(floating_ip)
        except SDKException as exc:
            logger.exception("Failed to create OpenStack floating IP")
            raise OpenStackServiceError(
                f"Failed to create OpenStack floating IP: {self._format_openstack_error(exc)}",
            ) from exc

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
        user_data: str | None = None,
    ) -> dict[str, Any]:
        try:
            self._validate_network_id(network_id)
            connection = self.get_connection()
            image = connection.image.find_image(image_id, ignore_missing=False)
            flavor = connection.compute.find_flavor(flavor_id, ignore_missing=False)
            network = self._resolve_network_by_id(connection, network_id)

            server_payload: dict[str, Any] = {
                "name": name,
                "image_id": image.id,
                "flavor_id": flavor.id,
                "networks": [{"uuid": network.id}],
            }

            if key_name:
                server_payload["key_name"] = key_name

            if metadata:
                server_payload["metadata"] = metadata

            if user_data:
                server_payload["user_data"] = user_data

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
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

    def _resolve_network_by_id(self, connection: Connection, network_id: str) -> Any:
        matching_networks = [
            network
            for network in connection.network.networks()
            if getattr(network, "id", None) == network_id
        ]

        if len(matching_networks) == 1:
            return matching_networks[0]

        if not matching_networks:
            raise OpenStackValidationError(
                f"Selected network id '{network_id}' is unavailable. Select a network by id from the networks endpoint.",
            )

        raise OpenStackValidationError(
            f"Selected network id '{network_id}' is ambiguous. Ask an administrator to verify OpenStack network IDs.",
        )

    def submit_vm_request(
        self,
        request: OpenStackVMRequest,
        *,
        owner: str | None = None,
        owner_role: str | None = None,
    ) -> dict[str, Any]:
        self._validate_network_id(request.network_id)
        policy_result = evaluate_vm_request(request)
        request_id = str(uuid4())
        now = self._now()
        self._record_audit_event(
            actor=owner,
            role=owner_role,
            action="request_submitted",
            resource_type="request",
            resource_id=request_id,
            request_id=request_id,
            status="submitted",
            message=(
                f"Request '{request.application_name or request.name}' submitted "
                f"for project '{request.project_name}', cost center '{request.cost_center}', "
                f"owner '{request.request_owner}', application type '{request.application_type or 'N/A'}', "
                f"environment '{request.environment}', {self._format_lifetime(request)} lifetime "
                f"and packages: {self._format_packages(request)}"
            ),
        )
        self._record_audit_event(
            actor="system",
            role="system",
            action="policy_evaluated",
            resource_type="request",
            resource_id=request_id,
            request_id=request_id,
            status=policy_result.final_decision,
            message=(
                f"Policy evaluated with governance score {policy_result.governance_score} "
                f"for project '{request.project_name}' / application '{request.application_name}' / "
                f"{request.environment} / {self._format_lifetime(request)} / "
                f"packages: {self._format_packages(request)}"
            ),
        )

        if policy_result.final_decision == "approval_required":
            self._record_audit_event(
                actor="system",
                role="system",
                action="approval_required",
                resource_type="request",
                resource_id=request_id,
                request_id=request_id,
                status="approval_required",
                message="Request requires admin approval",
            )
            record = self._build_request_record(
                request_id=request_id,
                request=request,
                policy_result=policy_result,
                status="approval_required",
                owner=owner,
                owner_role=owner_role,
                created_at=now,
                updated_at=now,
                activity_log=[
                    self._activity_entry(
                        action="submitted",
                        status="approval_required",
                        message=(
                            "Request submitted and routed for approval "
                            f"with packages: {self._format_packages(request)}"
                        ),
                        created_at=now,
                    ),
                ],
            )
            logger.info(
                "VM request id='%s' requires approval, score='%s'",
                request_id,
                policy_result.governance_score,
            )
            return self._request_store.save_request(record)

        self._record_audit_event(
            actor="system",
            role="system",
            action="auto_approved",
            resource_type="request",
            resource_id=request_id,
            request_id=request_id,
            status="auto_approved",
            message="Request auto-approved by policy",
        )
        self._record_audit_event(
            actor="system",
            role="system",
            action="provisioning_started",
            resource_type="server",
            resource_id=None,
            request_id=request_id,
            status="started",
            message="VM provisioning started",
        )
        try:
            server = self.create_server(
                name=request.name,
                image_id=request.image_id,
                flavor_id=request.flavor_id,
                network_id=request.network_id,
                key_name=request.key_name,
                security_group_id=request.security_group_id,
                user_data=self._build_cloud_init_user_data(request.packages),
                metadata=self._build_server_metadata(
                    owner=owner,
                    owner_role=owner_role,
                    app_tag=request.app_tag,
                    request_id=request_id,
                ),
            )
        except OpenStackServiceError as exc:
            failure_details = exc.failure_details or self._build_failure_details(exc)
            self._record_audit_event(
                actor="system",
                role="system",
                action="provisioning_failed",
                resource_type="server",
                resource_id=None,
                request_id=request_id,
                status="failed",
                message=failure_details["user_message"],
            )
            record = self._build_request_record(
                request_id=request_id,
                request=request,
                policy_result=policy_result,
                status="draft",
                owner=owner,
                owner_role=owner_role,
                created_at=now,
                updated_at=self._now(),
                provisioning_error=failure_details["user_message"],
                failure_details=failure_details,
                activity_log=[
                    self._activity_entry(
                        action="submitted",
                        status="auto_approved",
                        message=(
                            "Request submitted and auto-approved by policy "
                            f"with packages: {self._format_packages(request)}"
                        ),
                        created_at=now,
                    ),
                    self._activity_entry(
                        action="draft_saved",
                        status="draft",
                        message=f"Provisioning deferred: {failure_details['user_message']}",
                        created_at=self._now(),
                    ),
                ],
            )
            logger.warning(
                "Saved VM request id='%s' as draft because provisioning failed: %s",
                request_id,
                exc,
            )
            return self._request_store.save_request(record)

        status = (
            "provisioned_notify"
            if policy_result.governance_decision == "auto_provision_notify"
            else "provisioned"
        )
        self._record_audit_event(
            actor="system",
            role="system",
            action="provisioning_succeeded",
            resource_type="server",
            resource_id=server.get("id"),
            request_id=request_id,
            status="succeeded",
            message=f"VM provisioned with server id '{server.get('id')}'",
        )
        record = self._build_request_record(
            request_id=request_id,
            request=request,
            policy_result=policy_result,
            status=status,
            owner=owner,
            owner_role=owner_role,
            created_at=now,
            updated_at=self._now(),
            server=server,
            activity_log=[
                self._activity_entry(
                    action="submitted",
                    status="auto_approved",
                    message=(
                        "Request submitted and auto-approved by policy "
                        f"with packages: {self._format_packages(request)}"
                    ),
                    created_at=now,
                ),
                self._activity_entry(
                    action="provisioned",
                    status=status,
                    message=f"VM provisioned with server id '{server.get('id')}'",
                    created_at=self._now(),
                ),
            ],
        )
        logger.info("Auto-provisioned VM request id='%s', status='%s'", request_id, status)
        return self._request_store.save_request(record)

    def list_vm_requests(self) -> list[dict[str, Any]]:
        return self._request_store.list_requests()

    def list_pending_vm_requests(self) -> list[dict[str, Any]]:
        return [
            record
            for record in self._request_store.list_requests()
            if record.get("status") == "approval_required"
        ]

    def get_vm_request(self, request_id: str) -> dict[str, Any]:
        return self._get_request_or_raise(request_id)

    def list_audit_events(self) -> list[dict[str, Any]]:
        return sorted(
            self._audit_store.list_events(),
            key=lambda event: event.get("timestamp", ""),
            reverse=True,
        )

    def get_request_timeline(self, request_id: str) -> list[dict[str, Any]]:
        self._get_request_or_raise(request_id)
        return [
            event
            for event in reversed(self.list_audit_events())
            if event.get("request_id") == request_id
        ]

    def approve_vm_request(
        self,
        request_id: str,
        *,
        actor: str = "admin",
        role: str = "admin",
    ) -> dict[str, Any]:
        record = self._get_request_or_raise(request_id)
        if record["status"] != "approval_required":
            raise OpenStackServiceError(
                f"Request '{request_id}' cannot be approved from status '{record['status']}'",
            )

        request = OpenStackVMRequest(**record["request"])
        self._record_audit_event(
            actor=actor,
            role=role,
            action="approved",
            resource_type="request",
            resource_id=request_id,
            request_id=request_id,
            status="approved",
            message="Request approved",
        )
        self._record_audit_event(
            actor=actor,
            role=role,
            action="provisioning_started",
            resource_type="server",
            resource_id=None,
            request_id=request_id,
            status="started",
            message="VM provisioning started after approval",
        )
        try:
            server = self.create_server(
                name=request.name,
                image_id=request.image_id,
                flavor_id=request.flavor_id,
                network_id=request.network_id,
                key_name=request.key_name,
                security_group_id=request.security_group_id,
                user_data=self._build_cloud_init_user_data(request.packages),
                metadata=self._build_server_metadata(
                    owner=record.get("owner"),
                    owner_role=record.get("owner_role"),
                    app_tag=request.app_tag,
                    request_id=request_id,
                ),
            )
        except OpenStackServiceError as exc:
            failure_details = exc.failure_details or self._build_failure_details(exc)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="provisioning_failed",
                resource_type="server",
                resource_id=None,
                request_id=request_id,
                status="failed",
                message=failure_details["user_message"],
            )
            self._request_store.update_request(
                request_id,
                {
                    "status": "draft",
                    "updated_at": self._now(),
                    "provisioning_error": failure_details["user_message"],
                    "failure_details": failure_details,
                },
            )
            raise

        self._record_audit_event(
            actor=actor,
            role=role,
            action="provisioning_succeeded",
            resource_type="server",
            resource_id=server.get("id"),
            request_id=request_id,
            status="succeeded",
            message=f"VM provisioned with server id '{server.get('id')}'",
        )
        updated = self._request_store.update_request(
            request_id,
            {
                "status": "approved",
                "server": server,
                "updated_at": self._now(),
                "activity_log": self._append_activity(
                    record,
                    action="approved",
                    status="approved",
                    message=f"Request approved and VM provisioned with server id '{server.get('id')}'",
                    actor=actor,
                ),
            },
        )
        logger.info("Approved and provisioned VM request id='%s'", request_id)
        return updated or record

    def reject_vm_request(
        self,
        request_id: str,
        request: OpenStackRejectRequest | None = None,
        *,
        actor: str = "admin",
        role: str = "admin",
    ) -> dict[str, Any]:
        record = self._get_request_or_raise(request_id)
        if record["status"] != "approval_required":
            raise OpenStackServiceError(
                f"Request '{request_id}' cannot be rejected from status '{record['status']}'",
            )

        self._record_audit_event(
            actor=actor,
            role=role,
            action="rejected",
            resource_type="request",
            resource_id=request_id,
            request_id=request_id,
            status="rejected",
            message=request.reason if request and request.reason else "Request rejected",
        )
        updated = self._request_store.update_request(
            request_id,
            {
                "status": "rejected",
                "rejection_reason": request.reason if request else None,
                "updated_at": self._now(),
                "activity_log": self._append_activity(
                    record,
                    action="rejected",
                    status="rejected",
                    message=request.reason
                    if request and request.reason
                    else "Request rejected without a reason",
                    actor=actor,
                ),
            },
        )
        logger.info("Rejected VM request id='%s'", request_id)
        return updated or record

    def delete_server(
        self,
        server_id: str,
        *,
        actor: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Deleting OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.delete_server(server, ignore_missing=False)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="server_deleted",
                resource_type="server",
                resource_id=server.id,
                request_id=self._find_request_id_for_server(server.id),
                status="accepted",
                message=f"Server '{server.name or server.id}' delete requested",
            )
            return self._serialize_lifecycle_response(
                server=server,
                action="delete",
            )
        except SDKException as exc:
            logger.exception("Failed to delete OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to delete OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def start_server(
        self,
        server_id: str,
        *,
        actor: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Starting OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.start_server(server)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="server_started",
                resource_type="server",
                resource_id=server.id,
                request_id=self._find_request_id_for_server(server.id),
                status="accepted",
                message=f"Server '{server.name or server.id}' start requested",
            )
            return self._serialize_lifecycle_response(
                server=server,
                action="start",
            )
        except SDKException as exc:
            logger.exception("Failed to start OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to start OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def stop_server(
        self,
        server_id: str,
        *,
        actor: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info("Stopping OpenStack server id='%s', name='%s'", server.id, server.name)
            connection.compute.stop_server(server)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="server_stopped",
                resource_type="server",
                resource_id=server.id,
                request_id=self._find_request_id_for_server(server.id),
                status="accepted",
                message=f"Server '{server.name or server.id}' stop requested",
            )
            return self._serialize_lifecycle_response(
                server=server,
                action="stop",
            )
        except SDKException as exc:
            logger.exception("Failed to stop OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to stop OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def reboot_server(
        self,
        server_id: str,
        reboot_type: str = "SOFT",
        *,
        actor: str | None = None,
        role: str | None = None,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            normalized_reboot_type = reboot_type.upper()
            logger.info(
                "Rebooting OpenStack server id='%s', name='%s', type='%s'",
                server.id,
                server.name,
                normalized_reboot_type,
            )
            connection.compute.reboot_server(server, reboot_type=normalized_reboot_type)
            self._record_audit_event(
                actor=actor,
                role=role,
                action="server_rebooted",
                resource_type="server",
                resource_id=server.id,
                request_id=self._find_request_id_for_server(server.id),
                status="accepted",
                message=f"Server '{server.name or server.id}' {normalized_reboot_type.lower()} reboot requested",
            )
            return self._serialize_lifecycle_response(
                server=server,
                action=f"{normalized_reboot_type.lower()}-reboot",
            )
        except SDKException as exc:
            logger.exception("Failed to reboot OpenStack server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to reboot OpenStack server: {self._format_openstack_error(exc)}",
            ) from exc

    def attach_floating_ip(
        self,
        *,
        server_id: str,
        floating_ip: str | None = None,
    ) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            floating_ip_resource = (
                self._find_floating_ip_by_address(connection, floating_ip)
                if floating_ip
                else connection.network.create_ip(
                    floating_network_id=self._resolve_public_network(connection).id,
                )
            )
            address = floating_ip_resource.floating_ip_address

            logger.info(
                "Attaching OpenStack floating IP '%s' to server id='%s'",
                address,
                server.id,
            )
            connection.compute.add_floating_ip_to_server(server, address)
            return {
                "server_id": server.id,
                "floating_ip": address,
                "action": "attach",
                "status": "accepted",
            }
        except SDKException as exc:
            logger.exception("Failed to attach floating IP to server id='%s'", server_id)
            raise OpenStackServiceError(
                f"Failed to attach floating IP: {self._format_openstack_error(exc)}",
            ) from exc

    def detach_floating_ip(self, *, server_id: str, floating_ip: str) -> dict[str, Any]:
        try:
            connection = self.get_connection()
            server = connection.compute.get_server(server_id)
            logger.info(
                "Detaching OpenStack floating IP '%s' from server id='%s'",
                floating_ip,
                server.id,
            )
            connection.compute.remove_floating_ip_from_server(server, floating_ip)
            return {
                "server_id": server.id,
                "floating_ip": floating_ip,
                "action": "detach",
                "status": "accepted",
            }
        except SDKException as exc:
            logger.exception(
                "Failed to detach floating IP '%s' from server id='%s'",
                floating_ip,
                server_id,
            )
            raise OpenStackServiceError(
                f"Failed to detach floating IP: {self._format_openstack_error(exc)}",
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
            failure_details = self._build_failure_details(exc)
            raise OpenStackServiceError(
                failure_details["user_message"],
                failure_details=failure_details,
            ) from exc

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

    def _get_request_or_raise(self, request_id: str) -> dict[str, Any]:
        record = self._request_store.get_request(request_id)
        if not record:
            raise OpenStackRequestNotFoundError(f"Request '{request_id}' was not found")

        return record

    def _find_request_id_for_server(self, server_id: str) -> str | None:
        for record in self._request_store.list_requests():
            server = record.get("server") or {}
            if server.get("id") == server_id:
                return record.get("id")

        return None

    @staticmethod
    def _build_request_record(
        *,
        request_id: str,
        request: OpenStackVMRequest,
        policy_result: Any,
        status: str,
        created_at: str,
        updated_at: str,
        owner: str | None = None,
        owner_role: str | None = None,
        server: dict[str, Any] | None = None,
        provisioning_error: str | None = None,
        failure_details: dict[str, Any] | None = None,
        activity_log: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": request_id,
            "status": status,
            "owner": owner,
            "owner_role": owner_role,
            "request": request.model_dump(),
            "policy": policy_result.model_dump(),
            "estimated_cost": policy_result.estimated_cost,
            "risk_level": policy_result.risk_level,
            "governance_score": policy_result.governance_score,
            "approval_decision": policy_result.approval_decision,
            "cloud_init_generated": bool(request.packages),
            "selected_packages": request.packages,
            "server": server,
            "rejection_reason": None,
            "provisioning_error": provisioning_error,
            "failure_details": failure_details,
            "activity_log": activity_log or [],
            "expires_at": OpenStackService._calculate_expires_at(created_at, request),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    def _append_activity(
        self,
        record: dict[str, Any],
        *,
        action: str,
        status: str,
        message: str,
        actor: str = "admin",
    ) -> list[dict[str, Any]]:
        return [
            *record.get("activity_log", []),
            self._activity_entry(
                action=action,
                status=status,
                message=message,
                created_at=self._now(),
                actor=actor,
            ),
        ]

    def _record_audit_event(
        self,
        *,
        actor: str | None,
        role: str | None,
        action: str,
        resource_type: str,
        resource_id: str | None,
        request_id: str | None,
        status: str,
        message: str,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid4()),
            "timestamp": self._now(),
            "actor": actor or "system",
            "role": role or "system",
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "request_id": request_id,
            "status": status,
            "message": message,
        }
        return self._audit_store.save_event(event)

    @staticmethod
    def _activity_entry(
        *,
        action: str,
        status: str,
        message: str,
        created_at: str,
        actor: str = "system",
    ) -> dict[str, Any]:
        return {
            "action": action,
            "status": status,
            "message": message,
            "created_at": created_at,
            "actor": actor,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _calculate_expires_at(created_at: str, request: OpenStackVMRequest) -> str | None:
        if request.lifetime == "permanent" or request.lifetime_days == 0:
            return None

        created_datetime = datetime.fromisoformat(created_at)
        return (created_datetime + timedelta(days=request.lifetime_days)).isoformat()

    @staticmethod
    def _format_lifetime(request: OpenStackVMRequest) -> str:
        if request.lifetime == "permanent" or request.lifetime_days == 0:
            return "Permanent"

        return {
            1: "1 Day",
            7: "7 Days",
            30: "30 Days",
            90: "90 Days",
        }.get(request.lifetime_days, f"{request.lifetime_days} Days")

    @staticmethod
    def _format_packages(request: OpenStackVMRequest) -> str:
        return ", ".join(request.packages) if request.packages else "None"

    @staticmethod
    def _build_cloud_init_user_data(packages: list[str]) -> str | None:
        package_map = {
            "Docker": ["docker.io"],
            "Podman": ["podman"],
            "Nginx": ["nginx"],
            "Apache": ["apache2"],
            "Node.js": ["nodejs", "npm"],
            "Python": ["python3", "python3-pip", "python3-venv"],
            "PostgreSQL": ["postgresql-client"],
            "MySQL": ["mysql-client"],
            "Git": ["git"],
            "Ansible": ["ansible"],
        }
        service_commands = {
            "Docker": ["systemctl enable --now docker"],
            "Nginx": ["systemctl enable --now nginx"],
            "Apache": ["systemctl enable --now apache2"],
        }

        os_packages: list[str] = []
        runcmd: list[str] = []
        for package in packages:
            for os_package in package_map.get(package, []):
                if os_package not in os_packages:
                    os_packages.append(os_package)
            for command in service_commands.get(package, []):
                if command not in runcmd:
                    runcmd.append(command)

        if not os_packages and not runcmd:
            return None

        lines = [
            "#cloud-config",
            "package_update: true",
            "package_upgrade: false",
            "packages:",
            *[f"  - {package}" for package in os_packages],
        ]

        if runcmd:
            lines.extend(["runcmd:", *[f"  - {command}" for command in runcmd]])

        return "\n".join(lines) + "\n"

    @staticmethod
    def _validate_network_id(network_id: str) -> None:
        if not network_id or not network_id.strip():
            raise OpenStackValidationError("Network ID is required. Select a network by id.")

        if network_id.startswith("auto:"):
            raise OpenStackValidationError(
                "Network ID is required before provisioning. The automatic network placeholder cannot be used.",
            )

        try:
            UUID(network_id)
        except ValueError as exc:
            raise OpenStackValidationError(
                f"Invalid network_id '{network_id}'. Select a network by id, not by name.",
            ) from exc

    @staticmethod
    def _format_network_label(network: Any) -> str:
        name = getattr(network, "name", None)
        network_id = getattr(network, "id", None)
        return f"{name} ({network_id})" if name else str(network_id)

    @staticmethod
    def _extract_resource_id(resource: Any) -> str | None:
        if resource is None:
            return None

        if isinstance(resource, dict):
            return resource.get("id") or resource.get("image_id") or resource.get("imageId")

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
            "metadata": getattr(server, "metadata", None),
            "failure_details": OpenStackService._extract_server_failure_details(server),
        }

    @staticmethod
    def _build_server_metadata(
        *,
        owner: str | None,
        owner_role: str | None,
        app_tag: str | None,
        request_id: str | None = None,
    ) -> dict[str, str]:
        metadata = {
            "managed_by": "openstack-self-service",
        }
        if owner:
            metadata["owner"] = owner
        if owner_role:
            metadata["owner_role"] = owner_role
        if app_tag:
            metadata["app_tag"] = app_tag
        if request_id:
            metadata["request_id"] = request_id

        return metadata

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
    def _serialize_floating_ip(floating_ip: Any) -> dict[str, Any]:
        return {
            "id": floating_ip.id,
            "floating_ip_address": getattr(floating_ip, "floating_ip_address", None),
            "status": getattr(floating_ip, "status", None),
            "floating_network_id": getattr(floating_ip, "floating_network_id", None),
            "port_id": getattr(floating_ip, "port_id", None),
            "fixed_ip_address": getattr(floating_ip, "fixed_ip_address", None),
            "router_id": getattr(floating_ip, "router_id", None),
            "project_id": getattr(floating_ip, "project_id", None),
        }

    @staticmethod
    def _serialize_snapshot(snapshot: Any) -> dict[str, Any]:
        metadata = OpenStackService._extract_metadata(snapshot)
        return {
            "id": snapshot.id,
            "name": getattr(snapshot, "name", None),
            "status": getattr(snapshot, "status", None),
            "created_at": OpenStackService._serialize_value(getattr(snapshot, "created_at", None)),
            "size": getattr(snapshot, "size", None),
            "disk_format": getattr(snapshot, "disk_format", None),
            "visibility": getattr(snapshot, "visibility", None),
            "server_id": OpenStackService._extract_snapshot_server_id(snapshot),
            "description": metadata.get("description") or getattr(snapshot, "description", None),
            "metadata": metadata,
        }

    @staticmethod
    def _snapshot_belongs_to_server(snapshot: Any, server_id: str) -> bool:
        return OpenStackService._extract_snapshot_server_id(snapshot) == server_id

    @staticmethod
    def _extract_snapshot_server_id(snapshot: Any) -> str | None:
        metadata = OpenStackService._extract_metadata(snapshot)
        image_location = metadata.get("image_location")
        return (
            metadata.get("cms_snapshot_server_id")
            or metadata.get("instance_uuid")
            or metadata.get("server_id")
            or (image_location.removeprefix("snapshot/") if isinstance(image_location, str) else None)
        )

    @staticmethod
    def _extract_metadata(resource: Any) -> dict[str, Any]:
        metadata = getattr(resource, "metadata", None)
        if isinstance(metadata, dict):
            return metadata

        properties = getattr(resource, "properties", None)
        if isinstance(properties, dict):
            return properties

        if isinstance(resource, dict):
            for key in ("metadata", "properties"):
                value = resource.get(key)
                if isinstance(value, dict):
                    return value

        return {}

    @staticmethod
    def _extract_primary_server_network_id(connection: Connection, server: Any) -> str | None:
        try:
            for interface in connection.compute.server_interfaces(server):
                network_id = getattr(interface, "net_id", None) or getattr(interface, "network_id", None)
                if network_id:
                    return network_id
        except SDKException:
            logger.warning("Failed to resolve server network from interfaces", exc_info=True)

        return None

    @staticmethod
    def _extract_console_url(console: Any) -> str | None:
        if not console:
            return None

        if isinstance(console, dict):
            console_payload = console.get("remote_console") or console.get("console") or console
            if isinstance(console_payload, dict):
                return console_payload.get("url")
            return None

        url = getattr(console, "url", None)
        if url:
            return url

        remote_console = getattr(console, "remote_console", None)
        if isinstance(remote_console, dict):
            return remote_console.get("url")

        nested_console = getattr(console, "console", None)
        if isinstance(nested_console, dict):
            return nested_console.get("url")

        return None

    @staticmethod
    def _extract_server_ips(addresses: Any) -> tuple[str | None, str | None]:
        if not isinstance(addresses, dict):
            return None, None

        flattened: list[Any] = []
        for value in addresses.values():
            if isinstance(value, list):
                flattened.extend(value)
            else:
                flattened.append(value)

        private_ip: str | None = None
        floating_ip: str | None = None
        for item in flattened:
            if isinstance(item, dict):
                address = item.get("addr")
                ip_type = item.get("OS-EXT-IPS:type")
            else:
                address = str(item) if item else None
                ip_type = None

            if not address:
                continue

            if ip_type == "floating":
                floating_ip = floating_ip or address
            elif ip_type == "fixed":
                private_ip = private_ip or address
            elif OpenStackService._is_private_ip(address):
                private_ip = private_ip or address
            else:
                floating_ip = floating_ip or address

        return private_ip, floating_ip

    def _suggest_ssh_username(self, server: Any) -> str:
        metadata = getattr(server, "metadata", None) or {}
        image_name = str(metadata.get("image_name") or metadata.get("image") or "").lower()
        image = getattr(server, "image", None)
        if isinstance(image, dict):
            image_name = image_name or str(image.get("name") or "").lower()
        elif image is not None:
            image_name = image_name or str(getattr(image, "name", "") or "").lower()

        if "cirros" in image_name:
            return "cirros"

        return self._settings.ssh_default_username

    @staticmethod
    def _is_private_ip(ip_address: str) -> bool:
        return (
            ip_address.startswith("10.")
            or ip_address.startswith("192.168.")
            or any(ip_address.startswith(f"172.{index}.") for index in range(16, 32))
        )

    @staticmethod
    def _resolve_public_network(
        connection: Connection,
        public_network_id: str | None = None,
    ) -> Any:
        if public_network_id:
            return connection.network.find_network(public_network_id, ignore_missing=False)

        public_network = connection.network.find_network("public", ignore_missing=True)
        if public_network:
            return public_network

        for network in connection.network.networks():
            if getattr(network, "is_router_external", False):
                return network

        raise OpenStackServiceError(
            "Failed to resolve public network: no network named 'public' or external network found",
        )

    @staticmethod
    def _find_floating_ip_by_address(connection: Connection, floating_ip: str) -> Any:
        for floating_ip_resource in connection.network.ips():
            if floating_ip_resource.floating_ip_address == floating_ip:
                return floating_ip_resource

        raise OpenStackServiceError(f"Floating IP not found: {floating_ip}")

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

    @staticmethod
    def _extract_server_failure_details(server: Any) -> dict[str, Any] | None:
        status = str(getattr(server, "status", "") or "").upper()
        fault = getattr(server, "fault", None)
        if status != "ERROR" and not fault:
            return None

        raw_error = OpenStackService._serialize_fault(fault) if fault else None
        technical_reason = OpenStackService._fault_message(raw_error) or "Server entered ERROR state"
        return OpenStackService._translate_failure(
            technical_reason=technical_reason,
            raw_error=raw_error,
        )

    @staticmethod
    def _build_failure_details(exc: Exception) -> dict[str, Any]:
        technical_reason = OpenStackService._format_openstack_error(exc) if isinstance(exc, SDKException) else str(exc)
        raw_error = {
            "type": exc.__class__.__name__,
            "message": technical_reason,
        }
        status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
        if status_code:
            raw_error["status_code"] = status_code

        details = getattr(exc, "details", None)
        if details:
            raw_error["details"] = details

        return OpenStackService._translate_failure(
            technical_reason=technical_reason,
            raw_error=raw_error,
        )

    @staticmethod
    def _translate_failure(
        *,
        technical_reason: str,
        raw_error: Any,
    ) -> dict[str, Any]:
        normalized = technical_reason.lower()
        user_message = "OpenStack could not provision this VM."
        suggested_action = "Review the technical details or contact your cloud administrator."

        if "no valid host" in normalized:
            user_message = "Insufficient compute resources."
            suggested_action = "Try a smaller flavor or ask an administrator to add compute capacity."
        elif "image" in normalized and ("not found" in normalized or "could not be found" in normalized):
            user_message = "Selected image is unavailable."
            suggested_action = "Choose another image and submit the request again."
        elif "flavor" in normalized and ("not found" in normalized or "could not be found" in normalized):
            user_message = "Selected flavor is unavailable."
            suggested_action = "Choose another flavor and submit the request again."
        elif "network" in normalized and ("not found" in normalized or "could not be found" in normalized):
            user_message = "Selected network is unavailable."
            suggested_action = "Choose another network or ask an administrator to verify network access."
        elif "quota" in normalized or "overlimit" in normalized or "exceeded" in normalized:
            user_message = "Project quota exceeded."
            suggested_action = "Request a smaller VM or ask an administrator to increase project quota."
        elif (
            "connection" in normalized
            or "connect" in normalized
            or "timeout" in normalized
            or "timed out" in normalized
            or "unreachable" in normalized
            or "failed to create openstack connection" in normalized
        ):
            user_message = "OpenStack provider is unreachable."
            suggested_action = "Check OpenStack connectivity and try again."

        return {
            "user_message": user_message,
            "technical_reason": technical_reason,
            "suggested_action": suggested_action,
            "raw_error": raw_error,
        }

    @staticmethod
    def _serialize_fault(fault: Any) -> Any:
        if fault is None:
            return None

        if isinstance(fault, dict):
            return fault

        if hasattr(fault, "to_dict"):
            return fault.to_dict()

        return {
            key: OpenStackService._serialize_value(value)
            for key, value in vars(fault).items()
            if not key.startswith("_")
        } or str(fault)

    @staticmethod
    def _fault_message(raw_error: Any) -> str | None:
        if isinstance(raw_error, dict):
            for key in ("message", "faultstring", "details", "code"):
                value = raw_error.get(key)
                if value:
                    return str(value)

        if raw_error:
            return str(raw_error)

        return None
