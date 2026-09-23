/**
 * JARVIS Mobile Thin Client Application Logic
 * 
 * Provides voice, text, and camera interactions with zero local AI dependencies.
 * All reasoning (Qwen2.5 3B), vision (Moondream VLM), and speech (Piper TTS)
 * run entirely on the primary PC workstation via Device Gateway.
 */

// State
let gatewayUrl = window.location.origin;
let authToken = "";
let deviceName = "Mobile Phone";
let activePersona = "Jarvis";
let ws = null;
let heartbeatInterval = null;
let capturedImageBlob = null;
let isRecordingVoice = false;
let speechRecognizer = null;

// DOM Elements
const connBadge = document.getElementById("conn-badge");
const nodeHostLabel = document.getElementById("node-host");
const activePersonaLabel = document.getElementById("active-persona-label");
const activeDeviceCount = document.getElementById("active-device-count");
const chatStream = document.getElementById("chat-stream");
const queryInput = document.getElementById("query-input");
const btnSend = document.getElementById("btn-send");
const btnMic = document.getElementById("btn-mic");
const btnCamera = document.getElementById("btn-camera");
const cameraInput = document.getElementById("camera-input");
const cameraPreviewBar = document.getElementById("camera-preview-bar");
const cameraPreviewImg = document.getElementById("camera-preview-img");
const btnRemoveImage = document.getElementById("btn-remove-image");
const ttsPlayer = document.getElementById("tts-player");
const deviceList = document.getElementById("device-list");
const btnRefreshDevices = document.getElementById("btn-refresh-devices");
const castPlayerCard = document.getElementById("cast-player-card");
const castMediaTitle = document.getElementById("cast-media-title");
const remoteAudioPlayer = document.getElementById("remote-audio-player");
const btnCloseCast = document.getElementById("btn-close-cast");

// Settings Modal
const settingsModal = document.getElementById("settings-modal");
const btnSettings = document.getElementById("btn-settings");
const btnCloseSettings = document.getElementById("btn-close-settings");
const settingGatewayUrl = document.getElementById("setting-gateway-url");
const settingAuthToken = document.getElementById("setting-auth-token");
const settingDeviceName = document.getElementById("setting-device-name");
const btnSaveSettings = document.getElementById("btn-save-settings");

// Initialize Configuration
function initConfig() {
  const params = new URLSearchParams(window.location.search);
  // Authentication tokens are never accepted from URL query parameters.
  // Configure the token once through the settings UI or local storage.
  if (localStorage.getItem("jarvis_token")) {
    authToken = localStorage.getItem("jarvis_token");
  }

  if (params.has("url")) {
    gatewayUrl = params.get("url");
    localStorage.setItem("jarvis_gateway_url", gatewayUrl);
  } else if (localStorage.getItem("jarvis_gateway_url")) {
    gatewayUrl = localStorage.getItem("jarvis_gateway_url");
  } else if (window.location.origin && window.location.origin !== "null" && window.location.origin.startsWith("http")) {
    gatewayUrl = window.location.origin;
  }

  if (localStorage.getItem("jarvis_device_name")) {
    deviceName = localStorage.getItem("jarvis_device_name");
  }

  settingGatewayUrl.value = gatewayUrl;
  settingAuthToken.value = authToken;
  settingDeviceName.value = deviceName;

  // Show host IP in telemetry
  try {
    const hostPart = new URL(gatewayUrl).hostname;
    nodeHostLabel.textContent = `${hostPart} (Mesh)`;
  } catch (e) {
    nodeHostLabel.textContent = gatewayUrl;
  }
}

