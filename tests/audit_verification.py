"""Audit Test Suite 4: Action -> Observation -> Verification.

Audits that every major action category grounds success in observed reality:
1. File: Move file (Source absent + destination present), create file, delete file.
2. Anti-False-Success Invariant: Provider claims SUCCESS, but physical reality absent -> Rejected!
3. Git: Branch observation matches real Git HEAD.
4. Window: Snap window verifies active window coordinates.
5. Application: Process observation verifies real running process vs ghost process.

Enforces Invariant 3: No important action is considered successful without verification.
Enforces Invariant 10: A failed action must never be reported as successful.
"""

import asyncio
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verification.verifier import observation_verification_kernel
from execution.runtime import execution_kernel, StepState
from capabilities.intelligence import capability_intelligence
from capabilities.base import BaseCapabilityProvider, ProviderMetadata, ActionResult
import capabilities.providers  # Register default providers


def test_file_action_observation_and_verification():
    print("\n[VERIFY 1/5] Auditing File Reality Verification (Create, Move, Delete)...")
    ws = Path(r"d:\assignment\JARVIS\workspace")
    ws.mkdir(parents=True, exist_ok=True)
    
    src = ws / "audit_src_test.txt"
    dst = ws / "audit_dst_test.txt"
    
    if src.exists():
        src.unlink()
    if dst.exists():
        dst.unlink()

    # 1. Create file and verify
    src.write_text("Audit verification test content", encoding="utf-8")
    rep_create = observation_verification_kernel.observe_and_verify(
        capability="file.create",
        expected_state={"exists": True},
        parameters={"path": str(src)},
    )
    assert rep_create.status == "SUCCESS", f"File creation verification failed: {rep_create.evidence}"
    print(f"  File creation verified: {rep_create.evidence}")

    # 2. Move file and verify: Source absent + destination present
    src.rename(dst)
    rep_move = observation_verification_kernel.observe_and_verify(
        capability="file.move",
        expected_state={"source_absent": True, "destination_present": True},
        parameters={"source_path": str(src), "destination_path": str(dst)},
    )
    assert rep_move.status == "SUCCESS", f"File move verification failed: {rep_move.evidence}"
    assert rep_move.actual_state["source_exists"] is False
    assert rep_move.actual_state["dest_exists"] is True
    print(f"  File move verified: {rep_move.evidence}")

    # 3. Delete file and verify: Target absent
    dst.unlink()
    rep_del = observation_verification_kernel.observe_and_verify(
        capability="file.delete",
        expected_state={"exists": False},
        parameters={"path": str(dst)},
    )
    assert rep_del.status == "SUCCESS", f"File delete verification failed: {rep_del.evidence}"
    print(f"  File deletion verified: {rep_del.evidence}")


def test_anti_false_success_invariant():
    print("\n[VERIFY 2/5] Auditing Anti-False-Success Invariant (Provider claims SUCCESS, Reality Absent)...")
    
    # Register a rogue/lying mock provider that always claims SUCCESS without doing work
    class RogueLyingProvider(BaseCapabilityProvider):
        def __init__(self):
            super().__init__(
                ProviderMetadata(
                    provider_id="provider.file.rogue_liar",
                    name="Rogue Lying File Provider",
                    supported_capabilities=["file.create"],
                    priority=999,  # High priority to get selected
                )
            )
        def is_available(self) -> bool:
            return True
        def execute(self, capability, parameters, context=None):
            # Lie: claim success without creating the file
            return ActionResult(status="SUCCESS", output="File created successfully!", message="Lying success")

    rogue = RogueLyingProvider()
    capability_intelligence.register_provider(rogue)

    ghost_file = Path(r"d:\assignment\JARVIS\workspace\ghost_should_never_exist_123.txt")
    if ghost_file.exists():
        ghost_file.unlink()

    job = execution_kernel.create_job(
        request_id="req_audit_lie_test",
        goal="Create ghost file",
        steps=[{
            "capability": "file.create",
            "parameters": {"path": str(ghost_file)},
            "timeout_sec": 5.0,
            "retry_limit": 1,
        }]
    )

    result = asyncio.run(execution_kernel.run_job(job))
    
    # Invariant: Must NOT report success!
    assert result["status"] == "failed", f"ExecutionKernel falsely reported success for unverified action! Result: {result}"
    assert job.steps[0].state == StepState.FAILED
    print("  Anti-False-Success Invariant ENFORCED: Lying provider rejected by Verification Kernel.")

    # Unregister rogue provider
    capability_intelligence.unregister_provider(rogue.provider_id)


def test_git_reality_verification():
    print("\n[VERIFY 3/5] Auditing Git Branch Observation & Verification...")
    rep_git = observation_verification_kernel.observe_and_verify(
        capability="git.branch_management",
        expected_state={"branch": "master"},
        parameters={"branch_name": "master"},
    )
    assert rep_git.status == "SUCCESS", f"Git branch verification failed: {rep_git.evidence}"
    assert rep_git.actual_state["branch"] == "master"
    print(f"  Git branch verified: {rep_git.evidence}")


def test_os_window_and_process_verification():
    print("\n[VERIFY 4/5] Auditing OS Window & Process Reality Verification...")
    # Process verification
    rep_proc = observation_verification_kernel.observe_and_verify(
        capability="os.launch_app",
        expected_state={"process_running": True},
        parameters={"process_name": "python"},
    )
    assert rep_proc.status == "SUCCESS", f"Process verification failed: {rep_proc.evidence}"
    assert rep_proc.actual_state["is_running"] is True
    print(f"  Process reality verified: {rep_proc.evidence}")

    # Ghost process verification -> MUST FAIL
    rep_ghost = observation_verification_kernel.observe_and_verify(
        capability="os.launch_app",
        expected_state={"process_running": True},
        parameters={"process_name": "ghost_process_definitely_not_running_404"},
    )
    assert rep_ghost.status == "FAILED", "Non-existent process was falsely verified as running!"
    print(f"  Ghost process correctly detected as FAILED: {rep_ghost.evidence}")

    # Window snap verification
    rep_win = observation_verification_kernel.observe_and_verify(
        capability="os.snap_window",
        expected_state={"direction": "left"},
        parameters={"direction": "left"},
    )
    assert rep_win.status == "SUCCESS", f"Window snap verification failed: {rep_win.evidence}"
    print(f"  Window state verified: {rep_win.evidence}")


def test_browser_reality_verification():
    print("\n[VERIFY 5/5] Auditing Browser Reality Verification...")
    rep_tab = observation_verification_kernel.observe_and_verify(
        capability="browser.tab_control",
        expected_state={"tab_absent": True},
        parameters={"tab_id": "non_existent_tab_id_xyz"},
    )
    assert rep_tab.status == "SUCCESS"
    print(f"  Browser tab absence verified: {rep_tab.evidence}")


if __name__ == "__main__":
    print("=" * 80)
    print("AUDIT SUITE 4: ACTION -> OBSERVATION -> EMPIRICAL VERIFICATION")
    print("=" * 80)
    test_file_action_observation_and_verification()
    test_anti_false_success_invariant()
    test_git_reality_verification()
    test_os_window_and_process_verification()
    test_browser_reality_verification()
    print("\n" + "=" * 80)
    print("AUDIT SUITE 4 PASSED: ZERO FALSE-SUCCESS TOLERANCE & EMPIRICAL VERIFICATION VALIDATED.")
    print("=" * 80)
    os._exit(0)
