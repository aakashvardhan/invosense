# Invosense — Invoice Ingest (Polling)

Gmail polling service that saves invoice attachments (PDF/images) to disk and exposes a simple JSON API. Extraction and payment are handled by other services.

## Quick start

```cmd
cd invosense
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` with your Composio API key, then connect Gmail:

```cmd
python connect_gmail.py --wait
```

Start the server:

```cmd
set USE_CREWAI=false
python -m uvicorn main:app --reload --port 8000
```

## API

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Service + Gmail watcher status |
| `GET /connect/gmail` | OAuth URL to connect Gmail |
| `GET /connect/gmail/status` | Check Gmail connection |
| `GET /invoices` | List saved attachments |
| `GET /invoices/{id}` | Single attachment record |
| `POST /upload` | Manual upload fallback |

Example response:

```json
{
  "count": 1,
  "invoices": [
    {
      "invoice_id": "uuid",
      "source": "gmail",
      "filename": "invoice.jpg",
      "saved_path": "data/inbox/uuid_invoice.jpg",
      "status": "saved",
      "created_at": "2026-06-12T20:16:11.359873+00:00",
      "message_id": "gmail-message-id"
    }
  ]
}
```

## Ingest paths

| Source | How |
|--------|-----|
| **Gmail** | Polls every 30s for unread emails with attachments; marks read after save |
| **Upload** | `POST /upload` with multipart file |
| **Folder** | Drop files in `data/watch/` |

Saved files land in `data/inbox/`.

## Project layout

```
main.py              FastAPI app
ingest.py            Save attachments to data/inbox/
gmail_watcher.py     Composio Gmail poller
folder_watcher.py    Local folder poller
composio_gmail.py    Gmail OAuth helpers
connect_gmail.py     CLI to connect Gmail
storage.py           In-memory invoice registry

pipeline.py          Full AP pipeline (for future integration)
orchestrator.py      CrewAI orchestrator (future)
contracts.py         Shared dataclasses (future)
mocks/               Mock modules for pipeline spine (future)
```

## Optional: full pipeline deps

For `pipeline.py` / CrewAI orchestration (not needed for polling-only):

```cmd
pip install -r requirements-pipeline.txt
```

## Notes

- `/invoices` is in-memory — restarts clear the list; files in `data/inbox/` persist.
- Never commit `.env` — use `.env.example` as a template.
