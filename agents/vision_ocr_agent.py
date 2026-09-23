"""Camera OCR & Document Scanning Agent for JARVIS Layer 3 (Group 4).

Extracts text from photographed documents, receipts, whiteboard notes, and scanned images
using native offline Windows OCR (winsdk.windows.media.ocr.OcrEngine).
Integrates with Personal Knowledge Base for automated indexing and storage.
Zero external cloud dependency, completely private and local.
"""

import os
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import PROJECT_ROOT

logger = logging.getLogger("JARVIS.VisionOCRAgent")


class VisionOCRAgent:
    """Extracts text from camera feeds or image files and ingests into Knowledge Base."""

    def __init__(self):
        self._engine = None
        self._init_ocr_engine()

    def _init_ocr_engine(self) -> None:
        try:
            from winsdk.windows.media.ocr import OcrEngine
            self._engine = OcrEngine.try_create_from_user_profile_languages()
            if self._engine:
                logger.info("[VisionOCRAgent] Initialized native Windows OCR engine for: %s", self._engine.recognizer_language.display_name)
        except Exception as e:
            logger.warning("[VisionOCRAgent] Failed to initialize native Windows OCR: %s", e)

    async def _recognize_image_file_async(self, file_path: Path) -> Dict[str, Any]:
        """Loads image file into SoftwareBitmap and executes OCR."""
        from winsdk.windows.storage import StorageFile
        from winsdk.windows.graphics.imaging import BitmapDecoder

        if not self._engine:
            self._init_ocr_engine()
        if not self._engine:
            return {"success": False, "error": "Native OCR engine unavailable on this system."}

        storage_file = await StorageFile.get_file_from_path_async(str(file_path.resolve()))
        stream = await storage_file.open_async(0)  # Read access
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()

        result = await self._engine.recognize_async(bitmap)

        lines = []
        for line in result.lines:
            lines.append(line.text)

        full_text = "\n".join(lines).strip()
        return {
            "success": True,
            "text": full_text,
            "line_count": len(lines),
            "lines": lines,
            "language": self._engine.recognizer_language.display_name
        }

    def scan_document(
        self,
        image_path: str,
        save_to_kb: bool = False,
        document_title: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extracts text from an image path and optionally commits to Personal Knowledge Base."""
        path_obj = Path(image_path)
        if not path_obj.is_absolute():
            # Check in screenshots or workspace
            cand1 = PROJECT_ROOT / "workspace" / image_path
            cand2 = PROJECT_ROOT / "workspace" / "screenshots" / image_path
            if cand1.exists():
                path_obj = cand1
            elif cand2.exists():
                path_obj = cand2

        if not path_obj.exists():
            return {"success": False, "error": f"Image file '{image_path}' not found on disk."}

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            ocr_res = loop.run_until_complete(self._recognize_image_file_async(path_obj))
            loop.close()
        except Exception as e:
            logger.error("[VisionOCRAgent] OCR execution error: %s", e)
            return {"success": False, "error": str(e)}

        if not ocr_res.get("success"):
            return ocr_res

        extracted_text = ocr_res.get("text", "")
        kb_result = None

        if save_to_kb and extracted_text:
            try:
                from agents.personal_knowledge_base import personal_knowledge_base
                title = document_title or f"Scanned Document: {path_obj.stem}"
                personal_knowledge_base.add_note(
                    title=title,
                    content=extracted_text,
                    tags=["scanned_doc", "ocr", "camera"]
                )
                kb_result = f"Stored in Knowledge Base as '{title}'"
                logger.info("[VisionOCRAgent] Ingested document into Knowledge Base: '%s'", title)
            except Exception as kb_err:
                logger.warning("[VisionOCRAgent] KB ingestion warning: %s", kb_err)

        return {
            "success": True,
            "action": "scan_document",
            "file": str(path_obj),
            "filename": path_obj.name,
            "text": extracted_text,
            "line_count": ocr_res.get("line_count", 0),
            "kb_status": kb_result,
            "response": f"Extracted {ocr_res.get('line_count', 0)} lines of text from '{path_obj.name}'.\n\nPreview:\n{extracted_text[:200]}..." if extracted_text else f"No legible text found in '{path_obj.name}'."
        }

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Standardized interface for Orchestrator Agent Router."""
        image_path = inputs.get("image_path") or inputs.get("path") or inputs.get("file") or inputs.get("target", "")
        save_kb = bool(inputs.get("save_to_kb", inputs.get("save_kb", False)))
        doc_title = inputs.get("title") or inputs.get("document_title")

        return self.scan_document(
            image_path=image_path,
            save_to_kb=save_kb,
            document_title=doc_title
        )


vision_ocr_agent = VisionOCRAgent()
