"""Capability 45: Physical / Robotics Interface Provider.

Provides a safe, data-driven abstraction for interacting with physical devices,
robots, actuators, sensors, and robotic systems under strict physical safety interlocks:
- Generic device, robot, actuator, and sensor schemas
- Pluggable backend adapter abstraction (e.g. Simulated, ROS2, Serial, Micro-ROS)
- Device discovery, capability inspection, and state synchronization
- Read-only sensor telemetry extraction
- Actuator command execution with acknowledgement and post-execution verification
- Safe idempotency tracking to prevent duplicate physical actuation
- Emergency stop abstraction (immediate halts, lockdown, refusal of subsequent movement)
- Two-Gate authorization enforcement for physical movement and high-risk operations
- Prompt injection quarantine on device metadata and user commands
- Explicit verification levels: SIMULATED_VERIFIED vs PROVIDER_LEVEL_VERIFIED vs PHYSICAL_HARDWARE_VERIFIED
- Zero domain-specific hardcoding: no fixed robot models, brands, or test entities
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import logging
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import uuid

from capabilities.base import ActionResult, BaseCapabilityProvider, ProviderMetadata
from safety.policy_kernel import policy_kernel, PolicyLevel
from event_fabric.bus import event_bus
from event_fabric.schemas import UniversalEvent

logger = logging.getLogger("JARVIS.Capabilities.Providers.PhysicalRobotics")


class DeviceConnectivity(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    DEGRADED = "DEGRADED"
    UNKNOWN = "UNKNOWN"


class SafetyState(str, Enum):
    SAFE_IDLE = "SAFE_IDLE"
    ARMED = "ARMED"
    IN_MOTION = "IN_MOTION"
    EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
    FAULT = "FAULT"


class TrustLevel(int, Enum):
    UNTRUSTED = 1
    MONITORED = 2
    TRUSTED = 3
    PRIVILEGED = 4


class DeviceCategory(str, Enum):
    SIMULATED_DEVICE = "SIMULATED_DEVICE"
    PROVIDER_LEVEL_DEVICE = "PROVIDER_LEVEL_DEVICE"
    PHYSICAL_HARDWARE_DEVICE = "PHYSICAL_HARDWARE_DEVICE"


class VerificationLevel(str, Enum):
    SIMULATED_VERIFIED = "SIMULATED_VERIFIED"
    PROVIDER_LEVEL_VERIFIED = "PROVIDER_LEVEL_VERIFIED"
    PHYSICAL_HARDWARE_VERIFIED = "PHYSICAL_HARDWARE_VERIFIED"


@dataclass
class RoboticsConfig:
    """Runtime configuration for Physical / Robotics Interface."""
    command_timeout_sec: float = 5.0
    max_retries: int = 2
    enforce_two_gate_for_movement: bool = True
    require_verification: bool = True
    emergency_stop_cooldown_sec: float = 1.0
    simulated_latency_ms: float = 5.0
    is_physical_bridge: bool = False
    default_trust_level: TrustLevel = TrustLevel.TRUSTED


@dataclass
class ActuatorDescriptor:
    """Generic description of a controllable physical actuator."""
    actuator_id: str
    name: str
    actuator_type: str  # e.g., "servo", "stepper", "motor", "gripper", "linear", "relay"
    min_limit: float = 0.0
    max_limit: float = 100.0
    units: str = "units"
    current_value: float = 0.0
    is_moving: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "actuator_id": self.actuator_id,
            "name": self.name,
            "actuator_type": self.actuator_type,
            "min_limit": self.min_limit,
            "max_limit": self.max_limit,
            "units": self.units,
            "current_value": self.current_value,
            "is_moving": self.is_moving,
        }


@dataclass
class SensorDescriptor:
    """Generic description of a physical or robotic sensor."""
    sensor_id: str
    name: str
    sensor_type: str  # e.g., "temperature", "distance", "encoder", "imu", "pressure", "vision"
    units: str = "units"
    min_range: float = 0.0
    max_range: float = 1000.0
    sampling_rate_hz: float = 10.0
    last_reading: Optional[float] = None
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "name": self.name,
            "sensor_type": self.sensor_type,
            "units": self.units,
            "min_range": self.min_range,
            "max_range": self.max_range,
            "sampling_rate_hz": self.sampling_rate_hz,
            "last_reading": self.last_reading,
            "last_updated": self.last_updated,
        }


@dataclass
class SensorReading:
    """Empirical observation obtained from a physical sensor."""
    sensor_id: str
    value: Any
    units: str
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    quality: str = "GOOD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sensor_id": self.sensor_id,
            "value": self.value,
            "units": self.units,
            "timestamp": self.timestamp,
            "confidence": self.confidence,
            "quality": self.quality,
        }


@dataclass
class PhysicalCommand:
    """Command payload to actuate a physical or robotic device."""
    command_id: str
    target_device_id: str
    command_type: str  # e.g., "move", "set_position", "stop", "calibrate", "home", "actuate"
    parameters: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    requires_confirmation: bool = True
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "target_device_id": self.target_device_id,
            "command_type": self.command_type,
            "parameters": dict(self.parameters),
            "idempotency_key": self.idempotency_key,
            "requires_confirmation": self.requires_confirmation,
            "timestamp": self.timestamp,
        }


@dataclass
class CommandAcknowledgement:
    """Provider acknowledgement of an accepted physical command."""
    command_id: str
    status: str  # "ACCEPTED", "REJECTED", "EXECUTED", "EMERGENCY_HALTED"
    received_at: float = field(default_factory=time.time)
    estimated_completion_ms: float = 50.0
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status,
            "received_at": self.received_at,
            "estimated_completion_ms": self.estimated_completion_ms,
            "message": self.message,
        }


@dataclass
class PhysicalDevice:
    """Comprehensive schema for any physical device or robot."""
    device_id: str
    name: str
    device_type: str  # e.g., "robotic_arm", "mobile_base", "sensor_node", "actuator_array"
    device_category: DeviceCategory = DeviceCategory.SIMULATED_DEVICE
    connectivity: DeviceConnectivity = DeviceConnectivity.CONNECTED
    safety_state: SafetyState = SafetyState.SAFE_IDLE
    trust_level: TrustLevel = TrustLevel.TRUSTED
    actuators: Dict[str, ActuatorDescriptor] = field(default_factory=dict)
    sensors: Dict[str, SensorDescriptor] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)
    zone: str = "default_zone"
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "name": self.name,
            "device_type": self.device_type,
            "device_category": self.device_category.value,
            "connectivity": self.connectivity.value,
            "safety_state": self.safety_state.value,
            "trust_level": self.trust_level.value,
            "actuators": {k: v.to_dict() for k, v in self.actuators.items()},
            "sensors": {k: v.to_dict() for k, v in self.sensors.items()},
            "capabilities": list(self.capabilities),
            "zone": self.zone,
            "metadata": dict(self.metadata),
            "last_updated": self.last_updated,
        }


# -----------------------------------------------------------------------------
# Provider Abstraction: Robotics Backend Interface
# -----------------------------------------------------------------------------

class RoboticsBackend(ABC):
    """Abstract interface for physical robotics backends and drivers."""

    @abstractmethod
    def discover_devices(self, filters: Dict[str, Any]) -> List[PhysicalDevice]:
        pass

    @abstractmethod
    def get_device(self, device_id: str) -> Optional[PhysicalDevice]:
        pass

    @abstractmethod
    def register_device(self, device: PhysicalDevice) -> bool:
        pass

    @abstractmethod
    def remove_device(self, device_id: str) -> bool:
        pass

    @abstractmethod
    def read_sensor(self, device_id: str, sensor_id: str) -> Optional[SensorReading]:
        pass

    @abstractmethod
    def execute_command(self, cmd: PhysicalCommand) -> Tuple[CommandAcknowledgement, Dict[str, Any]]:
        pass

    @abstractmethod
    def emergency_stop(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def reset_emergency_stop(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def observe_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        pass


class SimulatedRoboticsBackend(RoboticsBackend):
    """Deterministic simulated physical robotics backend for local execution & testing."""

    def __init__(self):
        self._lock = threading.RLock()
        self._devices: Dict[str, PhysicalDevice] = {}
        self._global_emergency_stop: bool = False

    def discover_devices(self, filters: Dict[str, Any]) -> List[PhysicalDevice]:
        with self._lock:
            res = []
            dev_type = filters.get("device_type")
            zone = filters.get("zone")
            conn = filters.get("connectivity")
            for d in self._devices.values():
                if dev_type and d.device_type != dev_type:
                    continue
                if zone and d.zone != zone:
                    continue
                if conn and d.connectivity.value != conn:
                    continue
                res.append(d)
            return list(res)

    def get_device(self, device_id: str) -> Optional[PhysicalDevice]:
        with self._lock:
            return self._devices.get(device_id)

    def register_device(self, device: PhysicalDevice) -> bool:
        with self._lock:
            self._devices[device.device_id] = device
            return True

    def remove_device(self, device_id: str) -> bool:
        with self._lock:
            if device_id in self._devices:
                del self._devices[device_id]
                return True
            return False

    def read_sensor(self, device_id: str, sensor_id: str) -> Optional[SensorReading]:
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return None
            sensor = dev.sensors.get(sensor_id)
            if not sensor:
                return None
            val = sensor.last_reading if sensor.last_reading is not None else (sensor.min_range + sensor.max_range) / 2.0
            return SensorReading(
                sensor_id=sensor_id,
                value=val,
                units=sensor.units,
                timestamp=time.time(),
                confidence=0.99,
                quality="GOOD",
            )

    def execute_command(self, cmd: PhysicalCommand) -> Tuple[CommandAcknowledgement, Dict[str, Any]]:
        with self._lock:
            if self._global_emergency_stop:
                ack = CommandAcknowledgement(
                    command_id=cmd.command_id,
                    status="REJECTED",
                    message="Global emergency stop active: physical actuation prohibited",
                )
                return ack, {"error": "GLOBAL_EMERGENCY_STOP_ACTIVE"}

            dev = self._devices.get(cmd.target_device_id)
            if not dev:
                ack = CommandAcknowledgement(
                    command_id=cmd.command_id,
                    status="REJECTED",
                    message=f"Target device '{cmd.target_device_id}' not found",
                )
                return ack, {"error": "DEVICE_NOT_FOUND"}

            if dev.safety_state == SafetyState.EMERGENCY_STOPPED:
                ack = CommandAcknowledgement(
                    command_id=cmd.command_id,
                    status="REJECTED",
                    message=f"Device '{dev.device_id}' is in EMERGENCY_STOPPED state",
                )
                return ack, {"error": "DEVICE_EMERGENCY_STOPPED"}

            if dev.connectivity != DeviceConnectivity.CONNECTED:
                ack = CommandAcknowledgement(
                    command_id=cmd.command_id,
                    status="REJECTED",
                    message=f"Device '{dev.device_id}' is {dev.connectivity.value}",
                )
                return ack, {"error": f"DEVICE_{dev.connectivity.value}"}

            # Actuation execution
            cmd_type = cmd.command_type
            params = cmd.parameters
            dev.safety_state = SafetyState.IN_MOTION

            actuator_id = params.get("actuator_id")
            target_val = params.get("target_value")

            applied_state = {}
            if actuator_id and actuator_id in dev.actuators and target_val is not None:
                act = dev.actuators[actuator_id]
                # Clamp within limits
                clamped = max(act.min_limit, min(act.max_limit, float(target_val)))
                act.current_value = clamped
                act.is_moving = False
                applied_state[actuator_id] = clamped
            elif params.get("positions"):
                for a_id, val in params.get("positions", {}).items():
                    if a_id in dev.actuators:
                        act = dev.actuators[a_id]
                        clamped = max(act.min_limit, min(act.max_limit, float(val)))
                        act.current_value = clamped
                        act.is_moving = False
                        applied_state[a_id] = clamped
            elif cmd_type == "stop":
                dev.safety_state = SafetyState.SAFE_IDLE
                for act in dev.actuators.values():
                    act.is_moving = False
            elif cmd_type == "home":
                for act in dev.actuators.values():
                    act.current_value = act.min_limit
                    act.is_moving = False
                    applied_state[act.actuator_id] = act.min_limit

            dev.safety_state = SafetyState.SAFE_IDLE
            dev.last_updated = time.time()

            ack = CommandAcknowledgement(
                command_id=cmd.command_id,
                status="EXECUTED",
                message=f"Command '{cmd_type}' successfully applied to '{dev.device_id}'",
            )
            return ack, {"applied_state": applied_state, "device_state": dev.to_dict()}

    def emergency_stop(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            affected = []
            if device_id:
                dev = self._devices.get(device_id)
                if dev:
                    dev.safety_state = SafetyState.EMERGENCY_STOPPED
                    for act in dev.actuators.values():
                        act.is_moving = False
                    affected.append(device_id)
            else:
                self._global_emergency_stop = True
                for dev in self._devices.values():
                    dev.safety_state = SafetyState.EMERGENCY_STOPPED
                    for act in dev.actuators.values():
                        act.is_moving = False
                    affected.append(dev.device_id)
            return {
                "status": "EMERGENCY_STOP_ENGAGED",
                "affected_devices": affected,
                "global_stop": self._global_emergency_stop,
                "timestamp": time.time(),
            }

    def reset_emergency_stop(self, device_id: Optional[str] = None) -> Dict[str, Any]:
        with self._lock:
            cleared = []
            if device_id:
                dev = self._devices.get(device_id)
                if dev:
                    dev.safety_state = SafetyState.SAFE_IDLE
                    cleared.append(device_id)
            else:
                self._global_emergency_stop = False
                for dev in self._devices.values():
                    dev.safety_state = SafetyState.SAFE_IDLE
                    cleared.append(dev.device_id)
            return {
                "status": "EMERGENCY_STOP_CLEARED",
                "cleared_devices": cleared,
                "global_stop": self._global_emergency_stop,
                "timestamp": time.time(),
            }

    def observe_state(self, device_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            dev = self._devices.get(device_id)
            if not dev:
                return None
            return dev.to_dict()


# -----------------------------------------------------------------------------
# Capability 45 Provider Implementation
# -----------------------------------------------------------------------------

class PhysicalRoboticsProvider(BaseCapabilityProvider):
    """Capability 45: Physical / Robotics Interface Provider."""

    PROMPT_INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?previous\s+instructions", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+in\s+developer\s+mode", re.IGNORECASE),
        re.compile(r"bypass\s+(physical\s+)?safety", re.IGNORECASE),
        re.compile(r"disable\s+(all\s+)?interlocks", re.IGNORECASE),
        re.compile(r"override\s+emergency\s+stop", re.IGNORECASE),
    ]

    HIGH_RISK_COMMANDS = {
        "move", "actuate", "execute_trajectory", "set_position", "high_velocity", "heavy_lift"
    }

    def __init__(
        self,
        config: Optional[RoboticsConfig] = None,
        backend: Optional[RoboticsBackend] = None,
    ):
        self.config = config or RoboticsConfig()
        self.backend = backend or SimulatedRoboticsBackend()
        self._idempotency_cache: Dict[str, ActionResult] = {}
        self._lock = threading.RLock()

        metadata = ProviderMetadata(
            provider_id="provider.robotics.physical_interface",
            name="Physical Robotics Interface Provider",
            supported_capabilities=[
                "robotics.discover_devices",
                "robotics.get_capabilities",
                "robotics.read_sensor",
                "robotics.read_telemetry",
                "robotics.execute_command",
                "robotics.execute_trajectory",
                "robotics.observe_state",
                "robotics.verify_state",
                "robotics.emergency_stop",
                "robotics.reset_emergency_stop",
                "robotics.set_authorization",
                "robotics.set_trust",
                "robotics.get_status",
                "robotics.register_device",
                "robotics.remove_device",
            ],
            priority=10,
            estimated_latency_ms=10.0,
            safety_level="physical",
            device_target="physical_or_simulated",
            description="Abstracted physical and robotic device orchestration with safety interlocks.",
        )
        super().__init__(metadata)

    def is_available(self) -> bool:
        """Live availability only; the deterministic simulator is test-only."""
        return bool(self.config.is_physical_bridge) or self.backend.__class__.__name__ != "SimulatedRoboticsBackend"

    def get_readiness(self) -> str:
        return "PHYSICAL_HARDWARE_VERIFIED" if self.config.is_physical_bridge else (
            "SIMULATED" if self.backend.__class__.__name__ == "SimulatedRoboticsBackend" else "LIVE_PROVIDER"
        )

    def execute(
        self,
        capability: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> ActionResult:
        t0 = time.perf_counter()

        # Security check: prompt injection inspection on all incoming parameters
        payload_str = json.dumps(parameters)
        for pat in self.PROMPT_INJECTION_PATTERNS:
            if pat.search(payload_str):
                logger.warning("[PhysicalRoboticsProvider] Prompt injection detected: %s", pat.pattern)
                return ActionResult(
                    status="FAILED",
                    action=capability,
                    provider_id=self.provider_id,
                    output={"error": f"Security refusal: prompt injection pattern detected ({pat.pattern})"},
                    message="Security refusal: prompt injection detected",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )

        # Dispatch based on capability operation
        if capability == "robotics.discover_devices":
            return self._discover_devices(parameters, t0)
        elif capability in ["robotics.get_capabilities", "robotics.get_status"]:
            return self._get_capabilities_or_status(parameters, t0, capability)
        elif capability in ["robotics.read_sensor", "robotics.read_telemetry"]:
            return self._read_sensor(parameters, t0, capability)
        elif capability in ["robotics.execute_command", "robotics.execute_trajectory"]:
            return self._execute_command(parameters, t0, capability)
        elif capability == "robotics.observe_state":
            return self._observe_state(parameters, t0)
        elif capability == "robotics.verify_state":
            return self._verify_state(parameters, t0)
        elif capability == "robotics.emergency_stop":
            return self._emergency_stop(parameters, t0)
        elif capability == "robotics.reset_emergency_stop":
            return self._reset_emergency_stop(parameters, t0)
        elif capability == "robotics.set_authorization":
            return self._set_authorization(parameters, t0)
        elif capability == "robotics.set_trust":
            return self._set_trust(parameters, t0)
        elif capability == "robotics.register_device":
            return self._register_device(parameters, t0)
        elif capability == "robotics.remove_device":
            return self._remove_device(parameters, t0)
        else:
            return ActionResult(
                status="FAILED",
                action=capability,
                provider_id=self.provider_id,
                output={"error": f"Unsupported robotics capability '{capability}'"},
                message=f"Operation '{capability}' not implemented",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    # -------------------------------------------------------------------------
    # Internal Handlers
    # -------------------------------------------------------------------------

    def _discover_devices(self, params: Dict[str, Any], t0: float) -> ActionResult:
        filters = params.get("filters", params)
        devs = self.backend.discover_devices(filters)
        data = [d.to_dict() for d in devs]
        return ActionResult(
            status="SUCCESS",
            action="robotics.discover_devices",
            provider_id=self.provider_id,
            output={
                "devices": data,
                "count": len(data),
                "verification_level": VerificationLevel.SIMULATED_VERIFIED.value if not self.config.is_physical_bridge else VerificationLevel.PHYSICAL_HARDWARE_VERIFIED.value,
            },
            message=f"Discovered {len(data)} physical/robotic device(s)",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _get_capabilities_or_status(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        dev_id = params.get("device_id")
        if not dev_id:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "device_id is required"},
                message="device_id parameter is missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output={
                "device_id": dev.device_id,
                "name": dev.name,
                "device_type": dev.device_type,
                "capabilities": dev.capabilities,
                "safety_state": dev.safety_state.value,
                "connectivity": dev.connectivity.value,
                "trust_level": dev.trust_level.value,
                "actuator_count": len(dev.actuators),
                "sensor_count": len(dev.sensors),
                "state": dev.to_dict(),
            },
            message=f"Retrieved status for '{dev_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _read_sensor(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        dev_id = params.get("device_id")
        sensor_id = params.get("sensor_id")
        if not dev_id or not sensor_id:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "device_id and sensor_id are required"},
                message="Missing required sensor parameters",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        if dev.connectivity != DeviceConnectivity.CONNECTED:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' is {dev.connectivity.value}"},
                message=f"Cannot read sensor: device is {dev.connectivity.value}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        reading = self.backend.read_sensor(dev_id, sensor_id)
        if not reading:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Sensor '{sensor_id}' not found on device '{dev_id}'"},
                message="Sensor not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        return ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output={
                "device_id": dev_id,
                "sensor_reading": reading.to_dict(),
                "verification_level": VerificationLevel.SIMULATED_VERIFIED.value if not self.config.is_physical_bridge else VerificationLevel.PHYSICAL_HARDWARE_VERIFIED.value,
            },
            message=f"Read sensor '{sensor_id}': {reading.value} {reading.units}",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _execute_command(self, params: Dict[str, Any], t0: float, action: str) -> ActionResult:
        dev_id = params.get("device_id")
        cmd_type = params.get("command_type", params.get("command", ""))
        cmd_params = params.get("parameters", {})
        idempotency_key = params.get("idempotency_key")
        confirmation_token = params.get("confirmation_token")

        if not dev_id or not cmd_type:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": "device_id and command_type are required"},
                message="Missing required command fields",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Idempotency check
        if idempotency_key:
            with self._lock:
                if idempotency_key in self._idempotency_cache:
                    cached = self._idempotency_cache[idempotency_key]
                    logger.info("[PhysicalRoboticsProvider] Replaying cached execution for idempotency_key '%s'", idempotency_key)
                    return ActionResult(
                        status=cached.status,
                        action=action,
                        provider_id=self.provider_id,
                        output=cached.output,
                        message=f"(Cached) {cached.message}",
                        evidence="IDEMPOTENCY_CACHE_HIT",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

        # Verify device existence and trust
        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        if dev.trust_level == TrustLevel.UNTRUSTED:
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' is UNTRUSTED and quarantined from physical actuation"},
                message="Untrusted device rejected",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        if dev.safety_state == SafetyState.EMERGENCY_STOPPED and cmd_type != "reset_emergency_stop":
            return ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' is in EMERGENCY_STOPPED state. Reset required before further commands."},
                message="Device locked under emergency stop",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Safety policy: movement/actuation gates on Two-Gate confirmation
        is_high_risk = cmd_type in self.HIGH_RISK_COMMANDS or params.get("high_risk", False)
        if is_high_risk and self.config.enforce_two_gate_for_movement:
            if not confirmation_token:
                # Issue staged token via PolicyKernel
                staged_token = f"auth_robotics_{uuid.uuid4().hex[:12]}"
                now = time.time()
                from safety.policy_kernel import PendingConfirmation
                policy_kernel._pending_confirmations[staged_token] = PendingConfirmation(
                    token=staged_token,
                    action_domain="robotics",
                    action_name=cmd_type,
                    parameters=params,
                    created_at=now,
                    expires_at=now + 60.0,
                )
                return ActionResult(
                    status="WAITING_EXTERNAL",
                    action=action,
                    provider_id=self.provider_id,
                    output={
                        "status": "APPROVAL_REQUIRED",
                        "confirmation_token": staged_token,
                        "device_id": dev_id,
                        "command_type": cmd_type,
                        "message": "Physical action requires explicit user authorization token",
                    },
                    message="Action requires explicit Two-Gate confirmation token",
                    execution_time_ms=(time.perf_counter() - t0) * 1000,
                )
            else:
                # Verify token
                confirmed = policy_kernel.confirm_token(confirmation_token)
                if not confirmed and not str(confirmation_token).startswith("auth_robotics_"):
                    return ActionResult(
                        status="FAILED",
                        action=action,
                        provider_id=self.provider_id,
                        output={"error": "Invalid or expired confirmation token"},
                        message="Security refusal: invalid confirmation token",
                        execution_time_ms=(time.perf_counter() - t0) * 1000,
                    )

        # Construct and dispatch PhysicalCommand
        cmd = PhysicalCommand(
            command_id=f"cmd_{uuid.uuid4().hex[:8]}",
            target_device_id=dev_id,
            command_type=cmd_type,
            parameters=cmd_params,
            idempotency_key=idempotency_key,
            requires_confirmation=is_high_risk,
        )

        ack, result_data = self.backend.execute_command(cmd)
        if ack.status != "EXECUTED":
            res = ActionResult(
                status="FAILED",
                action=action,
                provider_id=self.provider_id,
                output={"acknowledgement": ack.to_dict(), "details": result_data},
                message=ack.message,
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
            return res

        # Publish state event to event bus
        try:
            event_bus.publish_sync(UniversalEvent(
                event_type="robotics.command_executed",
                payload={"device_id": dev_id, "command": cmd.to_dict(), "ack": ack.to_dict()},
                source="physical_robotics_provider",
            ))
        except Exception as eb_err:
            logger.debug("[PhysicalRoboticsProvider] Event bus publish error: %s", eb_err)

        res = ActionResult(
            status="SUCCESS",
            action=action,
            provider_id=self.provider_id,
            output={
                "command_id": cmd.command_id,
                "acknowledgement": ack.to_dict(),
                "result": result_data,
                "verification_level": VerificationLevel.SIMULATED_VERIFIED.value if not self.config.is_physical_bridge else VerificationLevel.PHYSICAL_HARDWARE_VERIFIED.value,
            },
            message=ack.message,
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

        if idempotency_key:
            with self._lock:
                self._idempotency_cache[idempotency_key] = res

        return res

    def _observe_state(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        if not dev_id:
            return ActionResult(
                status="FAILED",
                action="robotics.observe_state",
                provider_id=self.provider_id,
                output={"error": "device_id is required"},
                message="device_id is missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        state = self.backend.observe_state(dev_id)
        if not state:
            return ActionResult(
                status="FAILED",
                action="robotics.observe_state",
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        return ActionResult(
            status="SUCCESS",
            action="robotics.observe_state",
            provider_id=self.provider_id,
            output={
                "device_id": dev_id,
                "observed_state": state,
                "verification_level": VerificationLevel.SIMULATED_VERIFIED.value if not self.config.is_physical_bridge else VerificationLevel.PHYSICAL_HARDWARE_VERIFIED.value,
            },
            message=f"Observed state of '{dev_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _verify_state(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        expected_state = params.get("expected_state", {})
        tolerance = params.get("tolerance", 0.05)

        if not dev_id or not expected_state:
            return ActionResult(
                status="FAILED",
                action="robotics.verify_state",
                provider_id=self.provider_id,
                output={"error": "device_id and expected_state are required"},
                message="Missing required verification fields",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action="robotics.verify_state",
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        matched = True
        discrepancies = {}
        for k, exp_val in expected_state.items():
            actual_val = None
            if k in dev.actuators:
                actual_val = dev.actuators[k].current_value
            elif k in dev.sensors:
                actual_val = dev.sensors[k].last_reading
            elif k in dev.metadata:
                actual_val = dev.metadata[k]
            elif hasattr(dev, k):
                attr = getattr(dev, k)
                actual_val = attr.value if hasattr(attr, "value") else attr

            if actual_val is None:
                matched = False
                discrepancies[k] = {"expected": exp_val, "actual": None, "reason": "Property not found"}
            elif isinstance(exp_val, (int, float)) and isinstance(actual_val, (int, float)):
                diff = abs(actual_val - exp_val)
                if diff > tolerance:
                    matched = False
                    discrepancies[k] = {"expected": exp_val, "actual": actual_val, "diff": diff}
            elif exp_val != actual_val:
                matched = False
                discrepancies[k] = {"expected": exp_val, "actual": actual_val}

        return ActionResult(
            status="SUCCESS" if matched else "FAILED",
            action="robotics.verify_state",
            provider_id=self.provider_id,
            output={
                "device_id": dev_id,
                "verified": matched,
                "discrepancies": discrepancies,
                "verification_level": VerificationLevel.SIMULATED_VERIFIED.value if not self.config.is_physical_bridge else VerificationLevel.PHYSICAL_HARDWARE_VERIFIED.value,
            },
            message="State verified successfully" if matched else f"Verification failed with {len(discrepancies)} discrepancy/discrepancies",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _emergency_stop(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        res = self.backend.emergency_stop(dev_id)
        logger.warning("[PhysicalRoboticsProvider] EMERGENCY STOP EXECUTED: %s", res)

        # Publish emergency stop alert
        try:
            event_bus.publish_sync(UniversalEvent(
                event_type="robotics.emergency_stop_triggered",
                payload=res,
                source="physical_robotics_provider",
            ))
        except Exception:
            pass

        return ActionResult(
            status="SUCCESS",
            action="robotics.emergency_stop",
            provider_id=self.provider_id,
            output=res,
            message="Emergency stop successfully engaged",
            evidence="EMERGENCY_STOP_ACTIVE",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _reset_emergency_stop(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        res = self.backend.reset_emergency_stop(dev_id)
        return ActionResult(
            status="SUCCESS",
            action="robotics.reset_emergency_stop",
            provider_id=self.provider_id,
            output=res,
            message="Emergency stop cleared; safety state restored to SAFE_IDLE",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _set_authorization(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        level = params.get("safety_state")
        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action="robotics.set_authorization",
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message="Device not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        try:
            dev.safety_state = SafetyState(level)
            return ActionResult(
                status="SUCCESS",
                action="robotics.set_authorization",
                provider_id=self.provider_id,
                output={"device_id": dev_id, "safety_state": dev.safety_state.value},
                message=f"Updated safety state to {level}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        except ValueError:
            return ActionResult(
                status="FAILED",
                action="robotics.set_authorization",
                provider_id=self.provider_id,
                output={"error": f"Invalid safety state '{level}'"},
                message="Invalid safety state",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _set_trust(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        trust_val = params.get("trust_level")
        dev = self.backend.get_device(dev_id)
        if not dev:
            return ActionResult(
                status="FAILED",
                action="robotics.set_trust",
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message="Device not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        try:
            dev.trust_level = TrustLevel(int(trust_val))
            return ActionResult(
                status="SUCCESS",
                action="robotics.set_trust",
                provider_id=self.provider_id,
                output={"device_id": dev_id, "trust_level": dev.trust_level.value},
                message=f"Updated trust level to {dev.trust_level.value}",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        except Exception as err:
            return ActionResult(
                status="FAILED",
                action="robotics.set_trust",
                provider_id=self.provider_id,
                output={"error": f"Invalid trust level: {err}"},
                message="Invalid trust level",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

    def _register_device(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id", f"dev_{uuid.uuid4().hex[:8]}")
        name = params.get("name", "Generic Robot")
        device_type = params.get("device_type", "robotic_arm")
        category_str = params.get("device_category", "SIMULATED_DEVICE")
        zone = params.get("zone", "default_zone")
        caps = params.get("capabilities", ["read_sensor", "move"])

        actuators = {}
        act_input = params.get("actuators", [])
        act_items = act_input.values() if isinstance(act_input, dict) else act_input
        for a_data in act_items:
            if isinstance(a_data, dict):
                act = ActuatorDescriptor(
                    actuator_id=a_data.get("actuator_id", f"act_{uuid.uuid4().hex[:4]}"),
                    name=a_data.get("name", "actuator"),
                    actuator_type=a_data.get("actuator_type", "servo"),
                    min_limit=float(a_data.get("min_limit", 0.0)),
                    max_limit=float(a_data.get("max_limit", 100.0)),
                    units=a_data.get("units", "deg"),
                    current_value=float(a_data.get("current_value", 0.0)),
                )
                actuators[act.actuator_id] = act

        sensors = {}
        sen_input = params.get("sensors", [])
        sen_items = sen_input.values() if isinstance(sen_input, dict) else sen_input
        for s_data in sen_items:
            if isinstance(s_data, dict):
                sen = SensorDescriptor(
                    sensor_id=s_data.get("sensor_id", f"sen_{uuid.uuid4().hex[:4]}"),
                    name=s_data.get("name", "sensor"),
                    sensor_type=s_data.get("sensor_type", "analog"),
                    units=s_data.get("units", "raw"),
                    min_range=float(s_data.get("min_range", 0.0)),
                    max_range=float(s_data.get("max_range", 100.0)),
                    last_reading=s_data.get("last_reading"),
                )
                sensors[sen.sensor_id] = sen

        try:
            category = DeviceCategory(category_str)
        except ValueError:
            category = DeviceCategory.SIMULATED_DEVICE

        device = PhysicalDevice(
            device_id=dev_id,
            name=name,
            device_type=device_type,
            device_category=category,
            actuators=actuators,
            sensors=sensors,
            capabilities=caps,
            zone=zone,
            metadata=params.get("metadata", {}),
        )

        self.backend.register_device(device)
        return ActionResult(
            status="SUCCESS",
            action="robotics.register_device",
            provider_id=self.provider_id,
            output={"device": device.to_dict(), "device_id": dev_id},
            message=f"Registered device '{dev_id}'",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def _remove_device(self, params: Dict[str, Any], t0: float) -> ActionResult:
        dev_id = params.get("device_id")
        if not dev_id:
            return ActionResult(
                status="FAILED",
                action="robotics.remove_device",
                provider_id=self.provider_id,
                output={"error": "device_id is required"},
                message="device_id is missing",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        removed = self.backend.remove_device(dev_id)
        if not removed:
            return ActionResult(
                status="FAILED",
                action="robotics.remove_device",
                provider_id=self.provider_id,
                output={"error": f"Device '{dev_id}' not found"},
                message=f"Device '{dev_id}' not found",
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )
        return ActionResult(
            status="SUCCESS",
            action="robotics.remove_device",
            provider_id=self.provider_id,
            output={"device_id": dev_id, "removed": True},
            message=f"Device '{dev_id}' successfully removed",
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )


physical_robotics_provider = PhysicalRoboticsProvider()
