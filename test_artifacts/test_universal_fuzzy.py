"""Live Verification of Universal Fuzzy Matching Layer in JARVIS.

Tests 3 different typo/normalization categories through the ONE shared utility:
1. App name typo: 'open whatsup' / 'instgram' / 'close the chrome'
2. Stop/Action intent variant not previously hardcoded: 'hold playback', 'pause playback please', 'play again', 'freeze it'
3. Contact name typo: 'Rahull' -> 'Rahul Sharma', 'Mommy' -> 'Mom'
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utils.fuzzy_matcher import (
    normalize_query,
    calculate_similarity,
    match_app_or_site,
    match_intent_action,
    match_persona,
    match_contact,
)
from agents.action_tools import resolve_web_domain, open_application, close_application
from orchestrator.planner import task_planner
from perception.events import PerceptionEvent


def run_fuzzy_test():
    print("=" * 70)
    print("UNIVERSAL FUZZY MATCHER LIVE VERIFICATION")
    print("=" * 70)

    # -------------------------------------------------------------
    # CATEGORY 1: Application / Site Names with Typos & Articles
    # -------------------------------------------------------------
    print("\n--- CATEGORY 1: Application / Site Names (Typos & Article Normalization) ---")
    test_cases_apps = [
        ("whatsup", "whatsapp"),
        ("instgram", "instagram"),
        ("the chrome", "chrome"),
        ("close the chrome", "chrome"),
        ("spotfy", "spotify"),
    ]
    for raw, expected in test_cases_apps:
        normalized = normalize_query(raw)
        resolved = match_app_or_site(raw)
        print(f"  Input: '{raw}' -> normalized: '{normalized}' -> resolved: '{resolved}' (matches expected '{expected}': {resolved == expected})")
        assert resolved == expected, f"Failed: {raw} -> {resolved} != {expected}"

    # Also test resolve_web_domain using the shared utility
    domain_res = resolve_web_domain("whatsup")
    print(f"  resolve_web_domain('whatsup') -> {domain_res}")
    assert "whatsapp" in domain_res, f"Unexpected domain: {domain_res}"

    domain_res2 = resolve_web_domain("instgram")
    print(f"  resolve_web_domain('instgram') -> {domain_res2}")
    assert "instagram" in domain_res2, f"Unexpected domain: {domain_res2}"

    # -------------------------------------------------------------
    # CATEGORY 2: Stop / Follow-Up Intent Variants
    # -------------------------------------------------------------
    print("\n--- CATEGORY 2: Action / Follow-up Intent Variants (Shared Intent Clusters) ---")
    test_cases_intents = [
        ("pause playback please", "pause"),
        ("hold playback", "pause"),
        ("freeze it", "pause"),
        ("stop it", "pause"),
        ("play again", "resume"),
        ("unpause playback", "resume"),
        ("continue playing", "resume"),
        ("close the tab", "close"),
    ]
    for raw, expected in test_cases_intents:
        matched_intent = match_intent_action(raw)
        print(f"  Input: '{raw}' -> resolved intent: '{matched_intent}' (matches expected '{expected}': {matched_intent == expected})")
        assert matched_intent == expected, f"Failed: {raw} -> {matched_intent} != {expected}"

    # -------------------------------------------------------------
    # CATEGORY 3: Contact Name Resolution with Typos
    # -------------------------------------------------------------
    print("\n--- CATEGORY 3: Contact Name Typos (Shared Contact Matcher) ---")
    known_contacts = ["Rahul Sharma", "Priya Patel", "Mom", "Doctor Vikram", "Office Reception"]
    test_cases_contacts = [
        ("Rahull", "Rahul Sharma"),
        ("Priyah", "Priya Patel"),
        ("Mommy", "Mom"),
        ("Dr Vikram", "Doctor Vikram"),
    ]
    for raw, expected in test_cases_contacts:
        matched_contact = match_contact(raw, known_contacts)
        print(f"  Input: '{raw}' -> resolved contact: '{matched_contact}' (matches expected '{expected}': {matched_contact == expected})")
        assert matched_contact == expected, f"Failed: {raw} -> {matched_contact} != {expected}"

    # -------------------------------------------------------------
    # CATEGORY 4: Persona Name Typos
    # -------------------------------------------------------------
    print("\n--- CATEGORY 4: Persona Names (Shared Persona Matcher) ---")
    for raw, expected in [("fryday", "Friday"), ("ultran", "Ultron"), ("jarvis", "Jarvis")]:
        matched_p = match_persona(raw)
        print(f"  Input: '{raw}' -> resolved persona: '{matched_p}' (matches expected '{expected}': {matched_p == expected})")
        assert matched_p == expected, f"Failed: {raw} -> {matched_p} != {expected}"

    print("\n[SUCCESS] ALL 4 CATEGORIES RESOLVED CORRECTLY VIA utils.fuzzy_matcher!")


if __name__ == "__main__":
    run_fuzzy_test()
