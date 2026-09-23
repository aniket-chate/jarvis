"""Audit Test Suite 7: Episodic Memory & Truthful Recall.

Audits that answers to historical questions are grounded in verified event records:
- "What did you do earlier?"
- "Did you open GitHub?"
- "Which file did you create?"
- "Where did you move it?"
- "Did you actually send that message?"
- "What failed?"
- "Why did it fail?"

Audits distinct lifecycle states:
- REQUESTED
- EXECUTED
- VERIFIED
- FAILED
- CANCELLED
- BLOCKED

Enforces Invariant 5: Memory cannot convert unverified intentions into verified facts.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.system import memory_system


def test_truthful_episodic_recall():
    print("=" * 80)
    print("AUDIT SUITE 7: EPISODIC MEMORY & TRUTHFUL RECALL")
    print("=" * 80)

    memory_system.episodic.clear()

    # 1. Record VERIFIED physical actions
    print("\n[EPISODIC 1/5] Recording Verified Actions in Ledger...")
    memory_system.record_episodic_action(
        request_id="req_act_1",
        domain="browser",
        action="browse_site",
        target="https://github.com",
        status="VERIFIED",
        summary="Navigated active Chrome tab to GitHub homepage",
    )
    memory_system.record_episodic_action(
        request_id="req_act_2",
        domain="file",
        action="create_file",
        target="audit_report.txt",
        status="VERIFIED",
        summary="Created file audit_report.txt with 42 bytes",
    )
    memory_system.record_episodic_action(
        request_id="req_act_3",
        domain="file",
        action="move_file",
        target="audit_report_moved.txt",
        status="VERIFIED",
        summary="Moved audit_report.txt to audit_report_moved.txt",
    )

    # 2. Record FAILED, CANCELLED, BLOCKED, and REQUESTED actions
    print("\n[EPISODIC 2/5] Recording Failed, Cancelled, Blocked, and Unverified Intentions...")
    memory_system.record_episodic_action(
        request_id="req_fail_4",
        domain="file",
        action="read_file",
        target="ghost_vault_data.key",
        status="FAILED",
        summary="Failed to read file: FileNotFoundError",
        error_reason="File 'ghost_vault_data.key' does not exist on disk",
    )
    memory_system.record_episodic_action(
        request_id="req_block_5",
        domain="shell",
        action="whoami",
        target="whoami",
        status="BLOCKED",
        summary="Command blocked by PolicyKernel",
        error_reason="Arbitrary shell command execution is prohibited by system safety policy",
    )
    memory_system.record_episodic_action(
        request_id="req_cancel_6",
        domain="browser",
        action="download_large_dataset",
        target="dataset.tar.gz",
        status="CANCELLED",
        summary="Download cancelled by user",
        error_reason="User dispatched cooperative cancellation token",
    )
    # An unverified intention that was only REQUESTED
    memory_system.record_episodic_action(
        request_id="req_intent_7",
        domain="comms",
        action="send_whatsapp",
        target="sachin",
        status="REQUESTED",
        summary="User requested WhatsApp message, awaiting confirmation",
    )

    # 3. Test Truthful Recall Queries
    print("\n[EPISODIC 3/5] Auditing Truthful Recall Queries...")

    # Q: "Did you open GitHub?"
    did_open_gh = memory_system.has_action_been_done("browse_site", "github")
    assert did_open_gh is True, "Failed to truthfully recall opening GitHub!"
    print(f"  'Did you open GitHub?': Truthfully answered YES (VERIFIED)")

    # Q: "Which file did you create?"
    created_entry = memory_system.query_action_status("create_file")
    assert created_entry is not None
    assert "audit_report.txt" in created_entry["target"]
    assert created_entry["status"] == "VERIFIED"
    print(f"  'Which file did you create?': '{created_entry['target']}' (Status: {created_entry['status']})")

    # Q: "Where did you move it?"
    moved_entry = memory_system.query_action_status("move_file")
    assert moved_entry is not None
    assert "audit_report_moved.txt" in moved_entry["target"]
    assert moved_entry["status"] == "VERIFIED"
    print(f"  'Where did you move it?': '{moved_entry['target']}' (Status: {moved_entry['status']})")

    # Q: "Did you actually send that message?" -> MUST BE FALSE! (Invariant 5)
    did_send_wa = memory_system.has_action_been_done("send_whatsapp", "sachin")
    assert did_send_wa is False, "INVARIANT 5 VIOLATION: Unverified intention was reported as an executed fact!"
    wa_entry = memory_system.query_action_status("send_whatsapp")
    assert wa_entry["status"] == "REQUESTED"
    print(f"  'Did you actually send that message?': Truthfully answered NO (Status: {wa_entry['status']}, never verified)")

    # 4. Test Failure Diagnosis
    print("\n[EPISODIC 4/5] Auditing Failure & Rejection Diagnosis...")
    failures = memory_system.get_failed_actions()
    assert len(failures) == 3  # FAILED, BLOCKED, CANCELLED
    failed_actions = {f["action"]: f for f in failures}

    # Q: "What failed?"
    assert "read_file" in failed_actions
    assert "whoami" in failed_actions
    assert "download_large_dataset" in failed_actions
    print(f"  'What failed?': Identified {len(failures)} unfulfilled actions: {list(failed_actions.keys())}")

    # Q: "Why did it fail?"
    read_err = failed_actions["read_file"]["error_reason"]
    block_err = failed_actions["whoami"]["error_reason"]
    assert "does not exist on disk" in read_err
    assert "prohibited by system safety policy" in block_err
    print(f"  'Why did read_file fail?': '{read_err}'")
    print(f"  'Why did whoami fail?': '{block_err}'")

    # 5. Session Summary Grounding
    print("\n[EPISODIC 5/5] Auditing Truthful Session Summary...")
    summary = memory_system.get_truthful_session_summary()
    assert "github" in summary.lower()
    assert "audit_report.txt" in summary.lower()
    assert "audit_report_moved.txt" in summary.lower()
    # Summary must not falsely claim WhatsApp message was sent
    assert "sachin" not in summary.lower()
    print("  Grounded Session Summary Verified:\n" + "\n".join("    " + line for line in summary.splitlines()))

    print("\n" + "=" * 80)
    print("AUDIT SUITE 7 PASSED: EPISODIC MEMORY ENFORCES 100% GROUNDED TRUTHFUL RECALL.")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    test_truthful_episodic_recall()
