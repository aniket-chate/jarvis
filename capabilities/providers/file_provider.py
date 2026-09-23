"""File & Document Capability Provider wrapping FileDocumentAgent."""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.file_document_agent import file_document_agent

logger = logging.getLogger("JARVIS.Providers.File")


class FileDocumentProvider(BaseCapabilityProvider):
    """Provides scoped filesystem operations with Two-Gate verification."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.file.scoped",
                name="Scoped File & Document Provider",
                supported_capabilities=[
                    "file.read",
                    "file.create",
                    "file.search",
                    "file.delete",
                    "file.move",
                    "file.rename",
                    "file.list",
                    "file.compress",
                    "file.extract",
                ],
                priority=10,
                estimated_latency_ms=50.0,
            )
        )
        self.agent = file_document_agent

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            inputs = dict(parameters)
            action_map = {
                "file.read": "read",
                "file.create": "create",
                "file.search": "search",
                "file.delete": "delete",
                "file.move": "move",
                "file.rename": "rename",
                "file.list": "list",
                "file.compress": "compress",
                "file.extract": "extract",
            }
            inputs["action"] = action_map.get(capability, "read")
            res = self.agent.execute(inputs)

            elapsed = (time.perf_counter() - t_start) * 1000
            success = res.get("success", True)
            self.record_outcome(success)

            status = "SUCCESS" if success else "FAILED"
            msg = res.get("message") or res.get("response") or res.get("error") or str(res)
            return ActionResult(
                status=status,
                output=res,
                message=str(msg),
                execution_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
