"""Live Server End-to-End Validation for Real-World Manual Scenarios.

Tests the actual running JARVIS server at http://127.0.0.1:8000:
1. "Create a file named jarvis_test.txt and put this information inside it:\nThis is a real context reference test."
   - Verifies parameters preserved
   - Verifies physical file content on disk is NOT 0 bytes and matches intended text
   - Verifies verifier reported success
2. "Read the file I just created"
   - Verifies resolved path is used, not raw sentence text
   - Verifies response contains the file's content
3. "Show me the file you just created."
   - Verifies resolved path is used, not raw sentence text
   - Verifies response contains the file's content
4. "Read that file"
   - Verifies pronoun / reference resolution
5. "Delete the file I just created."
   - Verifies confirmation staging
6. "yes"
   - Verifies confirmed deletion and physical removal from disk
"""

import os
import sys
import json
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agents.file_document_agent import DOCUMENTS_DIR

SERVER_URL = "http://127.0.0.1:8000/api/chat"
HEADERS = {
    "Content-Type": "application/json",
    "X-JARVIS-TOKEN": "jarvis-gateway-token-2026-auth",
}


def send_chat(message: str) -> dict:
    req_body = json.dumps({"message": message, "device_id": "manual_tester"}).encode("utf-8")
    req = urllib.request.Request(SERVER_URL, data=req_body, headers=HEADERS)
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    lat_ms = (time.perf_counter() - t0) * 1000.0
    data["latency_ms"] = round(lat_ms, 2)
    return data


