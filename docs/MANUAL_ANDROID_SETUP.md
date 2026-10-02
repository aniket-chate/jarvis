# JARVIS Manual Android + PC Setup

This guide connects the Android JARVIS client to the Windows JARVIS brain over a LAN or Tailscale.

## 1. PC prerequisites

Install:
- Python 3.11/3.12
- Ollama
- Git
- Tailscale (only needed for remote/private-overlay access)

From the repository:

```powershell
cd D:\assignment\JARVIS
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create the local environment file:

```powershell
Copy-Item .env.example .env
```

### Required for an authenticated mobile connection

Set a strong random `GATEWAY_AUTH_TOKEN` in `.env`. It must be at least 32 characters.

PowerShell example:

```powershell
$token = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
Add-Content .env "GATEWAY_AUTH_TOKEN=$token"
```

If you already have a `GATEWAY_AUTH_TOKEN`, do not replace it; the Android app must use the same value.

### Local LLM

The current configuration targets:
- Core: `qwen2.5:3b`
- Vision: `moondream:latest`

Install the configured models if they are not already present:

```powershell
ollama pull qwen2.5:3b
ollama pull moondream:latest
```

The server can attempt to start Ollama automatically, but the model weights still need to exist.

## 2. Start the PC brain

For Android over LAN or Tailscale, bind the server to a reachable interface:

```powershell
python -m uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Keep this terminal running.

Check the server locally:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health
```

A healthy response requires Ollama to be available; a degraded response means the HTTP server is alive but one or more local model dependencies are unavailable.

## 3. Windows firewall

If Android cannot connect over the LAN, allow inbound TCP port 8000 for the JARVIS server on the private network.

Do not expose port 8000 directly to the public Internet.

## 4. LAN connection

Find the PC's private IPv4 address:

```powershell
ipconfig
```

Use the PC's LAN address, for example:

```
http://192.168.x.x:8000
```

Do not use `10.0.2.2` on a physical phone. That address is for the Android emulator to reach the host PC.

## 5. Tailscale connection

Install Tailscale on both the PC and Android phone and sign in to the same tailnet.

On the PC:

```powershell
tailscale ip -4
```

Use the returned Tailscale IP:

```
http://100.x.y.z:8000
```

If MagicDNS is enabled, the PC hostname can be used instead.

Tailscale supplies private network connectivity; JARVIS still needs its own FastAPI/WebSocket service running on port 8000.

## 6. Build and install the Android client

From Windows:

```powershell
cd D:\assignment\JARVIS\client\android
.\\gradlew.bat assembleDebug
```

Install the generated debug APK on the phone. With USB debugging enabled:

```powershell
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

If using Android Studio, open `client/android` and run the `app` configuration.

## 7. First Android launch

Open JARVIS and grant:
- Microphone permission, for voice input.
- Notification permission, so the persistent background connection notification can be shown.
- Accessibility permission, if you want JARVIS to observe and perform supported UI actions.
- Assistant role, if you want JARVIS to be invoked as the Android default assistant.

The app generates its own Android device ID and derives a runtime device name from the phone model.

## 8. Configure the Android client

Open JARVIS Settings and enter:

**Backend URL**
- LAN: `http://PC_LAN_IP:8000`
- Tailscale: `http://PC_TAILSCALE_IP:8000`

**User ID**
- Choose a stable local identifier for this installation, such as `default_user`.

**Device ID**
- Keep the generated value unless you have a deliberate device identity scheme.

**Device name**
- Keep the generated phone model name or choose a descriptive name.

**Auth token**
- Paste exactly the same `GATEWAY_AUTH_TOKEN` used by the PC.

The auth token is stored through the Android Keystore-backed secure field vault.

## 9. Start the connection

After saving settings:
1. Return to the main JARVIS screen.
2. Start/reconnect JARVIS if required.
3. Confirm the status changes through Connecting -> Authenticated.
4. Keep the persistent JARVIS Device Connection notification enabled.

The Android app uses one repository/WebSocket connection rather than creating a separate connection for every request.

## 10. First manual smoke test

Run these in order:

1. `hello`
2. `stop`
3. A harmless information request.
4. Press the voice button and say `stop`.
5. If Accessibility is enabled, ask for a supported UI observation/action.
6. Test a safe phone action such as opening an allowlisted app.

For device actions, JARVIS should only report successful execution after the Android node returns a real skill result.

## 11. Default assistant

In JARVIS Settings:
1. Tap **Set JARVIS as Default Assistant**.
2. Select JARVIS in Android's assistant-role picker.
3. Invoke the system assistant gesture/button.
4. Confirm the JARVIS assistant surface appears.
5. Use **Talk to JARVIS**.

Android keeps the selected VoiceInteractionService available for assistant interactions.

## 12. What requires API keys?

### Required
- `GATEWAY_AUTH_TOKEN`: yes, for authenticated API/WebSocket access.
- Ollama models: yes, but these are local model weights, not API keys.

### Optional
- `TAVILY_API_KEY` or `BRAVE_API_KEY`: web search.
- `OPENAI_API_KEY`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY`: cloud LLM fallback.
- Google OAuth client ID/secret: Gmail and Calendar.
- `WHATSAPP_BUSINESS_API_KEY`: official WhatsApp Business integration.
- `HOME_ASSISTANT_TOKEN`: Home Assistant.
- `TAILSCALE_AUTH_KEY`: optional automation/provisioning; it is not required just to use the Tailscale apps interactively.

## 13. Voice/model dependencies

The Android client uses Android's SpeechRecognizer for speech-to-text, so it does not require a separate JARVIS cloud speech API key.

The PC voice stack can use Piper TTS and falls back to pyttsx3 when the configured Piper voice model is unavailable. Full neural Piper voices require the corresponding voice model files under `models/piper/`.

Wake-word detection also depends on the configured wake-word model assets under `models/wakewords/`.

## 14. Troubleshooting

### Android says Unauthorized
- Verify the PC `GATEWAY_AUTH_TOKEN` is at least 32 characters.
- Paste the exact same token into Android Settings.
- Restart the PC server after changing `.env`.

### Android stays Connecting
- Confirm the PC server is running with `--host 0.0.0.0`.
- Confirm the Android backend URL uses the PC's LAN/Tailscale address.
- Check Windows Firewall.
- On Tailscale, verify both devices are in the same tailnet and reachable.

### Emulator works but physical phone does not
Replace `http://10.0.2.2:8000` with the PC's LAN or Tailscale address.

### Server is Degraded
Check Ollama:

```powershell
ollama list
ollama run qwen2.5:3b
```

Then retry the JARVIS health endpoint.

## 15. Security rules

- Never commit `.env`.
- Never put the gateway token in the WebSocket URL.
- Do not expose port 8000 directly to the Internet.
- Prefer LAN for home use and Tailscale for remote/private connectivity.
- Keep Android accessibility actions and sensitive-field protections enabled.
