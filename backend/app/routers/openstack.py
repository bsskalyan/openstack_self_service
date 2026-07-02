import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.config import get_settings
from app.schemas.openstack import (
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
    OpenStackSecurityGroupResponse,
    OpenStackServerLifecycleResponse,
    OpenStackServerResponse,
    OpenStackStatusResponse,
)
from app.services.openstack_service import (
    OpenStackConfigurationError,
    OpenStackService,
    OpenStackServiceError,
)


logger = logging.getLogger(__name__)


router = APIRouter()


@lru_cache
def get_openstack_service() -> OpenStackService:
    return OpenStackService(get_settings())


def handle_openstack_error(operation: str, exc: OpenStackServiceError) -> HTTPException:
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


@router.get(
    "/status",
    response_model=OpenStackStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_openstack_module_status(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        cloud_info = openstack_service.verify_authentication()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack status check", exc) from exc

    return {"module": "openstack", "status": "connected", "cloud": cloud_info}


@router.get(
    "/images",
    response_model=list[OpenStackImageResponse],
    status_code=status.HTTP_200_OK,
)
async def list_images(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_images()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack image listing", exc) from exc


@router.get(
    "/flavors",
    response_model=list[OpenStackFlavorResponse],
    status_code=status.HTTP_200_OK,
)
async def list_flavors(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_flavors()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack flavor listing", exc) from exc


@router.get(
    "/networks",
    response_model=list[OpenStackNetworkResponse],
    status_code=status.HTTP_200_OK,
)
async def list_networks(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_networks()
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
    request: OpenStackCreateFloatingIPRequest | None = Body(default=None),
) -> dict[str, Any]:
    try:
        return openstack_service.create_floating_ip(
            public_network_id=request.public_network_id if request else None,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP creation", exc) from exc


@router.get(
    "/servers",
    response_model=list[OpenStackServerResponse],
    status_code=status.HTTP_200_OK,
)
async def list_servers(
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> list[dict[str, Any]]:
    try:
        return openstack_service.list_servers()
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server listing", exc) from exc


@router.post(
    "/servers",
    response_model=OpenStackCreateServerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_server(
    request: OpenStackCreateServerRequest,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        return openstack_service.create_server(
            name=request.name,
            image_id=request.image_id,
            flavor_id=request.flavor_id,
            network_id=request.network_id,
            key_name=request.key_name,
            security_group_id=request.security_group_id,
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
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        return openstack_service.delete_server(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server deletion", exc) from exc


@router.post(
    "/servers/{server_id}/start",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_server(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        return openstack_service.start_server(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server start", exc) from exc


@router.post(
    "/servers/{server_id}/stop",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def stop_server(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        return openstack_service.stop_server(server_id)
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack server stop", exc) from exc


@router.post(
    "/servers/{server_id}/reboot",
    response_model=OpenStackServerLifecycleResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def reboot_server(
    server_id: str,
    openstack_service: Annotated[OpenStackService, Depends(get_openstack_service)],
) -> dict[str, Any]:
    try:
        return openstack_service.reboot_server(server_id)
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
    request: OpenStackAttachFloatingIPRequest | None = Body(default=None),
) -> dict[str, Any]:
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
) -> dict[str, Any]:
    try:
        return openstack_service.detach_floating_ip(
            server_id=server_id,
            floating_ip=floating_ip,
        )
    except OpenStackServiceError as exc:
        raise handle_openstack_error("OpenStack floating IP detach", exc) from exc
