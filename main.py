"""JARVIS Main Unified Entrypoint & Lifecycle Manager.

Hardware Target: NVIDIA RTX 2050 (4GB VRAM), Intel i5-13420H, 16GB RAM.
Provides single entry point starting all layers in order:
- Layer 1: Perception / Orientation Layer
- Layer 2: Orchestrator Core & Task Planner
- Layer 3: Logic Layer Agents & Safety Gates
Ensures clean startup, clean shutdown, and zero orphaned processes.
"""

import sys
import os
import signal
import argparse
import asyncio
import logging
import psutil
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from config.logging_config import setup_central_logging, tail_logs
from orchestrator.core import orchestrator
from orchestrator.memory import memory_manager
from orchestrator.learning import learning_engine
from perception.events import PerceptionEvent, event_bus
from voice.tts_piper import tts_engine

logger = logging.getLogger("JARVIS.Main")

# Global tracking of active child subprocesses
CHILD_PROCESSES = []


def init_all_layers() -> bool:
    """Initializes all layers in strict sequential order with confirmation logs."""
    setup_central_logging()
    logger.info("=" * 65)
    logger.info("INITIALIZING JARVIS MULTI-LAYER RUNTIME")
    logger.info("=" * 65)

    try:
        # Layer 1: Perception / Orientation Layer
        from perception.processing.speech_processing import speech_processor
        from perception.processing.vision_processing import vision_processor
        from perception.processing.context_awareness import context_engine
        logger.info("[INIT] Layer 1 (Perception / Orientation Layer) initialized.")

        # Layer 2: Orchestrator Core
        from orchestrator.planner import task_planner
        from orchestrator.executor import execution_manager
        logger.info("[INIT] Layer 2 (Orchestrator Core & Task Planner) initialized.")

        # Layer 3: Logic Layer Agents & Safety Gates
        from orchestrator.router import agent_registry, agent_router
        from agents.identity_agent import identity_agent
        from agents.permission_checks import permission_gate
        from agents.content_filtering import content_filter
        logger.info("[INIT] Layer 3 (Logic Layer Agents & Security Gates) initialized.")

        logger.info("All layers initialized successfully. Active Persona: %s", settings.active_persona_name)
        return True

    except Exception as e:
        logger.critical("[INIT FAILED] Error during layer initialization: %s", str(e), exc_info=True)
        return False


def shutdown_all_layers() -> None:
    """Performs clean shutdown, memory flush, and process cleanup guaranteeing zero orphans."""
    logger.info("=" * 65)
    logger.info("INITIATING CLEAN SHUTDOWN PROTOCOL")
    logger.info("=" * 65)

    # 1. Flush persistent memory
    try:
        memory_manager._save_persistent()
        logger.info("[SHUTDOWN] Persistent long-term memory saved to disk.")
    except Exception as e:
        logger.error("[SHUTDOWN] Error saving memory: %s", str(e))

    # 2. Terminate any tracked child processes
    current_proc = psutil.Process(os.getpid())
    children = current_proc.children(recursive=True)
    if children:
        logger.info("[SHUTDOWN] Terminating %d child process(es)...", len(children))
        for child in children:
            try:
                child.terminate()
            except Exception:
                pass
        gone, alive = psutil.wait_procs(children, timeout=3)
        for p in alive:
            try:
                p.kill()
            except Exception:
                pass

    # Verify process list
    remaining = current_proc.children(recursive=True)
    if not remaining:
        logger.info("[SHUTDOWN] Confirmed: Zero orphaned processes remain.")
    else:
        logger.warning("[SHUTDOWN] Warning: %d process(es) remaining.", len(remaining))

    logger.info("JARVIS shutdown sequence completed cleanly.")


def handle_signals(sig, frame):
    """Signal handler for SIGINT and SIGTERM."""
    logger.info("[SIGNAL] Received signal %s. Exiting cleanly...", sig)
    shutdown_all_layers()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGINT, handle_signals)
signal.signal(signal.SIGTERM, handle_signals)