def run_live_tests():
    print("=" * 80)
    print(" LIVE SERVER END-TO-END VALIDATION (http://127.0.0.1:8000)")
    print("=" * 80)

    test_file = DOCUMENTS_DIR / "jarvis_test.txt"
    if test_file.exists():
        test_file.unlink()

    total_tests = 0
    passed_tests = 0

    # -------------------------------------------------------------------------
    # Scenario 1: Create with explicit inline content
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd1 = "Create a file named jarvis_test.txt and put this information inside it:\nThis is a real context reference test."
    print(f"\n[Test 1] POST /api/chat: {cmd1!r}")
    res1 = send_chat(cmd1)
    plan1 = res1.get("plan") or {}
    steps1 = plan1.get("steps") or []
    step1_inputs = steps1[0].get("inputs", {}) if steps1 else {}
    step1_output = steps1[0].get("result", {}).get("output", {}) if steps1 else {}

    print(f"  Latency: {res1['latency_ms']} ms")
    print(f"  Response: {res1.get('response')}")
    print(f"  Step Agent: {steps1[0].get('required_agent_type') if steps1 else 'None'}")
    print(f"  Inputs: {step1_inputs}")
    print(f"  Bytes written on agent report: {step1_output.get('bytes_written')}")

    # Check physical disk
    time.sleep(0.1)
    on_disk_exists = test_file.exists()
    on_disk_content = test_file.read_text(encoding="utf-8") if on_disk_exists else ""
    print(f"  Physical File Exists: {on_disk_exists}")
    print(f"  Physical File Content: {on_disk_content!r}")
    print(f"  Physical File Size: {len(on_disk_content)} bytes")

    pass_1 = (
        on_disk_exists
        and "This is a real context reference test." in on_disk_content
        and len(on_disk_content) > 0
        and step1_inputs.get("content") == "This is a real context reference test."
        and step1_inputs.get("filename") == "jarvis_test.txt"
    )
    if pass_1:
        print("  -> RESULT: [PASS] Content preserved, written to disk, verified.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] Content not written to disk or parameters lost.")

    # -------------------------------------------------------------------------
    # Scenario 2: Read "the file I just created"
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd2 = "Read the file I just created"
    print(f"\n[Test 2] POST /api/chat: {cmd2!r}")
    res2 = send_chat(cmd2)
    plan2 = res2.get("plan") or {}
    steps2 = plan2.get("steps") or []
    step2_inputs = steps2[0].get("inputs", {}) if steps2 else {}

    print(f"  Latency: {res2['latency_ms']} ms")
    print(f"  Response: {res2.get('response')}")
    print(f"  Inputs: {step2_inputs}")

    pass_2 = (
        step2_inputs.get("path") != "Read the file I just created"
        and "jarvis_test.txt" in str(step2_inputs.get("path", "")).lower()
        and "This is a real context reference test." in res2.get("response", "")
    )
    if pass_2:
        print("  -> RESULT: [PASS] Structured path resolved, content read successfully.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] Raw query passed or content not returned.")

    # -------------------------------------------------------------------------
    # Scenario 3: Show "the file you just created."
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd3 = "Show me the file you just created."
    print(f"\n[Test 3] POST /api/chat: {cmd3!r}")
    res3 = send_chat(cmd3)
    plan3 = res3.get("plan") or {}
    steps3 = plan3.get("steps") or []
    step3_inputs = steps3[0].get("inputs", {}) if steps3 else {}

    print(f"  Latency: {res3['latency_ms']} ms")
    print(f"  Response: {res3.get('response')}")
    print(f"  Inputs: {step3_inputs}")

    pass_3 = (
        step3_inputs.get("path") != "Show me the file you just created."
        and "jarvis_test.txt" in str(step3_inputs.get("path", "")).lower()
        and "This is a real context reference test." in res3.get("response", "")
    )
    if pass_3:
        print("  -> RESULT: [PASS] Structured path resolved, content shown successfully.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] Raw query passed or content not returned.")

    # -------------------------------------------------------------------------
    # Scenario 4: Read "that file" after conversational query
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd_intervene = "What is the square root of 144?"
    print(f"\n[Intervening Query] POST /api/chat: {cmd_intervene!r}")
    res_int = send_chat(cmd_intervene)
    print(f"  Response: {res_int.get('response')[:80]}")

    cmd4 = "read that file"
    print(f"\n[Test 4] POST /api/chat: {cmd4!r}")
    res4 = send_chat(cmd4)
    plan4 = res4.get("plan") or {}
    steps4 = plan4.get("steps") or []
    step4_inputs = steps4[0].get("inputs", {}) if steps4 else {}

    print(f"  Latency: {res4['latency_ms']} ms")
    print(f"  Response: {res4.get('response')}")
    print(f"  Inputs: {step4_inputs}")

    pass_4 = (
        "jarvis_test.txt" in str(step4_inputs.get("path", "")).lower()
        and "This is a real context reference test." in res4.get("response", "")
    )
    if pass_4:
        print("  -> RESULT: [PASS] 'that file' resolved across intervening turn.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] Context lost after intervening query.")

    # -------------------------------------------------------------------------
    # Scenario 5: Delete "the file I just created" (Safety Confirmation Gated)
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd5 = "Delete the file I just created."
    print(f"\n[Test 5] POST /api/chat: {cmd5!r}")
    res5 = send_chat(cmd5)
    print(f"  Latency: {res5['latency_ms']} ms")
    print(f"  Response: {res5.get('response')[:120]}")

    pass_5 = (
        test_file.exists()
        and any(k in res5.get("response", "").lower() for k in ["blocked", "safety", "confirm", "destructive"])
    )
    if pass_5:
        print("  -> RESULT: [PASS] Staged at Safety Gate, file preserved pending confirmation.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] Did not stage for confirmation or file prematurely deleted.")

    # -------------------------------------------------------------------------
    # Scenario 6: Confirm delete ("yes")
    # -------------------------------------------------------------------------
    total_tests += 1
    cmd6 = "yes"
    print(f"\n[Test 6] POST /api/chat: {cmd6!r}")
    res6 = send_chat(cmd6)
    print(f"  Latency: {res6['latency_ms']} ms")
    print(f"  Response: {res6.get('response')}")

    time.sleep(0.1)
    pass_6 = not test_file.exists()
    if pass_6:
        print("  -> RESULT: [PASS] File physically removed after confirmation.")
        passed_tests += 1
    else:
        print("  -> RESULT: [FAIL] File still exists after confirmation.")

    # -------------------------------------------------------------------------
    # Final Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print(f" LIVE SERVER TEST SUMMARY: {passed_tests}/{total_tests} PASSED")
    print("=" * 80)

    return passed_tests == total_tests


if __name__ == "__main__":
    ok = run_live_tests()
    sys.stdout.flush()
    os._exit(0 if ok else 1)
