from pydantic import BaseModel


class CatalogServiceResponse(BaseModel):
    id: str
    provider: str
    name: str
    description: str
    recommended_cpu: int
    recommended_ram_gb: int
    recommended_disk_gb: int
    estimated_monthly_cost: float
    risk_level: str
    packages: list[str]
    environment: str
    app_tag: str
    public_ip_required: bool
