# JARVIS First-50 Manual Setup & Configuration Requirements

This document provides the exhaustive, audited inventory of all manual configuration requirements, external credentials, and hardware devices required for running JARVIS Capabilities 1–50.

> [!IMPORTANT]
> **Security Guarantee**: Zero secret values, raw API keys, or credentials are contained in this document. All sensitive tokens are verified by status ('Configured', 'Missing', 'Optional') only.

## 1. Summary of Configuration Status

- **Total Requirements Cataloged**: 18
- **Mandatory Core Requirements**: 4
- **Optional Cloud/External Services**: 10
- **Hardware-Dependent Interfaces**: 4

## 2. Exhaustive Requirements Matrix

| Requirement Name | Category | Nature | Used by Capabilities | Config Location | Status |
|---|---|---|---|---|---|
| `GEMINI_API_KEY` | API key | OPTIONAL | 10, 31, 32, 36, 40, 41... | `.env` | **Configured** |
| `TAVILY_API_KEY` | API key | OPTIONAL | 31, 32 | `.env` | **Configured** |
| `BRAVE_API_KEY` | API key | OPTIONAL | 31, 32 | `.env` | **Missing** |
| `OPENAI_API_KEY` | API key | OPTIONAL | 10, 36, 40, 46 | `.env` | **Missing** |
| `GROQ_API_KEY` | API key | OPTIONAL | 10, 36, 40 | `.env` | **Missing** |
| `GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET` | OAuth/account | OPTIONAL | 18, 19 | `.env or credentials/credentials.json` | **Configured** |
| `HOME_ASSISTANT_TOKEN` | smart-home integration | OPTIONAL | 22 | `.env` | **Missing** |
| `WHATSAPP_BUSINESS_API_KEY` | communication integration | OPTIONAL | 19, 21 | `.env` | **Missing** |
| `TAILSCALE_AUTH_KEY` | network | OPTIONAL | 48 | `.env` | **Configured** |
| `GATEWAY_AUTH_TOKEN` | API token | REQUIRED | 48 | `.env` | **Configured** |
| `OLLAMA_LOCAL_ENDPOINT` | local model | REQUIRED | 1, 2, 4, 10, 31, 32... | `Local Ollama daemon running on http://127.0.0.1:11434` | **Optional** |
| `WAKE_WORD_ONNX_MODELS` | model file | OPTIONAL | 1, 2 | `models/wake_words/ (jarvis.onnx)` | **Optional** |
| `MICROPHONE_INPUT_DEVICE` | microphone | HARDWARE-DEPENDENT | 1, 2 | `Windows Sound Settings (Default Audio Input)` | **Hardware-Dependent** |
| `WEBCAM_VIDEO_DEVICE` | camera | HARDWARE-DEPENDENT | 3, 4, 30 | `Windows Device Manager (Cameras / Imaging Devices)` | **Hardware-Dependent** |
| `ANDROID_DEVICE_ADB` | Android device | HARDWARE-DEPENDENT | 23, 24, 25, 26, 27, 28... | `Android Developer Options -> USB Debugging + ADB Daemon on PC` | **Hardware-Dependent** |
| `WINDOWS_ADMIN_AND_UI_PERMISSIONS` | Windows permission | REQUIRED | 11, 12, 13, 14, 15, 16... | `Windows User Account Control & Accessibility` | **Configured** |
| `PHYSICAL_ROBOTICS_SERIAL_PORT` | physical hardware | HARDWARE-DEPENDENT | 45 | `Serial COM Port / TCP Endpoint (config.yaml: hardware.robotics)` | **Hardware-Dependent** |
| `DATABASE_STORAGE_PATH` | database | REQUIRED | 5, 6, 7, 8, 9, 39... | `Local SQLite database at data/jarvis_memory.db` | **Configured** |

## 3. Provider Configuration Audit (Phase 3A)