// Connect WebSocket with Auth Token
function connectWebSocket() {
  if (ws) {
    try { ws.close(); } catch (e) {}
  }

  const wsUrl = gatewayUrl.replace(/^http/, "ws") + "/ws";
  console.log(`[JARVIS Mobile] Connecting to WebSocket: ${wsUrl}`);
  connBadge.textContent = "CONNECTING...";
  connBadge.className = "badge";

  try {
    if (!authToken) { connBadge.textContent = "AUTH TOKEN REQUIRED"; connBadge.className = "badge badge-offline"; return; }
    ws = new WebSocket(wsUrl, [`jarvis-auth.${authToken}`]);

    ws.onopen = () => {
      console.log("[JARVIS Mobile] WebSocket connected successfully");
      connBadge.textContent = "ONLINE // MESH";
      connBadge.className = "badge badge-online";

      // Register device identity
      ws.send(JSON.stringify({
        type: "register",
        device_id: `phone_${navigator.userAgent.includes("Android") ? "android" : "mobile"}`,
        name: deviceName,
        client_type: "phone"
      }));

      // Start heartbeat
      if (heartbeatInterval) clearInterval(heartbeatInterval);
      heartbeatInterval = setInterval(() => {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: "heartbeat" }));
        }
      }, 25000);

      fetchDevices();
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleServerMessage(data);
      } catch (err) {
        console.error("[JARVIS Mobile] Failed to parse message:", err);
      }
    };

    ws.onclose = (event) => {
      console.warn(`[JARVIS Mobile] WebSocket disconnected: code=${event.code}`);
      connBadge.textContent = event.code === 4401 ? "AUTH REJECTED (401)" : "DISCONNECTED";
      connBadge.className = "badge badge-offline";
      if (heartbeatInterval) clearInterval(heartbeatInterval);

      // Auto-reconnect after 4s if not explicit 4401 auth failure
      if (event.code !== 4401) {
        setTimeout(connectWebSocket, 4000);
      }
    };

    ws.onerror = (err) => {
      console.error("[JARVIS Mobile] WebSocket error:", err);
    };
  } catch (err) {
    console.error("[JARVIS Mobile] Connection error:", err);
    connBadge.textContent = "ERROR";
    connBadge.className = "badge badge-offline";
  }
}

// Handle Incoming Server Push Messages
function handleServerMessage(msg) {
  console.log("[JARVIS Mobile] Received message:", msg);

  if (msg.type === "task_progress") {
    showTypingIndicator(msg.message || `${msg.active_persona || activePersona} is working on it...`);
  } else if (msg.type === "chat_response") {
    removeTypingIndicator();
    appendMessage("assistant", msg.response, msg.active_persona);
    playTTS(msg.response, msg.active_persona);
  } else if (msg.type === "media_play" || msg.action === "play_media") {
    // Cross-device cast payload received!
    console.log("[JARVIS Mobile] Cast received: Playing on this mobile phone!", msg);
    displayCastMedia(msg.title || "Remote Audio Stream", msg.url);
  } else if (msg.type === "welcome") {
    if (msg.active_persona) {
      setActivePersonaUI(msg.active_persona);
    }
  }
}

function showTypingIndicator(text) {
  removeTypingIndicator();
  const ind = document.createElement("div");
  ind.id = "typing-indicator";
  ind.className = "typing-bubble";
  ind.innerHTML = `
    <div class="typing-dots"><span></span><span></span><span></span></div>
    <span class="typing-text">${escapeHtml(text)}</span>
  `;
  chatStream.appendChild(ind);
  chatStream.scrollTop = chatStream.scrollHeight;
}

function removeTypingIndicator() {
  const existing = document.getElementById("typing-indicator");
  if (existing) existing.remove();
}

// Remote Media Cast Player Overlay
function displayCastMedia(title, url) {
  castMediaTitle.textContent = title;
  remoteAudioPlayer.src = url;
  castPlayerCard.classList.remove("hidden");
  remoteAudioPlayer.play().catch(e => {
    console.log("[JARVIS Mobile] Autoplay blocked, user interaction required:", e);
  });
  appendMessage("system", `📡 Received media cast from PC: Now playing "${title}" on your phone.`);
}

btnCloseCast.addEventListener("click", () => {
  remoteAudioPlayer.pause();
  castPlayerCard.classList.add("hidden");
});

// Fetch Device Registry
async function fetchDevices() {
  try {
    const res = await fetch(`${gatewayUrl}/api/devices`, {
      headers: { "X-JARVIS-Token": authToken }
    });
    if (!res.ok) return;
    const data = await res.json();
    renderDevices(data.devices || []);
  } catch (err) {
    console.warn("[JARVIS Mobile] Could not fetch devices:", err);
  }
}

