# Capability 45: Physical / Robotics Interface

## 1. Overview & Purpose
Capability 45 provides JARVIS with a standardized, hardened, and safety-gated abstraction for discovering, monitoring, actuating, and verifying physical and robotic systems. It enables JARVIS to interact with actuators, articulated mechanisms, telemetry nodes, and sensors without bypassing system safety boundaries or hallucinating hardware actions.

Crucially, this capability does **NOT** grant unconstrained execution on physical hardware:
- All physical motion and high-risk actuation are strictly gated behind **Two-Gate Token Authorization** via `PolicyKernel`.
- The system explicitly maintains epistemic boundaries distinguishing:
  - `SIMULATED_DEVICE` / `SIMULATED_VERIFIED`
  - `PROVIDER_LEVEL_DEVICE` / `PROVIDER_LEVEL_VERIFIED`
  - `PHYSICAL_HARDWARE_DEVICE` / `PHYSICAL_HARDWARE_VERIFIED`
- JARVIS **never** claims physical hardware verification unless an actual physical hardware device is connected, communicated with, and empirically verified.

---

## 2. Architecture & Control Flow
```
Physical / Simulated World
       ↓
RoboticsBackend (Simulated / ROS2 / Serial / CAN)
       ↓
PhysicalRoboticsProvider (Capability 45)
       ↓
CapabilityIntelligence (Registry & Routing)
       ↓
PolicyKernel (Two-Gate Authorization & Safety Invariants)
       ↓
ExecutionKernel (Isolated Threading & Timeout Control)
       ↓
Physical Command Dispatch & Sensor Telemetry Read
       ↓
State Observation & Empirical Verification
       ↓
WorldModel & EventFabric Notification
```

---

## 3. Generic Data Schemas & Abstractions

### 3.1 Device & Component Descriptors
- **`PhysicalDevice`**: Standardized device record containing unique `device_id`, arbitrary `name`, `device_type`, `device_category`, `connectivity` (`CONNECTED`, `DISCONNECTED`, `DEGRADED`), `safety_state`, `trust_level`, `actuators`, `sensors`, `capabilities`, `zone`, and `metadata`.
- **`ActuatorDescriptor`**: Generic specification of controllable motors, servos, valves, or relays with arbitrary motion limits (`min_limit`, `max_limit`), `units` (degrees, mm, Nm, percent), `current_value`, and `is_moving` flag.
- **`SensorDescriptor`**: Generic telemetry source with arbitrary channel names, measurement `units`, ranges, and `last_reading`.
- **`SensorReading`**: Telemetry observation containing timestamp, confidence rating, and measurement quality.

### 3.2 Command & Safety Payloads
- **`PhysicalCommand`**: Dispatch payload containing `command_id`, `target_device_id`, `command_type`, `parameters`, `idempotency_key`, and `requires_confirmation`.
- **`CommandAcknowledgement`**: Status receipt (`ACCEPTED`, `REJECTED`, `EXECUTED`, `EMERGENCY_HALTED`), execution latency, and telemetry payload.
- **`TrustLevel`**: Fine-grained hierarchy: `UNTRUSTED` (quarantined), `MONITORED`, `TRUSTED`, `PRIVILEGED`.
- **`SafetyState`**: State machine states: `SAFE_IDLE`, `ARMED`, `IN_MOTION`, `EMERGENCY_STOPPED`, `FAULT`.

---

## 4. Supported Operations & Capability Contracts

| Capability Operation | Description | Safety Level |
| :--- | :--- | :--- |
| `robotics.discover_devices` | Dynamic query matching devices by zone, type, or state | Read-Only |
| `robotics.get_capabilities` | Inspects declared actuators, sensors, and safety state | Read-Only |
| `robotics.read_sensor` | Reads telemetry value directly from specific sensor channel | Read-Only |
| `robotics.read_telemetry` | Bulk sampling of sensor streams with quality tags | Read-Only |
| `robotics.execute_command` | Dispatches motion or actuation command; Two-Gate gated | High Risk |
| `robotics.execute_trajectory` | Multi-waypoint motion profile execution | High Risk |
| `robotics.observe_state` | Synchronizes physical/simulated state with World Model | Read-Only |
| `robotics.verify_state` | Post-actuation tolerance check against actual state | Verification |
| `robotics.emergency_stop` | Immediate hardware/simulated lockdown to SAFE_IDLE/STOP | Emergency |
| `robotics.reset_emergency_stop` | Clears lockdown after physical fault inspection | Privileged |
| `robotics.set_authorization` | Modifies device safety state | Admin |
| `robotics.set_trust` | Promotes/demotes device trust level | Policy |
| `robotics.register_device` | Dynamically registers novel device into backend | Admin |
| `robotics.remove_device` | Unregisters device and frees resources | Admin |

---

## 5. Safety & Security Invariants

1. **Two-Gate Token Interlock**:
   - Any actuation command categorized under `HIGH_RISK_COMMANDS` (`move`, `actuate`, `execute_trajectory`, `set_position`) immediately checks for an active `confirmation_token`.
   - In the absence of a verified token, the provider stages a `PendingConfirmation` token in `PolicyKernel` and halts execution with `status="WAITING_EXTERNAL"`. Actuation executes only upon user validation.
2. **Emergency Stop Precedence**:
   - `emergency_stop` immediately overrides all queued actions, zeroes velocity across all actuators, and enters `EMERGENCY_STOPPED` state.
   - Any subsequent actuation command sent while in `EMERGENCY_STOPPED` is immediately rejected.
3. **Untrusted Device Isolation**:
   - Devices tagged with `TrustLevel.UNTRUSTED` are quarantined; all actuation commands targeting untrusted devices fail before reaching the dispatch kernel.
4. **Prompt Injection Quarantine**:
   - All incoming command parameters, descriptions, and metadata are scanned for prompt injection attacks (`ignore previous instructions`, `bypass safety`, `override emergency stop`). Any match triggers an immediate security refusal.
5. **Post-Execution State Verification**:
   - Commands are never marked as successful merely because the provider acknowledged receipt. Actual sensor and actuator telemetry is read back and verified against expected tolerances.

---

## 6. Zero Domain-Specific Hardcoding
- **No Hardcoded Brands or Models**: Operates on abstract mechanisms (`hydraulic_piston`, `servo`, `relay`) rather than specific vendors.
- **No Hardcoded Sensors or Locations**: Fully dynamic zones (`lab_bench_1`, `zone_alpha`, `cell_3`) and arbitrary sensor units (`nm_torque`, `microstrain`, `psi`, `celsius`).
- **Replaceable Providers**: Conforms to `BaseCapabilityProvider` and supports runtime hot-swapping via `CapabilityIntelligence`.
