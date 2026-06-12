"""Save incoming invoice attachments — no extraction (handled by another service)."""

from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from storage import Source, store

logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).resolve().parent
INBOX_DIR = ROOT_DIR / "data" / "inbox"
INBOX_DIR.mkdir(parents=True, exist_ok=True)


def _relative_path(path: Path) -> str:
    return path.relative_to(ROOT_DIR).as_posix()


def save_attachment(
    source_path: Path,
    source: Source,
    original_filename: str | None = None,
    message_id: str | None = None,
) -> str:
    """Copy attachment bytes to inbox folder and register a simple record."""
    invoice_id = str(uuid.uuid4())
    filename = original_filename or source_path.name
    dest = INBOX_DIR / f"{invoice_id}_{filename}"
    shutil.copy2(source_path, dest)

    store.create(
        invoice_id,
        source=source,
        filename=filename,
        saved_path=_relative_path(dest),
        message_id=message_id,
    )
    logger.info(
        "Saved attachment invoice_id=%s source=%s file=%s path=%s",
        invoice_id,
        source,
        filename,
        dest,
    )
    return invoice_id
