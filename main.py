"""FastAPI entrypoint for the autonomous AP agent."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from composio_gmail import get_gmail_connection_status, start_gmail_connection
from folder_watcher import FolderWatcher
from gmail_watcher import GmailWatcher
from ingest import save_attachment
from storage import store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff"}

_gmail_watcher: GmailWatcher | None = None
_folder_watcher: FolderWatcher | None = None


def _save_from_path(
    path: Path,
    source: str,
    filename: str | None = None,
    message_id: str | None = None,
) -> None:
    save_attachment(path, source=source, original_filename=filename, message_id=message_id)  # type: ignore[arg-type]


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _gmail_watcher, _folder_watcher

    def on_gmail_attachment(path: Path, filename: str, message_id: str) -> None:
        _save_from_path(path, "gmail", filename, message_id)

    def on_folder_file(path: Path) -> None:
        _save_from_path(path, "folder", path.name.replace(".processing", ""))

    _gmail_watcher = GmailWatcher(on_attachment=on_gmail_attachment)
    _gmail_watcher.start()

    _folder_watcher = FolderWatcher(on_file=on_folder_file)
    _folder_watcher.start()

    logger.info("AP agent spine ready")
    yield

    if _gmail_watcher:
        _gmail_watcher.stop()
    if _folder_watcher:
        _folder_watcher.stop()


app = FastAPI(
    title="AP Agent",
    description="Autonomous accounts-payable pipeline spine",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    gmail_status = get_gmail_connection_status()
    return {
        "status": "ok",
        "gmail_watcher": bool(_gmail_watcher and _gmail_watcher.enabled),
        "gmail_connected": gmail_status.get("connected", False),
        "folder_watcher": True,
    }


@app.get("/connect/gmail")
def connect_gmail():
    """Return (and optionally open) the Composio OAuth URL to connect Gmail."""
    try:
        return start_gmail_connection(open_browser=False)
    except Exception as exc:
        return {"error": str(exc)}


@app.get("/connect/gmail/status")
def connect_gmail_status():
    """Check whether Gmail is connected for COMPOSIO_USER_ID."""
    return get_gmail_connection_status()


@app.get("/invoices")
def list_invoices():
    """Return saved invoice attachments (raw files, no extraction)."""
    records = store.list_all()
    return {
        "count": len(records),
        "invoices": [record.to_dict() for record in records],
    }


@app.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str):
    record = store.get(invoice_id)
    if not record:
        return {"error": "not_found", "invoice_id": invoice_id}
    return record.to_dict()


@app.post("/upload")
async def upload_invoice(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    """Fallback ingest: save an invoice image/PDF to the inbox folder."""
    suffix = Path(file.filename or "invoice.pdf").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        return {
            "error": "unsupported_file_type",
            "allowed": sorted(ALLOWED_EXTENSIONS),
        }

    contents = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="upload_")
    tmp.write(contents)
    tmp.close()
    tmp_path = Path(tmp.name)

    def _process() -> None:
        try:
            save_attachment(tmp_path, source="upload", original_filename=file.filename)
        finally:
            tmp_path.unlink(missing_ok=True)

    background_tasks.add_task(_process)

    return {
        "status": "accepted",
        "message": "Invoice saved to inbox",
        "filename": file.filename,
    }
