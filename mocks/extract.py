"""Mock extraction module — swap for real extract at integration."""

from __future__ import annotations

from pathlib import Path

from contracts import ExtractedInvoice


def run(image_path: str, invoice_id: str) -> ExtractedInvoice:
    """Extract invoice fields from an image or PDF attachment."""
    _ = Path(image_path)  # real module reads bytes from disk

    return ExtractedInvoice(
        invoice_id=invoice_id,
        vendor_name="Acme Supplies Co.",
        vendor_id="VND-1042",
        invoice_number="INV-2026-0042",
        invoice_date="2026-06-01",
        due_date="2026-06-30",
        currency="USD",
        subtotal=4200.00,
        tax=336.00,
        total=4536.00,
        line_items=[
            {"description": "Office chairs (x12)", "quantity": 12, "unit_price": 250.00, "amount": 3000.00},
            {"description": "Standing desks (x4)", "quantity": 4, "unit_price": 300.00, "amount": 1200.00},
        ],
        raw_text="Mock extraction from attachment",
    )
