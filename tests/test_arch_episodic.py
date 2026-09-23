"""Architectural Verification Test: 7-Tier Memory System & Episodic Recall."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from memory.system import memory_system


def test_seven_tier_memory():
    # 1. Working Memory: Pronoun binding
    memory_system.bind_pronoun("it", "active_factorial_code")
    assert memory_system.get_pronoun_binding("it") == "active_factorial_code"

    # 2. Episodic Memory: Recording verified physical events
    memory_system.record_episodic_action(
        request_id="req_test_01",
        persona="Friday",
        domain="browser",
        action="play_youtube",
        target="lofi study beats",
        status="completed",
        summary="Playing lofi study beats on YouTube"
    )

    # 3. Episodic Recall: Querying if action was done earlier
    was_done = memory_system.has_action_been_done("play_youtube", "lofi")
    assert was_done is True, "Episodic memory failed to recall past action!"

    was_not_done = memory_system.has_action_been_done("delete_database")
    assert was_not_done is False

    # 4. Truthful Session Summary
    summary = memory_system.get_truthful_session_summary()
    assert "lofi study beats" in summary.lower() or "youtube" in summary.lower()

    # 5. Semantic Memory: Fact query
    book = memory_system.query_fact("Aniket", "likes_book")
    assert book == "Mrutunjay"

    creator = memory_system.query_fact("Aniket", "creator_of")
    assert creator == "JARVIS"

    # 6. User Memory
    profile = memory_system.get_user_profile()
    assert profile.get("owner_name") == "Aniket"


if __name__ == "__main__":
    test_seven_tier_memory()
    print("ALL 7-TIER MEMORY & EPISODIC RECALL TESTS PASSED CLEANLY!")
