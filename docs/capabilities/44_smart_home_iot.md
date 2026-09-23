# Capability 44 — Smart Home / IoT

## 1. Overview & Architecture

Capability 44 provides device-agnostic, protocol-independent smart home and IoT control for JARVIS. It decouples capability orchestration from underlying hardware transports via a pluggable `IoTBackend` adapter pattern.

```
[IoT Request / Automation Trigger]
                │
                ▼
[Safety Policy Kernel Interlock]
  ├── Physical Risk Check (unlock, disarm -> Two-Gate Token)
  ├── Device Trust Gate (Untrusted Quarantine)
  └── Prompt Injection Quarantine
                │
                ▼
[Smart Home / IoT Provider]
       ├── Device Discovery & Identity Resolution
       ├── Capability & State Query Engine
       ├── Dynamic Zone & Grouping Manager
       ├── Availability & Connectivity Tracker
       └── Empirical Post-Action State Verifier
                │
                ▼
[Pluggable IoTBackend Adapter]
       ├── SimulatedIoTBackend (Deterministic Verification)
       ├── HomeAssistantRESTBackend (Live Bridge)
       └── Matter / Zigbee / MQTT Adapters
```

---

## 2. Contract Specification

- **Capability ID**: `44_smarthome_iot` (Alias: `44_smart_home_iot`)
- **Domain**: `iot`
- **Primary Provider**: `provider.iot.smart_mesh`
- **Fallback Provider**: `provider.iot.home_assistant`
- **Safety Classification**: `PHYSICAL`
- **Requires Two-Gate Confirmation**: `True` (for high-risk actions)
- **Verification Strategy**: `HOME_ASSISTANT_API_STATE`
- **Timeout**: `15.0s`

### Supported Operations

| Operation | Description | Safety Level |
|---|---|---|
| `iot.discover_devices` | Discovers devices matching dynamic filters (zone, capabilities) | `READ_ONLY` |
| `iot.query_state` | Reads current state and metadata of a device | `READ_ONLY` |
| `iot.control_device` | Executes verified commands against a target device | `PHYSICAL` |
| `iot.verify_state` | Empirically verifies post-action device state against expected values | `READ_ONLY` |
| `iot.group_devices` | Adds or removes devices from arbitrary logical groups/arrays | `MODIFYING` |
| `iot.set_availability`| Sets connectivity status (`ONLINE`, `OFFLINE`, `DEGRADED`) | `MODIFYING` |
| `iot.cast_media` | Casts media streams to supported media targets | `MODIFYING` |
| `iot.subscribe_events`| Subscribes to device state change notifications on Event Fabric | `READ_ONLY` |

---

## 3. Core Engine Mechanics

### A. Provider Abstraction
Core capability logic never interacts directly with low-level device sockets or vendor-specific REST APIs. All device communication routes through the `IoTBackend` interface:
- `discover_devices(filters)`
- `get_device(device_id)`
- `execute_command(device_id, command, parameters)`
- `set_connectivity(device_id, connectivity)`

Backends can be hot-swapped without altering higher-level automations or cognitive planning.

### B. Verification Level Reporting
Every action response and discovery payload explicitly reports its verification fidelity:
- **`PROVIDER-LEVEL VERIFIED`**: State transitions were validated against a deterministic software-modeled simulation backend.
- **`PHYSICAL HARDWARE VERIFIED`**: State transitions were verified through a live physical hardware bridge (e.g. physical Zigbee hub, Home Assistant instance).

### C. Physical Safety Interlock (Two-Gate)
Physical actions that affect physical security or boundaries (e.g. `unlock`, `disarm`, `open_barrier`) are classified as `PHYSICAL` safety level:
1. When invoked without a confirmation token, the provider halts with status `PENDING` and policy decision `CONFIRMATION_REQUIRED`.
2. A single-use confirmation token is generated with a 60-second TTL.
3. Execution proceeds only when the token is supplied.

### D. Device Trust & Quarantine
Devices carry trust classifications (`UNTRUSTED`, `MONITORED`, `TRUSTED`, `PRIVILEGED`). Untrusted devices are quarantined and rejected from command execution.

### E. Connectivity & Offline Handling
If a device is marked `OFFLINE` or `DEGRADED`, command attempts are immediately rejected with descriptive error statuses, preventing hanging network timeouts.

---

## 4. Verification Evidence

Capability 44 was verified against:
- Dynamic discovery with arbitrary filters and capability schemas
- Verified state read and post-command empirical verification
- Offline device rejection
- High-risk command Two-Gate safety interlock
- Untrusted device quarantine
- Arbitrary tag-based group management
- Concurrent multi-device operations
- Verification level distinction reporting
- Prompt injection quarantine
- Provider hot-swapping
