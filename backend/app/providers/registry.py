from app.providers.schemas import ProviderMetadata


def list_providers() -> list[ProviderMetadata]:
    return [
        ProviderMetadata(
            id="openstack",
            name="OpenStack",
            status="enabled",
            enabled=True,
            base_url="/api/v1/openstack",
            description="OpenStack cloud provider for VM self-service operations.",
        ),
        ProviderMetadata(
            id="proxmox",
            name="Proxmox",
            status="coming_soon",
            enabled=False,
            base_url=None,
            description="Proxmox provider integration is planned.",
        ),
        ProviderMetadata(
            id="opennebula",
            name="OpenNebula",
            status="coming_soon",
            enabled=False,
            base_url=None,
            description="OpenNebula provider integration is planned.",
        ),
        ProviderMetadata(
            id="cloudstack",
            name="CloudStack",
            status="coming_soon",
            enabled=False,
            base_url=None,
            description="CloudStack provider integration is planned.",
        ),
    ]
