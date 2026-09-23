"""Capability Providers registration."""

from capabilities.intelligence import capability_intelligence
from capabilities.providers.os_provider import OSWin32Provider
from capabilities.providers.browser_provider import ChromeCDPBrowserProvider
from capabilities.providers.scheduler_provider import APSchedulerProvider
from capabilities.providers.developer_provider import DeveloperTaskProvider
from capabilities.providers.file_provider import FileDocumentProvider
from capabilities.providers.search_provider import WebSearchProvider
from capabilities.providers.vision_provider import VisionOCRProvider
from capabilities.providers.audio_provider import AudioPerceptionProvider
from capabilities.providers.voice_provider import VoiceIntelligenceProvider
from capabilities.providers.wakeword_provider import WakeWordIntelligenceProvider
from capabilities.providers.multimodal_provider import MultimodalUnderstandingProvider
from capabilities.providers.persona_provider import PersonaManagerProvider
from capabilities.providers.emotion_provider import EmotionSocialContextProvider
from capabilities.providers.accessibility_provider import AccessibilityProvider
from capabilities.providers.knowledge_provider import KnowledgeProvider
from capabilities.providers.realtime_provider import RealTimeInfoProvider
from capabilities.providers.personal_search_provider import PersonalSearchProvider
from capabilities.providers.information_verification_provider import InformationVerificationProvider
from capabilities.providers.knowledge_synthesis_provider import KnowledgeSynthesisProvider
from capabilities.providers.device_mesh_provider import DeviceMeshProvider
from capabilities.providers.communication_provider import CommunicationHubProvider
from capabilities.providers.calendar_scheduler_provider import CalendarSchedulerProvider
from capabilities.providers.productivity_provider import PersonalProductivityProvider
from capabilities.providers.travel_navigation_provider import TravelNavigationProvider
from capabilities.providers.autonomous_agency_provider import AutonomousAgencyProvider
from capabilities.providers.workflow_automation_provider import (
    WorkflowAutomationProvider,
    workflow_automation_provider,
)
from capabilities.providers.monitoring_alerts_provider import (
    MonitoringAlertsProvider,
    monitoring_alerts_provider,
)
from capabilities.providers.smart_home_iot_provider import (
    SmartHomeIoTProvider,
    smart_home_iot_provider,
)
from capabilities.providers.physical_robotics_provider import (
    PhysicalRoboticsProvider,
    physical_robotics_provider,
)
from capabilities.providers.data_science_analytics_provider import (
    DataScienceAnalyticsProvider,
    data_science_analytics_provider,
)
from capabilities.providers.simulation_prediction_provider import (
    SimulationPredictionProvider,
    simulation_prediction_provider,
)
from capabilities.providers.security_identity_provider import (
    SecurityIdentityProvider,
    security_identity_provider,
)
from capabilities.providers.verification_diagnostics_provider import (
    VerificationDiagnosticsProvider,
    verification_diagnostics_provider,
)
from capabilities.providers.capability_evolution_provider import (
    CapabilityEvolutionProvider,
    capability_evolution_provider,
)


def register_default_providers():
    capability_intelligence.register_provider(OSWin32Provider())
    capability_intelligence.register_provider(ChromeCDPBrowserProvider())
    capability_intelligence.register_provider(APSchedulerProvider())
    capability_intelligence.register_provider(DeveloperTaskProvider())
    capability_intelligence.register_provider(FileDocumentProvider())
    capability_intelligence.register_provider(WebSearchProvider())
    capability_intelligence.register_provider(VisionOCRProvider())
    capability_intelligence.register_provider(AudioPerceptionProvider())
    capability_intelligence.register_provider(VoiceIntelligenceProvider())
    capability_intelligence.register_provider(WakeWordIntelligenceProvider())
    capability_intelligence.register_provider(MultimodalUnderstandingProvider())
    capability_intelligence.register_provider(PersonaManagerProvider())
    capability_intelligence.register_provider(EmotionSocialContextProvider())
    capability_intelligence.register_provider(AccessibilityProvider())
    capability_intelligence.register_provider(KnowledgeProvider())
    capability_intelligence.register_provider(RealTimeInfoProvider())
    capability_intelligence.register_provider(PersonalSearchProvider())
    capability_intelligence.register_provider(InformationVerificationProvider())
    capability_intelligence.register_provider(KnowledgeSynthesisProvider())
    capability_intelligence.register_provider(DeviceMeshProvider())
    capability_intelligence.register_provider(CommunicationHubProvider())
    capability_intelligence.register_provider(CalendarSchedulerProvider())
    capability_intelligence.register_provider(PersonalProductivityProvider())
    capability_intelligence.register_provider(TravelNavigationProvider())
    capability_intelligence.register_provider(AutonomousAgencyProvider())
    capability_intelligence.register_provider(workflow_automation_provider)
    capability_intelligence.register_provider(monitoring_alerts_provider)
    capability_intelligence.register_provider(smart_home_iot_provider)
    capability_intelligence.register_provider(physical_robotics_provider)
    capability_intelligence.register_provider(data_science_analytics_provider)
    capability_intelligence.register_provider(simulation_prediction_provider)
    capability_intelligence.register_provider(security_identity_provider)
    capability_intelligence.register_provider(verification_diagnostics_provider)
    capability_intelligence.register_provider(capability_evolution_provider)


register_default_providers()


