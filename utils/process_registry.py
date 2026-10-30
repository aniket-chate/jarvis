"""Track only subprocesses created and owned by JARVIS.

User-requested desktop applications and externally managed services must not be
registered here, so shutting down JARVIS never terminates unrelated programs.
"""

import logging
import subprocess
import threading
from typing import List

logger = logging.getLogger("JARVIS.ProcessRegistry")
CHILD_PROCESSES: List[subprocess.Popen] = []
_LOCK = threading.RLock()


def register_child_process(
    process: subprocess.Popen,
    *,
    reap_on_exit: bool = False,
) -> subprocess.Popen:
    """Register a JARVIS-owned child process and optionally reap it when it exits."""
    if process is None:
        return process

    with _LOCK:
        if process.poll() is None and process not in CHILD_PROCESSES:
            CHILD_PROCESSES.append(process)

    if reap_on_exit:
        def _reap() -> None:
            try:
                process.wait()
            except Exception:
                logger.debug("Child process watcher ended (%s).", type(process).__name__)
            finally:
                with _LOCK:
                    if process in CHILD_PROCESSES:
                        CHILD_PROCESSES.remove(process)

        threading.Thread(
            target=_reap,
            name="jarvis-child-reaper",
            daemon=True,
        ).start()

    return process


def terminate_registered_processes(timeout_seconds: float = 3.0) -> None:
    """Stop only explicitly registered JARVIS-owned children."""
    with _LOCK:
        children = list(CHILD_PROCESSES)

    for child in children:
        try:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=timeout_seconds)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=timeout_seconds)
            logger.info("Stopped registered JARVIS child (pid=%s).", child.pid)
        except Exception as exc:
            logger.warning(
                "Could not stop registered JARVIS child (%s).",
                type(exc).__name__,
            )
        finally:
            with _LOCK:
                if child in CHILD_PROCESSES:
                    CHILD_PROCESSES.remove(child)
