"""End-to-end AP pipeline: ingest -> orchestrate -> decide -> pay/publish."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from decision import route_invoice
from mocks import actions
from orchestrator import run as run_orchestrator
from storage import Source, store

logger = logging.getLogger(__name__)

ATTACHMENTS_DIR = Path(__file__).resolve().parent / "data" / "attachments"
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)


def process_attachment(source_path: Path, source: Source, original_filename: str | None = None) -> str:
    """Copy attachment, create invoice record, and run the full pipeline."""
    invoice_id = str(uuid.uuid4())
    filename = original_filename or source_path.name
    dest = ATTACHMENTS_DIR / f"{invoice_id}_{filename}"
    shutil.copy2(source_path, dest)

    store.create(invoice_id, source=source, filename=filename)
    logger.info("Pipeline started invoice_id=%s source=%s file=%s", invoice_id, source, filename)

    try:
        store.update(invoice_id, status="extracting")
        extracted, compliance_result = run_orchestrator(str(dest), invoice_id)
        store.update(invoice_id, status="compliance", extracted=extracted, compliance=compliance_result)

        store.update(invoice_id, status="deciding")
        decision = route_invoice(extracted, compliance_result)
        store.update(invoice_id, decision=decision)

        payment_result = None
        if decision.route == "auto_pay":
            store.update(invoice_id, status="paying")
            payment_result = actions.pay(decision)
            store.update(invoice_id, payment=payment_result, status="auto_pay")
        else:
            store.update(invoice_id, status="human_review")

        store.update(invoice_id, status="publishing")
        publish_result = actions.publish(decision, payment_result)
        store.update(invoice_id, publish=publish_result, status="completed")

        logger.info(
            "Pipeline completed invoice_id=%s route=%s",
            invoice_id,
            decision.route,
        )
        return invoice_id

    except Exception as exc:
        logger.exception("Pipeline failed invoice_id=%s", invoice_id)
        store.update(invoice_id, status="failed", error=str(exc))
        raise
