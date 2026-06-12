"""Mock actions module — swap for real payment/publish integrations."""

from __future__ import annotations

from contracts import Decision, PaymentResult, PublishResult


def pay(decision: Decision) -> PaymentResult:
    """Execute payment for an auto-pay decision."""
    extracted = decision.extracted
    return PaymentResult(
        invoice_id=decision.invoice_id,
        success=True,
        payment_id=f"PAY-{decision.invoice_id[:8].upper()}",
        amount=extracted.total,
        currency=extracted.currency,
        status="completed",
        message=f"Mock payment sent to {extracted.vendor_name}",
    )


def publish(decision: Decision, payment_result: PaymentResult | None) -> PublishResult:
    """Publish invoice outcome to downstream systems."""
    route_note = "auto-paid" if decision.route == "auto_pay" else "queued for review"
    pay_note = ""
    if payment_result and payment_result.success:
        pay_note = f" via {payment_result.payment_id}"

    return PublishResult(
        invoice_id=decision.invoice_id,
        success=True,
        destination="erp/general-ledger",
        record_id=f"GL-{decision.invoice_id[:8].upper()}",
        message=f"Mock publish: invoice {route_note}{pay_note}",
    )
