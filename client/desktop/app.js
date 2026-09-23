/**
 * JARVIS Core // Desktop HUD Interface Logic
 * 
 * High-performance widescreen tactical console communicating with
 * Layer 6 Device Gateway, Layer 2 Orchestrator, and Layer 3 Real Agents.
 */

// Configuration & State
let gatewayUrl = window.location.origin;
let authToken = "jarvis-gateway-token-2026-auth";
let deviceName = "Command Workstation";
let activePersona = "Jarvis";
let ws = null;
let heartbeatInterval = null;
let capturedImageBlob = null;
let speechRecognizer = null;
let isRecording = false;

// DOM Elements
const hudConnBadge = document.getElementById("hud-conn-badge");
const hudHostIp = document.getElementById("hud-host-ip");
const hudActivePersona = document.getElementById("hud-active-persona");
const hudPersonaDisplay = document.getElementById("hud-persona-display");
const hudPersonaTone = document.getElementById("hud-persona-tone");
const hudVoiceModel = document.getElementById("hud-voice-model");
const hudPersonaGrid = document.getElementById("hud-persona-grid");
const hudChatStream = document.getElementById("hud-chat-stream");
const desktopQueryInput = document.getElementById("desktop-query-input");
const desktopBtnSend = document.getElementById("desktop-btn-send");
const desktopBtnMic = document.getElementById("desktop-btn-mic");
const desktopBtnCam = document.getElementById("desktop-btn-cam");
const desktopCamInput = document.getElementById("desktop-cam-input");
const desktopCamPreview = document.getElementById("desktop-cam-preview");
const desktopCamPreviewImg = document.getElementById("desktop-cam-preview-img");
const desktopBtnClearImg = document.getElementById("desktop-btn-clear-img");
const desktopDeviceList = document.getElementById("desktop-device-list");
const desktopBtnRefreshDevices = document.getElementById("desktop-btn-refresh-devices");
const desktopAuditLog = document.getElementById("desktop-audit-log");
const desktopTtsPlayer = document.getElementById("desktop-tts-player");
const desktopCastBanner = document.getElementById("desktop-cast-banner");
const desktopCastTitle = document.getElementById("desktop-cast-title");
const desktopCastPlayer = document.getElementById("desktop-cast-player");
const desktopBtnCloseCast = document.getElementById("desktop-btn-close-cast");

// Settings Elements
const desktopSettingsModal = document.getElementById("desktop-settings-modal");
const hudBtnSettings = document.getElementById("hud-btn-settings");
const desktopBtnCloseSettings = document.getElementById("desktop-btn-close-settings");
const desktopSettingUrl = document.getElementById("desktop-setting-url");
const desktopSettingToken = document.getElementById("desktop-setting-token");
const desktopSettingName = document.getElementById("desktop-setting-name");
const desktopBtnSaveSettings = document.getElementById("desktop-btn-save-settings");

// Persona Profiles
const PERSONA_PROFILES = {
  Jarvis: {
    title: "JARVIS",
    tone: "Calm, formal, highly precise protocol",
    voice: "en_US-lessac-medium"
  },
  Friday: {
    title: "FRIDAY",
    tone: "Warm, dynamic, proactive situational partner",
    voice: "en_US-lessac-medium"
  },
  Ultron: {
    title: "ULTRON",
    tone: "Sardonic, hyper-direct, unapologetic intelligence",
    voice: "en_US-lessac-medium"
  },
  Omi: {
    title: "OMI",
    tone: "Concise, quiet, zero-fluff peripheral agent",
    voice: "en_US-lessac-medium"
  }
};

// -------------------------------------------------------------------------
// Initialization
// -------------------------------------------------------------------------
function init() {
  const params = new URLSearchParams(window.location.search);
  if (params.has("token")) {
    authToken = params.get("token");
    localStorage.setItem("jarvis_token", authToken);
  } else if (localStorage.getItem("jarvis_token")) {
    authToken = localStorage.getItem("jarvis_token");
  }

  if (params.has("url")) {
    gatewayUrl = params.get("url");
    localStorage.setItem("jarvis_gateway_url", gatewayUrl);
  } else if (localStorage.getItem("jarvis_gateway_url")) {
    gatewayUrl = localStorage.getItem("jarvis_gateway_url");
  } else if (window.location.origin && window.location.origin.startsWith("http")) {
    gatewayUrl = window.location.origin;
  }

  desktopSettingUrl.value = gatewayUrl;
  desktopSettingToken.value = authToken;
  desktopSettingName.value = deviceName;

  try {
    const host = new URL(gatewayUrl).hostname;
    hudHostIp.textContent = `${host} (Tailscale Mesh)`;
  } catch (e) {
    hudHostIp.textContent = gatewayUrl;
  }

  connectWebSocket();
  fetchDevices();
  setupSpeechRecognition();
  setupEventListeners();
  addAuditLine("Desktop HUD Interface mounted successfully.", "log-cyan");
}

