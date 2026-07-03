from typing import Any, Literal

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
    label: str
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
    metadata: dict[str, Any] | None = None
    failure_details: dict[str, Any] | None = None


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
    metadata: dict[str, Any] | None = None
    failure_details: dict[str, Any] | None = None


class OpenStackServerLifecycleResponse(BaseModel):
    id: str
    action: str
    status: str


class OpenStackRebootServerRequest(BaseModel):
    reboot_type: str = Field(default="SOFT", pattern="^(SOFT|HARD)$")


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


class OpenStackVMRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    image_id: str = Field(..., min_length=1)
    flavor_id: str = Field(..., min_length=1)
    network_id: str = Field(..., min_length=1)
    security_group_id: str | None = Field(default=None, min_length=1)
    key_name: str | None = Field(default=None, min_length=1)
    cpu: int = Field(..., ge=1)
    ram_gb: int = Field(..., ge=1)
    disk_gb: int = Field(..., ge=1)
    environment: str = Field(..., min_length=1)
    app_tag: str = Field(..., min_length=1)
    cost_center: str = Field(..., min_length=1)
    lifetime_days: int = Field(..., ge=0)
    lifetime: Literal["1_day", "7_days", "30_days", "90_days", "permanent"] = "30_days"
    packages: list[str] = Field(default_factory=list)
    public_ip_required: bool = False
    catalog_service_name: str | None = Field(default=None, min_length=1)
    project_name: str = Field(..., min_length=1)
    business_unit: str | None = Field(default=None, min_length=1)
    request_owner: str = Field(..., min_length=1)
    team_name: str | None = Field(default=None, min_length=1)
    application_name: str = Field(..., min_length=1)
    application_type: str | None = Field(default=None, min_length=1)
    purpose_description: str | None = Field(default=None, min_length=1)


class OpenStackRequestPolicyResult(BaseModel):
    basic_policy_decision: Literal["auto_approved", "approval_required"]
    governance_decision: Literal[
        "auto_provision",
        "auto_provision_notify",
        "approval_required",
    ]
    final_decision: Literal["auto_approved", "approval_required"]
    governance_score: int
    estimated_monthly_cost: float
    reasons: list[str]


class OpenStackRequestActivity(BaseModel):
    action: str
    status: str
    message: str
    created_at: str
    actor: str = "system"


class OpenStackAuditEvent(BaseModel):
    id: str
    timestamp: str
    actor: str
    role: str
    action: str
    resource_type: str
    resource_id: str | None = None
    request_id: str | None = None
    status: str
    message: str


class OpenStackVMRequestRecord(BaseModel):
    id: str
    status: str
    owner: str | None = None
    owner_role: str | None = None
    request: OpenStackVMRequest
    policy: OpenStackRequestPolicyResult
    server: dict[str, Any] | None = None
    rejection_reason: str | None = None
    provisioning_error: str | None = None
    failure_details: dict[str, Any] | None = None
    activity_log: list[OpenStackRequestActivity] = Field(default_factory=list)
    expires_at: str | None = None
    created_at: str
    updated_at: str


class OpenStackVMRequestResponse(BaseModel):
    id: str
    status: str
    owner: str | None = None
    owner_role: str | None = None
    policy: OpenStackRequestPolicyResult
    server: dict[str, Any] | None = None
    request: OpenStackVMRequest
    provisioning_error: str | None = None
    failure_details: dict[str, Any] | None = None
    activity_log: list[OpenStackRequestActivity] = Field(default_factory=list)
    expires_at: str | None = None
    created_at: str
    updated_at: str


class OpenStackRejectRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=500)
