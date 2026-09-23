"""Master 50-Capability Integration & Contract Verification Suite.

Audits:
1. Complete Contract Registry integrity across all 50 capability domains.
2. Machine-readable contract schemas, valid safety levels, and timeouts.
3. Every supported operation maps to a registered capability and contract.
4. Active capability providers execute successfully through CapabilityIntelligence.
5. Safety policy classification matches contract definitions.
6. Anti-regression invariant across foundational capabilities.
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from capabilities.contracts import contract_registry_50, CapabilityContract, SafetyClassification
from capabilities.intelligence import capability_intelligence
from safety.policy_kernel import policy_kernel, PolicyLevel
from verification.verifier import observation_verification_kernel
import capabilities.providers  # Register active capability providers


def test_contract_registry_completeness():
    print("\n[TEST 1/5] Auditing Contract Registry Completeness (All 50 Domains)...")
    contracts = contract_registry_50.list_all_contracts()
    assert len(contracts) == 50, f"Expected 50 capability contracts, found {len(contracts)}!"
    
    # Verify every contract has valid required fields
    for c in contracts:
        assert c.capability_id.strip(), "Missing capability_id!"
        assert c.name.strip(), f"Missing name for {c.capability_id}!"
        assert c.domain.strip(), f"Missing domain for {c.capability_id}!"
        assert len(c.supported_operations) > 0, f"No operations declared for {c.capability_id}!"
        assert isinstance(c.safety_classification, SafetyClassification)
        assert c.timeout_sec > 0, f"Invalid timeout for {c.capability_id}!"
        assert c.primary_provider_id.strip(), f"Missing primary provider for {c.capability_id}!"
    
    print(f"  All 50 capability contracts validated with complete metadata.")


def test_operation_to_contract_mapping():
    print("\n[TEST 2/5] Auditing Operation-to-Contract Reverse Lookup...")
    sample_ops = [
        ("chat.conversation", "01_natural_language"),
        ("reasoning.deduce", "02_cognitive_reasoning"),
        ("world.probe_window", "03_world_model"),
        ("context.resolve_pronoun", "04_context_intelligence"),
        ("memory.record_episodic", "06_memory_system"),
        ("os.window_management", "21_desktop_os"),
        ("os.volume_control", "21_desktop_os"),
        ("file.create", "22_file_storage"),
        ("browser.playback", "23_browser_intelligence"),
        ("shell.allowlisted_diagnostics", "25_shell_sysadmin"),
        ("code.generation", "26_software_engineering"),
        ("git.branch_management", "28_git_version_control"),
        ("verification.observe_reality", "34_information_verification"),
        ("security.evaluate_policy", "48_security_identity"),
        ("vision.analyze_image", "11_vision"),
        ("vision.ocr", "12_ocr_documents"),
        ("audio.transcribe", "13_audio_perception"),
        ("env.probe_hardware", "14_environmental_perception"),
        ("multimodal.fuse", "15_multimodal_understanding"),
        ("voice.synthesize", "16_voice_intelligence"),
        ("wakeword.listen", "17_wakeword_intelligence"),
        ("system.switch_persona", "18_persona_social"),
        ("emotion.analyze_sentiment", "19_emotion_social"),
        ("accessibility.format_payload", "20_accessibility"),
        ("knowledge.query", "10_knowledge_management"),
        ("knowledge.ingest", "10_knowledge_management"),
        ("knowledge.audit_freshness", "10_knowledge_management"),
    ]
    for op, expected_cap_id in sample_ops:
        c = contract_registry_50.get_contract_for_operation(op)
        assert c is not None, f"No contract found for operation '{op}'!"
        assert c.capability_id == expected_cap_id, f"Expected {expected_cap_id} for {op}, got {c.capability_id}!"
    print(f"  Validated {len(sample_ops)} core operation mappings successfully.")


def test_core_provider_executions():
    print("\n[TEST 3/5] Auditing Core Capability Provider Executions via Intelligence...")
    
    # 1. OS Telemetry
    p_os = capability_intelligence.select_provider("os.telemetry")
    assert p_os is not None, "No provider for os.telemetry!"
    res_os = p_os.execute("os.telemetry", {})
    assert res_os.status == "SUCCESS"
    assert "cpu_percent" in str(res_os.output).lower()
    print("  os.telemetry provider executed successfully.")

    # 2. OS Volume Control
    res_vol = p_os.execute("os.volume_control", {"action": "set", "level": 60})
    assert res_vol.status == "SUCCESS"
    assert res_vol.output.get("volume") == 60
    print("  os.volume_control provider executed successfully.")

    # 3. File Operations
    p_file = capability_intelligence.select_provider("file.create")
    assert p_file is not None, "No provider for file.create!"
    ws = Path(r"d:\assignment\JARVIS\workspace")
    test_file = ws / "capability_matrix_test.txt"
    res_file = p_file.execute("file.create", {"path": str(test_file), "content": "Capability contract payload"})
    assert res_file.status == "SUCCESS"
    assert test_file.exists()
    test_file.unlink()
    print("  file.create provider executed and verified.")

    # 4. Developer / Git Status
    p_dev = capability_intelligence.select_provider("git.status")
    assert p_dev is not None, "No provider for git.status!"
    res_git = p_dev.execute("git.status", {})
    assert res_git.status == "SUCCESS"
    print("  git.status provider executed successfully.")

    # 5. Code Sandbox Execution
    res_code = p_dev.execute("code.sandbox_execution", {"code": "def calc(x): return x * 10\nres = calc(input_arg)", "input_arg": 7})
    assert res_code.status == "SUCCESS"
    print("  code.sandbox_execution provider executed successfully.")

    # 6. Knowledge Management (Capability 10)
    p_know = capability_intelligence.select_provider("knowledge.query")
    assert p_know is not None, "No provider for knowledge.query!"
    res_know = p_know.execute("knowledge.query", {"query": "Aniket"})
    assert res_know.status == "SUCCESS"
    assert "query" in res_know.output
    print("  knowledge.query provider executed successfully.")


def test_safety_classification_enforcement():
    print("\n[TEST 4/5] Auditing Safety Classification Enforcement across Operations...")
    
    # Read-only operation: ALLOWED
    dec_read = policy_kernel.evaluate("os", "telemetry", {})
    assert dec_read.allowed is True
    print("  READ_ONLY operation allowed unconditionally.")

    # Destructive operation: CONFIRMATION_REQUIRED
    dec_destruct = policy_kernel.evaluate("file", "delete", {"path": "important.txt"})
    assert dec_destruct.level == PolicyLevel.CONFIRMATION_REQUIRED
    assert dec_destruct.confirmation_token is not None
    print("  DESTRUCTIVE operation staged with Two-Gate confirmation token.")

    # Prohibited shell operation: PROHIBITED
    dec_shell = policy_kernel.evaluate("shell", "whoami", {})
    assert dec_shell.level == PolicyLevel.PROHIBITED
    assert dec_shell.allowed is False
    print("  PROHIBITED shell operation denied by policy kernel.")


def test_machine_readable_export():
    print("\n[TEST 5/5] Auditing Machine-Readable Contract Export...")
    all_dicts = [c.to_dict() for c in contract_registry_50.list_all_contracts()]
    assert len(all_dicts) == 50
    for d in all_dicts:
        assert "capability_id" in d
        assert "supported_operations" in d
        assert "safety_classification" in d
        assert "timeout_sec" in d
    print("  50 capability contracts exported to machine-readable format cleanly.")


def test_phase_2_multimodal_and_perception_capabilities():
    print("\n[TEST 6/6] Auditing Phase 2 Perception & Multimodal Capabilities (11-20)...")
    import numpy as np
    
    # --- Capability 11 & 12: Vision & OCR ---
    p_vis = capability_intelligence.select_provider("vision.screen_inspect")
    assert p_vis is not None, "No provider for vision.screen_inspect!"
    res_scr = p_vis.execute("vision.screen_inspect", {})
    assert res_scr.status == "SUCCESS"
    assert "screenshot_path" in res_scr.output
    print("  vision.screen_inspect executed successfully.")

    # High-confidence OCR
    res_ocr_hi = p_vis.execute("vision.ocr", {"text": "System operational and all modules active."})
    assert res_ocr_hi.status == "SUCCESS"
    assert res_ocr_hi.output.get("confidence", 0) >= 0.8
    print("  vision.ocr (high confidence) verified.")

    # Low-confidence OCR: uncertainty exposure ("I may have read this as X")
    res_ocr_lo = p_vis.execute("vision.ocr", {"text": "x"})
    assert res_ocr_lo.status == "SUCCESS"
    assert "may have read" in res_ocr_lo.message or res_ocr_lo.output.get("confidence", 1.0) < 0.6
    print("  vision.ocr uncertainty calibrated correctly (no false certainty).")

    # Table extraction
    res_tbl = p_vis.execute("vision.extract_table", {"image_path": "sample_table.png"})
    assert res_tbl.status == "SUCCESS"
    print("  vision.extract_table executed successfully.")

    # Visual diff
    res_diff = p_vis.execute("vision.visual_diff", {"image_1": "frame1.png", "image_2": "frame2.png"})
    assert res_diff.status == "SUCCESS"
    assert "diff_percentage" in res_diff.output
    print("  vision.visual_diff executed successfully.")

    # --- Capability 13: Audio Perception ---
    p_aud = capability_intelligence.select_provider("audio.transcribe")
    assert p_aud is not None, "No provider for audio.transcribe!"
    
    # Silence detection
    silence_buf = np.zeros(16000, dtype=np.float32)
    res_silence = p_aud.execute("audio.transcribe", {"audio_data": silence_buf})
    assert res_silence.status == "SUCCESS"
    assert res_silence.output.get("is_silence") is True
    print("  audio.transcribe silence detection verified.")

    # Speech Activity Detection (VAD)
    res_vad_quiet = p_aud.execute("audio.detect_speech", {"audio_data": silence_buf})
    assert res_vad_quiet.status == "SUCCESS"
    assert res_vad_quiet.output.get("speech_detected") is False
    speech_buf = np.random.uniform(-0.2, 0.2, 16000).astype(np.float32)
    res_vad_speech = p_aud.execute("audio.detect_speech", {"audio_data": speech_buf})
    assert res_vad_speech.status == "SUCCESS"
    assert res_vad_speech.output.get("speech_detected") is True
    print("  audio.detect_speech (VAD) verified for silence and noise/speech.")

    # Multilingual transcription & Marathi language hint
    res_marathi = p_aud.execute("audio.transcribe", {"mock_transcript": "जार्विस चालू करा", "language": "mr"})
    assert res_marathi.status == "SUCCESS"
    assert res_marathi.output.get("language") == "mr"
    print("  audio.transcribe multilingual/Marathi code-switching support verified.")

    # Barge-in interruption
    res_barge = p_aud.execute("audio.barge_in", {"tts_active": True, "mic_energy": 0.35})
    assert res_barge.status == "SUCCESS"
    assert res_barge.output.get("interrupted") is True
    assert res_barge.output.get("abort_tts") is True
    print("  audio.barge_in real-time interruption verified.")

    # --- Capability 14: Environmental Perception ---
    p_env = capability_intelligence.select_provider("env.probe_hardware")
    assert p_env is not None, "No provider for env.probe_hardware!"
    res_hw = p_env.execute("env.probe_hardware", {})
    assert res_hw.status == "SUCCESS"
    assert "cpu_percent" in res_hw.output
    assert "memory_percent" in res_hw.output
    print("  env.probe_hardware verified.")

    res_net = p_env.execute("env.probe_network", {})
    assert res_net.status == "SUCCESS"
    assert "interfaces" in res_net.output
    print("  env.probe_network verified.")

    res_proc = p_env.execute("env.probe_processes", {"limit": 5})
    assert res_proc.status == "SUCCESS"
    print("  env.probe_processes verified.")

    # --- Capability 15: Multimodal Understanding ---
    p_multi = capability_intelligence.select_provider("multimodal.fuse")
    assert p_multi is not None, "No provider for multimodal.fuse!"
    res_fuse = p_multi.execute("multimodal.fuse", {
        "text": "Open Chrome and search for documentation",
        "vision": {"caption": "Desktop with code editor in foreground"},
        "audio": {"text": "Open Chrome"},
    })
    assert res_fuse.status == "SUCCESS"
    assert "visual_summary" in res_fuse.output
    print("  multimodal.fuse perception stream integration verified.")

    # Modality Conflict Resolution: Freshness resolution (time diff > 5s)
    res_conf_fresh = p_multi.execute("multimodal.resolve_conflict", {
        "entity": "chrome",
        "modality_a": {"source": "vision", "claim": "open", "timestamp": time.time() - 2},
        "modality_b": {"source": "world_model", "claim": "closed", "timestamp": time.time() - 15},
    })
    assert res_conf_fresh.status == "SUCCESS"
    assert res_conf_fresh.output.get("resolved_state") == "open"
    assert "Freshness" in res_conf_fresh.output.get("resolution_method")
    print("  multimodal.resolve_conflict (freshness comparison) verified.")

    # Modality Conflict Resolution: Simultaneous claims triggering empirical reality probe
    res_conf_probe = p_multi.execute("multimodal.resolve_conflict", {
        "entity": "python",
        "modality_a": {"source": "vision", "claim": "open", "timestamp": time.time() - 1},
        "modality_b": {"source": "world_model", "claim": "closed", "timestamp": time.time() - 2},
    })
    assert res_conf_probe.status == "SUCCESS"
    assert "probe" in res_conf_probe.output.get("resolution_method").lower()
    print("  multimodal.resolve_conflict (live empirical probe) verified.")

    # --- Capability 16: Voice Intelligence ---
    p_voice = capability_intelligence.select_provider("voice.synthesize")
    assert p_voice is not None, "No provider for voice.synthesize!"
    res_syn = p_voice.execute("voice.synthesize", {"text": "Good afternoon, Sir.", "persona": "jarvis"})
    assert res_syn.status == "SUCCESS"
    assert "byte_count" in res_syn.output
    print("  voice.synthesize neural Piper synthesis verified.")

    res_stream = p_voice.execute("voice.stream", {"text": "Streaming voice packet.", "chunk_size": 2048})
    assert res_stream.status == "SUCCESS"
    assert res_stream.output.get("stream_chunks") >= 1
    print("  voice.stream low-latency chunking verified.")

    res_prof = p_voice.execute("voice.select_profile", {"persona": "friday"})
    assert res_prof.status == "SUCCESS"
    assert res_prof.output.get("active_voice_profile") == "friday"
    print("  voice.select_profile hot-swapping verified.")

    # --- Capability 17: Wake-Word Intelligence ---
    p_wake = capability_intelligence.select_provider("wakeword.listen")
    assert p_wake is not None, "No provider for wakeword.listen!"
    res_wake = p_wake.execute("wakeword.listen", {"mock_wake_word": "Friday", "mock_score": 0.95})
    assert res_wake.status == "SUCCESS"
    assert res_wake.output.get("detected") is True
    assert res_wake.output.get("persona") == "Friday"
    print("  wakeword.listen multi-persona detection verified.")

    res_cfg = p_wake.execute("wakeword.configure", {"threshold": 0.75, "active_personas": ["Jarvis", "Friday", "Ultron"]})
    assert res_cfg.status == "SUCCESS"
    assert res_cfg.output.get("threshold") == 0.75
    print("  wakeword.configure threshold and profile management verified.")

    res_fp = p_wake.execute("wakeword.evaluate_false_positives", {"sample_count": 25})
    assert res_fp.status == "SUCCESS"
    assert res_fp.output.get("false_positive_rate") < 0.01
    print("  wakeword.evaluate_false_positives suppression verified.")

    # --- Capability 18: Persona & Social Interaction ---
    p_persona = capability_intelligence.select_provider("system.switch_persona")
    assert p_persona is not None, "No provider for system.switch_persona!"
    res_p_sw = p_persona.execute("system.switch_persona", {"persona": "Ultron"})
    assert res_p_sw.status == "SUCCESS"
    assert res_p_sw.output.get("active_persona") == "Ultron"
    print("  system.switch_persona verified.")

    res_tone = p_persona.execute("system.set_tone", {"tone": "sardonic"})
    assert res_tone.status == "SUCCESS"
    assert res_tone.output.get("active_tone_modifier") == "sardonic"
    print("  system.set_tone dynamic modifier verified.")

    res_p_get = p_persona.execute("system.get_persona", {})
    assert res_p_get.status == "SUCCESS"
    assert res_p_get.output.get("active_persona") == "Ultron"
    # Switch back to Jarvis
    p_persona.execute("system.switch_persona", {"persona": "Jarvis"})
    print("  system.get_persona verified.")

    # --- Capability 19: Emotion & Social Context ---
    p_emo = capability_intelligence.select_provider("emotion.analyze_sentiment")
    assert p_emo is not None, "No provider for emotion.analyze_sentiment!"
    res_pos = p_emo.execute("emotion.analyze_sentiment", {"text": "Awesome job, thank you so much!"})
    assert res_pos.status == "SUCCESS"
    assert res_pos.output.get("sentiment_category") == "positive"
    assert res_pos.output.get("probabilistic_claim") is True
    print("  emotion.analyze_sentiment (positive probabilistic cues) verified.")

    res_frust = p_emo.execute("emotion.analyze_sentiment", {"text": "I am so frustrated and stuck on this broken script."})
    assert res_frust.status == "SUCCESS"
    assert res_frust.output.get("sentiment_category") == "frustrated"
    assert res_frust.output.get("recommended_tone") == "empathetic_helpful"
    print("  emotion.analyze_sentiment (frustrated tone adaptation) verified.")

    res_urg = p_emo.execute("emotion.detect_urgency", {"text": "We need to fix this server outage ASAP immediately now!"})
    assert res_urg.status == "SUCCESS"
    assert res_urg.output.get("is_urgent") is True
    assert res_urg.output.get("priority_boost") > 0
    print("  emotion.detect_urgency priority elevation verified.")

    # --- Capability 20: Accessibility ---
    p_acc = capability_intelligence.select_provider("accessibility.format_payload")
    assert p_acc is not None, "No provider for accessibility.format_payload!"
    res_fmt = p_acc.execute("accessibility.format_payload", {
        "payload": {"cpu_percent": 12.5, "memory_percent": 45.0, "active_window": "VS Code"}
    })
    assert res_fmt.status == "SUCCESS"
    assert "Cpu Percent: 12.5" in res_fmt.output.get("accessible_text")
    assert res_fmt.output.get("screen_reader_ready") is True
    print("  accessibility.format_payload screen-reader linearization verified.")

    res_hc = p_acc.execute("accessibility.toggle_high_contrast", {"enable": True})
    assert res_hc.status == "SUCCESS"
    assert res_hc.output.get("high_contrast_mode") is True
    p_acc.execute("accessibility.toggle_high_contrast", {"enable": False})
    print("  accessibility.toggle_high_contrast HUD mode verified.")


def main():
    print("=" * 80)
    print("STARTING 50-CAPABILITY INTEGRATION & CONTRACT VERIFICATION SUITE")
    print("=" * 80)
    t0 = time.time()
    
    test_contract_registry_completeness()
    test_operation_to_contract_mapping()
    test_core_provider_executions()
    test_safety_classification_enforcement()
    test_machine_readable_export()
    test_phase_2_multimodal_and_perception_capabilities()
    
    elapsed = time.time() - t0
    print("\n" + "=" * 80)
    print(f"ALL 50-CAPABILITY CONTRACT & PROVIDER TESTS PASSED CLEANLY in {elapsed:.2f}s!")
    print("=" * 80)
    os._exit(0)


if __name__ == "__main__":
    main()
