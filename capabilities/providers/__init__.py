"""Capability provider registration with lazy/optional imports.

Provider modules are intentionally not imported at package import time. This keeps
core security tests and lightweight deployments from failing because an optional
hardware/ML integration is absent. Registration reports unavailable optional
providers instead of crashing the gateway.
"""

import importlib
import logging

from capabilities.intelligence import capability_intelligence

logger = logging.getLogger("JARVIS.Providers.Registry")

# (module, exported provider symbol). Symbols may be provider instances.
_PROVIDER_EXPORTS = [
    ("capabilities.providers.os_provider", "OSWin32Provider"),
    ("capabilities.providers.browser_provider", "ChromeCDPBrowserProvider"),
    ("capabilities.providers.scheduler_provider", "APSchedulerProvider"),
    ("capabilities.providers.developer_provider", "DeveloperTaskProvider"),
    ("capabilities.providers.file_provider", "FileDocumentProvider"),
    ("capabilities.providers.search_provider", "WebSearchProvider"),
    ("capabilities.providers.vision_provider", "VisionOCRProvider"),
    ("capabilities.providers.audio_provider", "AudioPerceptionProvider"),
    ("capabilities.providers.voice_provider", "VoiceIntelligenceProvider"),
    ("capabilities.providers.wakeword_provider", "WakeWordIntelligenceProvider"),
    ("capabilities.providers.multimodal_provider", "MultimodalUnderstandingProvider"),
    ("capabilities.providers.persona_provider", "PersonaManagerProvider"),
    ("capabilities.providers.emotion_provider", "EmotionSocialContextProvider"),
    ("capabilities.providers.accessibility_provider", "AccessibilityProvider"),
    ("capabilities.providers.knowledge_provider", "KnowledgeProvider"),
    ("capabilities.providers.realtime_provider", "RealTimeInfoProvider"),
    ("capabilities.providers.personal_search_provider", "PersonalSearchProvider"),
    ("capabilities.providers.information_verification_provider", "InformationVerificationProvider"),
    ("capabilities.providers.knowledge_synthesis_provider", "KnowledgeSynthesisProvider"),
    ("capabilities.providers.device_mesh_provider", "DeviceMeshProvider"),
    ("capabilities.providers.communication_provider", "CommunicationHubProvider"),
    ("capabilities.providers.calendar_scheduler_provider", "CalendarSchedulerProvider"),
    ("capabilities.providers.productivity_provider", "PersonalProductivityProvider"),
    ("capabilities.providers.travel_navigation_provider", "TravelNavigationProvider"),
    ("capabilities.providers.autonomous_agency_provider", "AutonomousAgencyProvider"),
    ("capabilities.providers.workflow_automation_provider", "workflow_automation_provider"),
    ("capabilities.providers.monitoring_alerts_provider", "monitoring_alerts_provider"),
    ("capabilities.providers.smart_home_iot_provider", "smart_home_iot_provider"),
    ("capabilities.providers.physical_robotics_provider", "physical_robotics_provider"),
    ("capabilities.providers.data_science_analytics_provider", "data_science_analytics_provider"),
    ("capabilities.providers.simulation_prediction_provider", "simulation_prediction_provider"),
    ("capabilities.providers.security_identity_provider", "security_identity_provider"),
    ("capabilities.providers.verification_diagnostics_provider", "verification_diagnostics_provider"),
    ("capabilities.providers.capability_evolution_provider", "capability_evolution_provider"),
]


def register_default_providers():
    """Register every provider whose optional dependencies are currently usable."""
    registered = []
    unavailable = []

    for module_name, export_name in _PROVIDER_EXPORTS:
        try:
            module = importlib.import_module(module_name)
            exported = getattr(module, export_name)
            provider = exported() if isinstance(exported, type) else exported
            capability_intelligence.register_provider(provider)
            registered.append(provider.provider_id)
        except Exception as exc:
            unavailable.append({"module": module_name, "error": str(exc)})
            logger.warning(
                "[Provider Registry] Skipping unavailable provider %s.%s: %s",
                module_name,
                export_name,
                exc,
            )

    logger.info(
        "[Provider Registry] Registered %d providers; skipped %d unavailable optional providers.",
        len(registered),
        len(unavailable),
    )
    return {"registered": registered, "unavailable": unavailable}


