import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.contracts import contract_registry_50
from capabilities.intelligence import capability_intelligence
import capabilities.providers

contracts = contract_registry_50.list_all_contracts()
print(f"Total contracts: {len(contracts)}")

for c in contracts:
    prov = None
    for op in c.supported_operations:
        p = capability_intelligence.select_provider(op)
        if p:
            prov = (op, p.provider_id)
            break
    print(f"[{c.capability_id}] {c.name} -> Op: {prov[0] if prov else 'NONE'} (Provider: {prov[1] if prov else 'NONE'})")

os._exit(0)
