"""JARVIS Capability Intelligence.

Implements the central CAPABILITY -> PROVIDERS abstraction.
Enables dynamic discovery, ranking, provider selection, and composition without
coupling the Cognitive Core to fixed agents.
"""

from collections import defaultdict
import logging
from typing import Any, Dict, List, Optional
from capabilities.base import BaseCapabilityProvider, ActionResult

logger = logging.getLogger("JARVIS.Capabilities.Intelligence")


class CapabilityIntelligence:
    """Discovers, ranks, and dynamically selects providers for requested capabilities."""

    def __init__(self):
        # Map of capability_name -> List[BaseCapabilityProvider]
        self._providers_by_capability: Dict[str, List[BaseCapabilityProvider]] = defaultdict(list)
        self._all_providers: Dict[str, BaseCapabilityProvider] = {}

    def register_provider(self, provider: BaseCapabilityProvider):
        """Registers a capability provider idempotently without duplicate entries."""
        if provider.provider_id in self._all_providers:
            self.unregister_provider(provider.provider_id)
        self._all_providers[provider.provider_id] = provider
        for cap in provider.supported_capabilities:
            existing_ids = [p.provider_id for p in self._providers_by_capability[cap]]
            if provider.provider_id not in existing_ids:
                self._providers_by_capability[cap].append(provider)
        logger.info(
            "[CapabilityIntelligence] Registered provider '%s' supporting: %s",
            provider.provider_id,
            provider.supported_capabilities,
        )

    def unregister_provider(self, provider_id: str):
        """Removes a provider dynamically (e.g. for swapping or testing)."""
        provider = self._all_providers.pop(provider_id, None)
        for cap in list(self._providers_by_capability.keys()):
            self._providers_by_capability[cap] = [
                p for p in self._providers_by_capability[cap] if p.provider_id != provider_id
            ]
            if not self._providers_by_capability[cap]:
                del self._providers_by_capability[cap]
        if provider:
            logger.info("[CapabilityIntelligence] Unregistered provider '%s'", provider_id)

    def select_provider(
        self,
        capability: str,
        context: Optional[Dict[str, Any]] = None,
        exclude_provider_ids: Optional[List[str]] = None,
    ) -> Optional[BaseCapabilityProvider]:
        """Selects the best available provider for the given capability, excluding any failed providers."""
        providers = self._providers_by_capability.get(capability, [])
        if not providers:
            # Fallback: check if capability has a wildcard or prefix match
            prefix = capability.split(".")[0] if "." in capability else capability
            for cap, provs in self._providers_by_capability.items():
                if cap.startswith(f"{prefix}."):
                    providers.extend(provs)

        if not providers:
            logger.warning("[CapabilityIntelligence] No providers registered for capability '%s'", capability)
            return None

        # Filter by availability and exclusion
        available = [p for p in providers if p.is_available()]
        if exclude_provider_ids:
            available = [p for p in available if p.provider_id not in exclude_provider_ids]

        if not available:
            logger.warning("[CapabilityIntelligence] All providers for '%s' are currently unavailable or excluded", capability)
            return None

        # Rank by (priority, -reliability, latency)
        ranked = sorted(
            available,
            key=lambda p: (p.metadata.priority, -p.reliability_score, p.metadata.estimated_latency_ms),
        )
        selected = ranked[0]
        logger.debug(
            "[CapabilityIntelligence] Selected provider '%s' for capability '%s' (reliability=%.2f)",
            selected.provider_id,
            capability,
            selected.reliability_score,
        )
        return selected

    def route_and_select(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Hierarchical classification, top-K ranking, contextual reranking, and provider selection.
        
        Lifecycle:
        USER INPUT -> Hierarchical Classifier -> TOP-K Candidates -> Contextual Reranker -> CAPABILITY -> PROVIDER
        """
        from cognitive.routing.hierarchical_classifier import hierarchical_classifier
        from capabilities.contracts.registry_50 import contract_registry_50

        # 1. Hierarchical Candidate Generation
        class_res = hierarchical_classifier.classify(user_input)

        if class_res.unknown or not class_res.top_k_capabilities:
            return {
                "status": "UNKNOWN",
                "domain": "UNKNOWN",
                "selected_capability": None,
                "operation": None,
                "provider": None,
                "confidence": 0.0,
                "requires_clarification": True,
                "clarification_prompt": "I could not identify a supported capability for this request.",
                "candidates": [],
            }

        # 2. Contextual Reranking using World Model and context
        ranked_caps = list(class_res.top_k_capabilities)
        if context and class_res.requires_context:
            active_win = str(context.get("active_window", "")).lower()
            if any(k in active_win for k in ["chrome", "browser", "edge"]):
                if "23_browser_intelligence" in ranked_caps:
                    ranked_caps.remove("23_browser_intelligence")
                    ranked_caps.insert(0, "23_browser_intelligence")

        selected_cap_id = ranked_caps[0]
        contract = contract_registry_50.get_contract(selected_cap_id)
        selected_op = contract.supported_operations[0] if contract and contract.supported_operations else selected_cap_id

        # 3. Dynamic Provider Selection
        provider = self.select_provider(selected_op, context=context)

        return {
            "status": "CLARIFICATION_REQUIRED" if class_res.requires_clarification else "ROUTED",
            "domain": class_res.domain,
            "selected_capability": selected_cap_id,
            "operation": selected_op,
            "contract": contract,
            "provider": provider,
            "confidence": class_res.confidence,
            "requires_clarification": class_res.requires_clarification,
            "requires_context": class_res.requires_context,
            "candidates": class_res.candidates,
            "top_k": ranked_caps,
        }


# Master Capability Intelligence singleton
capability_intelligence = CapabilityIntelligence()
