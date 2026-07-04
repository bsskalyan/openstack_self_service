import asyncio
import logging
import socket
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status

from app.core.config import get_settings
from app.core.user_context import (
    UNAUTHORIZED_MESSAGE,
    CurrentUser,
    VALID_ROLES,
    ensure_role,
    get_current_user,
)
from app.providers.openstack.schemas import (
    OpenStackAuditEvent,
    OpenStackCreateFloatingIPRequest,
    OpenStackCreateServerRequest,
    OpenStackCreateServerResponse,
    OpenStackCreateSnapshotRequest,
    OpenStackAttachFloatingIPRequest,
    OpenStackFlavorResponse,
    OpenStackFloatingIPActionResponse,
    OpenStackFloatingIPResponse,
    OpenStackImageResponse,
    OpenStackKeypairResponse,
    OpenStackNetworkResponse,
    OpenStackRebootServerRequest,
    OpenStackRejectRequest,
    OpenStackSecurityGroupResponse,
    OpenStackServerConsoleResponse,
    OpenStackServerLifecycleResponse,
    OpenStackServerResponse,
    OpenStackServerSshConsoleResponse,
    OpenStackSnapshotActionResponse,
    OpenStackSnapshotResponse,
    OpenStackStatusResponse,
    OpenStackVMRequest,
    OpenStackVMRequestRecord,
    OpenStackVMRequestResponse,
)
from app.providers.openstack.provider import OpenStackProvider
from app.providers.openstack.service import (
    OpenStackConfigurationError,
    OpenStackRequestNotFoundError,
    OpenStackService,
    OpenStackServiceError,
    OpenStackValidationError,
)


logger = logging.getLogger(__name__)


router = APIRouter()

WRITE_ROLES = {"admin", "engineer"}
ADMIN_ROLES = {"admin"}


@lru_cache
def get_openstack_service() -> OpenStackService:
    return OpenStackService(get_settings())


@lru_cache
def get_openstack_provider() -> OpenStackProvider:
    return OpenStackProvider(get_openstack_service())


def handle_openstack_error(operation: str, exc: OpenStackServiceError) -> HTTPException:
    detail: str | dict[str, Any] = exc.failure_details or str(exc)

    if isinstance(exc, OpenStackRequestNotFoundError):
        logger.warning("%s failed because the request was not found: %s", operation, exc)
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail,
        )

    if isinstance(exc, OpenStackConfigurationError):
        logger.warning("%s failed due to OpenStack configuration: %s", operation, exc)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail,
        )

    if isinstance(exc, OpenStackValidationError):
        logger.warning("%s failed due to invalid request data: %s", operation, exc)
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    logger.warning("%s failed: %s", operation, exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=detail,
    )


def is_request_visible_to_user(record: dict[str, Any], user: CurrentUser) -> bool:
    if user.is_admin:
        return True

    owner = record.get("owner")
    if owner:
        return owner == user.name

    return user.role == "engineer"


def assert_request_visible_to_user(record: dict[str, Any], user: CurrentUser) -> None:
    if not is_request_visible_to_user(record, user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=UNAUTHORIZED_MESSAGE,
        )


def assert_server_manage_allowed(
    server_id: str,
    user: CurrentUser,
    openstack_service: OpenStackService,
) -> None:
    if user.is_admin:
        return

    for record in openstack_service.list_vm_requests():
        server = record.get("server") or {}
        if server.get("id") != server_id:
            continue

        if is_request_visible_to_user(record, user):
            return

        metadata = server.get("metadata") or {}
        if metadata.get("owner") == user.name:
            return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=UNAUTHORIZED_MESSAGE,
    )


def is_audit_event_visible_to_user(event: dict[str, Any], user: CurrentUser) -> bool:
    if user.is_admin:
        return True

    if user.role == "viewer":
        return event.get("resource_type") in {"catalog", "server"} and event.get("status") in {
            "accepted",
            "succeeded",
        }

    if event.get("actor") == user.name:
        return True

    request_id = event.get("request_id")
    if request_id:
        try:
            record = get_openstack_service().get_vm_request(request_id)
        except OpenStackServiceError:
            return False

        return is_request_visible_to_user(record, user)

    return False


