from fastapi import APIRouter, status

from app.providers.registry import list_providers
from app.providers.schemas import ProviderMetadata


router = APIRouter()


@router.get(
    "/providers",
    response_model=list[ProviderMetadata],
    status_code=status.HTTP_200_OK,
)
async def get_providers() -> list[ProviderMetadata]:
    return list_providers()
