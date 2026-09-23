"""
Training and Evaluation Pipeline for JARVIS Hierarchical Routing Model.
"""

import json
import logging
from pathlib import Path
import sys
import time
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive.routing.hierarchical_classifier import (
    TFIDFCalibratedHierarchicalClassifier,
    ClassifierConfig,
    hierarchical_classifier,
    MODEL_DIR,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_DIR = PROJECT_ROOT / "datasets" / "routing"


def train_hierarchical_routing_model():
    print("=" * 65)
    print(" TRAINING JARVIS HIERARCHICAL CAPABILITY CLASSIFIER")
    print("=" * 65)

    train_path = DATASET_DIR / "train.json"
    val_path = DATASET_DIR / "val.json"

    if not train_path.exists():
        raise FileNotFoundError(f"Training dataset not found at {train_path}")

    with open(train_path, "r", encoding="utf-8") as f:
        train_examples = json.load(f)

    with open(val_path, "r", encoding="utf-8") as f:
        val_examples = json.load(f)

    print(f"Loaded {len(train_examples)} training examples and {len(val_examples)} validation examples.")

    config = ClassifierConfig(
        unknown_threshold=0.20,
        ambiguity_margin=0.10,
        top_k=5,
        ngram_range=(1, 2),
        min_df=1,
    )

    classifier = TFIDFCalibratedHierarchicalClassifier(config=config)
    t0 = time.perf_counter()
    classifier.fit(train_examples)
    train_time_ms = (time.perf_counter() - t0) * 1000
    print(f"Training completed in {train_time_ms:.2f} ms.")

    # Save trained model artifacts
    classifier.save(MODEL_DIR)
    print(f"Model saved to {MODEL_DIR}")

    # Evaluate on validation set
    print("\nRunning Validation Evaluation...")
    correct_domain = 0
    correct_top1_cap = 0
    correct_top3_cap = 0
    correct_top5_cap = 0
    unknown_hits = 0
    total_val = len(val_examples)
    latencies = []

    for ex in val_examples:
        text = ex["text"]
        true_dom = ex["domain"]
        true_cap = ex["primary_capability"]

        t_inf_0 = time.perf_counter()
        res = classifier.classify(text)
        latencies.append((time.perf_counter() - t_inf_0) * 1000)

        if true_cap == "UNKNOWN":
            if res.unknown:
                unknown_hits += 1
            continue

        if res.domain == true_dom:
            correct_domain += 1

        top_k_caps = res.top_k_capabilities
        if top_k_caps:
            if top_k_caps[0] == true_cap:
                correct_top1_cap += 1
            if true_cap in top_k_caps[:3]:
                correct_top3_cap += 1
            if true_cap in top_k_caps[:5]:
                correct_top5_cap += 1

    valid_val_count = sum(1 for ex in val_examples if ex["primary_capability"] != "UNKNOWN")
    dom_acc = (correct_domain / valid_val_count) * 100
    top1_acc = (correct_top1_cap / valid_val_count) * 100
    top3_acc = (correct_top3_cap / valid_val_count) * 100
    top5_acc = (correct_top5_cap / valid_val_count) * 100
    avg_lat = sum(latencies) / len(latencies)

    print("\n" + "-" * 55)
    print(" VALIDATION BENCHMARK RESULTS")
    print("-" * 55)
    print(f" Domain Accuracy:           {dom_acc:.2f}% ({correct_domain}/{valid_val_count})")
    print(f" Capability Top-1 Accuracy: {top1_acc:.2f}% ({correct_top1_cap}/{valid_val_count})")
    print(f" Capability Top-3 Recall:   {top3_acc:.2f}% ({correct_top3_cap}/{valid_val_count})")
    print(f" Capability Top-5 Recall:   {top5_acc:.2f}% ({correct_top5_cap}/{valid_val_count})")
    print(f" Average Latency:           {avg_lat:.2f} ms")
    print("-" * 55 + "\n")

    return {
        "domain_accuracy": dom_acc,
        "top1_accuracy": top1_acc,
        "top3_recall": top3_acc,
        "top5_recall": top5_acc,
        "average_latency_ms": avg_lat,
    }


if __name__ == "__main__":
    train_hierarchical_routing_model()
