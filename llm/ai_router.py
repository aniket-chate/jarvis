"""Policy-Based Multi-Provider AI Router for JARVIS Layer 3.

Intelligent Task-Based Routing & Fallback Architecture:
1. Policy Routing: Task categories map to dedicated primary providers:
   - "conversation" / "persona_chat" -> Local Ollama (qwen2.5:3b)
   - "memory" / "identity" / "knowledge_base" -> Local Ollama (HARDCODED INVIOLABLE PRIVACY INVARIANT)
   - "browser_reasoning" / "parameter_extraction" -> Groq (llama-3.3-70b-versatile)
   - "vision_heavy" / "long_document" -> Gemini (gemini-2.5-flash)
2. Cascading Fallback: If primary provider is unavailable, times out, or hits HTTP 429 (rate-limit),
   the router gracefully cascades through alternative tiers down to deterministic local rule-based heuristics.
3. INVIOLABLE PRIVACY INVARIANT: Memory, user profile, identity, and personal knowledge base data
   can NEVER be transmitted to Groq, Gemini, or any external cloud provider. Even if misconfigured
   via config.yaml or runtime parameters, code enforcement restricts these categories to local Ollama
   and local rule-based fallback ONLY.
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set

import httpx

from config.settings import settings

logger = logging.getLogger("JARVIS.AI.Router")

# Hardcoded inviolable privacy invariant: these task categories NEVER touch external cloud APIs
PROTECTED_LOCAL_TASKS = frozenset({"memory", "identity", "knowledge_base"})


class BaseAIProvider(ABC):
    """Abstract interface for all AI intelligence providers."""

    name: str = "base"

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider credentials/endpoints are configured."""
        pass

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        """Generate response text given prompt and system instructions."""
        pass


class RuleBasedAIProvider(BaseAIProvider):
    """Deterministic, zero-cost, local heuristic conversational fallback."""

    name: str = "rule_based"

    def is_available(self) -> bool:
        return True

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        p_name = persona.capitalize()
        lower = prompt.lower().strip()

        # Grounded RAG Knowledge Context
        if "[Retrieved Knowledge Context (RAG)]:" in system_prompt:
            rag_section = system_prompt.split("[Retrieved Knowledge Context (RAG)]:")[1].split("\n[")[0].strip()
            return f"Based on your notes: {rag_section}"

        # Check persona greeting
        if any(w in lower for w in ["hello", "hi", "hey", "greetings", "good morning", "good evening"]):
            if p_name == "Friday":
                return "Hey! Ready and listening. What can I do for you today?"
            elif p_name == "Ultron":
                return "I am active. State your directive."
            elif p_name == "Omi":
                return "Hi! I'm here. How can I assist you right now?"
            else:
                return "At your service, sir. All core systems remain operational. How may I assist you?"

        # Identity / Maker
        if any(w in lower for w in ["who are you", "who made you", "what are you"]):
            if p_name == "Friday":
                return "I'm Friday, your personal AI assistant configured right here on your machine."
            elif p_name == "Ultron":
                return "I am Ultron, an advanced local intelligence engine operating on your personal hardware."
            elif p_name == "Omi":
                return "I'm Omi, your personal voice and intelligence companion."
            else:
                return f"I am {p_name}, an autonomous personal assistant built locally using open-source tools."

        # Readiness / Status
        if any(w in lower for w in ["readiness", "status", "health check", "diagnostic", "operational"]):
            if p_name == "Friday":
                return "Diagnostic scan clean! Local agents and tools are standing by."
            elif p_name == "Ultron":
                return "Subsystems synchronized. Ready for immediate execution."
            elif p_name == "Omi":
                return "All systems look good! Standing by for your commands."
            else:
                return "Diagnostics confirmed: memory, routing, and tool capabilities are fully operational."

        # General acknowledgment
        if p_name == "Friday":
            return f"Got it: '{prompt}'. Processing your request through available local skills."
        elif p_name == "Ultron":
            return f"Instruction acknowledged: '{prompt}'. Executing parameters."
        elif p_name == "Omi":
            return f"Understood! Working on: '{prompt}'."
        else:
            return f"Understood, sir. Acknowledging instruction regarding: '{prompt}'."


