"""Ollama Client for JARVIS Core LLM (Qwen2.5 3B) and Vision (Moondream).

Designed specifically for 4GB VRAM target (NVIDIA RTX 2050) with graceful degradation.
If the Ollama engine fails to respond or is offline, this module logs the incident,
notifies the caller cleanly, and prevents any hard crashes or endless loops.
"""

import logging
from typing import Dict, List, Optional, Any
import httpx
from config.settings import settings
from llm.personas import get_system_prompt

logger = logging.getLogger("JARVIS.LLM")


def discover_ollama_binary() -> Optional[str]:
    """Finds the ollama executable on Windows or in PATH."""
    import shutil
    import os

    # 1. Check system PATH
    found = shutil.which("ollama") or shutil.which("ollama.exe")
    if found and os.path.exists(found):
        return found

    # 2. Check standard Windows installation directories
    candidate_paths = [
        r"D:\Ollama\ollama.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
        r"C:\Program Files (x86)\Ollama\ollama.exe",
        r"C:\Ollama\ollama.exe",
    ]
    for p in candidate_paths:
        if os.path.exists(p):
            return p
    return None


class OllamaClient:
    def __init__(self):
        self.host = settings.ollama.get("host", "http://127.0.0.1:11434").rstrip("/")
        self.default_model = settings.hardware.get("core_llm", "qwen2.5:3b")
        self.vision_model = settings.hardware.get("vision_llm", "moondream:latest")
        self.timeout = httpx.Timeout(float(settings.ollama.get("timeout_seconds", 30)), connect=2.0)
        self.retry_limit = int(settings.ollama.get("retry_limit", 1))
        self._last_health_cache: Optional[Dict[str, Any]] = None
        self._last_health_ts: float = 0.0

    async def check_health(self) -> Dict[str, Any]:
        """Checks if Ollama service is reachable and lists available models with 5s caching."""
        import time
        now = time.time()
        if self._last_health_cache is not None and (now - self._last_health_ts) < 5.0:
            return self._last_health_cache

        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(2.5, connect=2.0)) as client:
                res = await client.get(f"{self.host}/api/tags")
                if res.status_code == 200:
                    models = [m.get("name") for m in res.json().get("models", [])]
                    has_core = any(self.default_model in m for m in models)
                    has_vision = any(self.vision_model.split(":")[0] in m for m in models)
                    res_data = {
                        "online": True,
                        "status": "healthy",
                        "models": models,
                        "core_ready": has_core,
                        "vision_ready": has_vision,
                    }
                    self._last_health_cache = res_data
                    self._last_health_ts = now
                    return res_data
        except Exception as e:
            logger.warning("[Ollama Engine] Health check failed: %s", str(e))

        res_data = {
            "online": False,
            "status": "unhealthy",
            "models": [],
            "core_ready": False,
            "vision_ready": False,
        }
        self._last_health_cache = res_data
        self._last_health_ts = now
        return res_data

    async def ensure_ollama_service(self) -> Dict[str, Any]:
        """Verifies if Ollama is running; if not, attempts to auto-launch `ollama serve` and waits for it to become ready."""
        import os
        import asyncio
        import subprocess

        # 1. Check if already online
        health = await self.check_health()
        if health.get("online"):
            return {"ready": True, "already_running": True}

        # 2. Not online: Discover binary on disk
        bin_path = discover_ollama_binary()
        if not bin_path:
            logger.error("[Ollama Engine] Ollama executable not found in PATH or standard installation locations.")
            return {"ready": False, "error": "Ollama executable not found on disk"}

        logger.info("[Ollama Engine] Ollama service is offline. Attempting to auto-launch '%s serve'...", bin_path)
        try:
            if os.name == "nt":
                proc = subprocess.Popen(
                    f'start "" /B "{bin_path}" serve',
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL
                )
            else:
                proc = subprocess.Popen(
                    [bin_path, "serve"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True
                )
            logger.info("[Ollama Engine] Auto-launched 'ollama serve' (PID=%d). Polling for readiness...", getattr(proc, "pid", 0))
        except Exception as launch_err:
            logger.error("[Ollama Engine] Failed to auto-launch 'ollama serve': %s", launch_err)
            return {"ready": False, "error": f"Failed to launch: {launch_err}"}

        # 3. Poll service for up to 10 seconds
        for i in range(1, 11):
            await asyncio.sleep(1.0)
            health = await self.check_health()
            if health.get("online"):
                logger.info("[Ollama Engine] Auto-launched Ollama service successfully initialized on second %d.", i)
                return {"ready": True, "auto_launched": True, "pid": proc.pid}

        logger.warning("[Ollama Engine] Auto-launched Ollama service did not respond within 10 seconds.")
        return {"ready": False, "error": "Ollama launched but did not respond within 10 seconds"}

    async def warm_up(self, max_retries: int = 4, initial_delay: float = 1.0) -> Dict[str, Any]:
        """Performs actual generation test against Core LLM to verify weights are warm in VRAM/RAM.
        
        Attempts auto-launch if service is offline. Returns status dict with ready flag.
        """
        import time
        import asyncio

        # Pre-check: Ensure service is running or auto-launch it
        service_status = await self.ensure_ollama_service()
        if not service_status.get("ready"):
            logger.warning("[Ollama WarmCheck] Ollama service offline and auto-launch failed: %s", service_status.get("error"))

        delay = initial_delay
        payload = {
            "model": self.default_model,
            "prompt": "ping",
            "stream": False,
            "keep_alive": "60m",
            "options": {"num_predict": 1, "temperature": 0.0},
        }

        for attempt in range(1, max_retries + 1):
            t0 = time.perf_counter()
            try:
                async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=2.0)) as client:
                    res = await client.post(f"{self.host}/api/generate", json=payload)
                    dur_ms = (time.perf_counter() - t0) * 1000
                    if res.status_code == 200:
                        logger.info(
                            "[Ollama WarmCheck] Warm test generation succeeded on attempt %d (model=%s, dur=%.1fms)",
                            attempt,
                            self.default_model,
                            dur_ms,
                        )
                        return {
                            "ready": True,
                            "attempt": attempt,
                            "duration_ms": round(dur_ms, 1),
                            "model": self.default_model,
                        }
                    else:
                        logger.warning(
                            "[Ollama WarmCheck] Attempt %d: status %d (%s). Retrying in %.1fs...",
                            attempt,
                            res.status_code,
                            res.text[:100],
                            delay,
                        )
            except Exception as ex:
                logger.warning(
                    "[Ollama WarmCheck] Attempt %d failed (%s). Retrying in %.1fs...",
                    attempt,
                    str(ex),
                    delay,
                )

            if attempt < max_retries:
                await asyncio.sleep(delay)
                delay *= 1.5

        logger.error("[Ollama WarmCheck] All %d warm-up attempts failed for model %s", max_retries, self.default_model)
        return {
            "ready": False,
            "attempts": max_retries,
            "error": f"Ollama failed to produce warm test generation after {max_retries} attempts",
            "model": self.default_model,
        }

    async def generate_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        persona: Optional[str] = None,
        system_override: Optional[str] = None,
    ) -> str:
        """Generates text using the Core LLM (Qwen2.5 3B).

        Degrades gracefully with an explicit notification if Ollama is unreachable.
        """
        system_content = system_override or get_system_prompt(persona)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.default_model,
            "messages": messages,
            "stream": False,
            "keep_alive": "60m",
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,  # Sized carefully for 4GB VRAM
            },
        }

        # Attempt call with strict retry limit (never loop forever)
        for attempt in range(1, self.retry_limit + 2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(f"{self.host}/api/chat", json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        content = data.get("message", {}).get("content", "")
                        return content.strip()
                    else:
                        logger.error(
                            "[Ollama Error] Received status %d: %s",
                            response.status_code,
                            response.text,
                        )
            except httpx.ConnectError:
                logger.warning(
                    "[Ollama Offline] Could not connect to Ollama at %s (Attempt %d/%d)",
                    self.host,
                    attempt,
                    self.retry_limit + 1,
                )
            except httpx.TimeoutException:
                logger.warning(
                    "[Ollama Timeout] Request timed out after %.1f seconds",
                    self.timeout,
                )
            except Exception as e:
                logger.error("[Ollama Unexpected Error] %s", str(e))

    async def stream_response(
        self,
        prompt: str,
        history: Optional[List[Dict[str, str]]] = None,
        persona: Optional[str] = None,
        system_override: Optional[str] = None,
    ):
        """Asynchronously streams response tokens line-by-line from Ollama /api/chat.

        Yields token strings as they arrive.
        """
        import json
        system_content = system_override or get_system_prompt(persona)
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.default_model,
            "messages": messages,
            "stream": True,
            "keep_alive": "60m",
            "options": {
                "temperature": 0.7,
                "top_p": 0.9,
                "num_ctx": 4096,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream("POST", f"{self.host}/api/chat", json=payload) as response:
                    if response.status_code == 200:
                        async for line in response.aiter_lines():
                            if not line:
                                continue
                            try:
                                chunk_data = json.loads(line)
                                token = chunk_data.get("message", {}).get("content", "")
                                if token:
                                    yield token
                                if chunk_data.get("done", False):
                                    break
                            except Exception:
                                continue
                        return
                    else:
                        logger.warning("[Ollama Stream] Non-200 status: %d", response.status_code)
        except Exception as e:
            logger.warning("[Ollama Stream] Stream connection failed: %s", e)

        # Fallback to non-streaming response if stream fails
        fallback = await self.generate_response(prompt=prompt, history=history, persona=persona, system_override=system_override)
        yield fallback

    async def analyze_image(self, image_base64: str, prompt: str = "Describe this image.") -> str:
        """Analyzes an image using Moondream 1.6B VLM via Ollama."""
        payload = {
            "model": self.vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64],
                }
            ],
            "stream": False,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(f"{self.host}/api/chat", json=payload)
                if res.status_code == 200:
                    return res.json().get("message", {}).get("content", "").strip()
                logger.error("[VLM Error] Vision request failed with status %d", res.status_code)
        except Exception as e:
            logger.warning("[VLM Offline] Vision inference failed: %s", str(e))

        return "[Vision Notice]: The vision analysis engine is currently unavailable."
