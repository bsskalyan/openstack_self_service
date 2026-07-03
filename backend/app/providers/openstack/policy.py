from app.providers.openstack.schemas import OpenStackRequestPolicyResult, OpenStackVMRequest


def evaluate_vm_request(request: OpenStackVMRequest) -> OpenStackRequestPolicyResult:
    estimated_monthly_cost = estimate_monthly_cost(request)
    reasons: list[str] = []
    production_workload = is_production_environment(request.environment)
    permanent_lifetime = is_permanent_lifetime(request)
    large_vm = is_large_vm(request)

    basic_auto_approved = (
        request.cpu <= 6
        and request.ram_gb <= 12
        and request.disk_gb <= 200
        and not production_workload
        and not permanent_lifetime
        and request.public_ip_required is False
    )

    governance_score = 0
    if estimated_monthly_cost > 5000:
        governance_score += 30
        reasons.append("Estimated monthly cost is greater than 5000")

    if request.public_ip_required:
        governance_score += 30
        reasons.append("Public IP requested")

    if production_workload:
        governance_score += 20
        reasons.append("Production workload")

    if permanent_lifetime:
        governance_score += 20
        reasons.append("Permanent lifetime requested")

    if large_vm:
        governance_score += 20
        reasons.append("Large VM requested")

    if is_custom_image(request.image_id):
        governance_score += 15
        reasons.append("Custom image requested")

    if governance_score <= 30:
        governance_decision = "auto_provision"
    elif governance_score <= 60:
        governance_decision = "auto_provision_notify"
    else:
        governance_decision = "approval_required"

    final_decision = (
        "auto_approved"
        if basic_auto_approved and governance_decision != "approval_required"
        else "approval_required"
    )

    if not basic_auto_approved:
        reasons.append("Basic auto-approval policy was not satisfied")

    return OpenStackRequestPolicyResult(
        basic_policy_decision="auto_approved"
        if basic_auto_approved
        else "approval_required",
        governance_decision=governance_decision,
        final_decision=final_decision,
        governance_score=governance_score,
        estimated_monthly_cost=estimated_monthly_cost,
        reasons=reasons,
    )


def estimate_monthly_cost(request: OpenStackVMRequest) -> float:
    return float((request.cpu * 500) + (request.ram_gb * 150) + (request.disk_gb * 5))


def is_custom_image(image_id: str) -> bool:
    normalized = image_id.lower()
    return normalized.startswith("custom:") or "custom" in normalized


def is_production_environment(environment: str) -> bool:
    return environment.lower() in {"prod", "production"}


def is_permanent_lifetime(request: OpenStackVMRequest) -> bool:
    return str(request.lifetime or "").lower() == "permanent"


def is_large_vm(request: OpenStackVMRequest) -> bool:
    return request.cpu > 6 or request.ram_gb > 12 or request.disk_gb > 200
