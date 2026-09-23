# Capability 14: Environmental Perception

**Capability ID:** `14_environmental_perception`  
**Classification:** `EXISTING`  
**Safety Classification:** `READ_ONLY`  
**Domain:** `perception`  
**Primary Provider:** `provider.os.win32` (wrapping Win32 API & psutil)  
**Fallback Provider:** `provider.os.psutil`  

---

## 1. Capability Purpose & Scope
Monitors host hardware vitals (CPU load, core count, RAM utilization, battery charge, AC power state), network interface throughput and connectivity status, and active system processes to provide physical ground-truth context to the Cognitive Core.

---

## 2. Supported Operations
- `env.probe_hardware`: Probes physical CPU, memory, power state, and battery status.
- `env.probe_network`: Inspects network adapters, IP bindings, and network throughput counters.
- `env.probe_processes`: Observes active operating system processes with CPU and memory attribution.

---

## 3. Required Context & World Model State
- **Host OS State:** Real-time metrics from `psutil` and Windows native performance counters.
- **Process Table:** Active window handles and background PIDs.

---

## 4. Provider Implementation & Selection
- **Implementation:** `capabilities/providers/os_provider.py` (`OSWin32Provider`), backed by `agents/system_control_agent.py`.
- **Fast-Path Latency:** Executes in **1.5 ms - 8.0 ms**.

---

## 5. Safety, Verification & Error Handling
- **Safety Policy:** `Level 0: ALLOWED` (Read-only environmental sensing).
- **Verification Strategy:** `WIN32_API` verifies physical hardware statistics directly from OS kernel interfaces.
- **Edge Cases Handled:** Disconnected network interfaces, battery absence on desktop workstations, missing process handles.
