"""Central Settings and Secrets Configuration Layer for JARVIS.

All application modules MUST read configuration and secrets strictly through
this module. Never access os.environ or hardcode credentials inline.

Resilience rule:
If an API key or credential is missing or invalid, the dependent module is
flagged as unavailable with an informative log message, and the rest of JARVIS
continues operating normally.

Security rule:
NEVER log the actual key or token value anywhere. Log only presence,
absence, or authentication status.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml
from dotenv import load_dotenv

# Setup unified logger for configuration
logger = logging.getLogger("JARVIS.Config")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Root project paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
ENV_PATH = PROJECT_ROOT / ".env"
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
MODELS_DIR = PROJECT_ROOT / "models"


class PersonaConfig:
    def __init__(self, name: str, wake_model: str, tone: str, voice: str):
        self.name = name
        self.wake_model = wake_model
        self.tone = tone
        self.voice = voice

    def to_dict(self) -> Dict[str, str]:
        return {
            "name": self.name,
            "wake_model": self.wake_model,
            "tone": self.tone,
            "voice": self.voice,
        }


class Settings:
    def __init__(self):
        self.project_root = PROJECT_ROOT
        self.reload()

    def reload(self) -> None:
        """Reloads secrets from .env and architecture specs from config.yaml."""
        self._load_env()
        self._load_yaml()
        self._validate_and_log_status()

    def _load_env(self) -> None:
        """Loads secrets from git-ignored .env file."""
        if ENV_PATH.exists():
            load_dotenv(dotenv_path=ENV_PATH, override=True)
            logger.info("Loaded environment secrets from %s", ENV_PATH)
        else:
            logger.warning(".env file not found at %s; operating with default/empty secrets", ENV_PATH)

        # Extract secrets strictly through environment without ever logging their values
        self.tavily_api_key: Optional[str] = os.getenv("TAVILY_API_KEY") or None
        self.brave_api_key: Optional[str] = os.getenv("BRAVE_API_KEY") or None
        self.google_client_id: Optional[str] = os.getenv("GOOGLE_OAUTH_CLIENT_ID") or None
        self.google_client_secret: Optional[str] = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET") or None
        self.tailscale_auth_key: Optional[str] = os.getenv("TAILSCALE_AUTH_KEY") or None
        self.gateway_auth_token: Optional[str] = os.getenv("GATEWAY_AUTH_TOKEN") or None
        self.whatsapp_business_api_key: Optional[str] = os.getenv("WHATSAPP_BUSINESS_API_KEY") or None
        self.home_assistant_token: Optional[str] = os.getenv("HOME_ASSISTANT_TOKEN") or None
        # Cloud LLM fallback keys (strictly accessed through settings, never os.getenv directly in modules)
        self.openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY") or None
        self.gemini_api_key: Optional[str] = os.getenv("GEMINI_API_KEY") or None
        self.groq_api_key: Optional[str] = os.getenv("GROQ_API_KEY") or None
        self.openrouter_api_key: Optional[str] = os.getenv("OPENROUTER_API_KEY") or None
        self.llm_provider: str = os.getenv("JARVIS_LLM_PROVIDER") or "ollama"
        self.llm_fallback_enabled: bool = os.getenv("JARVIS_LLM_FALLBACK_ENABLED", "true").lower() == "true"

    def _load_yaml(self) -> None:
        """Loads central architecture and persona specs from config.yaml."""
        if not CONFIG_PATH.exists():
            raise FileNotFoundError(f"Missing mandatory configuration file: {CONFIG_PATH}")

        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}

        # Parse assistant personas
        self.personas: Dict[str, PersonaConfig] = {}
        for p in raw.get("assistant_personas", []):
            name = p.get("name", "Jarvis")
            self.personas[name.lower()] = PersonaConfig(
                name=name,
                wake_model=p.get("wake_model", f"{name.lower()}.onnx"),
                tone=p.get("tone", "calm, formal, precise"),
                voice=p.get("voice", "en_GB-alan-medium"),
            )

        self.config: Dict[str, Any] = raw
        self.active_persona_name: str = raw.get("active_persona", "Jarvis")
        self.hardware: Dict[str, Any] = raw.get("hardware", {})
        self.ollama: Dict[str, Any] = raw.get("ollama", {})
        self.voice: Dict[str, Any] = raw.get("voice", {})
        self.integrations: Dict[str, Any] = raw.get("integrations", {})
        self.locale: Dict[str, Any] = raw.get("locale", {
            "timezone": "Asia/Kolkata",
            "timezone_label": "IST",
            "country": "India",
            "country_code": "+91",
            "currency": "INR",
            "currency_symbol": "₹",
            "date_format": "DD-MM-YYYY",
            "search_region": "in"
        })
        self.ai_routing: Dict[str, Any] = raw.get("ai_routing", {})
        self.ai_task_routes: Dict[str, str] = self.ai_routing.get("task_routes", {})

    @property
    def timezone(self) -> str:
        return self.locale.get("timezone", "Asia/Kolkata")

    @property
    def currency(self) -> str:
        return self.locale.get("currency", "INR")

    @property
    def currency_symbol(self) -> str:
        return self.locale.get("currency_symbol", "₹")

    @property
    def default_country_code(self) -> str:
        return self.locale.get("country_code", "+91")

    @property
    def date_format(self) -> str:
        return self.locale.get("date_format", "DD-MM-YYYY")

    def _validate_and_log_status(self) -> None:
        """Audits all integration credentials and sets availability without logging values."""
        # 1. Search availability
        if self.tavily_api_key:
            self.search_available = True
            self.search_provider = "tavily"
        elif self.brave_api_key:
            self.search_available = True
            self.search_provider = "brave"
        else:
            self.search_available = False
            self.search_provider = None
            logger.warning("[Search Module] Neither TAVILY_API_KEY nor BRAVE_API_KEY found in .env. Web search will be disabled.")

        # 2. Google OAuth credentials
        has_env_oauth = bool(self.google_client_id and self.google_client_secret)
        has_file_oauth = (CREDENTIALS_DIR / "credentials.json").exists()
        self.google_oauth_configured = has_env_oauth or has_file_oauth

        if not self.google_oauth_configured:
            logger.warning("[Google Skills] No Google OAuth credentials found in .env or credentials/. Google Calendar and Gmail skills will be disabled.")

        # 3. Home Assistant
        ha_cfg = self.integrations.get("home_assistant", {})
        if ha_cfg.get("enabled", False) and not self.home_assistant_token:
            logger.warning("[Home Assistant] Enabled in config.yaml but HOME_ASSISTANT_TOKEN is not set in .env. Home Assistant skill will be disabled.")
            self.home_assistant_available = False
        else:
            self.home_assistant_available = ha_cfg.get("enabled", False) and bool(self.home_assistant_token)

        # 4. WhatsApp Business
        wa_cfg = self.integrations.get("whatsapp_business", {})
        if wa_cfg.get("enabled", False) and not self.whatsapp_business_api_key:
            logger.info("[WhatsApp] WHATSAPP_BUSINESS_API_KEY not configured. WhatsApp integration disabled.")
            self.whatsapp_available = False
        else:
            self.whatsapp_available = wa_cfg.get("enabled", False) and bool(self.whatsapp_business_api_key)

        # 5. Tailscale
        self.tailscale_configured = bool(self.tailscale_auth_key)

        # 6. Cloud LLM Fallback Availability
        self.openai_available = bool(self.openai_api_key)
        self.gemini_available = bool(self.gemini_api_key)
        self.groq_available = bool(self.groq_api_key)
        self.openrouter_available = bool(self.openrouter_api_key)
        self.cloud_llm_fallback_available = self.openai_available or self.gemini_available or self.groq_available or self.openrouter_available

    def check_secrets(self) -> Dict[str, Any]:
        """Startup routine reporting which keys are present and which modules are active vs disabled.

        Zero-leak guarantee: Reports ONLY boolean presence or 'ACTIVE'/'DISABLED' status.
        Never reveals or prints raw secret values.
        """
        report = {
            "keys_present": {
                "TAVILY_API_KEY": bool(self.tavily_api_key),
                "BRAVE_API_KEY": bool(self.brave_api_key),
                "GOOGLE_OAUTH_CLIENT_ID": bool(self.google_client_id),
                "GOOGLE_OAUTH_CLIENT_SECRET": bool(self.google_client_secret),
                "TAILSCALE_AUTH_KEY": bool(self.tailscale_auth_key),
                "GATEWAY_AUTH_TOKEN": bool(self.gateway_auth_token),
                "WHATSAPP_BUSINESS_API_KEY": bool(self.whatsapp_business_api_key),
                "HOME_ASSISTANT_TOKEN": bool(self.home_assistant_token),
                "OPENAI_API_KEY": bool(self.openai_api_key),
                "GEMINI_API_KEY": bool(self.gemini_api_key),
                "GROQ_API_KEY": bool(self.groq_api_key),
                "OPENROUTER_API_KEY": bool(self.openrouter_api_key),
            },
            "modules_status": {
                "web_search": "ACTIVE" if self.search_available else "DISABLED",
                "google_calendar": "ACTIVE" if self.google_oauth_configured else "DISABLED",
                "google_gmail": "ACTIVE" if self.google_oauth_configured else "DISABLED",
                "home_assistant": "ACTIVE" if self.home_assistant_available else "DISABLED",
                "whatsapp_business": "ACTIVE" if self.whatsapp_available else "DISABLED",
                "tailscale_mesh": "ACTIVE" if self.tailscale_configured else "DISABLED (Using local network / Tailscale IP)",
                "cloud_llm_fallback": "ACTIVE" if self.cloud_llm_fallback_available else "DISABLED (Local Ollama / Rule-Based only)",
                "device_gateway_auth": "ENFORCED" if self.gateway_auth_token else "DISABLED (GATEWAY_AUTH_TOKEN missing)",
            },
        }

        # Print structured audit log without leaking key values
        print("\n" + "=" * 60)
        print(" JARVIS CONFIG & SECRETS STARTUP AUDIT")
        print("=" * 60)
        print(" [Credentials Presence]")
        for key, present in report["keys_present"].items():
            status_str = "PRESENT" if present else "ABSENT"
            print(f"   - {key:<28}: {status_str}")

        print("\n [Dependent Modules Status]")
        for mod, status in report["modules_status"].items():
            print(f"   - {mod:<28}: {status}")
        print("=" * 60 + "\n")

        return report

    # Public helper methods
    def get_persona(self, name: Optional[str] = None) -> PersonaConfig:
        """Returns the requested persona or the current active persona."""
        lookup = (name or self.active_persona_name).lower()
        if lookup in self.personas:
            return self.personas[lookup]
        return self.personas.get("jarvis", PersonaConfig("Jarvis", "jarvis.onnx", "calm, formal, precise", "en_GB-alan-medium"))

    def set_active_persona(self, name: str) -> bool:
        """Switches the active persona dynamically when a wake word fires."""
        lookup = name.strip().lower()
        if lookup in self.personas:
            self.active_persona_name = self.personas[lookup].name
            logger.info("Active persona switched to: %s", self.active_persona_name)
            return True
        logger.warning("Attempted to switch to unknown persona '%s'; maintaining %s", name, self.active_persona_name)
        return False

    def list_personas(self) -> List[Dict[str, str]]:
        """Lists all registered personas."""
        return [p.to_dict() for p in self.personas.values()]


# Central global singleton instance
settings = Settings()
