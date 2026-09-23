"""OS Capability Provider wrapping system_control_agent."""

import logging
import time
from typing import Any, Dict, Optional
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
from agents.system_control_agent import system_control_agent

logger = logging.getLogger("JARVIS.Providers.OS")


class OSWin32Provider(BaseCapabilityProvider):
    """Provides desktop window management, volume, and telemetry capabilities."""

    def __init__(self):
        super().__init__(
            ProviderMetadata(
                provider_id="provider.os.win32",
                name="Windows 11 Native System Control",
                supported_capabilities=[
                    "os.window_management",
                    "os.telemetry",
                    "os.volume_control",
                    "os.process_control",
                    "env.probe_hardware",
                    "env.probe_network",
                    "env.probe_processes",
                ],
                priority=10,
                estimated_latency_ms=50.0,
            )
        )
        self.agent = system_control_agent

    def is_available(self) -> bool:
        return True

    def execute(self, capability: str, parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> ActionResult:
        t_start = time.perf_counter()
        try:
            if capability == "os.window_management":
                direction = parameters.get("direction", "left")
                res = self.agent.execute({"action": "snap_window", "direction": direction})
                elapsed = (time.perf_counter() - t_start) * 1000
                msg = str(res.get("response") or res.get("message") or res)
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=msg, message=msg, execution_time_ms=elapsed)

            elif capability == "os.telemetry":
                res = self.agent.execute({"action": "status"})
                elapsed = (time.perf_counter() - t_start) * 1000
                msg = str(res.get("response") or res.get("message") or res)
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=msg, execution_time_ms=elapsed)

            elif capability == "os.volume_control":
                action = parameters.get("action", "set")
                if action == "set" or "level" in parameters:
                    level = int(parameters.get("level", 50))
                    res = self.agent.set_volume(level)
                elif action == "adjust" or "delta" in parameters:
                    delta = int(parameters.get("delta", 10))
                    res = self.agent.adjust_volume(delta)
                elif action == "mute":
                    res = self.agent.mute_volume()
                elif action == "unmute":
                    res = self.agent.unmute_volume()
                else:
                    res = self.agent.set_volume(int(parameters.get("level", 50)))
                elapsed = (time.perf_counter() - t_start) * 1000
                msg = str(res.get("response") or res.get("message") or res)
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=msg, execution_time_ms=elapsed)

            elif capability == "os.process_control":
                limit = int(parameters.get("limit", 15))
                res = self.agent.list_processes(limit=limit)
                elapsed = (time.perf_counter() - t_start) * 1000
                msg = f"Retrieved {len(res.get('processes', []))} active processes."
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output=res, message=msg, execution_time_ms=elapsed)

            elif capability == "env.probe_hardware":
                import psutil
                cpu_pct = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory()
                battery = psutil.sensors_battery()
                hw_info = {
                    "cpu_percent": cpu_pct,
                    "cpu_count": psutil.cpu_count(logical=True),
                    "memory_total_gb": round(mem.total / (1024 ** 3), 2),
                    "memory_percent": mem.percent,
                    "battery_percent": battery.percent if battery else None,
                    "power_plugged": battery.power_plugged if battery else True,
                }
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                msg = f"Hardware probe: CPU {cpu_pct}%, RAM {mem.percent}%."
                return ActionResult(status="SUCCESS", output=hw_info, message=msg, execution_time_ms=elapsed)

            elif capability == "env.probe_network":
                import psutil
                addrs = psutil.net_if_addrs()
                io = psutil.net_io_counters()
                net_info = {
                    "interfaces": list(addrs.keys()),
                    "bytes_sent": io.bytes_sent,
                    "bytes_recv": io.bytes_recv,
                    "is_connected": io.bytes_recv > 0 or bool(addrs),
                }
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                msg = f"Network probe: {len(addrs)} interfaces detected."
                return ActionResult(status="SUCCESS", output=net_info, message=msg, execution_time_ms=elapsed)

            elif capability == "env.probe_processes":
                limit = int(parameters.get("limit", 15))
                res = self.agent.list_processes(limit=limit)
                elapsed = (time.perf_counter() - t_start) * 1000
                self.record_outcome(True)
                msg = f"Process probe: {len(res.get('processes', []))} active processes observed."
                return ActionResult(status="SUCCESS", output=res, message=msg, execution_time_ms=elapsed)

            elif capability == "system.switch_persona":
                from config.settings import settings
                target_p = parameters.get("persona", "Jarvis")
                settings.set_active_persona(target_p)
                elapsed = (time.perf_counter() - t_start) * 1000
                msg = f"Persona switched to {target_p}."
                self.record_outcome(True)
                return ActionResult(status="SUCCESS", output={"persona": target_p}, message=msg, execution_time_ms=elapsed)

            else:
                elapsed = (time.perf_counter() - t_start) * 1000
                return ActionResult(status="FAILED", output=None, message=f"Unsupported OS capability: {capability}", execution_time_ms=elapsed)
        except Exception as e:
            elapsed = (time.perf_counter() - t_start) * 1000
            self.record_outcome(False)
            return ActionResult(status="FAILED", output=str(e), message=str(e), execution_time_ms=elapsed)
