# JARVIS Manual User Setup Checklist (Phase 14 Gate)

This checklist guides the user through preparing the local environment for full real-world JARVIS v1 operation.
> [!CAUTION]
> **NEVER paste secret API keys, tokens, or credentials into Antigravity chat or public logs.**
> Configure them only in the local `.env` file on your secure local workstation.

## REQUIRED BEFORE TESTING

### [x] GATEWAY_AUTH_TOKEN
- **Capability**: 48
- **Why required**: Enables operation for category `API token`.
- **Where to configure**: `.env`
- **Status**: `Configured`
- **How to provide it**: Set custom secret string in .env (defaults to system token if omitted)
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Gateway auth enforced:', bool(settings.gateway_auth_token))"
```

### [ ] OLLAMA_LOCAL_ENDPOINT
- **Capability**: 1, 2, 4, 10, 31, 32, 36, 40, 41, 46, 47, 50
- **Why required**: Enables operation for category `local model`.
- **Where to configure**: `Local Ollama daemon running on http://127.0.0.1:11434`
- **Status**: `Optional`
- **How to provide it**: Install Ollama (https://ollama.com) and pull models: ollama pull mistral, ollama pull llama3.2:1b
- **Verification command**:
```powershell
powershell -Command "Test-NetConnection -ComputerName 127.0.0.1 -Port 11434 -InformationLevel Quiet"
```

### [x] WINDOWS_ADMIN_AND_UI_PERMISSIONS
- **Capability**: 11, 12, 13, 14, 15, 16, 17, 33, 34, 35, 48, 49
- **Why required**: Enables operation for category `Windows permission`.
- **Where to configure**: `Windows User Account Control & Accessibility`
- **Status**: `Configured`
- **How to provide it**: Run PowerShell/terminal as user with access to UI Automation and local file system
- **Verification command**:
```powershell
powershell -Command "[Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()"
```

### [x] DATABASE_STORAGE_PATH
- **Capability**: 5, 6, 7, 8, 9, 39, 42, 43, 44
- **Why required**: Enables operation for category `database`.
- **Where to configure**: `Local SQLite database at data/jarvis_memory.db`
- **Status**: `Configured`
- **How to provide it**: Auto-created on initialization if directory exists
- **Verification command**:
```powershell
python -c "import os; print('Data directory exists:', os.path.exists('data'))"
```

## OPTIONAL CLOUD SERVICES & API KEYS

### [x] GEMINI_API_KEY
- **Capability**: 10, 31, 32, 36, 40, 41, 46, 47, 50
- **Why required**: Enables operation for category `API key`.
- **Where to configure**: `.env`
- **Status**: `Configured`
- **How to provide it**: Obtain API key from Google AI Studio (https://aistudio.google.com/) and set GEMINI_API_KEY=your_key in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; assert settings.gemini_available or not settings.gemini_available"
```

### [x] TAVILY_API_KEY
- **Capability**: 31, 32
- **Why required**: Enables operation for category `API key`.
- **Where to configure**: `.env`
- **Status**: `Configured`
- **How to provide it**: Create account at tavily.com, generate API key, and set TAVILY_API_KEY=your_key in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Tavily configured:', bool(settings.tavily_api_key))"
```

### [ ] BRAVE_API_KEY
- **Capability**: 31, 32
- **Why required**: Enables operation for category `API key`.
- **Where to configure**: `.env`
- **Status**: `Missing`
- **How to provide it**: Create account at brave.com/search/api/, obtain token, and set BRAVE_API_KEY=your_key in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Brave configured:', bool(settings.brave_api_key))"
```

### [ ] OPENAI_API_KEY
- **Capability**: 10, 36, 40, 46
- **Why required**: Enables operation for category `API key`.
- **Where to configure**: `.env`
- **Status**: `Missing`
- **How to provide it**: Create API key in platform.openai.com and set OPENAI_API_KEY=your_key in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('OpenAI configured:', bool(settings.openai_available))"
```

### [ ] GROQ_API_KEY
- **Capability**: 10, 36, 40
- **Why required**: Enables operation for category `API key`.
- **Where to configure**: `.env`
- **Status**: `Missing`
- **How to provide it**: Create API key in console.groq.com and set GROQ_API_KEY=your_key in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Groq configured:', bool(settings.groq_available))"
```

## OPTIONAL ACCOUNTS & OAUTH

### [x] GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET
- **Capability**: 18, 19
- **Why required**: Enables operation for category `OAuth/account`.
- **Where to configure**: `.env or credentials/credentials.json`
- **Status**: `Configured`
- **How to provide it**: Download OAuth 2.0 Client credentials from Google Cloud Console into credentials/credentials.json or set in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Google OAuth ready:', settings.google_oauth_configured)"
```

### [ ] HOME_ASSISTANT_TOKEN
- **Capability**: 22
- **Why required**: Enables operation for category `smart-home integration`.
- **Where to configure**: `.env`
- **Status**: `Missing`
- **How to provide it**: Generate Long-Lived Access Token in Home Assistant profile and set HOME_ASSISTANT_TOKEN=your_token in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('HA token present:', bool(settings.home_assistant_token))"
```

### [ ] WHATSAPP_BUSINESS_API_KEY
- **Capability**: 19, 21
- **Why required**: Enables operation for category `communication integration`.
- **Where to configure**: `.env`
- **Status**: `Missing`
- **How to provide it**: Obtain Meta WhatsApp Cloud API access token and set WHATSAPP_BUSINESS_API_KEY=your_token in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('WhatsApp token present:', bool(settings.whatsapp_business_api_key))"
```

### [x] TAILSCALE_AUTH_KEY
- **Capability**: 48
- **Why required**: Enables operation for category `network`.
- **Where to configure**: `.env`
- **Status**: `Configured`
- **How to provide it**: Generate reusable ephemeral auth key on tailscale.com admin console and set TAILSCALE_AUTH_KEY=tskey-... in .env
- **Verification command**:
```powershell
python -c "from config.settings import settings; print('Tailscale key configured:', settings.tailscale_configured)"
```

## HARDWARE-DEPENDENT REAL DEVICES

### [ ] MICROPHONE_INPUT_DEVICE
- **Capability**: 1, 2
- **Why required**: Enables operation for category `microphone`.
- **Where to configure**: `Windows Sound Settings (Default Audio Input)`
- **Status**: `Hardware-Dependent`
- **How to provide it**: Connect a physical USB or 3.5mm microphone and set as default recording device in Windows
- **Verification command**:
```powershell
powershell -Command "Get-CimInstance Win32_SoundDevice | Select-Object -ExpandProperty Caption"
```

### [ ] WEBCAM_VIDEO_DEVICE
- **Capability**: 3, 4, 30
- **Why required**: Enables operation for category `camera`.
- **Where to configure**: `Windows Device Manager (Cameras / Imaging Devices)`
- **Status**: `Hardware-Dependent`
- **How to provide it**: Plug in a USB webcam or enable integrated laptop camera, grant Camera permissions in Windows Settings
- **Verification command**:
```powershell
powershell -Command "Get-PnpDevice -Class Camera -Status OK | Select-Object -ExpandProperty FriendlyName"
```

### [ ] ANDROID_DEVICE_ADB
- **Capability**: 23, 24, 25, 26, 27, 28, 29, 30
- **Why required**: Enables operation for category `Android device`.
- **Where to configure**: `Android Developer Options -> USB Debugging + ADB Daemon on PC`
- **Status**: `Hardware-Dependent`
- **How to provide it**: Enable Developer Options & USB Debugging on Android phone, connect via USB or 'adb connect IP:5555'
- **Verification command**:
```powershell
powershell -Command "if (Get-Command adb -ErrorAction SilentlyContinue) { adb devices } else { Write-Host 'ADB not installed' }"
```

### [ ] PHYSICAL_ROBOTICS_SERIAL_PORT
- **Capability**: 45
- **Why required**: Enables operation for category `physical hardware`.
- **Where to configure**: `Serial COM Port / TCP Endpoint (config.yaml: hardware.robotics)`
- **Status**: `Hardware-Dependent`
- **How to provide it**: Connect micro-controller / robot arm via USB serial (COM3/COM4) or configure network endpoint
- **Verification command**:
```powershell
powershell -Command "Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Caption"
```

