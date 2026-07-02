import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.schemas.openstack import OpenStackImageResponse, OpenStackStatusResponse
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
    except OpenStackConfigurationError as exc:
        logger.warning("OpenStack status check failed due to configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenStackServiceError as exc:
        logger.warning("OpenStack status check failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

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
    except OpenStackConfigurationError as exc:
        logger.warning("OpenStack image listing failed due to configuration: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except OpenStackServiceError as exc:
        logger.warning("OpenStack image listing failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc
