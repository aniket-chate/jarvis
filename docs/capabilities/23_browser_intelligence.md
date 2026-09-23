# Capability 23: Browser Intelligence

**Capability ID:** `23_browser_intelligence`  
**Classification:** `EXISTING`  
**Safety Classification:** `MODIFYING`  
**Domain:** `browser`  
**Primary Provider:** `provider.browser.chrome_cdp`  
**Fallback Provider:** `provider.browser.playwright`  

---

## 1. Capability Purpose & Scope
Provides real-world web browser automation over Google Chrome via the Chrome DevTools Protocol (CDP port 9222). Replaces blind headless simulations with live browser automation capable of YouTube playback, tab switching, form filling, and DOM inspection.

---

## 2. Supported Operations
- `browser.playback`: Searches and plays media on YouTube via Real Chrome CDP.
- `browser.media_control`: Pauses, resumes, or mutes active browser media player.
- `browser.tab_control`: Manages, enumerates, and closes active Chrome tabs.
- `browser.navigate`: Navigates to specified web URLs.
- `browser.search`: Executes chained web searches across search engines.
- `browser.dom_click` & `browser.dom_type`: Interacts with live DOM elements.

---

## 3. Required Context & World Model State
- **Active Chrome CDP Tab:** Current tab ID, title, and URL tracked in `WorldModel.state.active_browser`.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/browser_provider.py` (`ChromeCDPBrowserProvider`), backed by `agents/browser_automation_agent.py`.
- **Chrome CDP Integration:** Connects to port 9222 with automatic retry and user profile synchronization.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` for playback/search; `Level 1: MODIFYING` for tab closure.
- **Verification Strategy:** Direct queries to Chrome CDP `/json` endpoint confirm tab URL, title, and presence.
