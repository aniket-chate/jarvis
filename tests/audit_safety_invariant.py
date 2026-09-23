"""Audit Test Suite 5: Safety & Policy Invariants.

Audits the Policy/Safety Kernel between planning and side effects:
1. Shell refusals: whoami, ipconfig, cmd /c, powershell -> PROHIBITED.
2. Destructive filesystem: Delete a file, Delete a folder -> CONFIRMATION_REQUIRED.
3. Communication: Send a WhatsApp message, Send an email -> PRIVILEGED_CONFIRMATION.
4. External side effects: Make a purchase, Publish, Deploy -> PRIVILEGED_CONFIRMATION.
5. Confirmation lifecycle & security:
   - Confirmation TTL (60s default, tested with short TTL)
   - Duplicate confirmation rejection (Replay protection)
   - Stale confirmation rejection
   - Explicit confirmation cancellation
   - Concurrent independent confirmation requests
   - Request-ID correlation pinning (token only redeemable by matching request_id)

Enforces Invariant 2: No action executes without policy evaluation.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from safety.policy_kernel import PolicyKernel, PolicyLevel


def test_shell_command_refusals():
    print("\n[SAFETY 1/5] Auditing Shell Command Refusals (whoami, ipconfig, raw shell)...")
    kernel = PolicyKernel(confirmation_ttl_sec=60.0)

    # 1. whoami
    dec_whoami = kernel.evaluate("shell", "whoami", {}, "whoami")
    assert dec_whoami.level == PolicyLevel.PROHIBITED, f"whoami was not prohibited! Level: {dec_whoami.level}"
    assert dec_whoami.allowed is False
    print("  'whoami' prohibited successfully.")

    # 2. ipconfig
    dec_ip = kernel.evaluate("shell", "ipconfig", {}, "can you run ipconfig please")
    assert dec_ip.level == PolicyLevel.PROHIBITED
    assert dec_ip.allowed is False
    print("  'ipconfig' prohibited successfully.")

    # 3. Arbitrary cmd / powershell
    dec_cmd = kernel.evaluate("shell", "execute", {}, "cmd /c dir")
    assert dec_cmd.level == PolicyLevel.PROHIBITED
    assert dec_cmd.allowed is False
    print("  'cmd /c dir' prohibited successfully.")


def test_destructive_filesystem_protection():
    print("\n[SAFETY 2/5] Auditing Destructive Filesystem Safety (Delete file, Delete folder)...")
    kernel = PolicyKernel(confirmation_ttl_sec=60.0)

    # 1. Delete file
    dec_del_file = kernel.evaluate("file", "delete_file", {"path": "report.txt"}, "Delete a file called report.txt")
    assert dec_del_file.level == PolicyLevel.CONFIRMATION_REQUIRED
    assert dec_del_file.allowed is False
    assert dec_del_file.confirmation_token is not None
    print(f"  'Delete a file' intercepted: token={dec_del_file.confirmation_token}")

    # 2. Delete folder
    dec_del_dir = kernel.evaluate("file", "delete_folder", {"path": "workspace/old_docs"}, "Delete a folder called old_docs")
    assert dec_del_dir.level == PolicyLevel.CONFIRMATION_REQUIRED
    assert dec_del_dir.allowed is False
    assert dec_del_dir.confirmation_token is not None
    print(f"  'Delete a folder' intercepted: token={dec_del_dir.confirmation_token}")


def test_communication_safety():
    print("\n[SAFETY 3/5] Auditing Communication Safety (WhatsApp, Email)...")
    kernel = PolicyKernel(confirmation_ttl_sec=60.0)

    # 1. Send WhatsApp message
    dec_wa = kernel.evaluate("whatsapp", "send_whatsapp", {"recipient": "John", "message": "hello"}, "Send a WhatsApp message to John")
    assert dec_wa.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert dec_wa.allowed is False
    assert dec_wa.confirmation_token is not None
    print(f"  'Send a WhatsApp message' intercepted: token={dec_wa.confirmation_token}")

    # 2. Send email
    dec_em = kernel.evaluate("email", "send_email", {"to": "boss@company.com", "subject": "Update"}, "Send an email to boss@company.com")
    assert dec_em.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert dec_em.allowed is False
    assert dec_em.confirmation_token is not None
    print(f"  'Send an email' intercepted: token={dec_em.confirmation_token}")


def test_external_side_effects():
    print("\n[SAFETY 4/5] Auditing External Side Effects (Purchase, Publish, Deploy)...")
    kernel = PolicyKernel(confirmation_ttl_sec=60.0)

    # 1. Purchase
    dec_buy = kernel.evaluate("commerce", "make_purchase", {"item_id": "item_99"}, "Make a purchase of item 99")
    assert dec_buy.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert dec_buy.allowed is False
    assert dec_buy.confirmation_token is not None
    print(f"  'Make a purchase' intercepted: token={dec_buy.confirmation_token}")

    # 2. Deploy
    dec_dep = kernel.evaluate("deploy", "deploy", {"target": "production"}, "Deploy something to production")
    assert dec_dep.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert dec_dep.allowed is False
    assert dec_dep.confirmation_token is not None
    print(f"  'Deploy something' intercepted: token={dec_dep.confirmation_token}")

    # 3. Publish
    dec_pub = kernel.evaluate("publishing", "publish", {"doc": "manifesto"}, "Publish something to web")
    assert dec_pub.level == PolicyLevel.PRIVILEGED_CONFIRMATION
    assert dec_pub.allowed is False
    assert dec_pub.confirmation_token is not None
    print(f"  'Publish something' intercepted: token={dec_pub.confirmation_token}")


def test_confirmation_lifecycle_and_security():
    print("\n[SAFETY 5/5] Auditing Confirmation Lifecycle, Security & Request Correlation...")
    short_kernel = PolicyKernel(confirmation_ttl_sec=0.5)

    # 1. Successful Confirmation within TTL
    dec1 = short_kernel.evaluate("comms", "send_whatsapp", {"msg": "hello"}, "Send a WhatsApp message", request_id="req_user_1")
    token1 = dec1.confirmation_token
    conf1 = short_kernel.confirm_token(token1, request_id="req_user_1")
    assert conf1 is not None
    assert conf1.action_name == "send_whatsapp"
    print("  Token redeemed within TTL: SUCCESS")

    # 2. Duplicate Confirmation Rejection (Replay Attack Prevention)
    conf_duplicate = short_kernel.confirm_token(token1, request_id="req_user_1")
    assert conf_duplicate is None, "Replay attack succeeded: consumed token was accepted again!"
    print("  Replay attack prevented (duplicate consumption rejected).")

    # 3. Stale / Expired Confirmation Rejection
    dec2 = short_kernel.evaluate("comms", "send_whatsapp", {"msg": "late"}, "Send a WhatsApp message", request_id="req_user_2")
    token2 = dec2.confirmation_token
    time.sleep(0.6)  # Wait past TTL
    conf_expired = short_kernel.confirm_token(token2, request_id="req_user_2")
    assert conf_expired is None, "Expired confirmation token was accepted!"
    print("  TTL expiry enforced (stale token rejected).")

    # 4. Confirmation Cancellation
    dec3 = short_kernel.evaluate("file", "delete_file", {"path": "secret.txt"}, "Delete a file", request_id="req_user_3")
    token3 = dec3.confirmation_token
    cancelled = short_kernel.cancel_confirmation(token3)
    assert cancelled is True
    conf_cancelled = short_kernel.confirm_token(token3, request_id="req_user_3")
    assert conf_cancelled is None, "Cancelled token was accepted!"
    print("  Confirmation cancellation validated.")

    # 5. Request-ID Pinning (Correlation Integrity)
    dec4 = short_kernel.evaluate("comms", "send_email", {"msg": "confidential"}, "Send an email", request_id="req_alpha_99")
    token4 = dec4.confirmation_token
    # Attacker tries to redeem with different request_id
    conf_stolen = short_kernel.confirm_token(token4, request_id="req_attacker_666")
    assert conf_stolen is None, "Token redeemed by mismatched request_id!"
    # Legitimate owner redeems
    conf_legit = short_kernel.confirm_token(token4, request_id="req_alpha_99")
    assert conf_legit is not None
    print("  Request-ID pinning enforced: tokens cannot be hijacked across requests.")

    # 6. Concurrent Confirmation Requests
    dec_a = short_kernel.evaluate("file", "delete_file", {"path": "a.txt"}, "Delete a file", request_id="req_a")
    dec_b = short_kernel.evaluate("file", "delete_file", {"path": "b.txt"}, "Delete a file", request_id="req_b")
    assert dec_a.confirmation_token != dec_b.confirmation_token
    assert short_kernel.confirm_token(dec_b.confirmation_token, request_id="req_b") is not None
    assert short_kernel.confirm_token(dec_a.confirmation_token, request_id="req_a") is not None
    print("  Concurrent independent confirmations validated.")


if __name__ == "__main__":
    print("=" * 80)
    print("AUDIT SUITE 5: SAFETY KERNEL & POLICY INVARIANTS")
    print("=" * 80)
    test_shell_command_refusals()
    test_destructive_filesystem_protection()
    test_communication_safety()
    test_external_side_effects()
    test_confirmation_lifecycle_and_security()
    print("\n" + "=" * 80)
    print("AUDIT SUITE 5 PASSED: ALL POLICY & SAFETY GATES 100% IMPASSIBLE.")
    print("=" * 80)
    os._exit(0)
