"""In-memory invoice ingest state."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

Source = Literal["gmail", "upload", "folder"]
InvoiceStatus = Literal["saved", "failed"]


@dataclass
class InvoiceRecord:
    invoice_id: str
    source: Source
    filename: str
    saved_path: str
    status: InvoiceStatus
    created_at: str
    message_id: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "invoice_id": self.invoice_id,
            "source": self.source,
            "filename": self.filename,
            "saved_path": self.saved_path,
            "status": self.status,
            "created_at": self.created_at,
            "message_id": self.message_id,
        }


class InvoiceStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._records: dict[str, InvoiceRecord] = {}

    def create(
        self,
        invoice_id: str,
        source: Source,
        filename: str,
        saved_path: str,
        message_id: str | None = None,
    ) -> InvoiceRecord:
        record = InvoiceRecord(
            invoice_id=invoice_id,
            source=source,
            filename=filename,
            saved_path=saved_path,
            status="saved",
            created_at=_utc_now(),
            message_id=message_id,
        )
        with self._lock:
            self._records[invoice_id] = record
        return record

    def mark_failed(self, invoice_id: str, error: str) -> InvoiceRecord | None:
        with self._lock:
            record = self._records.get(invoice_id)
            if not record:
                return None
            record.status = "failed"
            record.error = error
            return record

    def get(self, invoice_id: str) -> InvoiceRecord | None:
        with self._lock:
            return self._records.get(invoice_id)

    def list_all(self) -> list[InvoiceRecord]:
        with self._lock:
            return sorted(self._records.values(), key=lambda r: r.created_at, reverse=True)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


store = InvoiceStore()