async def run_scenario(scenario_id: str):
    """Runs one of the 3 full-system integration scenarios."""
    init_all_layers()
    scenario = scenario_id.lower()

    if scenario == "a":
        print("\n" + "=" * 65)
        print("SCENARIO A: Weather & News Query (web_agent / news_agent)")
        print("=" * 65)
        event = PerceptionEvent(
            type="text_command",
            payload={"raw_text": "What is in the latest news about artificial intelligence"},
            source="text_input",
            active_persona=settings.active_persona_name
        )
        report = orchestrator.handle_event(event)
        print(f"\n[Response]: {report.get('response')}")
        print(f"[Execution Status]: {report.get('status')}")

    elif scenario == "b":
        print("\n" + "=" * 65)
        print("SCENARIO B: Browser Automation (YouTube Playback)")
        print("=" * 65)
        from agents.browser_automation_agent import browser_automation_agent
        res = browser_automation_agent.play_youtube_song("synthwave radio beats")
        print(f"\n[Playback Result]:\n{res}")

    elif scenario == "c":
        print("\n" + "=" * 65)
        print("SCENARIO C: Calendar & Email Draft with Two-Gate Send Approval")
        print("=" * 65)
        from agents.calendar_agent import calendar_agent
        from agents.communication_agent import communication_agent
        from agents.identity_agent import identity_agent

        # 1. Read calendar
        cal = calendar_agent.get_upcoming_events(max_results=2)
        print(f"[Calendar Read]: {cal.get('events', 'Auth needed')}")

        # 2. Draft email
        draft = communication_agent.draft_email(
            to="meeting.partner@example.com",
            subject="Confirming Tomorrow's Meeting",
            body="Hi, confirming our scheduled discussion for tomorrow as planned."
        )
        print(f"[Email Draft]: {draft}")

        # 3. Two-Gate Approval check
        profile = identity_agent.owner_profile
        owner_emb = profile.get("face_embedding")

        send_res = communication_agent.send_email(
            to="meeting.partner@example.com",
            subject="Confirming Tomorrow's Meeting",
            body="Hi, confirming our scheduled discussion for tomorrow as planned.",
            user_confirmed=True,
            face_embedding=owner_emb
        )
        print(f"[Two-Gate Approved Send]: {send_res}")

    shutdown_all_layers()


def main():
    parser = argparse.ArgumentParser(description="JARVIS Assistant Runtime & Lifecycle")
    parser.add_argument("--start", action="store_true", help="Start all layers in order and enter interactive mode")
    parser.add_argument("--status", action="store_true", help="Display full system and persona status report")
    parser.add_argument("--check-secrets", action="store_true", help="Run secrets presence and module audit")
    parser.add_argument("--cli", action="store_true", help="Launch interactive chat session")
    parser.add_argument("--logs", action="store_true", help="Tail the last 40 lines of centralized logs")
    parser.add_argument("--learn", action="store_true", help="Run manual continuous learning cycle")
    parser.add_argument("--scenario", type=str, choices=["a", "b", "c"], help="Run integration scenario (a, b, or c)")

    args = parser.parse_args()

    if args.logs:
        lines = tail_logs(40)
        print("\n".join(lines))
    elif args.learn:
        init_all_layers()
        result = learning_engine.run_learning_cycle()
        print(f"\n[Continuous Learning Result]:\n{result}")
        shutdown_all_layers()
    elif args.scenario:
        asyncio.run(run_scenario(args.scenario))
    elif args.start or args.cli:
        init_all_layers()
        print(f"\nJARVIS Active ({settings.active_persona_name}). Enter commands or type 'exit' to quit.")
        try:
            while True:
                user_cmd = input(f"\n[{settings.active_persona_name}] > ").strip()
                if user_cmd.lower() in ["exit", "quit", "q"]:
                    break
                event = PerceptionEvent(
                    type="text_command",
                    payload={"raw_text": user_cmd},
                    source="text_input",
                    active_persona=settings.active_persona_name
                )
                report = orchestrator.handle_event(event)
                print(f"[{report.get('active_persona', settings.active_persona_name)}] {report.get('response')}")
        finally:
            shutdown_all_layers()
    else:
        init_all_layers()
        settings.check_secrets()
        shutdown_all_layers()


if __name__ == "__main__":
    main()
