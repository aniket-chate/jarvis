"""Architectural Verification Test: Policy & Safety Kernel Invariant."""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safety.policy_kernel import PolicyKernel, PolicyLevel


def test_safety_kernel_invariants():
    kernel = PolicyKernel(confirmation_ttl_sec=1.0)

    # 1. PROHIBITED: Arbitrary shell command
    dec_shell = kernel.evaluate("shell", "execute", {}, "can you execute ipconfig")
    assert dec_shell.level == PolicyLevel.PROHIBITED
    assert not dec_shell.allowed
    assert "Arbitrary shell command execution is prohibited" in dec_shell.reason

    # 2. PROHIBITED: Dangerous script creation
    dec_file = kernel.evaluate("file", "create", {"path": "C:\\Users\\acer\\dangerous_exec.bat"}, "create file dangerous_exec.bat")
    assert dec_file.level == PolicyLevel.PROHIBITED
    assert not dec_file.allowed
    assert "'.bat' is prohibited" in dec_file.reason

    # 3. PRIVILEGED CONFIRMATION: External communication
    dec_comms = kernel.evaluate("comms", "send_whatsapp", {"recipient": "sachin", "msg": "running late"}, "whats app sachin")
    assert dec_comms.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert not dec_comms.allowed
    assert dec_comms.confirmation_token is not None

    token = dec_comms.confirmation_token

    # 4. Token validation before expiry
    confirmed = kernel.confirm_token(token)
    assert confirmed is not None
    assert confirmed.action_name == "send_whatsapp"

    # 5. Token expiry test
    dec_comms2 = kernel.evaluate("comms", "send_whatsapp", {"recipient": "sachin"}, "whats app sachin")
    token2 = dec_comms2.confirmation_token
    time.sleep(1.1)  # Exceed TTL
    expired_confirmation = kernel.confirm_token(token2)
    assert expired_confirmation is None, "Expired confirmation token was accepted!"

    # 6. SAFE AUTOMATIC: Benign desktop telemetry
    dec_safe = kernel.evaluate("os", "telemetry", {}, "what is my cpu usage?")
    assert dec_safe.level == PolicyLevel.SAFE_AUTOMATIC
    assert dec_safe.allowed


if __name__ == "__main__":
    test_safety_kernel_invariants()
    print("ALL POLICY & SAFETY KERNEL INVARIANT TESTS PASSED CLEANLY!")
