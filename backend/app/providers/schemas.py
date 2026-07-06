from pydantic import BaseModel, Field


class ProviderMetadata(BaseModel):
    id: str
    name: str
    status: str
    enabled: bool
    base_url: str | None = None
    description: str


class OpenStackProviderConfig(BaseModel):
    provider_name: str = Field(default="OpenStack", min_length=1, max_length=255)
    auth_url: str | None = None
    username: str | None = None
    password: str | None = None
    project: str | None = None
    user_domain: str = "default"
    project_domain: str = "default"
    region: str | None = None


class OpenStackProviderConfigResponse(BaseModel):
    provider_name: str
    auth_url: str | None
    username: str | None
    project: str | None
    user_domain: str
    project_domain: str
    region: str | None
    password_configured: bool
    status: str


class OpenStackProviderTestResponse(BaseModel):
    status: str
    message: str
    cloud: dict | None = None
