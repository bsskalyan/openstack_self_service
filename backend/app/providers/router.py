from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.user_context import CurrentUser, ensure_role, get_current_user
from app.providers.openstack.router import get_openstack_service
from app.providers.openstack.service import OpenStackServiceError
from app.providers.registry import list_providers
from app.providers.schemas import (
    OpenStackProviderConfig,
    OpenStackProviderConfigResponse,
    OpenStackProviderTestResponse,
    ProviderMetadata,
)


router = APIRouter()


@router.get(
    "/providers",
    response_model=list[ProviderMetadata],
    status_code=status.HTTP_200_OK,
)
async def get_providers() -> list[ProviderMetadata]:
    return list_providers()


@router.get(
    "/providers/openstack/config",
    response_model=OpenStackProviderConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def get_openstack_config(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    ensure_role(current_user, {"admin"})
    return get_openstack_service().get_provider_config()


@router.put(
    "/providers/openstack/config",
    response_model=OpenStackProviderConfigResponse,
    status_code=status.HTTP_200_OK,
)
async def save_openstack_config(
    config: OpenStackProviderConfig,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    ensure_role(current_user, {"admin"})
    return get_openstack_service().save_provider_config(config.model_dump())


@router.post(
    "/providers/openstack/test",
    response_model=OpenStackProviderTestResponse,
    status_code=status.HTTP_200_OK,
)
async def test_openstack_config(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    config: OpenStackProviderConfig | None = None,
) -> dict:
    ensure_role(current_user, {"admin"})
    try:
        return get_openstack_service().test_provider_config(
            config.model_dump() if config else None,
        )
    except OpenStackServiceError as exc:
        return {
            "status": "failed",
            "message": str(exc),
            "cloud": exc.failure_details,
        }
