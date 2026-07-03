from app.providers.openstack.schemas import OpenStackRequestPolicyResult, OpenStackVMRequest


def evaluate_vm_request(request: OpenStackVMRequest) -> OpenStackRequestPolicyResult:
    estimated_monthly_cost = estimate_monthly_cost(request)
    reasons: list[str] = []
    environment = request.environment.lower()
    is_production = environment in {"prod", "production"}
    is_permanent = request.lifetime == "permanent" or request.lifetime_days == 0

    basic_auto_approved = (
        request.cpu <= 6
        and request.ram_gb <= 12
        and request.disk_gb <= 200
        and not is_production
        and request.public_ip_required is False
        and not is_permanent
    )

    governance_score = 0
    if estimated_monthly_cost > 5000:
        governance_score += 30
        reasons.append("Estimated monthly cost is greater than 5000")

    if request.public_ip_required:
        governance_score += 30
        reasons.append("Public IP requested")

    if is_production:
        governance_score += 20
        reasons.append("Production workload")

    if is_permanent:
        governance_score += 20
        reasons.append("Permanent lifetime requested")

    if is_custom_image(request.image_id):
        governance_score += 15
        reasons.append("Custom image requested")

    if request.disk_gb > 200:
        governance_score += 20
        reasons.append("Disk size is greater than 200GB")

    if governance_score <= 30:
        governance_decision = "auto_provision"
    elif governance_score <= 60:
        governance_decision = "auto_provision_notify"
    else:
        governance_decision = "approval_required"

    if is_production and request.public_ip_required:
        governance_decision = "approval_required"
        reasons.append("Production workloads with a public IP require approval")

    if is_production and is_permanent:
        governance_decision = "approval_required"
        reasons.append("Permanent production workloads require approval")

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
