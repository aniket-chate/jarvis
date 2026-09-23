# Capability 36: Device Mesh

## 1. Capability Boundary
Capability 36 (`36_device_mesh`) manages a dynamically discovered network of user nodes across heterogeneous environments (Windows Workstations, Mobile Thin Clients, Tablets, and Embedded IoT units). It guarantees stable machine-readable identity, presence heartbeats, capability advertisement, dynamic data-driven device selection, strict trust management, and explicit revocation isolation.

It adheres to the frozen architecture:
- Devices are identified by machine-readable UUIDs (`device_id`), never friendly names or hardcoded IP addresses.
- Devices maintain explicit trust states: `UNKNOWN`, `PENDING`, `TRUSTED`, `REVOKED`, `OFFLINE`.
- Newly registered devices default to `PENDING` (`default_trust="PENDING"`). There is zero automatic trust escalation without policy authority.
- Revoked devices are permanently quarantined: re-registration cannot silently overwrite a `REVOKED` state back to `PENDING` or `TRUSTED`.
- Protected device operations cannot be executed on or dispatched to `UNKNOWN` or `PENDING` nodes.
- Device actions pass through the Unified Policy Kernel, Two-Gate Permissions, and Execution Kernel.

---

## 2. Capability Contract
- **Capability ID**: `36_device_mesh`
- **Domain**: `mesh`
- **Primary Provider**: `provider.mesh.device_mesh` (`DeviceMeshProvider`)
- **Fallback Provider**: `provider.mesh.local_lan`
- **Safety Classification**: `MODIFYING`
- **Verification Strategy**: `DEVICE_HANDSHAKE_PING`
- **Timeout**: `15.0s`

### Supported Operations (9)
1. `mesh.discover_peers`: Enumerates active mesh nodes with real-time online status and capability filtering.
2. `mesh.register_device`: Dynamically registers or updates a device record with advertised capabilities. Default trust state is `PENDING`.
3. `mesh.set_device_trust`: Authoritative trust escalation / demotion operation (`PENDING` -> `TRUSTED`, `TRUSTED` -> `REVOKED`, etc.) authorized via policy.
4. `mesh.get_device_status`: Fetches live reachability, latency, last-seen timestamp, and trust state for a specific node.
5. `mesh.route_to_device`: Routes a command payload to a target node through the DeviceGatewayRegistry WebSocket tunnel. Requires trusted node status.
6. `mesh.sync_state`: Synchronizes context, active personas, and perception state across mesh participants.
7. `mesh.device_heartbeat`: Updates liveness timestamps and calculates stale node timeouts.
8. `mesh.revoke_device`: Revokes node trust, sets trust to `REVOKED`, and severs active communication tunnels.
9. `mesh.select_device`: Discovers and ranks online, trusted nodes advertising requested capability (e.g. `notifications`, `audio.output`, `terminal`), selecting the lowest-latency node.

---

## 3. Trust-State Design & Escalation Policy

### Trust Hierarchy & Transitions
```text
  [New Device] ─── registration ───► PENDING / UNKNOWN
                                           │
                           mesh.set_device_trust (Policy Authorized)
                                           ▼
                                        TRUSTED ◄─── Heartbeat ───► OFFLINE
                                           │
                                  mesh.revoke_device
                                           ▼
                                        REVOKED (Permanent Isolation)
```

1. **Default Registration Trust (`PENDING`)**:
   Under `DeviceMeshConfig.default_trust = "PENDING"`, newly discovered or connecting devices cannot immediately execute commands or receive routed dispatches.
2. **Explicit Elevation Gate**:
   Transition from `PENDING` to `TRUSTED` requires explicit invocation of `mesh.set_device_trust(device_id, trust_state="TRUSTED")`, adhering to Identity and Security Policy.
3. **Revocation Quarantine**:
   Once marked `REVOKED`, a node's active WebSocket tunnel is terminated. Subsequent calls to `register_device` retain the `REVOKED` state to prevent rogue reconnection loops.
4. **Dispatch Enforcement**:
   `DeviceGatewayRegistry.dispatch_to_device(device_id, ...)` checks device trust. If the node is `UNKNOWN`, `PENDING`, or `REVOKED`, the dispatch is rejected immediately with `REJECTED_UNTRUSTED` or `REJECTED_REVOKED`.

---

## 4. Configuration & Anti-Hardcoding
All runtime thresholds are managed through `DeviceMeshConfig`:
```python
@dataclass
class DeviceMeshConfig:
    heartbeat_timeout_sec: float = 30.0
    stale_check_interval_sec: float = 10.0
    default_latency_ms: float = 10.0
    require_trust_for_routing: bool = True
    default_trust: str = "PENDING"
```
Zero device names, IP addresses, ports, or platform checks are hardcoded into capability logic. All peer resolution is dynamic.

---

## 5. Security & Privacy
- **Trust Isolation**: Revoked or offline devices are rejected by `DeviceGatewayRegistry.dispatch_to_device()` with `REJECTED_REVOKED` or `REJECTED_OFFLINE`.
- **Command Sanitization**: Incoming mesh inputs pass through the untrusted boundary and are sanitized before execution.
- **Token Authentication**: Remote mesh connections require `GATEWAY_AUTH_TOKEN` verification.

---

## 6. Verification & Tests
- **Independent Suite**: `tests/test_capability_36_device_mesh.py` (8/8 PASS)
  - `test_device_registration_and_identity`: Dynamic registration defaulting to `PENDING`.
  - `test_device_discovery_and_filtering`: Filtering by capability across dynamically added devices.
  - `test_device_trust_and_revocation`: `PENDING` -> `TRUSTED` elevation and `REVOKED` isolation.
  - `test_revoked_device_cannot_silently_re_register`: Prevents silent trust escalation on re-registration.
  - `test_untrusted_device_dispatch_rejection`: Validates rejection of `UNKNOWN` / `PENDING` dispatch.
  - `test_heartbeat_and_stale_detection`: Dynamic TTL calculation and offline state transitions.
  - `test_data_driven_device_selection`: Lowest-latency trusted device selection.
  - `test_concurrency_in_device_operations`: Multi-threaded mesh state updates.
- **Anti-Hardcoding Suite**: `tests/test_no_domain_specific_hardcoding_batch_36_38.py` (13/13 PASS)
  - Tests A, B, E (Source Removal), F (Config Change), G (Provider Replacement), and H (Unknown Entity).
- **Live Server Integration**: `tests/test_live_batch_36_37_38.py` (LIVE 1 & LIVE 2 PASS)
