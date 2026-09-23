"""Architectural Verification Test: Distributed Cognitive Tracing & Observability."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from observability.tracer import cognitive_tracer


def test_cognitive_trace_reconstruction():
    req_id = "req_trace_test_001"
    cognitive_tracer.start_trace(req_id)

    # 1. Record understanding span
    cognitive_tracer.record_span(
        req_id,
        "understanding",
        inputs={"utterance": "play lofi music"},
        outputs={"domain": "browser", "action": "play_youtube", "target": "lofi music"},
        duration_ms=12.0,
    )

    # 2. Record reasoning & goal
    cognitive_tracer.record_span(
        req_id,
        "reasoning",
        inputs={"intent": "play_youtube"},
        outputs={"deduction": "User requested media entertainment"},
        duration_ms=5.0,
    )
    cognitive_tracer.record_span(
        req_id,
        "goal",
        inputs={"goal": "play lofi"},
        outputs={"goal": "Search YouTube for lofi and start playback"},
    )

    # 3. Record capability selection
    cognitive_tracer.record_span(
        req_id,
        "capability",
        inputs={"capability": "browser.playback"},
        outputs={"provider": "provider.browser.chrome_cdp"},
    )

    # 4. Record policy decision
    cognitive_tracer.record_span(
        req_id,
        "policy",
        inputs={"capability": "browser.playback"},
        outputs={"level": "safe_automatic", "allowed": True},
    )

    # 5. Record execution & verification
    cognitive_tracer.record_span(
        req_id,
        "execution",
        inputs={"action": "play_youtube"},
        outputs={"action": "Started playback in Chrome"},
        duration_ms=180.0,
    )
    cognitive_tracer.record_span(
        req_id,
        "observation",
        inputs={"target": "chrome_cdp"},
        outputs={"observed": "YouTube video playing at 1080p"},
    )
    cognitive_tracer.record_span(
        req_id,
        "verification",
        inputs={"expected": "playing"},
        outputs={"status": "SUCCESS"},
    )

    # 6. Record learning
    cognitive_tracer.record_span(
        req_id,
        "learning",
        inputs={"result": "SUCCESS"},
        outputs={"reward": 1.0},
    )

    # Reconstruct narrative
    narrative = cognitive_tracer.get_narrative(req_id)
    assert narrative is not None
    assert narrative["what_jarvis_understood"]["domain"] == "browser"
    assert narrative["why_reasoning"] == "User requested media entertainment"
    assert narrative["capability_selected"] == "provider.browser.chrome_cdp"
    assert narrative["policy_decision"] == "safe_automatic"
    assert narrative["world_change_observed"] == "YouTube video playing at 1080p"
    assert narrative["verification_outcome"] == "SUCCESS"
    assert narrative["learning_outcome"] == 1.0


if __name__ == "__main__":
    test_cognitive_trace_reconstruction()
    print("ALL OBSERVABILITY & COGNITIVE TRACING TESTS PASSED CLEANLY!")
