import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.config import get_settings
from app.core.user_context import (
    UNAUTHORIZED_MESSAGE,
    CurrentUser,
    ensure_role,
    get_current_user,
)
from app.providers.openstack.schemas import (
    OpenStackCreateServerRequest,
    OpenStackCreateServerResponse,
    OpenStackAttachFloatingIPRequest,
    OpenStackCreateFloatingIPRequest,
    OpenStackFlavorResponse,
    OpenStackFloatingIPActionResponse,
    OpenStackFloatingIPResponse,
    OpenStackImageResponse,
    OpenStackKeypairResponse,
    OpenStackNetworkResponse,
    OpenStackRebootServerRequest,
    OpenStackRejectRequest,
    OpenStackSecurityGroupResponse,
    OpenStackServerLifecycleResponse,
    OpenStackServerResponse,
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
    if isinstance(exc, OpenStackRequestNotFoundError):
        logger.warning("%s failed because the request was not found: %s", operation, exc)
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )

    if isinstance(exc, OpenStackConfigurationError):
        logger.warning("%s failed due to OpenStack configuration: %s", operation, exc)
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )

    logger.warning("%s failed: %s", operation, exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=str(exc),
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
        return openstack_service.approve_vm_request(request_id, actor=current_user.name)
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
        return openstack_service.reject_vm_request(request_id, request, actor=current_user.name)
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
        return openstack_provider.delete_server(server_id)
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
        return openstack_provider.start_server(server_id)
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
        return openstack_provider.stop_server(server_id)
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
