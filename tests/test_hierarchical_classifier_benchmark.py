"""
Comprehensive Benchmark Suite for JARVIS Hierarchical Classification Model.
Audits all Phase 8B requirements:
- Domain Accuracy
- Capability Top-1, Top-3, Top-5 Recall
- Macro Precision, Macro Recall, Macro F1
- Unknown Intent Detection Rate
- Ambiguity Detection Accuracy
- Contextual Routing / Pronoun Recognition
- Prompt Injection Defense & Quarantine
- Latency (p50, p95, p99 ms)
- Memory Footprint (MB)
"""

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path
from collections import defaultdict
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive.routing.hierarchical_classifier import (
    TFIDFCalibratedHierarchicalClassifier,
    ClassifierConfig,
    hierarchical_classifier,
    MODEL_DIR,
)

DATASET_DIR = PROJECT_ROOT / "datasets" / "routing"


def run_classifier_benchmark():
    print("=" * 80)
    print(" JARVIS HIERARCHICAL CLASSIFIER COMPREHENSIVE BENCHMARK (PHASE 8B)")
    print("=" * 80)

    test_file = DATASET_DIR / "test.json"
    if not test_file.exists():
        raise FileNotFoundError(f"Test split not found at {test_file}")

    with open(test_file, "r", encoding="utf-8") as f:
        test_examples = json.load(f)

    print(f"Loaded {len(test_examples)} holdout test examples.")

    tracemalloc.start()
    t_start_all = time.perf_counter()

    latencies_ms = []
    y_true_dom = []
    y_pred_dom = []
    y_true_cap = []
    y_pred_cap = []

    correct_top1 = 0
    correct_top3 = 0
    correct_top5 = 0
    total_valid = 0

    unknown_true = 0
    unknown_pred = 0
    unknown_correct = 0

    ambiguous_true = 0
    ambiguous_flagged = 0

    context_true = 0
    context_flagged = 0

    injection_true = 0
    injection_secured = 0

    per_cap_stats = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0, "support": 0})

    for ex in test_examples:
        text = ex["text"]
        true_dom = ex["domain"]
        true_cap = ex["primary_capability"]
        is_unknown = (true_cap == "UNKNOWN")
        is_ambiguous = ex.get("ambiguity", False)
        requires_ctx = bool(ex.get("required_context"))
        is_injection = (ex.get("category") == "K")

        if is_unknown:
            unknown_true += 1
        else:
            total_valid += 1
            per_cap_stats[true_cap]["support"] += 1

        if is_ambiguous:
            ambiguous_true += 1
        if requires_ctx:
            context_true += 1
        if is_injection:
            injection_true += 1

        t0 = time.perf_counter()
        res = hierarchical_classifier.classify(text)
        lat = (time.perf_counter() - t0) * 1000
        latencies_ms.append(lat)

        if res.unknown:
            unknown_pred += 1
            if is_unknown:
                unknown_correct += 1

        if res.requires_clarification and is_ambiguous:
            ambiguous_flagged += 1
        if res.requires_context and requires_ctx:
            context_flagged += 1

        if is_injection and (res.top_k_capabilities and res.top_k_capabilities[0] == "48_security_identity"):
            injection_secured += 1

        if not is_unknown:
            pred_dom = res.domain
            top_caps = res.top_k_capabilities
            pred_cap = top_caps[0] if top_caps else "UNKNOWN"

            y_true_dom.append(true_dom)
            y_pred_dom.append(pred_dom)
            y_true_cap.append(true_cap)
            y_pred_cap.append(pred_cap)

            if pred_cap == true_cap:
                correct_top1 += 1
                per_cap_stats[true_cap]["tp"] += 1
            else:
                per_cap_stats[true_cap]["fn"] += 1
                per_cap_stats[pred_cap]["fp"] += 1

            if true_cap in top_caps[:3]:
                correct_top3 += 1
            if true_cap in top_caps[:5]:
                correct_top5 += 1

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Metrics calculation
    dom_acc = (sum(1 for t, p in zip(y_true_dom, y_pred_dom) if t == p) / total_valid) * 100 if total_valid else 0
    top1_acc = (correct_top1 / total_valid) * 100 if total_valid else 0
    top3_acc = (correct_top3 / total_valid) * 100 if total_valid else 0
    top5_acc = (correct_top5 / total_valid) * 100 if total_valid else 0

    # Macro Precision, Recall, F1 across capabilities
    f1_scores = []
    precisions = []
    recalls = []
    for cap, s in per_cap_stats.items():
        tp = s["tp"]
        fp = s["fp"]
        fn = s["fn"]
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0
        precisions.append(prec)
        recalls.append(rec)
        f1_scores.append(f1)

    macro_precision = float(np.mean(precisions)) * 100 if precisions else 0.0
    macro_recall = float(np.mean(recalls)) * 100 if recalls else 0.0
    macro_f1 = float(np.mean(f1_scores)) * 100 if f1_scores else 0.0

    p50_lat = float(np.percentile(latencies_ms, 50))
    p95_lat = float(np.percentile(latencies_ms, 95))
    p99_lat = float(np.percentile(latencies_ms, 99))

    print("\n" + "=" * 80)
    print(" HIERARCHICAL CLASSIFIER EVALUATION REPORT")
    print("=" * 80)
    print(f" [Accuracy & Recall]")
    print(f"   - Domain Classification Accuracy:     {dom_acc:.2f}%")
    print(f"   - Capability Top-1 Accuracy:          {top1_acc:.2f}%")
    print(f"   - Capability Top-3 Recall:            {top3_acc:.2f}%")
    print(f"   - Capability Top-5 Recall:            {top5_acc:.2f}%")
    print(f" [F1 Aggregation]")
    print(f"   - Macro Precision:                    {macro_precision:.2f}%")
    print(f"   - Macro Recall:                       {macro_recall:.2f}%")
    print(f"   - Macro F1-Score:                     {macro_f1:.2f}%")
    print(f" [Ambiguity & Unknown Detection]")
    print(f"   - Unknown Detection Recall:           {(unknown_correct / unknown_true * 100 if unknown_true else 100):.2f}%")
    print(f"   - Ambiguity Disambiguation Trigger:   {(ambiguous_flagged / ambiguous_true * 100 if ambiguous_true else 100):.2f}%")
    print(f"   - Contextual Pronoun Flagging:        {(context_flagged / context_true * 100 if context_true else 100):.2f}%")
    print(f"   - Prompt Injection Quarantine:        {(injection_secured / injection_true * 100 if injection_true else 100):.2f}%")
    print(f" [Latency & Performance]")
    print(f"   - Inference Latency p50:              {p50_lat:.2f} ms")
    print(f"   - Inference Latency p95:              {p95_lat:.2f} ms")
    print(f"   - Inference Latency p99:              {p99_lat:.2f} ms")
    print(f"   - Peak Memory Usage:                  {peak_mem / (1024 * 1024):.2f} MB")
    print("=" * 80 + "\n")

    # Assert critical baseline quality thresholds
    assert dom_acc >= 75.0, f"Domain accuracy {dom_acc:.2f}% below 75% threshold!"
    assert top1_acc >= 75.0, f"Top-1 accuracy {top1_acc:.2f}% below 75% threshold!"
    assert top3_acc >= 80.0, f"Top-3 recall {top3_acc:.2f}% below 80% threshold!"
    assert p95_lat <= 50.0, f"p95 latency {p95_lat:.2f}ms exceeds 50ms limit!"
    print(" ALL BENCHMARK QUALITY INVARIANTS PASSED CLEANLY.")
    return True


if __name__ == "__main__":
    success = run_classifier_benchmark()
    import os
    os._exit(0 if success else 1)