function renderDevices(devices) {
  activeDeviceCount.textContent = `${devices.filter(d => d.online).length} Live`;
  deviceList.innerHTML = "";

  devices.forEach(dev => {
    const chip = document.createElement("div");
    chip.className = `device-chip ${dev.online ? "online" : "offline"}`;
    chip.innerHTML = `
      <span class="chip-dot"></span>
      <span class="chip-name">${escapeHtml(dev.name)}</span>
      <span class="chip-type">[${dev.client_type}]</span>
    `;
    deviceList.appendChild(chip);
  });
}

btnRefreshDevices.addEventListener("click", fetchDevices);

// Append Message to UI
function appendMessage(role, text, persona = null) {
  const msgDiv = document.createElement("div");
  msgDiv.className = `message message-${role}`;

  const headerText = role === "user" ? "You (Mobile)" : (persona || activePersona);
  const bubbleHtml = `
    ${role !== "system" ? `<div class="msg-header">${escapeHtml(headerText)}</div>` : ""}
    <div class="msg-bubble">${formatMessageText(text)}</div>
  `;
  msgDiv.innerHTML = bubbleHtml;
  chatStream.appendChild(msgDiv);
  chatStream.scrollTop = chatStream.scrollHeight;
}

function formatMessageText(text) {
  return escapeHtml(text).replace(/\n/g, "<br>");
}

function escapeHtml(str) {
  return (str || "").replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[m]));
}

// Neural TTS Audio Playback (Streamed from PC Piper engine)
async function playTTS(text, persona) {
  if (!text || text.length > 300) return; // Keep brief for speech
  try {
    const res = await fetch(`${gatewayUrl}/api/tts/synthesize`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-JARVIS-Token": authToken
      },
      body: JSON.stringify({ text, persona })
    });

    if (res.ok) {
      const audioBlob = await res.blob();
      const audioUrl = URL.createObjectURL(audioBlob);
      ttsPlayer.src = audioUrl;
      ttsPlayer.play().catch(e => console.log("[TTS] Audio playback deferred:", e));
    }
  } catch (err) {
    console.warn("[JARVIS Mobile] TTS playback failed:", err);
  }
}

// Send Command (Text or Vision)
async function sendCommand() {
  const query = queryInput.value.trim();
  if (!query && !capturedImageBlob) return;

  queryInput.value = "";

  // 1. If Image is attached, analyze with Moondream on PC
  if (capturedImageBlob) {
    const imgToSend = capturedImageBlob;
    clearImagePreview();
    appendMessage("user", query ? `[Photo Attached] ${query}` : "[Photo Attached] What do you see in this photo?");
    appendMessage("system", "Uploading photo to PC for Moondream 1.6B VLM analysis...");

    const formData = new FormData();
    formData.append("image", imgToSend, "camera_capture.jpg");
    formData.append("prompt", query || "Describe what you see in this image in detail.");
    formData.append("persona", activePersona);

    try {
      const res = await fetch(`${gatewayUrl}/api/vision/analyze`, {
        method: "POST",
        headers: { "X-JARVIS-Token": authToken },
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        appendMessage("assistant", data.analysis || data.caption, activePersona);
        playTTS(data.analysis || data.caption, activePersona);
      } else {
        appendMessage("system", `Vision error: ${data.error || "Analysis failed"}`);
      }
    } catch (err) {
      appendMessage("system", `Vision network error: ${err.message}`);
    }
    return;
  }

  // 2. Otherwise regular text command
  appendMessage("user", query);

  // Send via WebSocket if open, else fallback to REST
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({
      type: "chat",
      query: query,
      persona: activePersona
    }));
  } else {
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
          device_id: "phone_client",
          device_name: deviceName
        })
      });

      if (!res.ok) {
        appendMessage("system", `Gateway error: HTTP ${res.status} Unauthorized/Error`);
        return;
      }

      const data = await res.json();
      appendMessage("assistant", data.response, data.active_persona);
      playTTS(data.response, data.active_persona);
    } catch (err) {
      appendMessage("system", `Connection failed: ${err.message}`);
    }
  }
}