| Provider Name | Capabilities | Credential Required | Fallback / Local Alternative | Availability |
|---|---|---|---|---|
| **PerceptionProvider (Voice/Audio)** | 1, 2 | None (Audio input device / local whisper) | Local PyAudio buffer / PyTTSx3 | `ACTIVE (Software fallback available)` |
| **VisionProvider (Webcam/Screen)** | 3, 4, 30 | None (Local OpenCV / Screen Capture) | Pillow / MSS Desktop Capture | `ACTIVE (Screen capture active, webcam hardware-dependent)` |
| **UnifiedMemoryProvider (7-Tier Memory)** | 5, 6, 7, 8, 9 | None (Local SQLite / In-Memory cache) | Local SQLite + In-Memory Working Set | `ACTIVE` |
| **CognitivePlanningProvider (Local LLM / Cloud Fallback)** | 10, 36, 40, 41, 50 | Ollama local daemon or GEMINI_API_KEY / OPENAI_API_KEY | Local Ollama (mistral/llama3.2) or deterministic template engine | `ACTIVE (Local deterministic rule engine always active)` |
| **DesktopControlProvider (OS / App / Browser)** | 11, 12, 13, 14, 15, 16, 17, 33, 34, 35 | None (Windows Accessibility / Win32 API) | subprocess / pywin32 / playwright | `ACTIVE` |
| **PersonalProductivityProvider (Calendar & Email)** | 18, 19 | Google OAuth Client Credentials or Local Calendar DB | Local SQLite Calendar and local Drafts buffer | `ACTIVE (Local calendar fallback active; Google cloud sync optional)` |
| **SocialCommunicationProvider (WhatsApp / Contacts)** | 20, 21 | WHATSAPP_BUSINESS_API_KEY or Local Contacts DB | Local SQLite Contact Book + Desktop Web Automation | `ACTIVE (Local contact book active)` |
| **SmartHomeIoTProvider (Home Assistant)** | 22 | HOME_ASSISTANT_TOKEN | Virtual IoT Device Hub (In-Memory switch simulator) | `ACTIVE (Virtual device hub fallback active)` |
| **AndroidBridgeProvider (ADB / scrcpy)** | 23, 24, 25, 26, 27, 28, 29, 30 | None (USB Debugging authorization on target device) | Virtual Android Device State Machine | `ACTIVE (Virtual state machine verified; physical device hardware-dependent)` |
| **WebResearchKnowledgeProvider (Search & Scraping)** | 31, 32, 37, 38 | TAVILY_API_KEY or BRAVE_API_KEY or Local DuckDuckGo parser | Local Knowledge Index & Offline Vector Document Store | `ACTIVE (Local knowledge base active; cloud search fallback optional)` |
| **AutonomousAgencyProvider (Goal & Task Planning)** | 39, 40, 41, 42, 43, 44 | None (Internal Cognitive Engine) | Deterministic DAG Execution Engine | `ACTIVE` |
| **PhysicalRoboticsProvider (Serial/TCP Actuation)** | 45 | None (Serial COM port / Network socket) | Virtual Kinematic Simulator (PyBullet / In-Memory Kinematics) | `ACTIVE (Software kinematic simulator active; physical robot arm hardware-dependent)` |
| **DataScienceAnalyticsProvider** | 46 | None (pandas, numpy, scipy, scikit-learn) | Local Scipy / Scikit-Learn Engine | `ACTIVE` |
| **SimulationPredictionProvider** | 47 | None (SciPy ODE / Monte Carlo engine) | Local Monte Carlo & State Space Simulator | `ACTIVE` |
| **SecurityIdentityPolicyProvider** | 48 | GATEWAY_AUTH_TOKEN (Optional TAILSCALE_AUTH_KEY) | Local Cryptographic Token Validator & Policy Kernel | `ACTIVE` |
| **VerificationSelfDiagnosticsProvider** | 49 | None (Internal Subsystem Probes) | Local Subsystem Heartbeat Monitor | `ACTIVE` |
| **CapabilityEvolutionProvider** | 50 | None (Internal AST & Sandbox Validator) | Sandboxed Contract Generation Engine | `ACTIVE` |

## 4. Hardware and Physical Device Audit (Phase 3B)

The following capabilities require real hardware devices for physical deployment, but support graceful offline software simulation for automated test suites:

1. **Android Phone via ADB** (Capabilities 23–30):
   - *Physical*: Requires Android device with USB Debugging enabled, connected to PC host.
   - *Software-Verifiable*: Tested via `VirtualAndroidNode` state machine.

2. **Microphone & Camera** (Capabilities 1–4):
   - *Physical*: Requires USB/integrated microphone and webcam.
   - *Software-Verifiable*: Tested via `SimulatedAudioBufferProvider` and synthetic numpy image arrays.

3. **Physical Robotics Actuator** (Capability 45):
   - *Physical*: Requires serial port (COM/tty) or IP socket to robot controller.
   - *Software-Verifiable*: Tested via `VirtualKinematicSimulator` with mathematical inverse kinematics verification.

4. **Smart Home Hub** (Capability 22):
   - *Physical*: Requires local Home Assistant server with Long-Lived Access Token.
   - *Software-Verifiable*: Tested via `VirtualIoTDeviceHub` local state register.

