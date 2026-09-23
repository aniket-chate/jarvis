"""File Input Channel for JARVIS.

Ingests local files (text, code, image, audio, documents), extracts metadata,
and emits 'file_received' PerceptionEvents onto the Unified Event Bus.
"""

import os
import mimetypes
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from perception.events import PerceptionEvent, event_bus
from config.settings import settings

logger = logging.getLogger("JARVIS.Channels.File")


class FileInputChannel:
    """Channel for ingesting local files into the perception pipeline."""

    def ingest_file(self, file_path: str) -> Optional[PerceptionEvent]:
        """Reads file, extracts metadata, and publishes a file_received event."""
        p = Path(file_path).resolve()
        if not p.exists() or not p.is_file():
            logger.error("[FileInputChannel] Target file does not exist: %s", file_path)
            return None

        mime_type, _ = mimetypes.guess_type(str(p))
        size_bytes = p.stat().st_size

        payload: Dict[str, Any] = {
            "path": str(p),
            "filename": p.name,
            "extension": p.suffix.lower(),
            "mime_type": mime_type or "application/octet-stream",
            "size_bytes": size_bytes,
        }

        # If text-based file, read first 8KB snippet
        is_text = mime_type and (mime_type.startswith("text/") or "json" in mime_type or "yaml" in mime_type)
        if is_text or p.suffix.lower() in [".txt", ".md", ".py", ".json", ".yaml", ".csv", ".log"]:
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    snippet = f.read(8192)
                payload["content_snippet"] = snippet
                payload["is_text"] = True
            except Exception as e:
                logger.warning("[FileInputChannel] Could not decode text: %s", str(e))
                payload["is_text"] = False
        else:
            payload["is_text"] = False

        event = PerceptionEvent(
            type="file_received",
            payload=payload,
            source="file_input",
            active_persona=settings.active_persona_name,
        )

        logger.debug("[FileInputChannel] Ingested file: %s (%d bytes)", p.name, size_bytes)
        event_bus.publish(event)
        return event


file_input_channel = FileInputChannel()
