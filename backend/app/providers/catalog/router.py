from fastapi import APIRouter, status

from app.providers.catalog.schemas import CatalogServiceResponse
from app.providers.openstack.catalog import get_openstack_catalog_services


router = APIRouter()


@router.get(
    "/services",
    response_model=list[CatalogServiceResponse],
    status_code=status.HTTP_200_OK,
)
async def list_catalog_services() -> list[dict[str, object]]:
    return get_openstack_catalog_services()
