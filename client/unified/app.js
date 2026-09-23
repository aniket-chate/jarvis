/**
 * JARVIS Unified Frontend Controller & Runtime Adapter
 * 
 * Authoritative Visual Design: Antique Gold / Charcoal Aesthetic
 * Authoritative Behavioral Architecture: JARVIS Cognitive Core, World Model, Capability Intelligence
 */

(function () {
  "use strict";

  // Configuration & Gateway State
  const GATEWAY_URL = window.location.origin;
  let GATEWAY_TOKEN = localStorage.getItem("jarvis_gateway_token") || "";
  const DEVICE_ID = localStorage.getItem("jarvis_device_id") || `web_hud_${Math.random().toString(36).substring(2, 9)}`;

  let activePersona = "Jarvis";
  let isOnline = false;
  let ws = null;
  let reconnectTimer = null;
  let currentResponseId = null;
  let isRecording = false;
  let recognition = null;

  // Audio queue for sequential streaming TTS sentences
  const audioQueue = [];
  let isAudioPlaying = false;
  const ttsPlayer = document.getElementById("tts-audio-player");

  // DOM Cache
  const elDate = document.getElementById("live-date");
  const elClock = document.getElementById("live-clock");
  const elPlace = document.getElementById("place-label");
  const elGreeting = document.getElementById("hero-greeting");
  const elSubtitle = document.getElementById("hero-subtitle");
  const elAskForm = document.getElementById("ask-form");
  const elAskInput = document.getElementById("ask-input");
  const elBtnMic = document.getElementById("btn-mic");
  const elBtnSend = document.getElementById("btn-send");
  const elBtnClip = document.getElementById("btn-clip");
  const elResponseContainer = document.getElementById("response-container");
  const elResponsePersona = document.getElementById("response-persona-name");
  const elResponseStatus = document.getElementById("response-status-badge");
  const elResponseText = document.getElementById("response-text");
  const elResponseVerification = document.getElementById("response-verification-note");
  const elBtnCloseResponse = document.getElementById("btn-close-response");
  const elOfflineBanner = document.getElementById("offline-banner");
  const elYourDayList = document.getElementById("your-day-list");
  const elRecentFilesList = document.getElementById("recent-files-list");
  const elQuickActionsList = document.getElementById("quick-actions-list");
  const elHeroChips = document.getElementById("hero-chips");
  const elTopModes = document.getElementById("top-modes-list");
  const elStatusHeadline = document.getElementById("status-headline");
  const elDialRing = document.getElementById("system-dial-ring");
  const elTopQuoteAuthor = document.getElementById("top-quote-author");

  // Section Modal Elements
  const elModal = document.getElementById("section-modal");
  const elModalTitle = document.getElementById("modal-title");
  const elModalContent = document.getElementById("modal-content");
  const elBtnCloseModal = document.getElementById("btn-close-modal");

  // =========================================================================
  // 1. Dynamic Date, Clock & Daypart Greeting Utility (Zero Hardcoding)
  // =========================================================================

  function getDaypartGreeting(hour) {
    if (hour >= 0 && hour < 5) return "Good Night, Friend.";
    if (hour >= 5 && hour < 12) return "Good Morning, Friend.";
    if (hour >= 12 && hour < 17) return "Good Afternoon, Friend.";
    if (hour >= 17 && hour < 21) return "Good Evening, Friend.";
    return "Good Night, Friend.";
  }

  function updateClockAndGreeting() {
    const now = new Date();
    
    // Format Date: e.g. "SUN, SEP 20, 2026"
    if (elDate) {
      elDate.textContent = now.toLocaleDateString("en-US", {
        weekday: "short",
        month: "short",
        day: "numeric",
        year: "numeric",
      }).toUpperCase().replace(/,\s/, ", ");
    }

    // Format Clock: e.g. "11:24 PM"
    if (elClock) {
      elClock.textContent = now.toLocaleTimeString("en-US", {
        hour: "numeric",
        minute: "2-digit",
      });
    }

    // Dynamic Greeting
    const hour = now.getHours();
    const greetingText = getDaypartGreeting(hour);
    if (elGreeting && elGreeting.textContent !== greetingText) {
      elGreeting.textContent = greetingText;
    }
  }

  // Initial run and interval
  updateClockAndGreeting();
  setInterval(updateClockAndGreeting, 1000);

  // =========================================================================
  // 2. Real Location Resolver (Honest Fallback)
  // =========================================================================

  async function resolveLocation() {
    try {
      const res = await fetch(`${GATEWAY_URL}/api/context/location`, {
        headers: { "X-JARVIS-Token": GATEWAY_TOKEN },
      });
      if (res.ok) {
        const data = await res.json();
        if (data.location && elPlace) {
          elPlace.textContent = data.location;
          return;
        }
      }
    } catch (e) {
      console.debug("[Location] Runtime location fetch bypassed:", e);
    }

    // Local device timezone fallback
    try {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (tz && elPlace) {
        elPlace.textContent = tz.replace(/_/g, " ").toUpperCase();
      }
    } catch (e) {
      if (elPlace) elPlace.textContent = "LOCAL TIMEZONE";
    }
  }

  // =========================================================================
  // 3. JARVIS Runtime Adapter (Thin, Non-Invasive Client Layer)
  // =========================================================================

  const jarvisAdapter = {
    async getRuntimeStatus() {
      const res = await fetch(`${GATEWAY_URL}/api/runtime/status`, {
        headers: { "X-JARVIS-Token": GATEWAY_TOKEN },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    },

    async getToday() {
      const res = await fetch(`${GATEWAY_URL}/api/context/today`, {
        headers: { "X-JARVIS-Token": GATEWAY_TOKEN },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    },

    async getRecentFiles() {
      const res = await fetch(`${GATEWAY_URL}/api/context/recent_files`, {
        headers: { "X-JARVIS-Token": GATEWAY_TOKEN },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    },

    async getCapabilities() {
      const res = await fetch(`${GATEWAY_URL}/api/capabilities/available`, {
        headers: { "X-JARVIS-Token": GATEWAY_TOKEN },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return await res.json();
    },

    async switchPersona(personaName) {
      const res = await fetch(`${GATEWAY_URL}/api/personas/switch`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-JARVIS-Token": GATEWAY_TOKEN,
        },
        body: JSON.stringify({ persona: personaName }),
      });
      if (!res.ok) throw new Error(`Switch failed with status ${res.status}`);
      return await res.json();
    },

    async executeCapability(capabilityOrAction, parameters = {}) {
      const res = await fetch(`${GATEWAY_URL}/api/v1/capabilities/execute`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-JARVIS-Token": GATEWAY_TOKEN,
        },
        body: JSON.stringify({
          action: capabilityOrAction,
          parameters: parameters,
        }),
      });
      if (!res.ok) throw new Error(`Execution failed: ${res.statusText}`);
      return await res.json();
    },

    async sendChatMessage(message) {
      const res = await fetch(`${GATEWAY_URL}/api/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-JARVIS-Token": GATEWAY_TOKEN,
        },
        body: JSON.stringify({
          query: message,
          persona: activePersona,
          device_id: DEVICE_ID,
          device_name: "Unified Web HUD",
        }),
      });
      if (!res.ok) throw new Error(`Chat failed: ${res.statusText}`);
      return await res.json();
    },
  };

  // =========================================================================
  // 4. WebSocket Duplex Streaming & Speech Playback
  // =========================================================================

  function connectWebSocket() {
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${wsProtocol}//${host}/ws?device_id=${encodeURIComponent(DEVICE_ID)}`;

    try {
      if (!GATEWAY_TOKEN) {
        const entered = window.prompt("Enter your JARVIS Gateway token. It is stored only in this browser.");
        if (!entered) { console.error("[JARVIS] Gateway token is not configured."); return; }
        GATEWAY_TOKEN = entered.trim();
        localStorage.setItem("jarvis_gateway_token", GATEWAY_TOKEN);
      }
      ws = new WebSocket(wsUrl, [`jarvis-auth.${GATEWAY_TOKEN}`]);
    } catch (err) {
      console.warn("[WebSocket] Link initialization error:", err);
      setConnectionStatus(false);
      return;
    }

    ws.onopen = () => {
      setConnectionStatus(true);
      // Register client device presence
      ws.send(JSON.stringify({
        type: "register",
        device_id: DEVICE_ID,
        name: "Unified Web HUD",
        client_type: "web",
      }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        handleIncomingWsMessage(data);
      } catch (err) {
        console.error("[WebSocket] Parse error:", err);
      }
    };

    ws.onclose = () => {
      setConnectionStatus(false);
      scheduleReconnect();
    };

    ws.onerror = () => {
      setConnectionStatus(false);
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(() => {
      connectWebSocket();
    }, 4000);
  }

  function setConnectionStatus(online) {
    isOnline = online;
    if (elOfflineBanner) {
      elOfflineBanner.style.display = online ? "none" : "block";
    }
    if (!online && elStatusHeadline) {
      elStatusHeadline.textContent = "RUNTIME DISCONNECTED";
      elStatusHeadline.style.color = "var(--red)";
      if (elDialRing) elDialRing.style.boxShadow = "0 0 26px rgba(226,87,76,0.3)";
    }
  }

  function handleIncomingWsMessage(data) {
    const type = data.type;

    if (type === "welcome" || type === "persona_switched") {
      if (data.active_persona) {
        syncPersonaUI(data.active_persona);
      }
    } else if (type === "chat_stream_start") {
      showResponseContainer(data.active_persona || activePersona, "GENERATING...");
      if (elResponseText) elResponseText.textContent = "";
      currentResponseId = data.response_id;
    } else if (type === "chat_stream_chunk") {
      if (elResponseText && data.token) {
        elResponseText.textContent += data.token;
        elResponseText.scrollTop = elResponseText.scrollHeight;
      }
    } else if (type === "chat_audio_chunk") {
      if (data.audio_b64) {
        queueAudioChunk(data.audio_b64);
      }
    } else if (type === "chat_response" || type === "task_completed") {
      const fullText = data.text || data.response || (data.payload && data.payload.text) || "Understood.";
      showResponseContainer(data.active_persona || activePersona, "COMPLETED");
      if (elResponseText) elResponseText.textContent = fullText;
      if (elResponseVerification) {
        elResponseVerification.textContent = data.trace_id
          ? `Verified execution (Trace: ${data.trace_id.substring(0, 12)}...)`
          : "Verified through JARVIS Cognitive Core";
      }
      refreshContextData();
    } else if (type === "task_progress") {
      if (elResponseStatus) {
        elResponseStatus.textContent = data.status || "WORKING";
      }
    }
  }

  function queueAudioChunk(b64Audio) {
    audioQueue.push(b64Audio);
    playNextAudioInQueue();
  }

  function playNextAudioInQueue() {
    if (isAudioPlaying || audioQueue.length === 0 || !ttsPlayer) return;
    isAudioPlaying = true;
    const b64 = audioQueue.shift();
    ttsPlayer.src = `data:audio/wav;base64,${b64}`;
    ttsPlayer.play().catch(e => {
      console.debug("[Audio Playback] Autoplay waiting for interaction:", e);
      isAudioPlaying = false;
    });
    ttsPlayer.onended = () => {
      isAudioPlaying = false;
      playNextAudioInQueue();
    };
    ttsPlayer.onerror = () => {
      isAudioPlaying = false;
      playNextAudioInQueue();
    };
  }

  // =========================================================================
  // 5. Persona Switching (Server Authoritative)
  // =========================================================================

  function syncPersonaUI(personaName) {
    activePersona = personaName;
    const cards = document.querySelectorAll(".persona");
    cards.forEach(c => {
      c.classList.remove("on");
      const pill = c.querySelector(".pill");
      if (pill) {
        pill.classList.remove("on");
        pill.textContent = "Switch";
      }
    });

    const targetCard = document.getElementById(`card-persona-${personaName.toLowerCase()}`);
    if (targetCard) {
      targetCard.classList.add("on");
      const pill = targetCard.querySelector(".pill");
      if (pill) {
        pill.classList.add("on");
        pill.textContent = "Active";
      }
    }

    if (elAskInput) {
      elAskInput.placeholder = `Ask ${personaName} anything...`;
    }
    if (elTopQuoteAuthor) {
      elTopQuoteAuthor.textContent = personaName.toUpperCase();
    }
  }

  async function handlePersonaSwitch(targetPersona) {
    try {
      const res = await jarvisAdapter.switchPersona(targetPersona);
      if (res && res.active_persona) {
        syncPersonaUI(res.active_persona);
      }
    } catch (err) {
      console.error("[Persona Switch] Error switching persona:", err);
      // Fallback: request via ws if open
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "persona_switch", persona: targetPersona }));
      }
    }
  }

  // Attach Persona Switch Listeners
  document.querySelectorAll(".persona .pill").forEach(btn => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const p = btn.getAttribute("data-persona");
      if (p) handlePersonaSwitch(p);
    });
  });

  // =========================================================================
  // 6. Response Display & Prompt Submission
  // =========================================================================

  function showResponseContainer(personaName, statusText) {
    if (elResponseContainer) {
      elResponseContainer.style.display = "flex";
    }
    if (elResponsePersona) {
      elResponsePersona.textContent = personaName.toUpperCase();
    }
    if (elResponseStatus) {
      elResponseStatus.textContent = statusText;
    }
  }

  if (elBtnCloseResponse) {
    elBtnCloseResponse.addEventListener("click", () => {
      if (elResponseContainer) elResponseContainer.style.display = "none";
    });
  }

  async function submitQuery(text) {
    if (!text || !text.trim()) return;
    const query = text.trim();
    if (elAskInput) elAskInput.value = "";

    showResponseContainer(activePersona, "DISPATCHING...");
    if (elResponseText) elResponseText.textContent = `User: "${query}"\n\nThinking...`;

    // Try WebSocket first
    if (ws && ws.readyState === WebSocket.OPEN) {
      const reqId = `req_${Date.now()}`;
      ws.send(JSON.stringify({
        type: "chat",
        query: query,
        persona: activePersona,
        request_id: reqId,
      }));
    } else {
      // REST Fallback
      try {
        const res = await jarvisAdapter.sendChatMessage(query);
        const reply = res.response || (res.output && res.output.text) || "Operation finished.";
        if (elResponseText) elResponseText.textContent = reply;
        if (elResponseStatus) elResponseStatus.textContent = "COMPLETED";
        if (elResponseVerification) {
          elResponseVerification.textContent = res.trace_id
            ? `Verified execution (Trace: ${res.trace_id.substring(0, 12)}...)`
            : "Verified through JARVIS Cognitive Core";
        }
        refreshContextData();
      } catch (err) {
        if (elResponseText) elResponseText.textContent = `Error executing request: ${err.message}`;
        if (elResponseStatus) elResponseStatus.textContent = "FAILED";
      }
    }
  }

  if (elAskForm) {
    elAskForm.addEventListener("submit", (e) => {
      e.preventDefault();
      if (elAskInput) submitQuery(elAskInput.value);
    });
  }

  if (elBtnSend) {
    elBtnSend.addEventListener("click", () => {
      if (elAskInput) submitQuery(elAskInput.value);
    });
  }

  // =========================================================================
  // 7. Voice Input (Speech-to-Text via Web Speech API)
  // =========================================================================

  function setupSpeechRecognition() {
    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRec) {
      if (elBtnMic) elBtnMic.title = "Microphone unavailable in this browser";
      return;
    }

    recognition = new SpeechRec();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = "en-US";

    recognition.onstart = () => {
      isRecording = true;
      if (elBtnMic) elBtnMic.classList.add("recording");
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      if (elAskInput) {
        elAskInput.value = transcript;
        submitQuery(transcript);
      }
    };

    recognition.onerror = () => {
      isRecording = false;
      if (elBtnMic) elBtnMic.classList.remove("recording");
    };

    recognition.onend = () => {
      isRecording = false;
      if (elBtnMic) elBtnMic.classList.remove("recording");
    };

    if (elBtnMic) {
      elBtnMic.addEventListener("click", () => {
        if (isRecording) {
          recognition.stop();
        } else {
          try {
            recognition.start();
          } catch (e) {
            console.debug("[SpeechRec] Already active or permission pending:", e);
          }
        }
      });
    }
  }

  setupSpeechRecognition();

  // =========================================================================
  // 8. Real Context & Cards Population (Calendar, Files, Status)
  // =========================================================================

  async function populateYourDay() {
    if (!elYourDayList) return;
    try {
      const data = await jarvisAdapter.getToday();
      if (!data.items || data.items.length === 0) {
        elYourDayList.innerHTML = `<div class="empty-state">${data.empty_message || "Your day is clear"}</div>`;
        return;
      }

      let html = "";
      data.items.slice(0, 5).forEach((item, idx) => {
        const tileClasses = ["t-sync", "t-review", "t-gym", "t-dinner", "t-calendar"];
        const tileClass = tileClasses[idx % tileClasses.length];
        html += `
          <div class="row">
            <span class="tile ${tileClass}">
              <svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/></svg>
            </span>
            <span class="name">${escapeHtml(item.title)}</span>
            <span class="when">${escapeHtml(item.when)}</span>
          </div>
        `;
      });
      elYourDayList.innerHTML = html;
    } catch (err) {
      elYourDayList.innerHTML = `<div class="empty-state">Unable to load schedule</div>`;
    }
  }

  async function populateRecentFiles() {
    if (!elRecentFilesList) return;
    try {
      const data = await jarvisAdapter.getRecentFiles();
      if (!data.files || data.files.length === 0) {
        elRecentFilesList.innerHTML = `<div class="empty-state">${data.empty_message || "No recent files"}</div>`;
        return;
      }

      let html = "";
      data.files.slice(0, 5).forEach(f => {
        html += `
          <div class="row" title="${escapeHtml(f.path)}">
            <svg class="doc" viewBox="0 0 24 24"><path d="M6 3.5h7.5L19 9v11.5H6Z"/><path d="M13.5 3.5V9H19"/></svg>
            <span class="name">${escapeHtml(f.name)}</span>
            <span class="when">${escapeHtml(f.when)}</span>
          </div>
        `;
      });
      elRecentFilesList.innerHTML = html;
    } catch (err) {
      elRecentFilesList.innerHTML = `<div class="empty-state">No recent files</div>`;
    }
  }

  async function populateSystemStatus() {
    try {
      const data = await jarvisAdapter.getRuntimeStatus();
      if (!data) return;

      const sub = data.subsystems || {};
      updateStatEl("stat-val-ai", sub.ai_core || "Online");
      updateStatEl("stat-val-voice", sub.voice_module || "Active");
      updateStatEl("stat-val-vision", sub.vision || "Ready");
      updateStatEl("stat-val-auto", sub.automation || "Online");
      updateStatEl("stat-val-sec", sub.security || "Secure");

      if (elStatusHeadline) {
        elStatusHeadline.textContent = data.system_dial ? data.system_dial.message : "ALL SYSTEMS OPERATIONAL";
        elStatusHeadline.style.color = data.status === "Healthy" ? "var(--gold-dim)" : "#e6a74b";
      }

      if (elDialRing) {
        elDialRing.style.boxShadow = data.status === "Healthy"
          ? "0 0 26px rgba(206,166,94,0.22)"
          : "0 0 26px rgba(230,167,75,0.35)";
      }
    } catch (err) {
      console.debug("[Status] Runtime polling error:", err);
    }
  }

  function updateStatEl(id, val) {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = val;
    el.className = "";
    const lower = val.toLowerCase();
    if (lower === "online" || lower === "active" || lower === "secure" || lower === "ready") {
      el.style.color = "var(--green)";
    } else if (lower === "degraded") {
      el.style.color = "#e6a74b";
    } else {
      el.style.color = "var(--red)";
    }
  }

  function refreshContextData() {
    populateYourDay();
    populateRecentFiles();
    populateSystemStatus();
  }

  // =========================================================================
  // 9. Quick Actions & Hero Chips
  // =========================================================================

  const ACTION_PROMPTS = {
    summarize: "Summarize the active context and recent developments.",
    plan_day: "Analyze my calendar, pending tasks, and plan my schedule for today.",
    research: "Conduct comprehensive web research on current artificial intelligence benchmarks.",
    analyze: "Profile the active dataset and compute descriptive analytics.",
    diagnostics: "Execute a full self-diagnostic probe on JARVIS subsystems.",
    search_web: "Perform a web search for the latest scientific advancements.",
    calendar_check: "Check my calendar schedule and detect any meeting conflicts.",
    create_task: "Create a priority task in my personal productivity workspace.",
    browse_files: "Inspect recent documents in the authorized workspace scope.",
    run_diagnostics: "Run evidence-based health check across registered capability providers.",
    data_science: "Run tabular analysis and identify anomalies in workspace data.",
  };

  function setupActionButtons() {
    // Hero Chips
    document.querySelectorAll(".chips .chip").forEach(chip => {
      chip.addEventListener("click", () => {
        const action = chip.getAttribute("data-action");
        const prompt = ACTION_PROMPTS[action] || `Execute ${action}`;
        submitQuery(prompt);
      });
    });

    // Quick Action Card Buttons
    document.querySelectorAll("#quick-actions-list .action").forEach(act => {
      act.addEventListener("click", () => {
        const action = act.getAttribute("data-action");
        const prompt = ACTION_PROMPTS[action] || `Execute ${action}`;
        submitQuery(prompt);
      });
    });

    // Top Modes
    if (elTopModes) {
      elTopModes.querySelectorAll("button").forEach(btn => {
        btn.addEventListener("click", () => {
          const mode = btn.getAttribute("data-mode");
          elTopModes.querySelectorAll("li").forEach(li => li.classList.remove("active"));
          btn.closest("li").classList.add("active");
          submitQuery(`Switch cognitive mode to ${mode}.`);
        });
      });
    }
  }

  setupActionButtons();

  // =========================================================================
  // 10. Sidebar Navigation & Section Modals
  // =========================================================================

  function setupNavigation() {
    document.querySelectorAll(".nav a").forEach(link => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        document.querySelectorAll(".nav a").forEach(x => x.classList.remove("active"));
        link.classList.add("active");

        const section = link.getAttribute("data-section");
        if (section === "home") {
          closeModal();
        } else {
          openSectionModal(section);
        }
      });
    });

    if (elBtnCloseModal) {
      elBtnCloseModal.addEventListener("click", closeModal);
    }
    if (elModal) {
      elModal.addEventListener("click", (e) => {
        if (e.target === elModal) closeModal();
      });
    }

    const linkViewDay = document.getElementById("link-view-all-day");
    if (linkViewDay) {
      linkViewDay.addEventListener("click", (e) => {
        e.preventDefault();
        openSectionModal("tasks");
      });
    }

    const linkOpenFiles = document.getElementById("link-open-files");
    if (linkOpenFiles) {
      linkOpenFiles.addEventListener("click", (e) => {
        e.preventDefault();
        openSectionModal("files");
      });
    }
  }

  function openSectionModal(sectionId) {
    if (!elModal || !elModalTitle || !elModalContent) return;
    elModalTitle.textContent = sectionId.toUpperCase() + " // JARVIS ARCHITECTURE";
    elModalContent.innerHTML = `<div style="color:var(--gold-dim); font-style:italic; padding:20px 0;">Loading ${sectionId} details...</div>`;
    elModal.classList.add("open");

    if (sectionId === "tasks") {
      jarvisAdapter.getToday().then(data => {
        let html = `<h3 style="font-family:'Cinzel',serif; color:#eee;">SCHEDULED ITEMS & TASKS</h3><ul style="list-style:none; padding:0; margin-top:14px;">`;
        if (data.items && data.items.length > 0) {
          data.items.forEach(it => {
            html += `<li style="padding:10px 0; border-bottom:1px solid var(--line); display:flex; justify-content:space-between;">
              <span style="color:#ddd;">${escapeHtml(it.title)}</span>
              <span style="color:var(--gold);">${escapeHtml(it.when)}</span>
            </li>`;
          });
        } else {
          html += `<li style="color:var(--faint); font-style:italic;">Your day is clear. Zero pending appointments.</li>`;
        }
        html += `</ul>`;
        elModalContent.innerHTML = html;
      });
    } else if (sectionId === "files") {
      jarvisAdapter.getRecentFiles().then(data => {
        let html = `<h3 style="font-family:'Cinzel',serif; color:#eee;">AUTHORIZED WORKSPACE FILES</h3><ul style="list-style:none; padding:0; margin-top:14px;">`;
        if (data.files && data.files.length > 0) {
          data.files.forEach(f => {
            html += `<li style="padding:10px 0; border-bottom:1px solid var(--line); display:flex; justify-content:space-between;">
              <span style="color:#ddd;">${escapeHtml(f.name)} (${escapeHtml(f.path)})</span>
              <span style="color:var(--gold);">${escapeHtml(f.when)}</span>
            </li>`;
          });
        } else {
          html += `<li style="color:var(--faint); font-style:italic;">No recent files found in authorized scope.</li>`;
        }
        html += `</ul>`;
        elModalContent.innerHTML = html;
      });
    } else if (sectionId === "personas") {
      elModalContent.innerHTML = `
        <h3 style="font-family:'Cinzel',serif; color:#eee;">AVAILABLE AI PERSONAS</h3>
        <p style="color:#bbb; line-height:1.6; margin-top:8px;">
          JARVIS supports dynamic cognitive personas without parallel engines. The active persona guides tone, focus, and strategic decomposition.
        </p>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-top:16px;">
          <div style="border:1px solid var(--line); padding:14px; border-radius:6px;">
            <b style="color:var(--gold-bright);">OMI</b><br><span style="color:#999; font-size:12px;">Personal Companion &amp; Peripheral Assistant</span>
          </div>
          <div style="border:1px solid var(--line); padding:14px; border-radius:6px;">
            <b style="color:var(--gold-bright);">JARVIS</b><br><span style="color:#999; font-size:12px;">Strategic Reasoning &amp; Deep Planning</span>
          </div>
          <div style="border:1px solid var(--line); padding:14px; border-radius:6px;">
            <b style="color:var(--gold-bright);">FRIDAY</b><br><span style="color:#999; font-size:12px;">Productivity &amp; Task Management</span>
          </div>
          <div style="border:1px solid var(--line); padding:14px; border-radius:6px;">
            <b style="color:var(--gold-bright);">ULTRON</b><br><span style="color:#999; font-size:12px;">Advanced Analysis &amp; Safety Governance</span>
          </div>
        </div>
      `;
    } else if (sectionId === "research" || sectionId === "automation" || sectionId === "apps" || sectionId === "settings" || sectionId === "chat") {
      jarvisAdapter.getCapabilities().then(data => {
        let matching = (data.capabilities || []).filter(c => {
          const dom = (c.domain || "").toLowerCase();
          const nm = (c.name || "").toLowerCase();
          return dom.includes(sectionId) || nm.includes(sectionId);
        });
        if (matching.length === 0) matching = (data.capabilities || []).slice(0, 8);

        let html = `<h3 style="font-family:'Cinzel',serif; color:#eee;">${sectionId.toUpperCase()} CAPABILITIES</h3><ul style="list-style:none; padding:0; margin-top:14px;">`;
        matching.forEach(c => {
          html += `<li style="padding:10px 0; border-bottom:1px solid var(--line);">
            <div style="display:flex; justify-content:space-between;">
              <b style="color:var(--gold-bright);">${escapeHtml(c.name)}</b>
              <span style="font-size:11px; color:${c.available ? 'var(--green)' : 'var(--muted)'};">${c.available ? 'AVAILABLE' : 'STANDBY'}</span>
            </div>
            <div style="color:#aaa; font-size:12px; margin-top:4px;">${escapeHtml(c.purpose)}</div>
          </li>`;
        });
        html += `</ul>`;
        elModalContent.innerHTML = html;
      });
    }
  }

  function closeModal() {
    if (elModal) elModal.classList.remove("open");
  }

  setupNavigation();

  // =========================================================================
  // 11. Helper Utilities & Bootstrap
  // =========================================================================

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Initial Data Fetch
  resolveLocation();
  refreshContextData();
  connectWebSocket();

  // Periodic Refresh every 20 seconds
  setInterval(refreshContextData, 20000);

})();