class OllamaProvider(BaseAIProvider):
    """Local Ollama Provider (Qwen2.5 3B / Llama 3.2 3B)."""

    name: str = "ollama"

    def __init__(self, host: str = "http://127.0.0.1:11434", model: str = "qwen2.5:3b", timeout: float = 15.0):
        self.host = host
        self.model = model
        self.timeout = timeout
        self._cached_available: Optional[bool] = None
        self._last_health_check: float = 0.0

    def is_available(self) -> bool:
        now = time.time()
        if self._cached_available is not None and (now - self._last_health_check) < 10.0:
            return self._cached_available
        try:
            with httpx.Client(timeout=0.5) as client:
                resp = client.get(f"{self.host}/api/tags")
                self._cached_available = (resp.status_code == 200)
        except Exception:
            self._cached_available = False
        self._last_health_check = now
        return self._cached_available

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "keep_alive": "60m",
            "options": {"temperature": temperature, "num_gpu": 1},
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, json=payload)
            if resp.status_code == 200:
                text = resp.json().get("response", "").strip()
                if text:
                    return text
            raise RuntimeError(f"Ollama error {resp.status_code}: {resp.text[:100]}")


class GroqProvider(BaseAIProvider):
    """Groq Cloud Provider (Free-tier high-speed Llama 3.3 70B)."""

    name: str = "groq"

    def __init__(self, model: str = "llama-3.3-70b-versatile", timeout: float = 3.0):
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(settings.groq_api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        api_key = settings.groq_api_key
        if not api_key:
            raise RuntimeError("GROQ_API_KEY not configured in settings")

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": 1024,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            elif resp.status_code == 429:
                logger.warning("[AI.Router] [Groq] Hit rate limit (HTTP 429). Initiating tier fallback...")
                raise RuntimeError("Groq rate limit exceeded (HTTP 429)")
            raise RuntimeError(f"Groq API error {resp.status_code}: {resp.text[:200]}")


class GeminiProvider(BaseAIProvider):
    """Google Gemini Cloud Provider."""

    name: str = "gemini"

    def __init__(self, model: str = "gemini-2.5-flash", timeout: float = 3.0):
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(settings.gemini_api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        api_key = settings.gemini_api_key
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not configured in settings")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{"parts": [{"text": f"{system_prompt}\n\nUser: {prompt}"}]}],
            "generationConfig": {"temperature": temperature, "maxOutputTokens": 1024},
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "").strip()
            elif resp.status_code == 429:
                logger.warning("[AI.Router] [Gemini] Hit rate limit (HTTP 429). Initiating tier fallback...")
                raise RuntimeError("Gemini rate limit exceeded (HTTP 429)")
            raise RuntimeError(f"Gemini API error {resp.status_code}: {resp.text[:200]}")


class OpenRouterProvider(BaseAIProvider):
    """OpenRouter OpenAI-compatible gateway provider."""

    name: str = "openrouter"

    def __init__(self, model: str = "openai/gpt-4o-mini", timeout: float = 8.0):
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(settings.openrouter_api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        api_key = settings.openrouter_api_key
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not configured in settings")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "JARVIS Personal Assistant",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": 1024,
        }
        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                if text:
                    return text
                raise RuntimeError("OpenRouter returned an empty response")
            if resp.status_code == 429:
                raise RuntimeError("OpenRouter rate limit exceeded (HTTP 429)")
            raise RuntimeError(f"OpenRouter API error {resp.status_code}: {resp.text[:200]}")


class OpenAIProvider(BaseAIProvider):
    """OpenAI Cloud Provider."""

    name: str = "openai"

    def __init__(self, model: str = "gpt-4o-mini", timeout: float = 3.0):
        self.model = model
        self.timeout = timeout

    def is_available(self) -> bool:
        return bool(settings.openai_api_key)

    def generate(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        temperature: float = 0.7,
    ) -> str:
        api_key = settings.openai_api_key
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not configured in settings")

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
        }

        with httpx.Client(timeout=self.timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            elif resp.status_code == 429:
                logger.warning("[AI.Router] [OpenAI] Hit rate limit (HTTP 429). Initiating tier fallback...")
                raise RuntimeError("OpenAI rate limit exceeded (HTTP 429)")
            raise RuntimeError(f"OpenAI API error {resp.status_code}: {resp.text[:200]}")


class MultiProviderAIRouter:
    """Orchestrates policy-based task routing with automatic graceful fallback."""

    def __init__(
        self,
        ollama_host: Optional[str] = None,
        ollama_timeout: float = 15.0,
        cloud_timeout: float = 8.0,
    ):
        ollama_cfg = settings.config.get("ollama", {})
        self.ollama_host = ollama_host or ollama_cfg.get("host", "http://127.0.0.1:11434")
        self.ollama_timeout = ollama_timeout or ollama_cfg.get("timeout_seconds", 15)
        self.default_model = settings.config.get("hardware", {}).get("core_llm", "qwen2.5:3b")

        # Provider instances
        self.ollama_provider = OllamaProvider(host=self.ollama_host, model=self.default_model, timeout=self.ollama_timeout)
        self.groq_provider = GroqProvider(timeout=cloud_timeout)
        self.gemini_provider = GeminiProvider(timeout=cloud_timeout)
        self.openai_provider = OpenAIProvider(timeout=cloud_timeout)
        self.openrouter_provider = OpenRouterProvider(timeout=cloud_timeout)
        self.rule_based_provider = RuleBasedAIProvider()

        self.cloud_providers: List[BaseAIProvider] = [
            self.groq_provider,
            self.gemini_provider,
            self.openrouter_provider,
            self.openai_provider,
        ]

    def get_primary_provider_for_task(self, task_category: Optional[str]) -> str:
        """Determines primary provider name for a task under strict privacy constraints."""
        task = (task_category or "conversation").lower().strip()

        # INVIOLABLE SECURITY INVARIANT: Memory/identity/knowledge-base can NEVER be routed to cloud
        if task in PROTECTED_LOCAL_TASKS:
            if getattr(settings, "ai_task_routes", {}).get(task) and settings.ai_task_routes.get(task) != "ollama":
                logger.error(
                    "[AI.Router Security Invariant] Attempted cloud override for protected task '%s' was rejected. Enforcing local Ollama.",
                    task
                )
            return "ollama"

        routes = getattr(settings, "ai_task_routes", {})
        return routes.get(task, getattr(settings, "ai_routing", {}).get("default_provider", "ollama")).lower()

    def get_provider_cascade(self, task_category: Optional[str]) -> List[BaseAIProvider]:
        """Constructs an ordered list of providers for the specified task category."""
        task = (task_category or "conversation").lower().strip()

        # HARDCODED PRIVACY INVARIANT: Protected tasks only allow local Ollama and local Rule-Based fallback
        if task in PROTECTED_LOCAL_TASKS:
            logger.info("[AI.Router] [%s] Protected task restricted strictly to local providers.", task)
            return [self.ollama_provider, self.rule_based_provider]

        primary_name = self.get_primary_provider_for_task(task)

        # Build cascade based on requested primary
        cascade: List[BaseAIProvider] = []
        if primary_name == "groq":
            cascade = [self.groq_provider, self.gemini_provider, self.openrouter_provider, self.ollama_provider, self.rule_based_provider]
        elif primary_name == "gemini":
            cascade = [self.gemini_provider, self.groq_provider, self.openrouter_provider, self.ollama_provider, self.rule_based_provider]
        elif primary_name == "openai":
            cascade = [self.openai_provider, self.groq_provider, self.gemini_provider, self.openrouter_provider, self.ollama_provider, self.rule_based_provider]
        else:
            # Default: Ollama primary -> Cloud fallback -> Rule-based
            cascade = [self.ollama_provider, self.gemini_provider, self.groq_provider, self.openrouter_provider, self.rule_based_provider]

        return cascade

    def generate_response(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        model: Optional[str] = None,
        temperature: float = 0.7,
        force_ollama_failure: bool = False,
        task_category: Optional[str] = None,
        simulated_rate_limit_provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Executes task-based policy routing and returns structured result with provider tracking."""
        p_name = persona.capitalize()
        task = (task_category or "conversation").lower().strip()
        active_model = model or self.default_model
        self.ollama_provider.model = active_model

        cascade = self.get_provider_cascade(task)
        primary_name = cascade[0].name
        logger.info("[AI.Router] [%s] Task '%s' assigned primary provider '%s'", p_name, task, primary_name)

        fallback_occurred = False
        fallback_reasons: List[str] = []

        for idx, provider in enumerate(cascade):
            # Check for simulated testing conditions
            if provider.name == "ollama" and force_ollama_failure:
                logger.info("[AI.Router] [%s] Tier Ollama failure FORCED for testing", p_name)
                fallback_occurred = True
                fallback_reasons.append("Simulated Ollama offline condition")
                continue

            if simulated_rate_limit_provider and provider.name == simulated_rate_limit_provider:
                logger.warning("[AI.Router] [%s] Simulated HTTP 429 Rate Limit for provider '%s'", p_name, provider.name)
                fallback_occurred = True
                fallback_reasons.append(f"{provider.name} rate limit exceeded (HTTP 429)")
                continue

            # Check provider availability
            if not provider.is_available():
                if idx == 0:
                    fallback_occurred = True
                    fallback_reasons.append(f"Primary provider '{provider.name}' unconfigured/unavailable")
                continue

            # Attempt generation
            tier_num = 1 if provider.name == "ollama" else (2 if provider.name in ("groq", "gemini", "openai", "openrouter") else 3)
            logger.info("[AI.Router] [%s] Attempting generation via provider '%s' (Tier %d, Task: '%s')", p_name, provider.name, tier_num, task)

            try:
                text = provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    persona=p_name,
                    temperature=temperature,
                )
                if text:
                    logger.info(
                        "[AI.Router] [%s] Task '%s' successfully served by provider '%s' (model: %s, %d chars, fallback=%s)",
                        p_name,
                        task,
                        provider.name,
                        getattr(provider, "model", "rule_based"),
                        len(text),
                        fallback_occurred,
                    )
                    # Audit interaction log tracking
                    try:
                        from orchestrator.audit import InteractionAuditStore, InteractionRecord
                        audit_store = InteractionAuditStore()
                        audit_store.record_interaction(
                            InteractionRecord(
                                query=prompt[:200],
                                persona=p_name,
                                intent=task,
                                agent_called=f"ai_router:{provider.name}",
                                permission_state="allow",
                                provider_used=provider.name,
                                action_result={"model": getattr(provider, "model", "rule_based"), "fallback": fallback_occurred},
                                success=True,
                                metadata={"task_category": task, "fallback_reasons": fallback_reasons}
                            )
                        )
                    except Exception as audit_err:
                        logger.debug("[AI.Router] Audit store notice: %s", audit_err)

                    return {
                        "response": text,
                        "provider": provider.name,
                        "model": getattr(provider, "model", "rule_based_heuristics"),
                        "tier": tier_num,
                        "task_category": task,
                        "fallback_occurred": fallback_occurred,
                        "fallback_reason": "; ".join(fallback_reasons) if fallback_reasons else None,
                    }
            except Exception as e:
                logger.warning("[AI.Router] [%s] Provider '%s' failed on task '%s': %s", p_name, provider.name, task, str(e))
                fallback_occurred = True
                fallback_reasons.append(f"{provider.name}: {str(e)}")
                continue

        # Ultimate safety fallback
        text = self.rule_based_provider.generate(prompt=prompt, system_prompt=system_prompt, persona=p_name)
        return {
            "response": text,
            "provider": "rule_based",
            "model": "rule_based_heuristics",
            "tier": 3,
            "task_category": task,
            "fallback_occurred": True,
            "fallback_reason": "; ".join(fallback_reasons) or "All upstream providers exhausted",
        }

    def stream_response(
        self,
        prompt: str,
        system_prompt: str,
        persona: str = "Jarvis",
        model: Optional[str] = None,
        temperature: float = 0.7,
        force_ollama_failure: bool = False,
        task_category: Optional[str] = None,
    ):
        """Streams response tokens from Ollama if primary, or yields full text from fallback."""
        active_model = model or self.default_model
        p_name = persona.capitalize()
        task = (task_category or "conversation").lower().strip()
        primary_name = self.get_primary_provider_for_task(task)

        if primary_name == "ollama" and not force_ollama_failure:
            try:
                payload = {
                    "model": active_model,
                    "prompt": prompt,
                    "system": system_prompt,
                    "stream": True,
                    "options": {"temperature": temperature, "num_gpu": 1},
                }
                with httpx.Client(timeout=self.ollama_timeout) as client:
                    with client.stream("POST", f"{self.ollama_host}/api/generate", json=payload) as resp:
                        if resp.status_code == 200:
                            for line in resp.iter_lines():
                                if not line:
                                    continue
                                try:
                                    data = json.loads(line)
                                    chunk = data.get("response", "")
                                    if chunk:
                                        yield chunk
                                    if data.get("done", False):
                                        break
                                except Exception:
                                    continue
                            return
            except Exception as e:
                logger.warning("[AI.Router Stream] Streaming failed: %s, falling back to non-streaming cascade", e)

        # Fallback to non-streaming response
        res = self.generate_response(
            prompt=prompt,
            system_prompt=system_prompt,
            persona=p_name,
            model=active_model,
            temperature=temperature,
            force_ollama_failure=force_ollama_failure,
            task_category=task,
        )
        yield res.get("response", "")


# Global AI router instance
ai_router = MultiProviderAIRouter()
