"""JARVIS Capability Intelligence.

Answers: "WHAT CAN ACCOMPLISH THIS GOAL?"
Provides Capability Discovery, Selection, and Dynamic Composition across:
Tools, APIs, Agents, Models, Services, Devices.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("JARVIS.Capabilities")


@dataclass
class Capability:
    name: str
    domain: str              # "browser", "os", "file", "git", "code", "scheduler", "chat"
    description: str
    target_agent: str
    required_permissions: List[str] = field(default_factory=list)
    requires_two_gate: bool = False
    handler: Optional[Callable[..., Any]] = None


class CapabilityRegistry:
    """Discovers, selects, and composes capabilities to fulfill goals."""

    def __init__(self):
        self._capabilities: Dict[str, Capability] = {}
        self._register_core_capabilities()

    def _register_core_capabilities(self):
        # Browser capabilities
        self.register(Capability(
            name="play_youtube",
            domain="browser",
            description="Searches and plays media on YouTube via Real Chrome CDP",
            target_agent="browser_automation_agent",
        ))
        self.register(Capability(
            name="pause_media",
            domain="browser",
            description="Pauses active media in browser",
            target_agent="browser_automation_agent",
        ))
        self.register(Capability(
            name="resume_media",
            domain="browser",
            description="Resumes paused media in browser",
            target_agent="browser_automation_agent",
        ))
        self.register(Capability(
            name="close_tab",
            domain="browser",
            description="Closes the active Chrome browser tab",
            target_agent="browser_automation_agent",
        ))

        # OS capabilities
        self.register(Capability(
            name="snap_window",
            domain="os",
            description="Snaps the foreground desktop window left, right, or maximized",
            target_agent="system_control_agent",
        ))
        self.register(Capability(
            name="multi_telemetry",
            domain="os",
            description="Collects CPU, RAM, Network status, and Time simultaneously",
            target_agent="system_control_agent",
        ))

        # Scheduler capabilities
        self.register(Capability(
            name="set_reminder",
            domain="scheduler",
            description="Sets an alarm/reminder for a specified delay or time",
            target_agent="scheduler_agent",
        ))

        # Git & Developer capabilities
        self.register(Capability(
            name="create_branch",
            domain="git",
            description="Creates a safe temporary git branch",
            target_agent="developer_task_agent",
        ))
        self.register(Capability(
            name="switch_branch",
            domain="git",
            description="Switches git branches",
            target_agent="developer_task_agent",
        ))

        # Code capabilities
        self.register(Capability(
            name="generate_code",
            domain="code",
            description="Generates clean code for algorithms or functions",
            target_agent="core_llm_agent",
        ))
        self.register(Capability(
            name="execute_code",
            domain="code",
            description="Executes code in safe local sandbox",
            target_agent="core_llm_agent",
        ))

        # Chat & Memory capabilities
        self.register(Capability(
            name="session_summary",
            domain="chat",
            description="Summarizes real verified actions taken during session",
            target_agent="core_llm_agent",
        ))

        # Knowledge Management capabilities (Capability 10)
        self.register(Capability(
            name="query_knowledge",
            domain="knowledge",
            description="Queries personal knowledge base with dense semantic vector search and provenance",
            target_agent="personal_knowledge_base",
        ))
        self.register(Capability(
            name="ingest_knowledge",
            domain="knowledge",
            description="Ingests notes, references, and documents with deduplication and versioning",
            target_agent="personal_knowledge_base",
        ))
        self.register(Capability(
            name="audit_knowledge",
            domain="knowledge",
            description="Audits knowledge freshness, staleness, and physical file integrity",
            target_agent="personal_knowledge_base",
        ))
        self.register(Capability(
            name="delete_knowledge",
            domain="knowledge",
            description="Deletes notes from index, physical disk, and vector store with verification",
            target_agent="personal_knowledge_base",
        ))
        self.register(Capability(
            name="index_knowledge",
            domain="knowledge",
            description="Synchronizes disk files and dense vector index",
            target_agent="personal_knowledge_base",
        ))

    def register(self, cap: Capability):
        key = f"{cap.domain}:{cap.name}"
        self._capabilities[key] = cap

    def select(self, domain: str, action: str) -> Optional[Capability]:
        key = f"{domain}:{action}"
        cap = self._capabilities.get(key)
        if not cap:
            # Fallback by domain
            for c in self._capabilities.values():
                if c.domain == domain:
                    return c
        return cap

    def list_capabilities(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": c.name,
                "domain": c.domain,
                "description": c.description,
                "target_agent": c.target_agent,
                "requires_two_gate": c.requires_two_gate,
            }
            for c in self._capabilities.values()
        ]


capability_registry = CapabilityRegistry()
