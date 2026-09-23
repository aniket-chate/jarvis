"""Centralized Logging & Monitoring Configuration for JARVIS.

Tags all log messages by:
- Layer (Layer 1: Perception, Layer 2: Orchestration, Layer 3: Logic, Layer 0: System/Infra)
- Module / Subsystem
- Active Persona (Jarvis, Friday, Ultron, Omi)
- Timing / Execution Duration
- Log Severity & Usage Events
Outputs to both logs/jarvis.log and the console.
Includes a simple tail/view helper method.
"""

import os
import sys
import time
import logging
from pathlib import Path
from typing import Optional, List

from config.settings import PROJECT_ROOT, settings

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
MAIN_LOG_PATH = LOGS_DIR / "jarvis.log"


class JarvisLogFormatter(logging.Formatter):
    """Custom formatter enriching records with layer, module, and active persona tags."""

    def format(self, record: logging.LogRecord) -> str:
        # Determine layer from logger name
        name = record.name.lower()
        if "perception" in name or "voice" in name or "vision" in name or "wakeword" in name:
            layer = "Layer-1 [Perception]"
        elif "orchestrator" in name or "planner" in name or "executor" in name or "memory" in name or "router" in name:
            layer = "Layer-2 [Orchestrator]"
        elif "agent" in name or "skill" in name or "safety" in name or "identity" in name:
            layer = "Layer-3 [Logic]"
        else:
            layer = "Layer-0 [System]"

        persona = getattr(record, "persona", None) or settings.active_persona_name
        duration_ms = getattr(record, "duration_ms", None)
        duration_str = f" ({duration_ms:.1f}ms)" if duration_ms is not None else ""

        timestamp = self.formatTime(record, self.datefmt)
        msg = record.getMessage()

        return f"{timestamp} [{record.levelname:<7}] [{layer}] [{record.name}] [{persona}]{duration_str} {msg}"


def setup_central_logging(level: int = logging.INFO) -> None:
    """Configures centralized root logging for JARVIS."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers
    if root_logger.handlers:
        for h in list(root_logger.handlers):
            root_logger.removeHandler(h)

    formatter = JarvisLogFormatter(datefmt="%Y-%m-%d %H:%M:%S")

    # File Handler
    file_handler = logging.FileHandler(MAIN_LOG_PATH, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


def tail_logs(lines: int = 40) -> List[str]:
    """Reads and returns the last N lines of the centralized log file."""
    if not MAIN_LOG_PATH.exists():
        return ["No logs recorded yet."]

    with open(MAIN_LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
        return [line.rstrip() for line in all_lines[-lines:]]


class TimedOperation:
    """Context manager for measuring and logging execution duration."""

    def __init__(self, logger: logging.Logger, operation_name: str, persona: Optional[str] = None):
        self.logger = logger
        self.operation_name = operation_name
        self.persona = persona or settings.active_persona_name
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = (time.perf_counter() - self.start_time) * 1000.0
        extra = {"persona": self.persona, "duration_ms": duration_ms}
        if exc_type:
            self.logger.error(
                "Failed operation '%s' with error: %s",
                self.operation_name,
                str(exc_val),
                extra=extra
            )
        else:
            self.logger.info(
                "Completed operation '%s'",
                self.operation_name,
                extra=extra
            )