async def _bridge_ssh_session(
    *,
    websocket: WebSocket,
    openstack_service: OpenStackService,
    current_user: CurrentUser,
    server_id: str,
    session: dict[str, Any],
) -> None:
    settings = get_settings()
    ssh_key_path = Path(settings.ssh_private_key_path or "")
    if not settings.ssh_private_key_path or not ssh_key_path.exists():
        await websocket.send_text(
            "\r\nCLI console is not configured. Set SSH_PRIVATE_KEY_PATH on the backend.\r\n",
        )
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    client: Any = None
    channel: Any = None
    reader_task: asyncio.Task[None] | None = None
    session_opened = False

    try:
        await websocket.send_text(
            f"\r\nConnecting to {session['username']}@{session['host']}...\r\n",
        )
        client, channel = await asyncio.to_thread(
            _open_paramiko_shell,
            host=session["host"],
            username=session["username"],
            key_path=str(ssh_key_path),
            known_hosts_path=settings.ssh_known_hosts_path,
        )
        session_opened = True
        openstack_service.record_console_audit_event(
            actor=current_user.name,
            role=current_user.role,
            action="cli_console_opened",
            server_id=server_id,
            status="succeeded",
            message="CLI console session opened.",
        )
        await websocket.send_text("\r\nConnected. Private keys and passwords are never exposed.\r\n\r\n")
        reader_task = asyncio.create_task(_stream_ssh_output(channel, websocket))

        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=settings.ssh_session_timeout_seconds,
                )
            except TimeoutError:
                await websocket.send_text("\r\nSession timed out due to inactivity.\r\n")
                break
            except WebSocketDisconnect:
                break

            if channel.closed:
                break
            await asyncio.to_thread(channel.send, message)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - map SSH library errors to friendly terminal text.
        logger.exception("SSH console session failed for server id='%s'", server_id)
        await websocket.send_text(_friendly_ssh_error(exc))
    finally:
        if reader_task:
            reader_task.cancel()
        if channel is not None:
            await asyncio.to_thread(channel.close)
        if client is not None:
            await asyncio.to_thread(client.close)
        if session_opened:
            openstack_service.record_console_audit_event(
                actor=current_user.name,
                role=current_user.role,
                action="cli_console_closed",
                server_id=server_id,
                status="succeeded",
                message="CLI console session closed.",
            )
        try:
            await websocket.close()
        except RuntimeError:
            pass


def _open_paramiko_shell(
    *,
    host: str,
    username: str,
    key_path: str,
    known_hosts_path: str | None,
) -> tuple[Any, Any]:
    try:
        import paramiko
    except ImportError as exc:  # pragma: no cover - depends on deployment environment.
        raise RuntimeError("Paramiko is not installed. Install backend requirements.") from exc

    client = paramiko.SSHClient()
    client.load_system_host_keys()
    if known_hosts_path:
        client.load_host_keys(known_hosts_path)
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    client.connect(
        hostname=host,
        port=22,
        username=username,
        key_filename=key_path,
        timeout=12,
        banner_timeout=12,
        auth_timeout=12,
        look_for_keys=False,
        allow_agent=False,
    )
    channel = client.invoke_shell(term="xterm-256color", width=120, height=32)
    channel.settimeout(0.2)
    return client, channel


async def _stream_ssh_output(channel: Any, websocket: WebSocket) -> None:
    while not channel.closed:
        try:
            data = await asyncio.to_thread(channel.recv, 4096)
        except (TimeoutError, socket.timeout):
            continue
        except Exception:
            break

        if not data:
            break
        await websocket.send_text(data.decode("utf-8", errors="replace"))


