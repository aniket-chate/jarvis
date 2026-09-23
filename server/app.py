"""FastAPI Device Gateway Server for JARVIS Multi-Device Mesh.

Wraps Layer 2's Orchestrator Core and Layer 1's Unified Event Bus into a local
and Tailscale-accessible REST & WebSocket API.
Enforces strict token-based authentication on every incoming request.
Hosts the Mobile Thin Client static web app.
"""

import os
import io
import time
import hmac
import uuid
import base64
import asyncio
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Depends,
    Header,
    Query,
    Request,
    Response,
    File,
    UploadFile,
    Form,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from config.settings import settings, PROJECT_ROOT
from orchestrator.core import orchestrator_core
from perception.events import PerceptionEvent, event_bus
from gateway.registry import gateway_registry
from llm.ollama_client import OllamaClient
from agents.cast_agent import cast_agent
from agents.vision_agent import vision_agent
from voice.tts_piper import tts_engine
from orchestrator.memory import memory_manager
from orchestrator.router import REGISTRY_CONFIG_PATH
from capabilities.providers import register_default_providers

# Initialize default capability providers in CapabilityIntelligence
register_default_providers()

logger = logging.getLogger("JARVIS.Server")

app = FastAPI(
    title="JARVIS Device Gateway",
    version="2.0.0",
    description="Cross-Device Gateway & Orchestrator API for JARVIS Brain",
)

# Enable CORS for local network and Tailscale mesh
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in os.getenv(
            "JARVIS_CORS_ORIGINS", "http://localhost,http://127.0.0.1"
        ).split(",") if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-JARVIS-Token"],
)

ollama = OllamaClient()

# Startup health-gate state
ollama_warm = False
ollama_warming = True

@app.on_event("startup")
async def startup_warmup_gate():
    """Confirms Ollama responds to actual generation with retry/backoff before accepting normal queries."""
    global ollama_warm, ollama_warming
    register_default_providers()
    logger.info("[Startup Gate] Capability Intelligence default providers confirmed registered.")
    logger.info("[Startup Gate] Launching Ollama warm-up test generation...")
    async def _do_warmup():
        global ollama_warm, ollama_warming
        try:
            warm_res = await ollama.warm_up(max_retries=5, initial_delay=1.0)
            ollama_warm = bool(warm_res.get("ready", False))
            if ollama_warm:
                logger.info("[Startup Gate] Ollama local engine confirmed ONLINE and warm: model=%s (%s)", warm_res.get("model"), warm_res)
            else:
                logger.error(
                    "[Startup Gate CRITICAL WARNING] Ollama could not be started and is running in DEGRADED/CLOUD-FALLBACK mode! "
                    "Local models are unavailable; queries will cascade to cloud fallback."
                )
        except Exception as err:
            logger.error("[Startup Gate CRITICAL WARNING] Ollama warm-up encountered exception: %s. Operating in DEGRADED mode.", err)
            ollama_warm = False
        finally:
            ollama_warming = False
    # Pre-warm routing classifier and neural TTS in parallel background tasks
    async def _warm_classifier():
        try:
            from cognitive.routing.hierarchical_classifier import hierarchical_classifier
            await asyncio.to_thread(hierarchical_classifier.classify, "ping")
            logger.info("[Startup Gate] Hierarchical routing classifier pre-warmed.")
        except Exception as c_err:
            logger.debug("[Startup Gate] Classifier pre-warm warning: %s", c_err)

    async def _warm_tts():
        try:
            from voice.tts_piper import tts_engine
            await asyncio.to_thread(tts_engine.synthesize_to_wav_bytes, "Ready.", settings.active_persona_name)
            logger.info("[Startup Gate] Piper neural TTS engine pre-warmed.")
        except Exception as t_err:
            logger.debug("[Startup Gate] TTS pre-warm warning: %s", t_err)

    asyncio.create_task(_warm_classifier())
    asyncio.create_task(_warm_tts())
    asyncio.create_task(_do_warmup())

    # Event bus subscriber for alarms
    def _on_alarm_event(ev: PerceptionEvent):
        if ev.type == "alarm_triggered":
            payload = {
                "type": "alarm_triggered",
                "alarm_id": ev.payload.get("alarm_id"),
                "message": ev.payload.get("message"),
                "fired_at": ev.payload.get("fired_at"),
                "active_persona": ev.active_persona or settings.active_persona_name,
                "timestamp": time.time(),
            }
            logger.info("[Server EventBus] Broadcasting alarm_triggered to clients: %s", payload)
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(gateway_registry.broadcast_all(payload))
            except RuntimeError:
                pass

    event_bus.subscribe("alarm_triggered", _on_alarm_event)


