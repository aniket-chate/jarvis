"""Architectural Verification Test: Observation & Empirical Verification."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from verification.verifier import observation_verification_kernel
from cognitive.world_model import world_model


def test_empirical_verification_accuracy():
    # 1. Test verification of a non-existent file -> MUST return FAILED
    fake_path = r"C:\Users\acer\Desktop\non_existent_file_xyz_9999.txt"
    report_fail = observation_verification_kernel.observe_and_verify(
        capability="file.create",
        expected_state={"exists": True},
        parameters={"path": fake_path},
    )
    assert report_fail.status == "FAILED", "Non-existent file was incorrectly marked as successful!"
    assert report_fail.retry_recommended is True

    # 2. Test verification of an existing file (README.md) -> MUST return SUCCESS
    real_path = r"d:\assignment\JARVIS\.env"
    report_success = observation_verification_kernel.observe_and_verify(
        capability="file.read",
        expected_state={"exists": True},
        parameters={"path": real_path},
    )
    assert report_success.status == "SUCCESS"
    assert report_success.confidence == 1.0
    assert "exists=True" in report_success.evidence

    # 3. Test git branch verification
    report_git = observation_verification_kernel.observe_and_verify(
        capability="git.branch_management",
        expected_state={"branch": "for"},
        parameters={"branch_name": "for"},
    )
    assert report_git.status in ["SUCCESS", "PARTIAL"]
    assert report_git.actual_state.get("branch") is not None

    # 4. Verify World Model was updated with Git state
    assert world_model.state.active_git_branch is not None


if __name__ == "__main__":
    test_empirical_verification_accuracy()
    print("ALL OBSERVATION & EMPIRICAL VERIFICATION TESTS PASSED CLEANLY!")
