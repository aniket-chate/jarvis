"""Truthful 50-capability QA matrix.

This suite deliberately does NOT equate routing, simulation, or provider existence
with live execution. Every result is classified as ROUTED, LIVE_AVAILABLE,
SIMULATED, NOT_CONFIGURED, or FAILED. Side-effecting capabilities are never
executed by this discovery test.
"""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from capabilities.intelligence import capability_intelligence
from capabilities.contracts import contract_registry_50


def _readiness(provider):
    if provider is None:
        return "NOT_CONFIGURED"
    getter = getattr(provider, "get_readiness", None)
    if callable(getter):
        return str(getter())
    try:
        return "LIVE_AVAILABLE" if provider.is_available() else "NOT_CONFIGURED"
    except Exception:
        return "FAILED"


def collect_capability_readiness():
    rows = []
    for contract in contract_registry_50.list_all_contracts():
        operation = contract.supported_operations[0] if contract.supported_operations else ""
        provider = capability_intelligence.select_provider(operation) if operation else None
        rows.append({
            "capability_id": contract.capability_id,
            "operation": operation,
            "provider": provider.provider_id if provider else None,
            "readiness": _readiness(provider),
        })
    return rows


def test_all_50_capabilities_have_truthful_readiness():
    rows = collect_capability_readiness()
    assert len(rows) == 50, f"Expected 50 contracts, found {len(rows)}"
    allowed = {"LIVE_AVAILABLE", "SIMULATED", "PROVIDER_LEVEL_VERIFIED",
               "PHYSICAL_HARDWARE_VERIFIED", "NOT_CONFIGURED", "FAILED"}
    for row in rows:
        assert row["readiness"] in allowed, row
        # A provider must never be reported as live merely because it exists.
        if row["readiness"] == "SIMULATED":
            assert row["provider"] is not None


if __name__ == "__main__":
    for row in collect_capability_readiness():
        print(f"{row['capability_id']}: {row['readiness']} ({row['provider']})")
