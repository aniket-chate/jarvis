# Secure Remote Access via Tailscale (JARVIS Layer 6 Mesh)

This guide documents how the JARVIS Device Gateway is reached from any mobile device (Android/iOS) anywhere in the world using Tailscale, with zero open router ports, zero paid cloud hosting, and strict cryptographic authentication.

---

## 1. Network Architecture

```
+-------------------------------------------------------------+
|                      TAILSCALE MESH                         |
|                                                             |
|   [ Mobile Phone ]                     [ Host PC ]                 |
|   Anywhere on 4G/5G / WiFi            RTX 2050 (Ollama/VLM) |
|   Tailscale IP: <DEVICE_TAILSCALE_IP>     Tailscale IP: <JARVIS_TAILSCALE_IP>
|        |                                    |               |
|        +========= WireGuard Tunnel ========+               |
|                 (Encrypted, Peer-to-Peer)                  |
|                                             |               |
|                                    FastAPI Gateway:8000     |
|                                    - Auth Token Enforced    |
|                                    - Mobile Thin Client UI  |
|                                    - WebSocket Duplex       |
+-------------------------------------------------------------+
```

- **Host Tailscale IP:** `<JARVIS_TAILSCALE_IP>`
- **Port:** `8000` (Bound to `0.0.0.0` to accept both LAN and Tailscale connections)
- **Encryption:** Automatic peer-to-peer WireGuard noise protocol.

---

## 2. Setting Up Your Mobile Phone

1. **Install Tailscale**:
   - Android: Download from Google Play Store.
   - iOS: Download from Apple App Store.
2. **Log In**:
   - Log into Tailscale using the same account used on the PC (`<TAILSCALE_ACCOUNT>`).
   - Confirm the phone appears in your Tailscale machine list.
3. **Open JARVIS Mobile Thin Client**:
   - Open your mobile browser (Chrome / Safari / Firefox).
   - Navigate to:
     ```
     http://<JARVIS_TAILSCALE_IP>:8000/
     ```
   - When prompted by the client, enter `GATEWAY_AUTH_TOKEN`; the client stores it locally and uses the supported authenticated transport.
  - *Tip:* Add to Home Screen to use it like a native full-screen app.

---

## 3. Security & Authentication

- **Never Open or Unauthenticated**:
  Even though Tailscale is a private overlay network, the Gateway requires `GATEWAY_AUTH_TOKEN` (`<GATEWAY_AUTH_TOKEN>`) on every request.
  - HTTP Requests: `X-JARVIS-Token` header.
  - WebSocket Connections: `jarvis-auth.<GATEWAY_AUTH_TOKEN>` subprotocol.
  - Unauthorized requests are rejected immediately with `HTTP 401 Unauthorized` or WebSocket close code `4401`.

---

## 4. Features on Mobile

1. **Voice Input**:
   - Tap the microphone button (🎙️) to speak. Web Speech API transcribes speech into text in Indian English (`en-IN`) and sends it to the Gateway.
2. **Text Input**:
   - Type commands or questions.
3. **Camera Vision**:
   - Tap the camera button (📷) to snap a picture or upload from gallery. The raw image is sent directly to the PC where Moondream 1.6B VLM analyzes it and streams the answer back.
4. **Cross-Device Casting**:
   - Say a media command that names the desired content and destination. The PC dispatches media according to the enabled casting capability.
   - Say: *"Play on PC"*. The media is routed to the PC's speakers and browser.