# -------------------------------------------------------------------------
# Security & Token Authentication
# -------------------------------------------------------------------------
def verify_gateway_token(
    request: Request,
    x_jarvis_token: Optional[str] = Header(None, alias="X-JARVIS-Token"),
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> str:
    """Validates the incoming client token against GATEWAY_AUTH_TOKEN.
    
    Accepts:
    1. Header: X-JARVIS-Token: <token>
    2. Header: Authorization: Bearer <token>
    3. Query parameter: ?token=<token>
    """
    configured_token = settings.gateway_auth_token
    if not configured_token:
        logger.error("[Gateway Auth] GATEWAY_AUTH_TOKEN is not configured; protected API is fail-closed.")
        raise HTTPException(status_code=503, detail="Gateway authentication is not configured.")

    provided_token = None
    if x_jarvis_token:
        provided_token = x_jarvis_token
    elif authorization:
        parts = authorization.strip().split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            provided_token = parts[1]
        else:
            provided_token = authorization.strip()
    elif token:
        # Kept only for HTTP backward compatibility. WebSocket authentication
        # does not accept query-string tokens.
        provided_token = token

    if not provided_token or not hmac.compare_digest(provided_token, configured_token):
        logger.warning(
            "[Gateway Auth] Rejected unauthorized request from %s to %s",
            request.client.host if request.client else "unknown",
            request.url.path,
        )
        raise HTTPException(status_code=401, detail="Unauthorized: invalid or missing JARVIS Gateway token.")
    return provided_token


# -------------------------------------------------------------------------
# Request & Response Models
# -------------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: Optional[str] = None
    message: Optional[str] = None
    persona: Optional[str] = None
    device_id: Optional[str] = "mobile_client"
    device_name: Optional[str] = "Mobile Client"


class SwitchPersonaRequest(BaseModel):
    persona: str


class DeviceRegisterRequest(BaseModel):
    device_id: str
    name: str
    client_type: str  # "phone", "pc", "tv", "tablet", "web"
    ip_address: Optional[str] = None
    capabilities: Optional[List[str]] = None


class CastPlayRequest(BaseModel):
    device: str
    media_url: Optional[str] = None
    title: Optional[str] = "Media Playback"
    content_type: Optional[str] = "video/mp4"


class TTSRequest(BaseModel):
    text: str
    persona: Optional[str] = None


class MemoryItemRequest(BaseModel):
    key: str
    value: Any
    persistent: bool = True
    confidence: float = 1.0


class CapabilityExecuteRequest(BaseModel):
    capability: Optional[str] = None
    action: str
    parameters: Optional[Dict[str, Any]] = None


# -------------------------------------------------------------------------
# Health & Status (Audit & Telemetry)
# -------------------------------------------------------------------------
@app.get("/health")
@app.get("/api/v1/health")
async def health_check():
    """System health check and integration availability audit."""
    ollama_health = await ollama.check_health()
    return {
        "status": "healthy" if ollama_online else "degraded",
        "active_persona": settings.active_persona_name,
        "hardware_target": settings.hardware.get("target_gpu", "RTX 2050"),
        "vram_budget_mb": settings.hardware.get("vram_budget_mb", 4096),
        "ollama": ollama_health,
        "ollama_warm": ollama_warm,
        "ollama_warming": ollama_warming,
        "auth_enforced": True,
        "skills": {
            "web_search": settings.search_available,
            "google_oauth": settings.google_oauth_configured,
            "home_assistant": settings.home_assistant_available,
            "whatsapp_business": settings.whatsapp_available,
        },
    }


# -------------------------------------------------------------------------
# Device Registry API (Protected)
# -------------------------------------------------------------------------
@app.get("/api/devices")
async def list_devices(_token: str = Depends(verify_gateway_token)):
    """Lists all registered devices in the JARVIS mesh with real-time online status."""
    return {"devices": gateway_registry.list_active_devices()}


@app.post("/api/devices/register")
@app.post("/api/v1/devices/register")
async def register_device(
    req: DeviceRegisterRequest,
    request: Request,
    _token: str = Depends(verify_gateway_token),
):
    """Registers or updates a client device (e.g. mobile phone or TV)."""
    client_ip = req.ip_address or (request.client.host if request.client else "127.0.0.1")
    dev = gateway_registry.register_device(
        device_id=req.device_id,
        name=req.name,
        client_type=req.client_type,
        ip_address=client_ip,
        capabilities=req.capabilities,
    )
    return {"status": "registered", "device": dev.to_dict()}


@app.post("/api/devices/heartbeat")
@app.post("/api/v1/devices/heartbeat")
@app.post("/api/v1/devices/{device_id}/heartbeat")
async def device_heartbeat(
    device_id: Optional[str] = None,
    _token: str = Depends(verify_gateway_token),
):
    """Refreshes active presence for a client device."""
    dev_id = device_id or "unknown"
    success = gateway_registry.touch(dev_id)
    return {"status": "alive" if success else "unknown_device", "device_id": dev_id}



# -------------------------------------------------------------------------
# Layer 2 Orchestrator & Layer 1 Event Bus (Protected)
# -------------------------------------------------------------------------
@app.post("/api/chat")
async def chat_endpoint(
    req: ChatRequest,
    request: Request,
    _token: str = Depends(verify_gateway_token),
):
    """Routes client command through Layer 1's Event Bus and Layer 2's Orchestrator Core."""
    client_ip = request.client.host if request.client else "127.0.0.1"

    # 1. Update/register client presence
    gateway_registry.register_device(
        device_id=req.device_id or "remote_client",
        name=req.device_name or "Remote Client",
        client_type="phone" if "phone" in (req.device_name or "").lower() else "web",
        ip_address=client_ip,
    )

    # 2. Emit Layer 1 PerceptionEvent
    active_persona = req.persona or settings.active_persona_name
    cmd_text = req.query or req.message or ""
    event = PerceptionEvent(
        type="text_input",
        payload={
            "text": cmd_text,
            "source_device": req.device_id,
            "client_ip": client_ip,
        },
        source=f"gateway_{req.device_id}",
        active_persona=active_persona,
    )
    event_bus.publish(event)

    # 3. Process through Layer 2 Orchestrator Core
    result = orchestrator_core.process_event(event)

    return {
        "status": "ok",
        "active_persona": result.get("active_persona", active_persona),
        "response": result.get("response", ""),
        "type": result.get("type", "task_executed"),
        "trace_id": result.get("trace_id"),
        "plan": result.get("plan"),
    }


@app.post("/api/v1/capabilities/execute")
async def execute_capability(
    req: CapabilityExecuteRequest,
    _token: str = Depends(verify_gateway_token),
):
    """Compatibility capability endpoint with mandatory safety evaluation."""
    from capabilities.intelligence import capability_intelligence
    from safety.policy_kernel import policy_kernel

    cap_id = req.capability or req.action
    params = dict(req.parameters or {})
    domain = cap_id.split(".", 1)[0]
    decision = policy_kernel.evaluate(domain=domain, action=req.action, parameters=params)
    if not decision.allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "BLOCKED",
                "reason": decision.reason,
                "confirmation_token": decision.confirmation_token,
                "confirmation_prompt": decision.confirmation_prompt,
            },
        )

    provider = capability_intelligence.select_provider(cap_id)
    if not provider or not provider.is_available():
        raise HTTPException(status_code=503, detail=f"Live provider unavailable for capability '{cap_id}'")
    result = provider.execute(req.action, params)
    return {
        "status": result.status,
        "action": req.action,
        "provider_id": provider.provider_id,
        "output": result.output,
        "message": result.message,
        "evidence": result.evidence,
        "execution_time_ms": result.execution_time_ms,
    }


@app.get("/api/personas")
async def list_personas(_token: str = Depends(verify_gateway_token)):
    """Lists registered personas."""
    return {
        "active_persona": settings.active_persona_name,
        "personas": settings.list_personas(),
    }


@app.post("/api/personas/switch")
async def switch_persona(
    req: SwitchPersonaRequest,
    _token: str = Depends(verify_gateway_token),
):
    """Dynamically switches active persona across all layers."""
    success = settings.set_active_persona(req.persona)
    if not success:
        raise HTTPException(status_code=400, detail=f"Unknown persona '{req.persona}'")
    return {
        "status": "switched",
        "active_persona": settings.active_persona_name,
        "details": settings.get_persona().to_dict(),
    }


