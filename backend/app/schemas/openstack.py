from pydantic import BaseModel, ConfigDict


class OpenStackCloudInfo(BaseModel):
    authenticated: bool
    auth_url: str | None
    region: str | None
    project_id: str | None
    project_name: str | None
    user_name: str | None
    token_expires_at: str | None


class OpenStackStatusResponse(BaseModel):
    module: str
    status: str
    cloud: OpenStackCloudInfo


class OpenStackImageResponse(BaseModel):
    id: str
    name: str | None
    status: str | None
    visibility: str | None
    disk_format: str | None
    size: int | None

    model_config = ConfigDict(from_attributes=True)
