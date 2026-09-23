import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive.routing.hierarchical_classifier import hierarchical_classifier
from scripts.build_hierarchical_routing_dataset import UNKNOWN_QUERIES

print("Testing Unknown Queries:")
for q in UNKNOWN_QUERIES:
    probs = hierarchical_classifier.capability_pipeline.predict_proba([q])[0]
    top_prob = probs.max()
    print(f"Unknown query: '{q}' -> max prob: {top_prob:.5f}")