# -------------------------------------------------------------------------
# Skill & Capability Introspection API (Protected)
# -------------------------------------------------------------------------
@app.get("/api/skills")
async def list_skills_endpoint(_token: str = Depends(verify_gateway_token)):
    """Lists registered agent skills and capabilities (merged from legacy api/routes/skills.py)."""
    import yaml
    skills = []
    if REGISTRY_CONFIG_PATH.exists():
        try:
            with open(REGISTRY_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                for aid, spec in data.get("agents", {}).items():
                    skills.append({
                        "id": aid,
                        "name": spec.get("name", aid),
                        "description": spec.get("description", ""),
                        "capabilities": spec.get("capabilities", []),
                        "trigger_keywords": spec.get("trigger_keywords", [])
                    })
        except Exception as e:
            logger.warning("[Gateway] Error reading agent registry for skills endpoint: %s", e)

    return {"skills": skills, "total_count": len(skills)}


# -------------------------------------------------------------------------
# HUD Runtime State, Context & Capability Endpoints
# -------------------------------------------------------------------------
@app.get("/api/runtime/status")
@app.get("/api/v1/runtime/status")
async def runtime_status_endpoint(_token: str = Depends(verify_gateway_token)):
    """Returns granular, real-time subsystem statuses across JARVIS for the HUD."""
    from capabilities.intelligence import capability_intelligence
    from safety.policy_kernel import policy_kernel
    from agents.scheduler_agent import scheduler_agent

    # 1. AI Core & Providers
    ollama_health = await ollama.check_health()
    ollama_online = bool(ollama_health.get("online") or ollama_health.get("status") == "healthy")
    ai_status = "Online" if ollama_online else ("Degraded" if ollama_warming else "Degraded")

    # 2. Voice Module
    tts_prov = capability_intelligence.select_provider("voice.synthesize")
    voice_status = "Active" if (tts_prov and tts_prov.is_available()) else "Ready"

    # 3. Vision Engine
    vis_prov = capability_intelligence.select_provider("vision.analyze_image")
    vision_status = "Ready" if (vis_prov and vis_prov.is_available()) else "Unavailable"

    # 4. Automation / Scheduler
    auto_status = "Online" if (scheduler_agent.scheduler and scheduler_agent.scheduler.running) else "Disabled"

    # 5. Security & Policy
    sec_status = "Secure" if policy_kernel is not None else "Degraded"

    # 6. Memory & World Model
    try:
        mem_count = len(memory_manager.get_all_memories())
        memory_status = "Active"
    except Exception as exc:
        logger.warning("[Runtime Status] Memory health check failed: %s", exc)
        mem_count = 0
        memory_status = "Unavailable"

    # Provider-Level Granular Health Mapping
    gemini_key = getattr(settings, "gemini_api_key", None)
    groq_key = getattr(settings, "groq_api_key", None)
    openrouter_key = getattr(settings, "openrouter_api_key", None) or os.getenv("OPENROUTER_API_KEY")
    openai_key = getattr(settings, "openai_api_key", None) or os.getenv("OPENAI_API_KEY")
    piper_available = tts_engine._piper_voice is not None or bool(list(tts_engine.models_dir.glob("*.onnx")))

    providers_map = {
        "backend": "Online",
        "ollama": "Online" if ollama_online else "Offline",
        "gemini": "Configured" if bool(gemini_key) else "Unconfigured",
        "groq": "Configured" if bool(groq_key) else "Unconfigured",
        "openrouter": "Configured" if bool(openrouter_key) else "Unconfigured",
        "openai": "Configured" if bool(openai_key) else "Unconfigured",
        "piper_tts": "Online" if piper_available else "Fallback",
        "rule_based": "Online",
    }

    # Overall System Health Invariant: Cannot claim Healthy if primary local Ollama is Offline
    is_all_ok = (ai_status in ["Online", "Ready"]) and (voice_status in ["Active", "Ready"]) and (sec_status == "Secure") and ollama_online
    overall_health = "Healthy" if is_all_ok else "Degraded"

    if overall_health == "Healthy":
        dial_msg = "ALL SYSTEMS OPERATIONAL"
    elif not ollama_online:
        dial_msg = "DEGRADED - OLLAMA OFFLINE (FALLBACK ACTIVE)"
    else:
        dial_msg = "SYSTEMS ATTENTION REQUIRED"

    return {
        "status": overall_health,
        "active_persona": settings.active_persona_name,
        "subsystems": {
            "ai_core": ai_status,
            "voice_module": voice_status,
            "vision": vision_status,
            "automation": auto_status,
            "security": sec_status,
            "memory": memory_status,
        },
        "providers": providers_map,
        "system_dial": {
            "health": overall_health,
            "dial_symbol": "ॐ",
            "message": dial_msg,
        },
        "timestamp": time.time(),
    }


@app.get("/api/capabilities/available")
@app.get("/api/v1/capabilities/available")
async def available_capabilities_endpoint(_token: str = Depends(verify_gateway_token)):
    """Lists registered capabilities available for HUD quick actions."""
    from capabilities.contracts.registry_50 import contract_registry_50
    from capabilities.intelligence import capability_intelligence

    caps = []
    for contract in contract_registry_50.list_all_contracts():
        prov = capability_intelligence.select_provider(contract.supported_operations[0]) if contract.supported_operations else None
        caps.append({
            "capability_id": contract.capability_id,
            "name": contract.name,
            "domain": contract.domain.value if hasattr(contract.domain, "value") else str(contract.domain),
            "purpose": contract.purpose,
            "operations": contract.supported_operations,
            "primary_provider": prov.provider_id if prov else contract.primary_provider_id,
            "available": prov.is_available() if prov else False,
        })
    return {"capabilities": caps, "total": len(caps)}


@app.get("/api/context/today")
@app.get("/api/v1/context/today")
async def today_context_endpoint(_token: str = Depends(verify_gateway_token)):
    """Fetches real scheduled events, alarms, and tasks for today."""
    from capabilities.intelligence import capability_intelligence
    today_items = []

    # Query Capability 38 (Calendar & Scheduler)
    cal_prov = capability_intelligence.select_provider("calendar.get_events")
    if cal_prov:
        try:
            res = cal_prov.execute("calendar.get_events", {"limit": 10})
            if res.status == "SUCCESS" and "events" in res.output:
                for ev in res.output["events"]:
                    today_items.append({
                        "id": ev.get("event_id"),
                        "title": ev.get("title", "Event"),
                        "when": ev.get("start_time", "Today"),
                        "type": "calendar",
                        "status": ev.get("status", "CONFIRMED"),
                    })
        except Exception as e:
            logger.debug("[Today Context] Calendar query error: %s", e)

    # Query in-app Scheduler Alarms/Reminders
    from agents.scheduler_agent import scheduler_agent
    try:
        jobs = scheduler_agent.scheduler.get_jobs()
        for j in jobs:
            next_run = j.next_run_time.strftime("%I:%M %p") if j.next_run_time else "Scheduled"
            today_items.append({
                "id": j.id,
                "title": j.name or f"Alarm ({j.id})",
                "when": next_run,
                "type": "reminder",
                "status": "SCHEDULED",
            })
    except Exception as e:
        logger.debug("[Today Context] Scheduler jobs query error: %s", e)

    # Query Capability 39 (Productivity Tasks)
    prod_prov = capability_intelligence.select_provider("productivity.get_tasks")
    if prod_prov:
        try:
            res = prod_prov.execute("productivity.get_tasks", {"limit": 10})
            if res.status == "SUCCESS" and "tasks" in res.output:
                for t in res.output["tasks"]:
                    today_items.append({
                        "id": t.get("id"),
                        "title": t.get("title", "Task"),
                        "when": t.get("due_at") or "Pending",
                        "type": "task",
                        "status": t.get("status", "READY"),
                    })
        except Exception as e:
            logger.debug("[Today Context] Productivity tasks query error: %s", e)

    return {
        "items": today_items,
        "count": len(today_items),
        "empty_message": "Your day is clear" if len(today_items) == 0 else None,
    }


@app.get("/api/context/recent_files")
@app.get("/api/v1/context/recent_files")
async def recent_files_endpoint(_token: str = Depends(verify_gateway_token)):
    """Fetches real recent files within authorized workspace/data/docs scope."""
    recent = []
    scan_dirs = [PROJECT_ROOT / "docs", PROJECT_ROOT / "workspace", PROJECT_ROOT / "data"]
    found_files = []
    for d in scan_dirs:
        if d.exists():
            for p in d.glob("**/*"):
                if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in [".md", ".json", ".txt", ".py", ".pdf", ".html"]:
                    try:
                        mtime = p.stat().st_mtime
                        found_files.append((mtime, p))
                    except Exception:
                        pass

    found_files.sort(key=lambda x: x[0], reverse=True)
    now = time.time()
    for mtime, p in found_files[:5]:
        diff_sec = now - mtime
        if diff_sec < 3600:
            when = f"{max(1, int(diff_sec // 60))}m ago"
        elif diff_sec < 86400:
            when = f"{int(diff_sec // 3600)}h ago"
        else:
            when = f"{int(diff_sec // 86400)}d ago"

        try:
            rel_p = str(p.relative_to(PROJECT_ROOT))
        except ValueError:
            rel_p = p.name

        recent.append({
            "name": p.name,
            "path": rel_p,
            "when": when,
            "size_bytes": p.stat().st_size,
        })

    return {
        "files": recent,
        "count": len(recent),
        "empty_message": "No recent files" if len(recent) == 0 else None,
    }


@app.get("/api/context/location")
@app.get("/api/v1/context/location")
async def location_context_endpoint(_token: str = Depends(verify_gateway_token)):
    """Returns honest location from World Model / device / timezone with precision."""
    local_now = datetime.now()
    offset = local_now.astimezone().utcoffset()
    offset_hours = offset.total_seconds() / 3600.0 if offset else 0.0
    sign = "+" if offset_hours >= 0 else "-"
    abs_hours = int(abs(offset_hours))
    abs_mins = int((abs(offset_hours) - abs_hours) * 60)
    offset_str = f"UTC{sign}{abs_hours:02d}:{abs_mins:02d}"

    if offset_hours == 5.5:
        region = f"IST ({offset_str})"
    elif offset_hours == 0.0:
        region = "UTC (GMT)"
    else:
        region = f"LOCAL TIMEZONE ({offset_str})"

    return {
        "location": region,
        "source": "device_timezone",
        "precision": "coarse",
        "utc_offset": offset_str,
    }



# -------------------------------------------------------------------------
# Explicit Memory Management API (Protected)
# -------------------------------------------------------------------------
@app.get("/api/memory")
async def list_memories_endpoint(
    query: Optional[str] = Query(None),
    _token: str = Depends(verify_gateway_token)
):
    """Lists explicit memory facts and decay metadata (merged from legacy api/routes/memory.py)."""
    memories = memory_manager.get_all_memories()
    if query:
        q_lower = query.lower()
        memories = {k: v for k, v in memories.items() if q_lower in k.lower() or q_lower in str(v).lower()}

    # Include decay confidence metadata for each key
    items = []
    for k, v in memories.items():
        conf = memory_manager.get_effective_confidence(k)
        items.append({
            "key": k,
            "value": v,
            "confidence": conf
        })

    return {"memories": items, "count": len(items)}


@app.post("/api/memory")
async def create_memory_endpoint(
    req: MemoryItemRequest,
    _token: str = Depends(verify_gateway_token)
):
    """Stores an explicit memory item with sanitization and decay tracking."""
    stored_val = memory_manager.store(
        key=req.key,
        value=req.value,
        persistent=req.persistent,
        confidence=req.confidence
    )
    return {
        "status": "stored",
        "key": req.key,
        "value": stored_val,
        "confidence": req.confidence
    }


@app.delete("/api/memory/{key}")
async def delete_memory_endpoint(
    key: str,
    _token: str = Depends(verify_gateway_token)
):
    """Deletes an explicit memory item."""
    success = memory_manager.forget(key)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory key '{key}' not found.")
    return {"status": "deleted", "key": key}


# -------------------------------------------------------------------------
# Cross-Device Media Casting API (Protected)
# -------------------------------------------------------------------------
@app.post("/api/cast/play")
async def cast_play_endpoint(
    req: CastPlayRequest,
    _token: str = Depends(verify_gateway_token),
):
    """Dispatches media playback to targeted device (Phone, TV, PC)."""
    res = cast_agent.cast_to_device(
        device_name=req.device,
        media_url=req.media_url or "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        content_type=req.content_type or "video/mp4",
        title=req.title or "Media Stream",
    )
    return res


# -------------------------------------------------------------------------
# Vision Analysis API (Protected)
# -------------------------------------------------------------------------
@app.post("/api/vision/analyze")
async def analyze_vision_endpoint(
    image: UploadFile = File(...),
    prompt: Optional[str] = Form("Describe what you see in this image in detail."),
    persona: Optional[str] = Form(None),
    _token: str = Depends(verify_gateway_token),
):
    """Accepts camera capture from mobile thin client, routes through Capability Intelligence."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Empty image uploaded")

    target_persona = persona or settings.active_persona_name

    try:
        from capabilities.intelligence import capability_intelligence
        provider = capability_intelligence.select_provider("vision.analyze_image")
        if provider:
            action_res = provider.execute(
                "vision.analyze_image",
                {
                    "image": image_bytes,
                    "prompt": prompt,
                    "persona_name": target_persona,
                },
            )
            if action_res.status == "SUCCESS":
                return action_res.output
            else:
                logger.warning("[Vision API] Provider execution failed: %s, falling back", action_res.message)
    except Exception as e:
        logger.debug("[Vision API] CapabilityIntelligence route bypassed: %s", e)

    # Fallback to direct vision_agent if provider selection not resolved
    res = vision_agent.analyze_image(
        image_input=image_bytes,
        prompt=prompt,
        persona_name=target_persona,
    )
    return res


# -------------------------------------------------------------------------
# Neural TTS Audio Streaming API (Protected)
# -------------------------------------------------------------------------
@app.post("/api/tts/synthesize")
async def synthesize_tts_endpoint(
    req: TTSRequest,
    _token: str = Depends(verify_gateway_token),
):
    """Synthesizes text into WAV audio using Capability Intelligence."""
    target_persona = req.persona or settings.active_persona_name

    try:
        from capabilities.intelligence import capability_intelligence
        provider = capability_intelligence.select_provider("voice.synthesize")
        if provider:
            action_res = provider.execute(
                "voice.synthesize",
                {
                    "text": req.text,
                    "persona": target_persona,
                },
            )
            if action_res.status == "SUCCESS" and "wav_bytes" in action_res.output:
                return Response(content=action_res.output["wav_bytes"], media_type="audio/wav")
    except Exception as e:
        logger.debug("[TTS API] CapabilityIntelligence route bypassed: %s", e)

    # Fallback to direct tts_engine if provider selection not resolved
    temp_wav = PROJECT_ROOT / "data" / "tts_cache" / f"tts_{int(time.time() * 1000)}.wav"
    success = tts_engine.synthesize_to_wav(
        text=req.text,
        output_path=temp_wav,
        persona_name=target_persona,
    )
    if not success or not temp_wav.exists():
        raise HTTPException(status_code=500, detail="Failed to synthesize audio on host PC")

    with open(temp_wav, "rb") as f:
        wav_data = f.read()

    # Clean up temporary cache file
    try:
        temp_wav.unlink(missing_ok=True)
    except Exception:
        pass

    return Response(content=wav_data, media_type="audio/wav")


# -------------------------------------------------------------------------
# Duplex WebSocket Endpoint (Protected)
# -------------------------------------------------------------------------
@app.websocket("/ws")
@app.websocket("/api/v1/ws")
async def websocket_gateway(
    websocket: WebSocket,
    device_id: Optional[str] = Query(None),
):
    """Real-time duplex WebSocket endpoint authenticated before acceptance."""
    configured_token = settings.gateway_auth_token
    if not configured_token:
        await websocket.close(code=1011, reason="Gateway authentication is not configured")
        return

    # Browser clients cannot set arbitrary Authorization headers, so the
    # authenticated subprotocol is supported. Native clients may use the
    # Authorization header. Query-string tokens are deliberately rejected.
    provided_token = None
    authorization = websocket.headers.get("authorization")
    if authorization:
        parts = authorization.strip().split()
        provided_token = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else authorization.strip()

    requested_protocols = websocket.headers.get("sec-websocket-protocol", "")
    selected_protocol = None
    for protocol in [p.strip() for p in requested_protocols.split(",") if p.strip()]:
        if protocol.startswith("jarvis-auth."):
            provided_token = protocol[len("jarvis-auth."):]
            selected_protocol = protocol
            break

    if not provided_token or not hmac.compare_digest(provided_token, configured_token):
        logger.warning("[WebSocket Auth] Rejected unauthorized connection from %s", websocket.client.host if websocket.client else "unknown")
        await websocket.close(code=4401, reason="Unauthorized")
        return

    await websocket.accept(subprotocol=selected_protocol)
    client_ip = websocket.client.host if websocket.client else "127.0.0.1"
    active_device_id = device_id or f"client_{int(time.time())}"
    logger.info("[WebSocket] Authorized client connected from %s (device_id=%s)", client_ip, active_device_id)

    # Register initial connection
    dev = gateway_registry.register_device(
        device_id=active_device_id,
        name="Mobile/Android Client",
        client_type="phone",
        ip_address=client_ip,
        websocket=websocket,
    )

    try:
        # Send initial handshake welcome
        await websocket.send_json({
            "type": "welcome",
            "active_persona": settings.active_persona_name,
            "device_id": active_device_id,
            "status": "connected",
        })

        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "chat")

            if msg_type == "auth":
                # Android native client authentication handshake
                auth_token = data.get("token") or ""
                if not auth_token or not hmac.compare_digest(auth_token, configured_token):
                    await websocket.close(code=4401, reason="Unauthorized")
                    return
                custom_id = data.get("device_id") or active_device_id
                user_id = data.get("user_id") or "owner"
                gateway_registry.register_device(
                    device_id=custom_id,
                    name=data.get("device_name", "Android Native Client"),
                    client_type=data.get("client_type", "phone"),
                    ip_address=client_ip,
                    websocket=websocket,
                )
                active_device_id = custom_id
                await websocket.send_json({
                    "type": "auth_success",
                    "user_id": user_id,
                    "username": "Authorized User",
                    "device_id": active_device_id,
                    "status": "authenticated"
                })

            elif msg_type == "register":
                # Update device identity (e.g. client provided custom name/type)
                custom_id = data.get("device_id", active_device_id)
                custom_name = data.get("name", "Mobile Client")
                custom_type = data.get("client_type", "phone")
                gateway_registry.register_device(
                    device_id=custom_id,
                    name=custom_name,
                    client_type=custom_type,
                    ip_address=client_ip,
                    websocket=websocket,
                )
                active_device_id = custom_id
                await websocket.send_json({"type": "registered", "device_id": active_device_id})

            elif msg_type in ["heartbeat", "ping"]:
                gateway_registry.touch(active_device_id)
                await websocket.send_json({"type": "pong", "timestamp": time.time()})

            elif msg_type == "voice_turn":
                # Structured voice turn merged from legacy api/routes/websocket.py
                turn_id = data.get("voice_turn_id") or data.get("request_id") or f"turn_{int(time.time() * 1000)}"
                query = data.get("text") or data.get("query") or ""
                persona = data.get("persona") or settings.active_persona_name

                if query:
                    event = PerceptionEvent(
                        type="voice_input",
                        payload={"text": query, "source_device": active_device_id, "voice_turn_id": turn_id},
                        source=f"ws_voice_{active_device_id}",
                        active_persona=persona,
                    )
                    event_bus.publish(event)
                    result = await asyncio.to_thread(orchestrator_core.process_event, event)
                    resp_str = result.get("response", "")
                    await websocket.send_json({
                        "type": "voice_response",
                        "voice_turn_id": turn_id,
                        "request_id": turn_id,
                        "status": "success",
                        "text": resp_str,
                        "spoken_response": resp_str,
                        "active_persona": result.get("active_persona", persona),
                        "trace_id": result.get("trace_id"),
                        "requires_confirmation": False,
                    })

            elif msg_type == "cancel":
                target_resp_id = data.get("response_id")
                logger.info("[TTS_CANCEL] Cancellation requested for response_id=%s", target_resp_id)
                # Mark cancelled
                await websocket.send_json({
                    "type": "tts_cancel",
                    "response_id": target_resp_id,
                    "timestamp": time.time(),
                })

            elif msg_type == "persona_switch":
                requested_p = data.get("persona")
                if requested_p:
                    if settings.active_persona_name.lower() != requested_p.lower():
                        settings.set_active_persona(requested_p)
                        logger.info("[WebSocket] Persona switched dynamically to '%s'", settings.active_persona_name)
                    await websocket.send_json({
                        "type": "persona_switched",
                        "active_persona": settings.active_persona_name,
                        "status": "ok"
                    })

            elif msg_type in ["chat", "command", "query"]:
                query = data.get("query") or data.get("text") or data.get("command") or data.get("message") or ""
                # Maintain server-authoritative persona state; do not overwrite from stale client payload
                persona = settings.active_persona_name

                req_id = data.get("request_id") or str(uuid.uuid4())
                resp_id = data.get("response_id") or str(uuid.uuid4())

                # Check if this message is an explicit stop / cancel command
                lower_query = query.strip().lower()
                if lower_query in ["stop", "cancel", "be quiet", "stop speaking", "shut up", "pause speaking"]:
                    logger.info("[TTS_CANCEL] Explicit cancel command '%s' [request_id=%s, response_id=%s]", lower_query, req_id, resp_id)
                    await websocket.send_json({
                        "type": "tts_cancel",
                        "request_id": req_id,
                        "response_id": resp_id,
                        "timestamp": time.time(),
                    })
                    await websocket.send_json({
                        "type": "chat_response",
                        "request_id": req_id,
                        "response_id": resp_id,
                        "active_persona": persona,
                        "response": "Stopped.",
                        "text": "Stopped.",
                        "payload": {
                            "text": "Stopped.",
                            "spoken_text": "Stopped.",
                            "intent": "cancel",
                            "confidence": 1.0,
                            "requires_confirmation": False,
                            "is_exit": False,
                            "action_result": None,
                        },
                        "status": "ok",
                    })
                    continue

                client_caps = data.get("client_capabilities") or data.get("capabilities") or {}
                req_accessibility = bool(data.get("accessibility") or client_caps.get("accessibility") or client_caps.get("screen_reader"))

                if query:
                    t_received = time.time()
                    t_received_perf = time.perf_counter()
                    logger.info("[RESPONSE_START] Starting response generation [request_id=%s, response_id=%s, persona=%s, query='%s', accessible=%s]", req_id, resp_id, persona, query, req_accessibility)

                    # Publish event to Layer 1 Event Bus
                    event = PerceptionEvent(
                        type="text_input",
                        payload={"text": query, "source_device": active_device_id, "request_id": req_id, "response_id": resp_id},
                        source=f"ws_{active_device_id}",
                        active_persona=persona,
                    )
                    event_bus.publish(event)

                    # Broadcast user query to all connected displays (e.g. Workstation HUD)
                    await gateway_registry.broadcast_all({
                        "type": "user_query_broadcast",
                        "text": query,
                        "author": data.get("user") or data.get("author") or "User",
                        "request_id": req_id,
                        "timestamp": time.time(),
                    })

                    # 1. Send immediate progress feedback
                    progress_payload = {
                        "type": "task_progress",
                        "request_id": req_id,
                        "response_id": resp_id,
                        "status": "working",
                        "message": f"{persona} is processing...",
                        "active_persona": persona,
                        "timestamp": time.time(),
                        "query": query,
                    }
                    await websocket.send_json(progress_payload)
                    await gateway_registry.broadcast_all(progress_payload, exclude_ws=websocket)

                    # 2. Inspect plan to see if query is pure Core LLM or a tool task
                    from orchestrator.planner import task_planner
                    from agents.core_llm_agent import core_llm_agent
                    import re

                    t_plan_start = time.perf_counter()
                    plan = task_planner.create_plan(event)
                    t_plan_end = time.perf_counter()
                    logger.info("[PLANNER_COMPLETE] [request_id=%s] Planning completed in %.1fms", req_id, (t_plan_end - t_plan_start) * 1000)

                    first_agent = (getattr(plan.steps[0], "required_agent_type", None) or getattr(plan.steps[0], "agent_type", "core_llm_agent")) if plan.steps else "core_llm_agent"

                    ttft_ms = 0.0
                    ttfa_ms = 0.0

                    # In-memory fast synthesis returning base64 WAV with zero disk I/O
                    def _fast_synth_b64(txt: str, p: str) -> Optional[str]:
                        clean = re.sub(r"[*_#`]", "", txt).strip()
                        if not clean:
                            return None
                        try:
                            from capabilities.intelligence import capability_intelligence
                            provider = capability_intelligence.select_provider("voice.synthesize")
                            if provider:
                                res = provider.execute("voice.synthesize", {"text": clean, "persona": p})
                                if res.status == "SUCCESS" and "wav_bytes" in res.output:
                                    return base64.b64encode(res.output["wav_bytes"]).decode("utf-8")
                            wav_bytes = tts_engine.synthesize_to_wav_bytes(clean, persona_name=p)
                            if wav_bytes:
                                return base64.b64encode(wav_bytes).decode("utf-8")
                        except Exception as synth_err:
                            logger.warning("[TTS_ERROR] [request_id=%s, response_id=%s] Fast synthesis warning: %s", req_id, resp_id, synth_err)
                        return None

                    def _split_into_sentences(text: str) -> List[str]:
                        """Robust natural sentence segmentation handling abbreviations, decimals, and ellipsis."""
                        clean = re.sub(r"[*_#`]", "", text).strip()
                        if not clean:
                            return []
                        temp = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\.', r'\1<DOT>', clean, flags=re.IGNORECASE)
                        temp = re.sub(r'(\d+)\.(\d+)', r'\1<DECIMAL>\2', temp)
                        temp = re.sub(r'\.\.\.', '<ELLIPSIS>', temp)
                        raw_chunks = re.split(r'(?<=[.!?])\s+', temp)
                        sentences = []
                        for c in raw_chunks:
                            restored = c.replace('<DOT>', '.').replace('<DECIMAL>', '.').replace('<ELLIPSIS>', '...').strip()
                            if restored:
                                sentences.append(restored)
                        return sentences if sentences else [clean]

                    if first_agent == "core_llm_agent" and getattr(plan, "intent", None) != "persona_switch":
                        # Startup health-gate: If query arrives before Ollama is confirmed warm, respond honestly
                        if not ollama_warm and ollama_warming:
                            logger.info("[Startup Gate] Query '%s' received while Ollama is warming up. Responding honestly.", query)
                            warm_notice = f"[{persona}]: I am still starting up and warming the local models, one moment please."
                            await websocket.send_json({
                                "type": "chat_response",
                                "request_id": req_id,
                                "response_id": resp_id,
                                "active_persona": persona,
                                "response": warm_notice,
                                "text": warm_notice,
                                "payload": {
                                    "text": warm_notice,
                                    "spoken_text": warm_notice,
                                    "intent": "warmup_in_progress",
                                    "confidence": 1.0,
                                    "requires_confirmation": False,
                                    "is_exit": False,
                                    "action_result": None,
                                    "status": "warming",
                                },
                                "status": "warming",
                                "trace_id": plan.plan_id,
                            })
                            continue

                        # Fast streaming path for Core LLM
                        logger.info("[ROUTER_COMPLETE] [request_id=%s, response_id=%s] Routed to core_llm_agent in %.1fms", req_id, resp_id, (time.time() - t_received) * 1000)
                        await websocket.send_json({
                            "type": "chat_stream_start",
                            "request_id": req_id,
                            "response_id": resp_id,
                            "active_persona": persona,
                            "trace_id": plan.plan_id,
                            "timestamp": time.time(),
                        })

                        full_text = ""
                        stream_buffer = ""
                        sentence_queue: asyncio.Queue = asyncio.Queue()
                        cancelled = False
                        first_chunk_sent = False

                        # Worker to sequentially synthesize and send each sentence
                        async def _tts_worker():
                            nonlocal ttfa_ms
                            s_idx = 0
                            try:
                                while True:
                                    item = await sentence_queue.get()
                                    if item is None:
                                        sentence_queue.task_done()
                                        break
                                    if cancelled:
                                        sentence_queue.task_done()
                                        continue

                                    s_text, is_final = item
                                    seq_id = s_idx + 1
                                    logger.info("[TTS_SYNTH_START] [request_id=%s, response_id=%s, sequence_id=%d] Synthesizing: '%s'", req_id, resp_id, seq_id, s_text[:40])
                                    t_synth_start = time.perf_counter()
                                    b64 = await asyncio.to_thread(_fast_synth_b64, s_text, persona)
                                    synth_dur = (time.perf_counter() - t_synth_start) * 1000
                                    
                                    if b64 and not cancelled:
                                        if ttfa_ms == 0.0:
                                            ttfa_ms = (time.time() - t_received) * 1000
                                            logger.info("[TTFA] [request_id=%s, response_id=%s] Time to First Audio: %.1fms", req_id, resp_id, ttfa_ms)

                                        logger.info("[TTS_SYNTH_COMPLETE] [request_id=%s, response_id=%s, sequence_id=%d] Audio synthesized in %.1fms", req_id, resp_id, seq_id, synth_dur)
                                        try:
                                            chunk_payload = {
                                                "type": "chat_audio_chunk",
                                                "request_id": req_id,
                                                "response_id": resp_id,
                                                "sequence_id": seq_id,
                                                "audio_b64": b64,
                                                "text": s_text,
                                                "is_final": is_final,
                                                "active_persona": persona,
                                                "trace_id": plan.plan_id,
                                            }
                                            await websocket.send_json(chunk_payload)
                                            await gateway_registry.broadcast_all(chunk_payload, exclude_ws=websocket)
                                        except Exception as ws_err:
                                            logger.info("[TTS_CANCEL] [request_id=%s, response_id=%s] Client disconnected during audio send: %s", req_id, resp_id, ws_err)
                                            break
                                    elif not b64:
                                        logger.warning("[TTS_ERROR] [request_id=%s, response_id=%s, sequence_id=%d] Synthesis returned empty audio", req_id, resp_id, seq_id)
                                    s_idx += 1
                                    sentence_queue.task_done()
                            except asyncio.CancelledError:
                                logger.info("[TTS_CANCEL] [request_id=%s, response_id=%s] TTS worker cancelled", req_id, resp_id)
                            except Exception as ex:
                                logger.error("[TTS_ERROR] [request_id=%s, response_id=%s] TTS worker error: %s", req_id, resp_id, ex)

                        tts_task = asyncio.create_task(_tts_worker())
                        sys_extra = plan.steps[0].inputs.get("system_extra") if (plan.steps and hasattr(plan.steps[0], "inputs")) else None
                        def _token_gen():
                            for t in core_llm_agent.stream_response(query, persona_name=persona, system_extra=sys_extra):
                                yield t

                        loop = asyncio.get_running_loop()
                        iterator = iter(_token_gen())
                        token_count = 0

                        while True:
                            token = await loop.run_in_executor(None, next, iterator, None)
                            if token is None:
                                break
                            token_count += 1
                            if token_count == 1:
                                ttft_ms = (time.time() - t_received) * 1000
                                logger.info("[LLM_FIRST_TOKEN] [request_id=%s, response_id=%s] TTFT: %.1fms", req_id, resp_id, ttft_ms)

                            full_text += token
                            stream_buffer += token

                            logger.debug("[LLM_CHUNK] [request_id=%s, response_id=%s] token: '%s'", req_id, resp_id, token)
                            await websocket.send_json({
                                "type": "chat_stream_chunk",
                                "request_id": req_id,
                                "response_id": resp_id,
                                "token": token,
                                "trace_id": plan.plan_id,
                            })

                            # Early clause flush on first sentence for ultra-low TTFA
                            buf_words = stream_buffer.strip().split()
                            if not first_chunk_sent and len(buf_words) >= 4 and any(token.endswith(p) for p in [",", ";", ":", "—", "-"]):
                                s_chunk = stream_buffer.strip()
                                stream_buffer = ""
                                first_chunk_sent = True
                                logger.info("[SENTENCE_READY] [request_id=%s, response_id=%s] Early clause: '%s'", req_id, resp_id, s_chunk[:35])
                                logger.info("[TTS_QUEUE_ADD] [request_id=%s, response_id=%s] Queued early clause", req_id, resp_id)
                                await sentence_queue.put((s_chunk, False))

                            # Full sentence boundary detection (even 1 or 2 word answers like "Yes, sir." or "Understood.")
                            elif any(punct in token for punct in [".", "!", "?"]) and len(buf_words) >= 1:
                                # Ensure we don't prematurely split on decimal digits or common abbreviations
                                ends_clean = not re.search(r'\b(?:Mr|Mrs|Ms|Dr|Prof|Sr|Jr|vs|etc|e\.g|i\.e)\.$', stream_buffer.strip(), re.I) and not re.search(r'\d+\.$', stream_buffer.strip())
                                if ends_clean:
                                    s_chunk = stream_buffer.strip()
                                    stream_buffer = ""
                                    first_chunk_sent = True
                                    logger.info("[SENTENCE_READY] [request_id=%s, response_id=%s] Sentence: '%s'", req_id, resp_id, s_chunk[:35])
                                    logger.info("[TTS_QUEUE_ADD] [request_id=%s, response_id=%s] Queued sentence", req_id, resp_id)
                                    await sentence_queue.put((s_chunk, False))

                        # Flush any remaining buffer as final sentence
                        if stream_buffer.strip():
                            s_chunk = stream_buffer.strip()
                            stream_buffer = ""
                            logger.info("[SENTENCE_READY] [request_id=%s, response_id=%s] Remaining final chunk: '%s'", req_id, resp_id, s_chunk[:35])
                            logger.info("[TTS_QUEUE_ADD] [request_id=%s, response_id=%s] Queued final chunk", req_id, resp_id)
                            await sentence_queue.put((s_chunk, True))

                        final_resp = full_text.strip() or f"[{persona}]: Understood."
                        t_llm_complete = time.time()
                        logger.info("[LLM_COMPLETE] [request_id=%s, response_id=%s] LLM generation complete (%d chars) in %.1fms", req_id, resp_id, len(final_resp), (t_llm_complete - t_received) * 1000)

                        # Update Continuous Learning Engine for live Core LLM turn
                        try:
                            from orchestrator.learning import learning_engine
                            learning_engine.record_feedback(
                                action="core_llm_agent",
                                reward=1.0 if len(final_resp) > 0 else -0.5,
                                context=f"query:{query[:30]}"
                            )
                        except Exception as rl_err:
                            logger.debug("[Server] RL feedback recording warning: %s", rl_err)

                        # Immediately finalize the authoritative response on UI so UI and TTS stay perfectly in sync
                        resp_payload = {
                            "type": "chat_response",
                            "request_id": req_id,
                            "response_id": resp_id,
                            "active_persona": persona,
                            "response": final_resp,
                            "text": final_resp,
                            "payload": {
                                "text": final_resp,
                                "spoken_text": final_resp,
                                "intent": "chat",
                                "confidence": 1.0,
                                "requires_confirmation": False,
                                "is_exit": False,
                                "action_result": None,
                                "ttft_ms": round(ttft_ms, 1),
                                "ttfa_ms": round(ttfa_ms, 1),
                            },
                            "status": "ok",
                            "trace_id": plan.plan_id,
                            "plan": plan.to_dict(),
                        }
                        # Attach screen-reader accessible payload if requested by client/device capabilities
                        if req_accessibility:
                            try:
                                from capabilities.intelligence import capability_intelligence
                                acc_provider = capability_intelligence.select_provider("accessibility.format_payload")
                                if acc_provider:
                                    acc_res = acc_provider.execute("accessibility.format_payload", {
                                        "payload": final_resp,
                                        "role": "response",
                                    })
                                    if acc_res.status == "SUCCESS":
                                        resp_payload["accessible_payload"] = acc_res.output
                            except Exception as acc_err:
                                logger.debug("[Accessibility Interface] Error attaching payload: %s", acc_err)

                        await websocket.send_json(resp_payload)
                        await gateway_registry.broadcast_all(resp_payload, exclude_ws=websocket)

                        # Await remaining TTS synthesis chunks in background task
                        await sentence_queue.put(None)
                        await tts_task
                        logger.info("[TTS_RESPONSE_COMPLETE] [request_id=%s, response_id=%s] All sentences synthesized and dispatched", req_id, resp_id)

                    else:
                        # Standard tool execution path (system control, action tools, registry, browser, etc.)
                        t_tool_start = time.perf_counter()
                        logger.info("[ROUTER_COMPLETE] [request_id=%s, response_id=%s] Routed to tool agent '%s' in %.1fms", req_id, resp_id, first_agent, (t_tool_start - t_received_perf) * 1000)
                        result = await asyncio.to_thread(orchestrator_core.process_event, event, plan)
                        t_tool_end = time.perf_counter()
                        resp_str = result.get("response", "")
                        logger.info("[TOOL_EXEC_COMPLETE] [request_id=%s, response_id=%s] Tool executed in %.1fms. Result text: '%s'", req_id, resp_id, (t_tool_end - t_tool_start) * 1000, resp_str[:60])

                        final_persona = result.get("active_persona", persona) if result.get("type") == "persona_switch" else persona
                        # Authoritative UI message matching exact tool response dispatched IMMEDIATELY
                        tool_resp_payload = {
                            "type": "chat_response",
                            "request_id": req_id,
                            "response_id": resp_id,
                            "active_persona": final_persona,
                            "response": resp_str,
                            "text": resp_str,
                            "payload": {
                                "text": resp_str,
                                "spoken_text": resp_str,
                                "intent": "task",
                                "confidence": 1.0,
                                "requires_confirmation": False,
                                "is_exit": False,
                                "action_result": result.get("plan"),
                                "tool_exec_ms": round((t_tool_end - t_tool_start) * 1000, 1),
                            },
                            "status": "ok",
                            "trace_id": result.get("trace_id"),
                            "plan": result.get("plan"),
                        }
                        # Attach screen-reader accessible payload if requested by client/device capabilities
                        if req_accessibility:
                            try:
                                from capabilities.intelligence import capability_intelligence
                                acc_provider = capability_intelligence.select_provider("accessibility.format_payload")
                                if acc_provider:
                                    acc_res = acc_provider.execute("accessibility.format_payload", {
                                        "payload": resp_str,
                                        "table": result.get("plan"),
                                        "role": "status",
                                    })
                                    if acc_res.status == "SUCCESS":
                                        tool_resp_payload["accessible_payload"] = acc_res.output
                            except Exception as acc_err:
                                logger.debug("[Accessibility Interface] Error attaching tool payload: %s", acc_err)

                        await websocket.send_json(tool_resp_payload)
                        await gateway_registry.broadcast_all(tool_resp_payload, exclude_ws=websocket)

                        # Concurrent background TTS synthesis for tool response so WebSocket is immediately free
                        async def _synth_tool_audio(text_to_speak, p_name, r_id, rp_id, tr_id, target_ws):
                            # Sanitize text for speech: strip URLs, markdown links, code blocks, tables
                            clean_speech = re.sub(r'https?://\S+', '', text_to_speak)
                            clean_speech = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean_speech)
                            clean_speech = re.sub(r'```[\s\S]*?```', '', clean_speech)
                            clean_speech = re.sub(r'\|[^\n]+\|', '', clean_speech)
                            clean_speech = re.sub(r'#{1,6}\s*', '', clean_speech)
                            clean_speech = re.sub(r'\s+', ' ', clean_speech).strip()
                            # Spoken confirmation should be concise (at most first 2 sentences)
                            sentences = _split_into_sentences(clean_speech)[:2]
                            for s_idx, s_text in enumerate(sentences):
                                is_final_chunk = (s_idx == len(sentences) - 1)
                                seq_id = s_idx + 1
                                try:
                                    logger.info("[TTS_SYNTH_START] [request_id=%s, response_id=%s, sequence_id=%d] Synthesizing tool speech: '%s'", r_id, rp_id, seq_id, s_text[:35])
                                    t_s_start = time.perf_counter()
                                    b64_audio = await asyncio.to_thread(_fast_synth_b64, s_text, p_name)
                                    t_s_dur = (time.perf_counter() - t_s_start) * 1000
                                    if b64_audio:
                                        if s_idx == 0:
                                            tool_ttfa_ms = (time.perf_counter() - t_received_perf) * 1000
                                            logger.info("[TTFA] [request_id=%s, response_id=%s] Tool Time to First Audio: %.1fms", r_id, rp_id, tool_ttfa_ms)
                                        logger.info("[TTS_SYNTH_COMPLETE] [request_id=%s, response_id=%s, sequence_id=%d] Audio synthesized in %.1fms", r_id, rp_id, seq_id, t_s_dur)
                                        tool_chunk_payload = {
                                            "type": "chat_audio_chunk",
                                            "request_id": r_id,
                                            "response_id": rp_id,
                                            "sequence_id": seq_id,
                                            "audio_b64": b64_audio,
                                            "text": s_text,
                                            "is_final": is_final_chunk,
                                            "active_persona": p_name,
                                            "trace_id": tr_id,
                                        }
                                        await target_ws.send_json(tool_chunk_payload)
                                        await gateway_registry.broadcast_all(tool_chunk_payload, exclude_ws=target_ws)
                                except Exception as err:
                                    logger.debug("[TTS Tool Async Error]: %s", err)
                            logger.info("[TTS_RESPONSE_COMPLETE] [request_id=%s, response_id=%s] Tool TTS complete", r_id, rp_id)

                        asyncio.create_task(_synth_tool_audio(resp_str, persona, req_id, resp_id, result.get("trace_id"), websocket))

                        # Emit real media_playback_started event if media/song playback initiated
                        plan_dict = result.get("plan") or {}
                        is_media = False
                        if isinstance(plan_dict, dict):
                            if plan_dict.get("is_playing") or plan_dict.get("action") in ["chained_play", "play_youtube"]:
                                is_media = True
                        if not is_media and ("playing '" in resp_str.lower() or "playback" in resp_str.lower()):
                            is_media = True
                        if is_media:
                            logger.info("[WebSocket] Emitting REAL media_playback_started event for: '%s'", query)
                            await websocket.send_json({
                                "type": "media_playback_started",
                                "query": query,
                                "action": "chained_play",
                                "status": "playing",
                                "timestamp": time.time(),
                            })

            elif msg_type == "cast_command":
                target_device = data.get("device", "phone")
                media_url = data.get("media_url")
                title = data.get("title", "Cast Media")
                cast_res = cast_agent.cast_to_device(
                    device_name=target_device,
                    media_url=media_url or "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
                    title=title,
                )
                await websocket.send_json({"type": "cast_result", "result": cast_res})

    except WebSocketDisconnect:
        logger.info("[WebSocket] Client '%s' disconnected", device_id)
        gateway_registry.detach_websocket(device_id)
    except Exception as e:
        logger.error("[WebSocket Error] %s", str(e))
        gateway_registry.detach_websocket(device_id)


# -------------------------------------------------------------------------
# Static Web App Mounting: Unified Responsive Client & Legacy Clients
# -------------------------------------------------------------------------
UNIFIED_DIR = PROJECT_ROOT / "client" / "unified"
UNIFIED_DIR.mkdir(parents=True, exist_ok=True)

MOBILE_DIR = PROJECT_ROOT / "client" / "mobile"
MOBILE_DIR.mkdir(parents=True, exist_ok=True)

DESKTOP_DIR = PROJECT_ROOT / "client" / "desktop"
DESKTOP_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/unified", StaticFiles(directory=str(UNIFIED_DIR), html=True), name="unified")
app.mount("/mobile", StaticFiles(directory=str(UNIFIED_DIR), html=True), name="mobile")
app.mount("/desktop", StaticFiles(directory=str(DESKTOP_DIR), html=True), name="desktop")


@app.get("/")
async def root_redirect():
    """Serves the Unified Responsive Futuristic Client by default across all viewports."""
    index_file = UNIFIED_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return FileResponse(MOBILE_DIR / "index.html")


@app.get("/desktop")
async def desktop_redirect():
    """Serves the Desktop HUD Client (flagged for retirement in favor of unified client)."""
    index_file = DESKTOP_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return HTMLResponse("<h2>JARVIS Desktop HUD Client is Running.</h2>")

