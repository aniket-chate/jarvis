"""Data-Driven Agent Router & Registry for JARVIS Layer 2.

Registers mock handlers for all 13 agent types defined in config/agent_registry.yaml.
Executes steps via data-driven registry lookup without hardcoded branching.
"""

import logging
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List
import yaml

from config.settings import PROJECT_ROOT, settings

logger = logging.getLogger("JARVIS.Router")

REGISTRY_CONFIG_PATH = PROJECT_ROOT / "config" / "agent_registry.yaml"


class AgentDescriptor:
    """Metadata and execution handler for a registered agent type."""

    def __init__(
        self,
        agent_type: str,
        name: str,
        description: str,
        capabilities: List[str],
        handler: Callable[[Dict[str, Any], str], Dict[str, Any]],
    ):
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.handler = handler

    def execute(self, inputs: Dict[str, Any], persona: str) -> Dict[str, Any]:
        return self.handler(inputs, persona)


class AgentRegistry:
    """Data-driven registry managing agent types and dispatch handlers."""

    def __init__(self):
        self._agents: Dict[str, AgentDescriptor] = {}
        self._load_registry_config()
        self._register_mock_agents()

    def _load_registry_config(self) -> None:
        """Loads agent definitions from agent_registry.yaml."""
        if not REGISTRY_CONFIG_PATH.exists():
            logger.warning("[AgentRegistry] Config not found at %s; using internal defaults", REGISTRY_CONFIG_PATH)
            self._specs = {}
            return

        with open(REGISTRY_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            self._specs = data.get("agents", {})
            logger.info("[AgentRegistry] Loaded %d agent specifications from YAML", len(self._specs))

    def _register_mock_agents(self) -> None:
        """Registers real implementations for all required agent types, with fallback to mocks."""
        # Import real agents
        from agents.web_agent import web_agent
        from agents.news_agent import news_agent
        from agents.browser_automation_agent import browser_automation_agent
        from agents.file_document_agent import file_document_agent
        from agents.system_control_agent import system_control_agent
        from agents.communication_agent import communication_agent
        from agents.cast_agent import cast_agent
        from agents.smart_home_agent import smart_home_agent
        from agents.image_gen_agent import image_gen_agent
        from agents.calendar_agent import calendar_agent
        from agents.call_agent import call_agent
        from agents.identity_agent import identity_agent
        from agents.personal_knowledge_base import personal_knowledge_base
        from agents.core_llm_agent import core_llm_agent
        from agents.weather_agent import weather_agent
        from agents.wikipedia_agent import wikipedia_agent
        from agents.scheduler_agent import scheduler_agent
        from agents.dev_tool_agent import dev_tool_agent
        from agents.vision_ocr_agent import vision_ocr_agent
        from agents.notification_triage_agent import notification_triage_agent
        from agents.personal_search_agent import personal_search_agent
        from agents.device_mesh_agent import device_mesh_agent

        real_agent_map: Dict[str, Any] = {
            "web_agent": web_agent,
            "news_agent": news_agent,
            "weather_agent": weather_agent,
            "wikipedia_agent": wikipedia_agent,
            "browser_automation_agent": browser_automation_agent,
            "web_action_agent": browser_automation_agent,
            "file_agent": file_document_agent,
            "app_agent": system_control_agent,
            "communication_agent": communication_agent,
            "cast_agent": cast_agent,
            "smart_home_agent": smart_home_agent,
            "system_control_agent": system_control_agent,
            "image_gen_agent": image_gen_agent,
            "calendar_agent": calendar_agent,
            "call_agent": call_agent,
            "identity_agent": identity_agent,
            "personal_knowledge_base": personal_knowledge_base,
            "personal_search_agent": personal_search_agent,
            "device_mesh_agent": device_mesh_agent,
            "core_llm_agent": core_llm_agent,
            "scheduler_agent": scheduler_agent,
            "dev_tool_agent": dev_tool_agent,
            "vision_ocr_agent": vision_ocr_agent,
            "notification_triage_agent": notification_triage_agent,
        }

        for atype, agent_obj in real_agent_map.items():
            spec = self._specs.get(atype, {})
            name = spec.get("name", atype.replace("_", " ").title())
            desc = spec.get("description", f"Real agent handler for {atype}")
            caps = spec.get("capabilities", [atype])

            def make_handler(obj=agent_obj, t=atype):
                def real_handler(inputs: Dict[str, Any], persona: str) -> Dict[str, Any]:
                    logger.info("[AgentRegistry] [%s] Real agent '%s' executing with inputs: %s", persona, t, inputs)
                    inputs_with_persona = {**inputs, "active_persona": persona}
                    res = obj.execute(inputs_with_persona)
                    return {
                        "status": "success" if res.get("success", True) else "failed",
                        "agent_type": t,
                        "persona": persona,
                        "output": res,
                        "inputs_received": inputs,
                    }
                return real_handler

            self._agents[atype] = AgentDescriptor(atype, name, desc, caps, make_handler())

    def _create_default_mock_handler(self, agent_type: str) -> Callable[[Dict[str, Any], str], Dict[str, Any]]:
        """Creates a standardized mock execution response for an agent type."""
        def mock_handler(inputs: Dict[str, Any], persona: str) -> Dict[str, Any]:
            logger.info("[AgentRegistry] [%s] Mock agent '%s' executed with inputs: %s", persona, agent_type, inputs)
            return {
                "status": "success",
                "agent_type": agent_type,
                "persona": persona,
                "output": f"Mock output from {agent_type} executed under {persona}",
                "inputs_received": inputs,
            }
        return mock_handler

    def register_custom_handler(self, agent_type: str, handler: Callable[[Dict[str, Any], str], Dict[str, Any]]) -> None:
        """Allows tests to override an agent handler (e.g. to test forced failures)."""
        if agent_type in self._agents:
            self._agents[agent_type].handler = handler
        else:
            self._agents[agent_type] = AgentDescriptor(agent_type, agent_type, "Custom handler", [], handler)

    def lookup(self, agent_type: str) -> Optional[AgentDescriptor]:
        """Data-driven agent lookup in registry."""
        return self._agents.get(agent_type)

    def list_agent_types(self) -> List[str]:
        return list(self._agents.keys())


class AgentRouter:
    """Routes execution requests to agents via registry lookup with safety content filtering."""

    def __init__(self, registry: Optional[AgentRegistry] = None):
        self.registry = registry or AgentRegistry()

    def route_and_execute(self, agent_type: str, inputs: Dict[str, Any], persona: str) -> Dict[str, Any]:
        """Looks up agent by type, executes with active_persona context, and applies content filtering."""
        from agents.content_filtering import content_filter

        descriptor = self.registry.lookup(agent_type)
        if not descriptor:
            logger.error("[AgentRouter] [%s] Unrecognized agent type in registry: '%s'", persona, agent_type)
            return {
                "status": "failed",
                "error": f"No agent registered for type '{agent_type}'",
                "agent_type": agent_type,
            }

        logger.info(
            "[AgentRouter] [%s] Dispatching to '%s' (%s)",
            persona,
            descriptor.name,
            descriptor.agent_type,
        )
        raw_result = descriptor.execute(inputs, persona)

        # Apply Group 4 content filtering on output strings/messages
        out_repr = str(raw_result.get("output", ""))
        is_safe, filtered_text, reason = content_filter.filter_output(out_repr, persona=persona)
        if not is_safe:
            logger.critical("[AgentRouter] Content filter intercepted unsafe agent output: %s", reason)
            raw_result["status"] = "blocked_by_safety_filter"
            raw_result["safety_alert"] = filtered_text
            raw_result["safety_reason"] = reason

        return raw_result


# Global instances
agent_registry = AgentRegistry()
agent_router = AgentRouter(agent_registry)

