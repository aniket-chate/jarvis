"""JARVIS Pre-Capability Architecture Integration & Regression Audit Master Runner.

Executes all 13 comprehensive Pre-Capability Audit Suites and tabulates pass/fail statistics.
"""

import sys
import subprocess
import time
from pathlib import Path

AUDIT_SUITES = [
    "tests/audit_concurrency_stress.py",
    "tests/audit_context_resolution.py",
    "tests/audit_world_model_reality.py",
    "tests/audit_verification.py",
    "tests/audit_safety_invariant.py",
    "tests/audit_autonomy.py",
    "tests/audit_episodic_recall.py",
    "tests/audit_multi_intent_recovery.py",
    "tests/audit_checkpoint_recovery.py",
    "tests/audit_provider_replaceability.py",
    "tests/audit_security_injection.py",
    "tests/audit_invariants.py",
    "tests/audit_10_scenarios.py",
]

def main():
    root = Path(__file__).resolve().parent.parent
    python_exe = sys.executable

    print("=" * 80)
    print("STARTING FULL PRE-CAPABILITY ARCHITECTURAL AUDIT (ALL 13 SUITES)")
    print("=" * 80)

    results = []
    total_start = time.time()

    for suite in AUDIT_SUITES:
        suite_path = root / suite
        print(f"\n[RUNNING AUDIT SUITE] {suite} ...")
        t0 = time.time()
        res = subprocess.run([python_exe, str(suite_path)], cwd=str(root), capture_output=True, text=True)
        duration = time.time() - t0

        if res.returncode == 0:
            print(f"[AUDIT PASSED] {suite} ({duration:.2f}s)")
            results.append((suite, "PASSED", duration, ""))
        else:
            print(f"[AUDIT FAILED] {suite} ({duration:.2f}s)")
            print(res.stdout[-600:])
            print(res.stderr[-600:])
            results.append((suite, "FAILED", duration, res.stderr or res.stdout))

    total_duration = time.time() - total_start
    passed_count = sum(1 for _, status, _, _ in results if status == "PASSED")
    failed_count = sum(1 for _, status, _, _ in results if status == "FAILED")

    print("\n" + "=" * 80)
    print(f"PRE-CAPABILITY AUDIT COMPLETE: {passed_count}/{len(results)} SUITES PASSED in {total_duration:.2f}s")
    print("=" * 80)

    for suite, status, dur, _ in results:
        indicator = "[PASS]" if status == "PASSED" else "[FAIL]"
        print(f"  {indicator} {suite:<45} : {status} ({dur:.2f}s)")

    if failed_count > 0:
        print(f"\nAUDIT HAS FAILED SUITES ({failed_count}). CANNOT DECLARE READY.")
        sys.exit(1)
    else:
        print("\nALL PRE-CAPABILITY AUDIT SUITES PASSED WITH 100% SUCCESS.")
        sys.exit(0)

if __name__ == "__main__":
    main()