def _terminal_error_message(exc: OpenStackServiceError) -> str:
    detail = exc.failure_details or {}
    message = detail.get("user_message") or str(exc)
    suggestion = detail.get("suggested_action")
    return f"\r\n{message}\r\n{suggestion or ''}\r\n"


def _friendly_ssh_error(exc: Exception) -> str:
    error_text = str(exc).lower()
    if "paramiko is not installed" in error_text:
        return "\r\nCLI console backend is missing Paramiko. Install backend requirements.\r\n"
    if "authentication failed" in error_text or "not a valid" in error_text:
        return "\r\nAuthentication failed. Verify SSH_PRIVATE_KEY_PATH and VM keypair.\r\n"
    if "server not found in known_hosts" in error_text or "not found in known_hosts" in error_text:
        return "\r\nSSH host key is not trusted. Add the VM host key to SSH_KNOWN_HOSTS_PATH.\r\n"
    if "unable to connect" in error_text or "timed out" in error_text or "timeout" in error_text:
        return "\r\nSSH port unavailable. Verify security group rules and VM reachability.\r\n"
    if "no existing session" in error_text:
        return "\r\nSSH session could not be opened on the VM.\r\n"
    return "\r\nCLI console connection failed. Verify VM SSH reachability and key configuration.\r\n"