// Camera Capture
btnCamera.addEventListener("click", () => {
  cameraInput.click();
});

cameraInput.addEventListener("change", (e) => {
  const file = e.target.files[0];
  if (!file) return;

  capturedImageBlob = file;
  const reader = new FileReader();
  reader.onload = (ev) => {
    cameraPreviewImg.src = ev.target.result;
    cameraPreviewBar.classList.remove("hidden");
  };
  reader.readAsDataURL(file);
});

btnRemoveImage.addEventListener("click", clearImagePreview);

function clearImagePreview() {
  capturedImageBlob = null;
  cameraInput.value = "";
  cameraPreviewBar.classList.add("hidden");
}

// Microphone Speech Recognition
btnMic.addEventListener("click", toggleVoiceRecording);

function toggleVoiceRecording() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition is not supported in this browser. Please use Chrome/Safari or type your command.");
    return;
  }

  if (isRecordingVoice) {
    if (speechRecognizer) speechRecognizer.stop();
    return;
  }

  speechRecognizer = new SpeechRecognition();
  speechRecognizer.continuous = false;
  speechRecognizer.interimResults = false;
  speechRecognizer.lang = "en-IN"; // English (India) default

  speechRecognizer.onstart = () => {
    isRecordingVoice = true;
    btnMic.classList.add("recording");
    queryInput.placeholder = "Listening... Speak now...";
  };

  speechRecognizer.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    queryInput.value = transcript;
    sendCommand();
  };

  speechRecognizer.onerror = (event) => {
    console.warn("[Voice] Speech recognition error:", event.error);
    stopVoiceRecordingUI();
  };

  speechRecognizer.onend = () => {
    stopVoiceRecordingUI();
  };

  speechRecognizer.start();
}

function stopVoiceRecordingUI() {
  isRecordingVoice = false;
  btnMic.classList.remove("recording");
  queryInput.placeholder = "Message JARVIS, or 'play song on my phone'...";
}

// Persona Switch Tabs
document.querySelectorAll(".persona-tab").forEach(tab => {
  tab.addEventListener("click", async () => {
    const persona = tab.getAttribute("data-persona");
    setActivePersonaUI(persona);

    try {
      await fetch(`${gatewayUrl}/api/personas/switch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-JARVIS-Token": authToken
        },
        body: JSON.stringify({ persona })
      });
      appendMessage("system", `Switched active persona to ${persona}.`);
    } catch (e) {
      console.warn("Could not sync persona switch:", e);
    }
  });
});

function setActivePersonaUI(persona) {
  activePersona = persona;
  activePersonaLabel.textContent = persona;
  document.querySelectorAll(".persona-tab").forEach(tab => {
    if (tab.getAttribute("data-persona").toLowerCase() === persona.toLowerCase()) {
      tab.classList.add("active");
    } else {
      tab.classList.remove("active");
    }
  });
}

// Settings Modal Handlers
btnSettings.addEventListener("click", () => settingsModal.classList.remove("hidden"));
btnCloseSettings.addEventListener("click", () => settingsModal.classList.add("hidden"));

btnSaveSettings.addEventListener("click", () => {
  gatewayUrl = settingGatewayUrl.value.trim().replace(/\/$/, "");
  authToken = settingAuthToken.value.trim();
  deviceName = settingDeviceName.value.trim() || "Mobile Phone";

  localStorage.setItem("jarvis_gateway_url", gatewayUrl);
  localStorage.setItem("jarvis_token", authToken);
  localStorage.setItem("jarvis_device_name", deviceName);

  settingsModal.classList.add("hidden");
  connectWebSocket();
});

// Event Listeners for Input
btnSend.addEventListener("click", sendCommand);
queryInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendCommand();
  }
});

// Bootstrapping
window.addEventListener("DOMContentLoaded", () => {
  initConfig();
  connectWebSocket();
});
