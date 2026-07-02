import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.schemas.openstack import (
    OpenStackFlavorResponse,
    OpenStackImageResponse,
    OpenStackKeypairResponse,
    OpenStackNetworkResponse,
    OpenStackSecurityGroupResponse,
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