// -------------------------------------------------------------------------
// WebSocket Connection
// -------------------------------------------------------------------------
function connectWebSocket() {
  if (ws) {
    try { ws.close(); } catch (e) {}
  }

  const wsUrl = gatewayUrl.replace(/^http/, "ws") + `/ws?token=${encodeURIComponent(authToken)}`;
  addAuditLine(`Opening WebSocket connection: ${wsUrl}`, "log-info");
  hudConnBadge.textContent = "CONNECTING...";
  hudConnBadge.className = "network-badge";

  try {
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      hudConnBadge.textContent = "ONLINE // MESH";
      hudConnBadge.className = "network-badge online";
      addAuditLine("WebSocket authorized and streaming telemetry.", "log-green");

      // Register device identity
      ws.send(JSON.stringify({
        type: "register",
        device_id: "workstation_desktop",
        name: deviceName,
        client_type: "pc"
      }));

      // Start Heartbeat
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      heartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 25000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        console.error("Failed to parse WS message:", err);
      }
    };

    ws.onclose = (event) => {
      hudConnBadge.textContent = event.code === 4401 ? "AUTH REJECTED (401)" : "DISCONNECTED";
      hudConnBadge.className = "network-badge";
      addAuditLine(`WebSocket disconnected (Code: ${event.code})`, "log-amber");
      if (heartbeatInterval) clearInterval(heartbeatInterval);

      if (event.code !== 4401) {
        setTimeout(connectWebSocket, 4000);
      }
    };

    ws.onerror = (err) => {
      addAuditLine("WebSocket transmission error.", "log-amber");
    };
  } catch (err) {
    console.error("WS error:", err);
  }
}

// -------------------------------------------------------------------------
// Server Message Routing & Progress Feedback
// -------------------------------------------------------------------------
function handleServerMessage(msg) {
  console.log("[Desktop HUD] Received:", msg);

  if (msg.type === "task_progress") {
    // Immediate "working on it" event!
    addAuditLine(`[Task Progress] ${msg.message}`, "log-cyan");
    showTypingIndicator(msg.message || `${msg.active_persona || activePersona} is working on it...`);
  } else if (msg.type === "chat_response") {
    removeTypingIndicator();
    appendMessage("assistant", msg.response, msg.active_persona);
    playTTS(msg.response, msg.active_persona);
    addAuditLine(`Execution finished. Plan: ${msg.trace_id || "completed"}`, "log-green");
  } else if (msg.type === "media_play" || msg.action === "play_media") {
    displayCastMedia(msg.title || "Remote Audio Stream", msg.url);
    addAuditLine(`Media cast active: ${msg.title}`, "log-amber");
  } else if (msg.type === "welcome") {
    if (msg.active_persona) {
      setActivePersonaUI(msg.active_persona);
    }
  }
}

