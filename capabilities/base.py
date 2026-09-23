"""JARVIS Capability Provider Base Contract.

Defines the abstract interface for all capability providers.
Any tool, agent, API, model, or service implements this interface to register as a provider.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import time
from typing import Any, Dict, List, Optional


@dataclass
class ProviderMetadata:
    provider_id: str
    name: str
    supported_capabilities: List[str]
    priority: int = 100       # Lower is preferred
    estimated_latency_ms: float = 100.0
    cost_per_call: float = 0.0
    requires_permissions: List[str] = field(default_factory=list)
    is_local: bool = True
    version: str = "1.0.0"
    description: str = ""
    device_target: str = "local"
    safety_level: str = "read_only"
    author: str = "JARVIS"


@dataclass
class ActionResult:
    status: str              # "SUCCESS", "PARTIAL", "FAILED"
    output: Any
    message: str = ""
    evidence: str = ""
    execution_time_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    action: str = ""
    provider_id: str = ""


class BaseCapabilityProvider(ABC):
    """Abstract Base Class for all Capability Providers."""

    def __init__(self, metadata: ProviderMetadata):
        self.metadata = metadata
        self._failure_count: int = 0
        self._success_count: int = 0

    @property
    def provider_id(self) -> str:
        return self.metadata.provider_id

    @property
    def supported_capabilities(self) -> List[str]:
        return self.metadata.supported_capabilities

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the provider is currently healthy and online."""
        pass

    @abstractmethod
    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        """Executes the requested capability with the given parameters."""
        pass

    def record_outcome(self, success: bool):
        if not hasattr(self, "_success_count"):
            self._success_count = 0
        if not hasattr(self, "_failure_count"):
            self._failure_count = 0
        if success:
            self._success_count += 1
        else:
            self._failure_count += 1

    @property
    def reliability_score(self) -> float:
        success = getattr(self, "_success_count", 0)
        failure = getattr(self, "_failure_count", 0)
        total = success + failure
        if total == 0:
            return 1.0
        return success / total
