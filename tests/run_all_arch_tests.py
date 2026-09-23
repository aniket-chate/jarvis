"""Master Architectural Verification Suite Runner.

Executes all 11 architectural phase test suites in sequence.
Guarantees full system invariants:
- Concurrency & cancellation
- Context & pronoun resolution
- Cognitive Core dual-process routing
- Capability Intelligence & provider replaceability
- Policy & Safety Two-Gate invariant
- Execution Kernel isolation & timeouts
- Observation & empirical verification
- 7-Tier Memory & episodic recall
- Autonomous Runtime & Agency
- Experience-Driven Learning & RL
- Observability & Distributed Tracing
"""

import subprocess
import sys
from pathlib import Path

TESTS = [
    "test_arch_concurrency.py",
    "test_arch_context.py",
    "test_arch_cognitive_core.py",
    "test_arch_providers.py",
    "test_arch_safety.py",
    "test_arch_execution.py",
    "test_arch_verification.py",
    "test_arch_episodic.py",
    "test_arch_autonomy.py",
    "test_arch_learning.py",
    "test_arch_observability.py",
]

def main():
    test_dir = Path(__file__).parent
    python_exe = sys.executable
    failed = []

    print("=" * 80)
    print("STARTING FULL ARCHITECTURAL VERIFICATION SUITE (ALL 12 PHASES)")
    print("=" * 80)

    for test_file in TESTS:
        test_path = test_dir / test_file
        print(f"\n[RUNNING] {test_file} ...")
        res = subprocess.run([python_exe, str(test_path)], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"[PASSED] {test_file}")
            for line in res.stdout.strip().splitlines()[-3:]:
                print(f"   {line}")
        else:
            print(f"[FAILED] {test_file} (code {res.returncode})")
            print("STDOUT:\n", res.stdout)
            print("STDERR:\n", res.stderr)
            failed.append(test_file)

    print("\n" + "=" * 80)
    if not failed:
        print(f"ALL {len(TESTS)} ARCHITECTURAL PHASES VERIFIED SUCCESSFULLY! 100% PASS.")
    else:
        print(f"FAILURES DETECTED in: {failed}")
    print("=" * 80)
    sys.exit(len(failed))

if __name__ == "__main__":
    main()