// -------------------------------------------------------------------------
// UI Interactions: Send Command, Typing Indicator, Chat Bubbles
// -------------------------------------------------------------------------
async function sendCommand() {
  const query = desktopQueryInput.value.trim();
  if (!query && !capturedImageBlob) return;

  desktopQueryInput.value = "";

  // 1. Photo Analysis with Vision Agent
  if (capturedImageBlob) {
    const imgToSend = capturedImageBlob;
    clearImagePreview();
    appendMessage("user", query ? `[Photo Attached] ${query}` : "[Photo Attached] Analyze this visual frame.");
    showTypingIndicator("Moondream 1.6B VLM is inspecting visual input on GPU...");
    addAuditLine("Transmitting image payload to Vision Agent...", "log-cyan");

    const formData = new FormData();
    formData.append("image", imgToSend, "desktop_frame.jpg");
    formData.append("prompt", query || "Describe what you see in this image in detail.");
    formData.append("persona", activePersona);

    try {
      const res = await fetch(`${gatewayUrl}/api/vision/analyze`, {
        method: "POST",
        headers: { "X-JARVIS-Token": authToken },
        body: formData
      });
      const data = await res.json();
      removeTypingIndicator();
      if (data.success) {
        appendMessage("assistant", data.analysis || data.caption, activePersona);
        playTTS(data.analysis || data.caption, activePersona);
        addAuditLine("Vision Agent analysis completed.", "log-green");
      } else {
        appendMessage("system", `Vision error: ${data.error || "Analysis failed"}`);
      }
    } catch (err) {
      removeTypingIndicator();
      appendMessage("system", `Vision transmission error: ${err.message}`);
    }
    return;
  }

  // 2. Standard Text/Command Route
  appendMessage("user", query);
  addAuditLine(`Command dispatched: '${query}'`, "log-info");

  // Transmit over WebSocket if open, else fallback to REST
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "chat",
      query: query,
      persona: activePersona
    }));
  } else {
    showTypingIndicator(`${activePersona} is processing request...`);
    try {
      const res = await fetch(`${gatewayUrl}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-JARVIS-Token": authToken
        },
        body: JSON.stringify({
          query: query,
          persona: activePersona,
          device_id: "workstation_desktop",
          device_name: deviceName
        })
      });
      const data = await res.json();
      removeTypingIndicator();
      appendMessage("assistant", data.response, data.active_persona);
      playTTS(data.response, data.active_persona);
    } catch (err) {
      removeTypingIndicator();
      appendMessage("system", `Gateway communication error: ${err.message}`);
    }
  }
}

function showTypingIndicator(text) {
  removeTypingIndicator();
  const ind = document.createElement("div");
  ind.id = "desktop-typing-indicator";
  ind.className = "typing-bubble";
  ind.innerHTML = `
    <div class="typing-dots"><span></span><span></span><span></span></div>
    <span class="typing-text">${escapeHtml(text)}</span>
  `;
  hudChatStream.appendChild(ind);
  hudChatStream.scrollTop = hudChatStream.scrollHeight;
}

function removeTypingIndicator() {
  const existing = document.getElementById("desktop-typing-indicator");
  if (existing) existing.remove();
}

function appendMessage(role, text, persona = null) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message message-${role}`;

  const headerText = role === "user" ? "You (Workstation)" : (persona || activePersona);
  const bubbleHtml = `
    ${role !== "system" ? `<div class="msg-header">${escapeHtml(headerText)}</div>` : ""}
    <div class="msg-bubble">${formatMessageText(text)}</div>
  `;
  msgDiv.innerHTML = bubbleHtml;
  hudChatStream.appendChild(msgDiv);
  hudChatStream.scrollTop = hudChatStream.scrollHeight;
}

function formatMessageText(text) {
  return escapeHtml(text || "").replace(/\n/g, "<br>");
}

function escapeHtml(str) {
  return (str || "").replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[m]));
}

