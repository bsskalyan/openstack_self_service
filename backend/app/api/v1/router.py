from fastapi import APIRouter

from app.providers.catalog import router as catalog_router
from app.providers.openstack import router as openstack_router


api_router = APIRouter()
api_router.include_router(catalog_router.router, prefix="/catalog", tags=["catalog"])
api_router.include_router(openstack_router.router, prefix="/openstack", tags=["openstack"])
