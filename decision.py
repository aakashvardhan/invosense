"""Invoice routing decision logic."""

from __future__ import annotations

from contracts import ComplianceResult, Decision, ExtractedInvoice
from mocks.compliance import get_policy_config


def route_invoice(extracted: ExtractedInvoice, compliance: ComplianceResult) -> Decision:
    """Apply policy rules and return a routing Decision."""
    policy = get_policy_config()
    high_value_cap = float(policy["high_value_cap"])

    if compliance.has_flags:
        return Decision(
            invoice_id=extracted.invoice_id,
            route="human_review",
            reason=f"Compliance flags present: {', '.join(compliance.flags) or compliance.status}",
            extracted=extracted,
            compliance=compliance,
            policy_snapshot=policy,
        )

    if extracted.total > high_value_cap:
        return Decision(
            invoice_id=extracted.invoice_id,
            route="human_review",
            reason=f"Total {extracted.total} exceeds high_value_cap {high_value_cap}",
            extracted=extracted,
            compliance=compliance,
            policy_snapshot=policy,
        )

    if not policy.get("auto_pay_enabled", True):
        return Decision(
            invoice_id=extracted.invoice_id,
            route="human_review",
            reason="Auto-pay disabled by policy",
            extracted=extracted,
            compliance=compliance,
            policy_snapshot=policy,
        )

    return Decision(
        invoice_id=extracted.invoice_id,
        route="auto_pay",
        reason="Clean invoice within policy limits",
        extracted=extracted,
        compliance=compliance,
        policy_snapshot=policy,
    )