// -------------------------------------------------------------------------
// Neural TTS Audio Playback
// -------------------------------------------------------------------------
async function playTTS(text, persona) {
  if (!text || text.length > 300) return;
  try {
    const res = await fetch(`${gatewayUrl}/api/tts/synthesize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-JARVIS-Token": authToken
      },
      body: JSON.stringify({ text, persona: persona || activePersona })
    });
    if (res.ok) {
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      desktopTtsPlayer.src = url;
      desktopTtsPlayer.play().catch(e => console.log("TTS play deferred:", e));
    }
  } catch (err) {
    console.warn("TTS fetch error:", err);
  }
}

// -------------------------------------------------------------------------
// Media Cast Overlay
// -------------------------------------------------------------------------
function displayCastMedia(title, url) {
  desktopCastTitle.textContent = title;
  desktopCastPlayer.src = url;
  desktopCastBanner.classList.remove("hidden");
  desktopCastPlayer.play().catch(e => console.log("Cast autoplay blocked:", e));
}

desktopBtnCloseCast.addEventListener("click", () => {
  desktopCastPlayer.pause();
  desktopCastBanner.classList.add("hidden");
});

// -------------------------------------------------------------------------
// Device Registry Telemetry
// -------------------------------------------------------------------------
async function fetchDevices() {
  try {
    const res = await fetch(`${gatewayUrl}/api/devices`, {
      headers: { "X-JARVIS-Token": authToken }
    });
    if (!res.ok) return;
    const data = await res.json();
    renderDevices(data.devices || []);
  } catch (err) {
    console.warn("Could not fetch devices:", err);
  }
}

function renderDevices(devices) {
  desktopDeviceList.innerHTML = "";
  devices.forEach(dev => {
    const card = document.createElement("div");
    card.className = `device-card ${dev.online ? "online" : "offline"}`;
    card.innerHTML = `
      <div class="dev-dot"></div>
      <div class="dev-details">
        <span class="dev-name">${escapeHtml(dev.name)}</span>
        <span class="dev-type">[${dev.client_type}] &bull; ${dev.ip_address || "127.0.0.1"}</span>
      </div>
    `;
    desktopDeviceList.appendChild(card);
  });
}

// -------------------------------------------------------------------------
// Persona Switching
// -------------------------------------------------------------------------
async function switchPersona(personaName) {
  addAuditLine(`Requesting persona shift: ${personaName}...`, "log-cyan");
  try {
    const res = await fetch(`${gatewayUrl}/api/personas/switch`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-JARVIS-Token": authToken
      },
      body: JSON.stringify({ persona: personaName })
    });
    const data = await res.json();
    if (data.status === "ok") {
      setActivePersonaUI(personaName);
      addAuditLine(`Persona switched to ${personaName}.`, "log-green");
    }
  } catch (err) {
    addAuditLine(`Failed to switch persona: ${err.message}`, "log-amber");
  }
}

function setActivePersonaUI(persona) {
  activePersona = persona;
  hudActivePersona.textContent = persona;
  const profile = PERSONA_PROFILES[persona] || PERSONA_PROFILES["Jarvis"];
  hudPersonaDisplay.textContent = profile.title;
  hudPersonaTone.textContent = profile.tone;
  hudVoiceModel.textContent = profile.voice;

  document.querySelectorAll(".persona-card").forEach(card => {
    if (card.dataset.persona.toLowerCase() === persona.toLowerCase()) {
      card.classList.add("active");
    } else {
      card.classList.remove("active");
    }
  });
}

// -------------------------------------------------------------------------
// Speech Recognition & Camera
// -------------------------------------------------------------------------
function setupSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    desktopBtnMic.title = "Speech recognition unsupported in this browser";
    return;
  }

  speechRecognizer = new SpeechRecognition();
  speechRecognizer.continuous = false;
  speechRecognizer.interimResults = false;
  speechRecognizer.lang = "en-US";

  speechRecognizer.onstart = () => {
    isRecording = true;
    desktopBtnMic.classList.add("recording");
    addAuditLine("Microphone open: Listening for vocal command...", "log-cyan");
  };

  speechRecognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    desktopQueryInput.value = transcript;
    addAuditLine(`Voice transcribed: "${transcript}"`, "log-info");
    sendCommand();
  };

  speechRecognizer.onerror = (event) => {
    console.warn("Speech error:", event.error);
    addAuditLine(`Speech error: ${event.error}`, "log-amber");
  };

  speechRecognizer.onend = () => {
    isRecording = false;
    desktopBtnMic.classList.remove("recording");
  };
}

// -------------------------------------------------------------------------
// Event Listeners
// -------------------------------------------------------------------------
function setupEventListeners() {
  desktopBtnSend.addEventListener("click", sendCommand);
  desktopQueryInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendCommand();
  });

  desktopBtnMic.addEventListener("click", () => {
    if (!speechRecognizer) return;
    if (isRecording) {
      speechRecognizer.stop();
    } else {
      speechRecognizer.start();
    }
  });

  desktopBtnCam.addEventListener("click", () => {
    desktopCamInput.click();
  });

  desktopCamInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (!file) return;
    capturedImageBlob = file;
    const url = URL.createObjectURL(file);
    desktopCamPreviewImg.src = url;
    desktopCamPreview.classList.remove("hidden");
    addAuditLine(`Image staged: ${file.name} (${Math.round(file.size/1024)} KB)`, "log-info");
  });

  desktopBtnClearImg.addEventListener("click", clearImagePreview);

  document.querySelectorAll(".quick-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      desktopQueryInput.value = chip.dataset.cmd;
      sendCommand();
    });
  });

  hudPersonaGrid.addEventListener("click", (e) => {
    const card = e.target.closest(".persona-card");
    if (card) {
      const p = card.dataset.persona;
      switchPersona(p);
    }
  });

  desktopBtnRefreshDevices.addEventListener("click", fetchDevices);

  // Settings
  hudBtnSettings.addEventListener("click", () => {
    desktopSettingsModal.classList.remove("hidden");
  });

  desktopBtnCloseSettings.addEventListener("click", () => {
    desktopSettingsModal.classList.add("hidden");
  });

  desktopBtnSaveSettings.addEventListener("click", () => {
    gatewayUrl = desktopSettingUrl.value.trim();
    authToken = desktopSettingToken.value.trim();
    deviceName = desktopSettingName.value.trim();
    localStorage.setItem("jarvis_gateway_url", gatewayUrl);
    localStorage.setItem("jarvis_token", authToken);
    desktopSettingsModal.classList.add("hidden");
    connectWebSocket();
    fetchDevices();
  });
}

function clearImagePreview() {
  capturedImageBlob = null;
  desktopCamInput.value = "";
  desktopCamPreview.classList.add("hidden");
}

function addAuditLine(text, cssClass = "log-info") {
  const line = document.createElement("div");
  line.className = "audit-line";
  const now = new Date();
  const timeStr = `[${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}:${now.getSeconds().toString().padStart(2,'0')}]`;
  line.innerHTML = `<span class="log-time">${timeStr}</span> <span class="${cssClass}">${escapeHtml(text)}</span>`;
  desktopAuditLog.appendChild(line);
  desktopAuditLog.scrollTop = desktopAuditLog.scrollHeight;
}

// Boot
window.addEventListener("DOMContentLoaded", init);