@router.get(
    "/status",
    response_model=OpenStackStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_openstack_module_status(
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
) -> dict[str, Any]:
    try:
        cloud_info = openstack_provider.status()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack status check", exc) from exc

    return {"module": "openstack", "status": "connected", "cloud": cloud_info}


@router.get(
    "/images",
    response_model=list[OpenStackImageResponse],
    status_code=status.HTTP_200_OK,
)
async def list_images(
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
) -> list[dict[str, Any]]:
    try:
        return openstack_provider.list_images()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack image listing", exc) from exc


@router.get(
    "/flavors",
    response_model=list[OpenStackFlavorResponse],
    status_code=status.HTTP_200_OK,
)
async def list_flavors(
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
) -> list[dict[str, Any]]:
    try:
        return openstack_provider.list_flavors()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack flavor listing", exc) from exc


@router.get(
    "/networks",
    response_model=list[OpenStackNetworkResponse],
    status_code=status.HTTP_200_OK,
)
async def list_networks(
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
) -> list[dict[str, Any]]:
    try:
        return openstack_provider.list_networks()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack network listing", exc) from exc


@router.get(
    "/security-groups",
    response_model=list[OpenStackSecurityGroupResponse],
    status_code=status.HTTP_200_OK,
)
async def list_security_groups(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_security_groups()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack security group listing", exc) from exc


@router.get(
    "/keypairs",
    response_model=list[OpenStackKeypairResponse],
    status_code=status.HTTP_200_OK,
)
async def list_keypairs(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_keypairs()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack keypair listing", exc) from exc


@router.get(
    "/floating-ips",
    response_model=list[OpenStackFloatingIPResponse],
    status_code=status.HTTP_200_OK,
)
async def list_floating_ips(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_floating_ips()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP listing", exc) from exc


@router.post(
    "/floating-ips",
    response_model=OpenStackFloatingIPResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_floating_ip(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: OpenStackCreateFloatingIPRequest | None = Body(default=None),
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    try:
        return openstack_service.create_floating_ip(
            public_network_id=request.public_network_id if request else None,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP creation", exc) from exc


@router.post(
    "/requests",
    response_model=OpenStackVMRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_vm_request(
    request: OpenStackVMRequest,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    try:
        return openstack_service.submit_vm_request(
            request,
            owner=current_user.name,
            owner_role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack VM request submission", exc) from exc


@router.get(
    "/requests",
    response_model=list[OpenStackVMRequestRecord],
    status_code=status.HTTP_200_OK,
)
async def list_vm_requests(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    ensure_role(current_user, WRITE_ROLES)
    records = openstack_service.list_vm_requests()
    if current_user.is_admin:
        return records

    return [record for record in records if is_request_visible_to_user(record, current_user)]


@router.get(
    "/requests/pending",
    response_model=list[OpenStackVMRequestRecord],
    status_code=status.HTTP_200_OK,
)
async def list_pending_vm_requests(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    ensure_role(current_user, ADMIN_ROLES)
    return openstack_service.list_pending_vm_requests()


@router.get(
    "/audit",
    response_model=list[OpenStackAuditEvent],
    status_code=status.HTTP_200_OK,
)
async def list_audit_events(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    return [
        event
        for event in openstack_service.list_audit_events()
        if is_audit_event_visible_to_user(event, current_user)
    ]


@router.get(
    "/requests/{request_id}/timeline",
    response_model=list[OpenStackAuditEvent],
    status_code=status.HTTP_200_OK,
)
async def get_request_timeline(
    request_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[dict[str, Any]]:
    try:
        record = openstack_service.get_vm_request(request_id)
        assert_request_visible_to_user(record, current_user)
        return [
            event
            for event in openstack_service.get_request_timeline(request_id)
            if is_audit_event_visible_to_user(event, current_user)
        ]
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack request timeline lookup", exc) from exc


@router.get(
    "/requests/{request_id}",
    response_model=OpenStackVMRequestRecord,
    status_code=status.HTTP_200_OK,
)
async def get_vm_request(
    request_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    try:
        record = openstack_service.get_vm_request(request_id)
        assert_request_visible_to_user(record, current_user)
        return record
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack VM request lookup", exc) from exc


@router.post(
    "/requests/{request_id}/approve",
    response_model=OpenStackVMRequestRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def approve_vm_request(
    request_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, ADMIN_ROLES)
    try:
        return openstack_service.approve_vm_request(
            request_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack VM request approval", exc) from exc


@router.post(
    "/requests/{request_id}/reject",
    response_model=OpenStackVMRequestRecord,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reject_vm_request(
    request_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: OpenStackRejectRequest | None = Body(default=None),
) -> dict[str, Any]:
    ensure_role(current_user, ADMIN_ROLES)
    try:
        return openstack_service.reject_vm_request(
            request_id,
            request,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack VM request rejection", exc) from exc


@router.get(
    "/servers",
    response_model=list[OpenStackServerResponse],
    status_code=status.HTTP_200_OK,
)
async def list_servers(
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
) -> list[dict[str, Any]]:
    try:
        return openstack_provider.list_servers()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server listing", exc) from exc


@router.post(
    "/servers",
    response_model=OpenStackCreateServerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_server(
    request: OpenStackCreateServerRequest,
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    try:
        return openstack_provider.create_server(
            name=request.name,
            image_id=request.image_id,
            flavor_id=request.flavor_id,
            network_id=request.network_id,
            key_name=request.key_name,
            security_group_id=request.security_group_id,
            metadata={
                "managed_by": "openstack-self-service",
                "owner": current_user.name,
                "owner_role": current_user.role,
            },
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server creation", exc) from exc


@router.get(
    "/servers/{server_id}/console",
    response_model=OpenStackServerConsoleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_server_console(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.get_server_console(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server console", exc) from exc


@router.get(
    "/servers/{server_id}/ssh-console",
    response_model=OpenStackServerSshConsoleResponse,
    status_code=status.HTTP_200_OK,
)
async def get_server_ssh_console(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.get_server_ssh_console_metadata(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack SSH console metadata", exc) from exc


@router.get(
    "/servers/{server_id}/snapshots",
    response_model=list[OpenStackSnapshotResponse],
    status_code=status.HTTP_200_OK,
)
async def list_server_snapshots(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_server_snapshots(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack snapshot listing", exc) from exc


@router.post(
    "/servers/{server_id}/snapshots",
    response_model=OpenStackSnapshotResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_server_snapshot(
    server_id: str,
    request: OpenStackCreateSnapshotRequest,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.create_server_snapshot(
            server_id,
            name=request.name,
            description=request.description,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack snapshot creation", exc) from exc


@router.delete(
    "/snapshots/{snapshot_id}",
    response_model=OpenStackSnapshotActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_snapshot(
    snapshot_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    try:
        snapshot_server_id = openstack_service.get_snapshot_server_id(snapshot_id)
        if snapshot_server_id:
            assert_server_manage_allowed(snapshot_server_id, current_user, openstack_service)
        elif not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=UNAUTHORIZED_MESSAGE,
            )
        return openstack_service.delete_snapshot(
            snapshot_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack snapshot deletion", exc) from exc


@router.post(
    "/servers/{server_id}/restore-snapshot/{snapshot_id}",
    response_model=OpenStackSnapshotActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def restore_server_snapshot(
    server_id: str,
    snapshot_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.restore_server_snapshot(
            server_id,
            snapshot_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack snapshot restore", exc) from exc


@router.websocket("/servers/{server_id}/ssh/ws")
async def open_server_ssh_websocket(
    websocket: WebSocket,
    server_id: str,
    user_name: Annotated[str | None, Query(alias="user")] = None,
    user_role: Annotated[str | None, Query(alias="role")] = None,
) -> None:
    role = (user_role or "viewer").strip().lower()
    if role not in VALID_ROLES:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    current_user = CurrentUser(name=(user_name or "viewer").strip() or "viewer", role=role)  # type: ignore[arg-type]
    openstack_service = get_openstack_service()

    try:
        ensure_role(current_user, WRITE_ROLES)
        assert_server_manage_allowed(server_id, current_user, openstack_service)
        session = openstack_service.prepare_ssh_console_session(server_id)
    except HTTPException:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    except OpenStackServiceError as exc:
        await websocket.accept()
        await websocket.send_text(_terminal_error_message(exc))
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return

    await websocket.accept()
    await _bridge_ssh_session(
        websocket=websocket,
        openstack_service=openstack_service,
        current_user=current_user,
        server_id=server_id,
        session=session,
    )


@router.delete(
    "/servers/{server_id}",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_server(
    server_id: str,
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_provider.service)
    try:
        return openstack_provider.delete_server(
            server_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server deletion", exc) from exc


@router.post(
    "/servers/{server_id}/start",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_server(
    server_id: str,
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_provider.service)
    try:
        return openstack_provider.start_server(
            server_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server start", exc) from exc


@router.post(
    "/servers/{server_id}/stop",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_server(
    server_id: str,
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_provider.service)
    try:
        return openstack_provider.stop_server(
            server_id,
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server stop", exc) from exc


@router.post(
    "/servers/{server_id}/reboot",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reboot_server(
    server_id: str,
    openstack_provider: Annotated[OpenStackProvider, Depends(get_openstack_provider)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: OpenStackRebootServerRequest | None = Body(default=None),
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_provider.service)
    try:
        return openstack_provider.reboot_server(
            server_id,
            reboot_type=request.reboot_type if request else "SOFT",
            actor=current_user.name,
            role=current_user.role,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server reboot", exc) from exc


@router.post(
    "/servers/{server_id}/floating-ip",
    response_model=OpenStackFloatingIPActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def attach_floating_ip(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    request: OpenStackAttachFloatingIPRequest | None = Body(default=None),
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.attach_floating_ip(
            server_id=server_id,
            floating_ip=request.floating_ip if request else None,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP attach", exc) from exc


@router.delete(
    "/servers/{server_id}/floating-ip/{floating_ip}",
    response_model=OpenStackFloatingIPActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def detach_floating_ip(
    server_id: str,
    floating_ip: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    ensure_role(current_user, WRITE_ROLES)
    assert_server_manage_allowed(server_id, current_user, openstack_service)
    try:
        return openstack_service.detach_floating_ip(
            server_id=server_id,
            floating_ip=floating_ip,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP detach", exc) from exc
