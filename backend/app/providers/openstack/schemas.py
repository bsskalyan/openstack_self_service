from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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


class OpenStackFlavorResponse(BaseModel):
    id: str
    name: str | None
    vcpus: int | None
    ram: int | None
    disk: int | None
    ephemeral: int | None
    swap: int | None
    is_public: bool | None


class OpenStackNetworkResponse(BaseModel):
    id: str
    name: str | None
    status: str | None
    admin_state_up: bool | None
    is_shared: bool | None
    is_router_external: bool | None
    project_id: str | None


class OpenStackSecurityGroupRuleResponse(BaseModel):
    id: str | None
    direction: str | None
    ethertype: str | None
    protocol: str | None
    port_range_min: int | None
    port_range_max: int | None
    remote_ip_prefix: str | None
    remote_group_id: str | None


class OpenStackSecurityGroupResponse(BaseModel):
    id: str
    name: str | None
    description: str | None
    project_id: str | None
    rules: list[OpenStackSecurityGroupRuleResponse]


class OpenStackKeypairResponse(BaseModel):
    name: str
    type: str | None
    fingerprint: str | None
    public_key: str | None


class OpenStackServerResponse(BaseModel):
    id: str
    name: str | None
    status: str | None
    flavor_id: str | None
    image_id: str | None
    addresses: dict[str, Any] | None
    project_id: str | None
    created_at: str | None
    updated_at: str | None
    vm_state: str | None


class OpenStackCreateServerRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    image_id: str = Field(..., min_length=1)
    flavor_id: str = Field(..., min_length=1)
    network_id: str = Field(..., min_length=1)
    key_name: str | None = Field(default=None, min_length=1)
    security_group_id: str | None = Field(default=None, min_length=1)


class OpenStackCreateServerResponse(BaseModel):
    id: str
    name: str | None
    status: str | None
    addresses: dict[str, Any] | None
    image_id: str | None
    flavor_id: str | None


class OpenStackServerLifecycleResponse(BaseModel):
    id: str
    action: str
    status: str


class OpenStackFloatingIPResponse(BaseModel):
    id: str
    floating_ip_address: str | None
    status: str | None
    floating_network_id: str | None
    port_id: str | None
    fixed_ip_address: str | None
    router_id: str | None
    project_id: str | None


class OpenStackCreateFloatingIPRequest(BaseModel):
    public_network_id: str | None = Field(default=None, min_length=1)


class OpenStackAttachFloatingIPRequest(BaseModel):
    floating_ip: str | None = Field(default=None, min_length=1)


class OpenStackFloatingIPActionResponse(BaseModel):
    server_id: str
    floating_ip: str
    action: str
    status: str
