"""Composio Gmail watcher — polls for invoice attachments."""

from __future__ import annotations

import logging
import os
import tempfile
import threading
import urllib.request
from pathlib import Path
from typing import Any, Callable

from composio_gmail import get_client, get_user_id

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff"}
POLL_INTERVAL_SEC = int(os.getenv("GMAIL_POLL_INTERVAL_SEC", "30"))
GMAIL_FETCH_TOOL = os.getenv("COMPOSIO_GMAIL_FETCH_TOOL", "GMAIL_FETCH_EMAILS")
GMAIL_ATTACHMENT_TOOL = os.getenv("COMPOSIO_GMAIL_ATTACHMENT_TOOL", "GMAIL_GET_ATTACHMENT")
GMAIL_MARK_READ_TOOL = os.getenv("COMPOSIO_GMAIL_MARK_READ_TOOL", "GMAIL_BATCH_MODIFY_MESSAGES")
GMAIL_QUERY = os.getenv(
    "GMAIL_INVOICE_QUERY",
    "is:unread has:attachment",
)


class GmailWatcher:
    """Poll Gmail via Composio for new invoice attachments."""

    def __init__(
        self,
        on_attachment: Callable[[Path, str, str], None],
        poll_interval_sec: int = POLL_INTERVAL_SEC,
    ) -> None:
        self._on_attachment = on_attachment
        self._poll_interval_sec = poll_interval_sec
        self._seen_message_ids: set[str] = set()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._composio = None
        self._user_id = get_user_id()
        self._connected = False

    @property
    def enabled(self) -> bool:
        return bool(os.getenv("COMPOSIO_API_KEY"))

    def start(self) -> None:
        if not self.enabled:
            logger.info("Gmail watcher disabled (COMPOSIO_API_KEY not set)")
            return
        if self._thread and self._thread.is_alive():
            return

        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="gmail-watcher", daemon=True)
        self._thread.start()
        logger.info("Gmail watcher started (interval=%ss)", self._poll_interval_sec)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=self._poll_interval_sec + 5)

    def _ensure_client(self) -> bool:
        if self._composio is not None:
            return self._connected

        try:
            self._composio = get_client()
            self._connected = True
            return True
        except ImportError:
            logger.warning("composio package not installed; Gmail watcher inactive")
            return False
        except Exception as exc:
            logger.warning("Failed to init Composio client: %s", exc)
            return False

    def _poll_loop(self) -> None:
        while not self._stop.is_set():
            try:
                if self._ensure_client():
                    self._poll_once()
            except Exception:
                logger.exception("Gmail poll error")

            self._stop.wait(self._poll_interval_sec)

    def _execute_tool(self, slug: str, arguments: dict[str, Any]) -> dict[str, Any]:
        assert self._composio is not None
        response = self._composio.tools.execute(
            slug,
            arguments,
            user_id=self._user_id,
            dangerously_skip_version_check=True,
        )
        return _as_dict(response)

    def _poll_once(self) -> None:
        try:
            response = self._execute_tool(
                GMAIL_FETCH_TOOL,
                {
                    "query": GMAIL_QUERY,
                    "max_results": 10,
                },
            )
        except Exception as exc:
            logger.warning("Gmail fetch failed: %s", exc)
            return

        if response.get("error"):
            logger.warning("Gmail fetch returned error: %s", response["error"])
            return

        messages = _normalize_messages(response)
        new_messages = [
            m for m in messages
            if (m.get("messageId") or m.get("id")) not in self._seen_message_ids
        ]
        if messages:
            logger.debug(
                "Gmail poll: %s unread with attachments, %s not yet processed this session",
                len(messages),
                len(new_messages),
            )

        for message in messages:
            message_id = message.get("messageId") or message.get("id")
            if not message_id or message_id in self._seen_message_ids:
                continue

            handled = False
            for attachment in _extract_attachments(message):
                filename = attachment.get("filename") or attachment.get("name") or "attachment.pdf"
                ext = Path(filename).suffix.lower()
                if ext not in ALLOWED_EXTENSIONS:
                    logger.info("Skipping unsupported attachment %s", filename)
                    continue

                attachment_id = attachment.get("attachmentId") or attachment.get("attachment_id")
                if not attachment_id:
                    logger.warning("Attachment %s missing attachmentId", filename)
                    continue

                try:
                    path = self._download_attachment(message_id, attachment_id, filename)
                except Exception as exc:
                    logger.warning("Failed to download %s: %s", filename, exc)
                    continue

                try:
                    logger.info("Saving Gmail attachment message=%s file=%s", message_id, filename)
                    self._on_attachment(path, filename, message_id)
                    handled = True
                finally:
                    path.unlink(missing_ok=True)

            if handled:
                self._seen_message_ids.add(message_id)
                self._mark_as_read(message_id)

    def _mark_as_read(self, message_id: str) -> None:
        try:
            response = self._execute_tool(
                GMAIL_MARK_READ_TOOL,
                {
                    "messageIds": [message_id],
                    "removeLabelIds": ["UNREAD"],
                },
            )
            if response.get("error"):
                logger.warning("Failed to mark message %s as read: %s", message_id, response["error"])
                return
            logger.info("Marked Gmail message as read: %s", message_id)
        except Exception as exc:
            logger.warning("Failed to mark message %s as read: %s", message_id, exc)

    def _download_attachment(self, message_id: str, attachment_id: str, filename: str) -> Path:
        response = self._execute_tool(
            GMAIL_ATTACHMENT_TOOL,
            {
                "message_id": message_id,
                "attachment_id": attachment_id,
                "file_name": filename,
            },
        )
        if response.get("error"):
            raise RuntimeError(str(response["error"]))

        file_info = _extract_file_info(response)
        suffix = Path(filename).suffix or ".pdf"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, prefix="gmail_")
        tmp.close()
        dest = Path(tmp.name)

        if file_info.get("s3url"):
            urllib.request.urlretrieve(file_info["s3url"], dest)  # noqa: S310
            return dest

        if file_info.get("data"):
            import base64

            dest.write_bytes(base64.b64decode(file_info["data"]))
            return dest

        raise RuntimeError(f"No downloadable content for attachment {filename}")


def _as_dict(response: object) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    if hasattr(response, "model_dump"):
        return response.model_dump()
    return {"data": response}


def _normalize_messages(response: dict[str, Any]) -> list[dict[str, Any]]:
    data = response.get("data", response)
    if isinstance(data, dict):
        messages = data.get("messages") or data.get("emails") or []
        if isinstance(messages, list):
            return [m for m in messages if isinstance(m, dict)]
    if isinstance(data, list):
        return [m for m in data if isinstance(m, dict)]
    return []


def _extract_attachments(message: dict[str, Any]) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for key in ("attachmentList", "attachments", "attachment", "parts"):
        value = message.get(key)
        if isinstance(value, list):
            attachments.extend(a for a in value if isinstance(a, dict))
        elif isinstance(value, dict):
            attachments.append(value)
    return attachments


def _extract_file_info(response: dict[str, Any]) -> dict[str, Any]:
    data = response.get("data", response)
    if isinstance(data, dict):
        file_info = data.get("file")
        if isinstance(file_info, dict):
            return file_info
        if "s3url" in data or "data" in data:
            return data
    return {}
