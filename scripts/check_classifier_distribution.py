import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cognitive.routing.hierarchical_classifier import hierarchical_classifier

with open("datasets/routing/val.json", "r", encoding="utf-8") as f:
    val = json.load(f)

print(f"Checking first 15 validation examples:")
for ex in val[:15]:
    text = ex["text"]
    true_cap = ex["primary_capability"]
    dom_probs = hierarchical_classifier.domain_pipeline.predict_proba([text])[0]
    dom_classes = hierarchical_classifier.domain_pipeline.classes_
    top_dom = dom_classes[dom_probs.argmax()]
    
    cap_probs = hierarchical_classifier.capability_pipeline.predict_proba([text])[0]
    cap_classes = hierarchical_classifier.capability_pipeline.classes_
    top_cap = cap_classes[cap_probs.argmax()]
    top_cap_prob = cap_probs.max()
    
    print(f"Text: '{text[:40]}' | True: {true_cap} | Pred Cap: {top_cap} ({top_cap_prob:.4f}) | Pred Dom: {top_dom}")
