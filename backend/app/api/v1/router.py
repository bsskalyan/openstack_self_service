from fastapi import APIRouter

from app.routers import openstack


api_router = APIRouter()
api_router.include_router(openstack.router, prefix="/openstack", tags=["openstack"])
