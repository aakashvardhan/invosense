"""Mock compliance module — swap for real compliance at integration."""

from __future__ import annotations

import os

from contracts import ComplianceResult, ExtractedInvoice


def get_policy_config() -> dict:
    """Return AP routing policy thresholds."""
    return {
        "high_value_cap": float(os.getenv("HIGH_VALUE_CAP", "5000")),
        "auto_pay_enabled": os.getenv("AUTO_PAY_ENABLED", "true").lower() == "true",
        "require_vendor_verification": True,
    }


def run(invoice: ExtractedInvoice) -> ComplianceResult:
    """Run compliance checks against an extracted invoice."""
    return ComplianceResult(
        invoice_id=invoice.invoice_id,
        status="clean",
        flags=[],
        vendor_verified=True,
        amount_verified=True,
        duplicate_check_passed=True,
        notes="Mock compliance: all checks passed",
    )
