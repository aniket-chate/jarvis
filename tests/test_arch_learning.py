"""Architectural Verification Test: Experience-Driven Learning Architecture."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from learning_system.experience_store import ExperienceStore, ExperienceEvaluator


def test_experience_learning_pipeline(tmp_path):
    # Use temporary file to avoid polluting permanent storage during test
    test_file = Path(r"d:\assignment\JARVIS\memory\test_experience_ledger.json")
    if test_file.exists():
        test_file.unlink()

    store = ExperienceStore(storage_path=test_file)
    evaluator = ExperienceEvaluator(store)

    # 1. Record experiences for provider A (3 successes, 1 failure)
    store.record_experience("r1", "play music", "browser.playback", "provider.browser.chrome", "SUCCESS", 120.0, 1.0)
    store.record_experience("r2", "play music", "browser.playback", "provider.browser.chrome", "SUCCESS", 140.0, 1.0)
    store.record_experience("r3", "play music", "browser.playback", "provider.browser.chrome", "SUCCESS", 110.0, 1.0)
    store.record_experience("r4", "play music", "browser.playback", "provider.browser.chrome", "FAILED", 800.0, -1.0)

    # 2. Evaluate performance
    perf = evaluator.evaluate_provider_performance("provider.browser.chrome")
    assert perf["sample_count"] == 4
    assert perf["reliability"] == 0.75
    assert perf["avg_latency_ms"] > 0

    # Cleanup
    if test_file.exists():
        test_file.unlink()


if __name__ == "__main__":
    test_experience_learning_pipeline(None)
    print("ALL EXPERIENCE-DRIVEN LEARNING ARCHITECTURAL TESTS PASSED CLEANLY!")
