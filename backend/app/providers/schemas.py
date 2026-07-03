from pydantic import BaseModel


class ProviderMetadata(BaseModel):
    id: str
    name: str
    status: str
    enabled: bool
    base_url: str | None = None
    description: str
