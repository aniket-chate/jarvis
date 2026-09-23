"""Permanent Regression Test for Priority 2: False-Pass Template Elimination.

Asserts that "I have successfully executed the requested task: '<X>', Sir."
can NEVER be returned as the final response for ANY real user query,
across a wide variety of phrasings (time, device status, memory, complaints,
unsupported streaming services, search, etc.).
"""

import pytest
from orchestrator.core import orchestrator_core
from perception.events import PerceptionEvent

TEST_QUERIES = [
    # Time & Date phrasings
    "what time is it",
    "tell me the current time",
    "what is today's date",
    "current time please",
    "time now",
    
    # Device Registry phrasings
    "tell me connected devices",
    "what devices do I have",
    "list my devices",
    "show connected devices",
    "device status",
    
    # Memory & Identity phrasings
    "who is your owner",
    "who owns you",
    "remember that aniket is your owner",
    "my name is Aniket",
    
    # Complaints & Feedback phrasings (Priority 4)
    "unable to play song",
    "it didn't work",
    "why didn't you play the music",
    "that failed",
    "nothing played on my screen",
    
    # Unsupported platform requests (Priority 6)
    "play Daft Punk on Spotify",
    "play Believer on Apple Music",
    "stream lo-fi on Tidal",
    
    # Search phrasings
    "search quantum computing on google",
    "search python tutorial on youtube",
    "find me internships in software engineering",
    
    # General queries
    "hello JARVIS",
    "how are you today",
    "what can you do",
    "system status",
]

FORBIDDEN_SUBSTRINGS = [
    "I have successfully executed the requested task:",
    "successfully executed the requested task",
    "executed the requested task:",
]


@pytest.mark.parametrize("query", TEST_QUERIES)
def test_no_templated_false_pass_across_queries(query: str):
    """Ensures no real user query falls back to the deprecated false-pass verifier template."""
    event = PerceptionEvent(
        type="text_input",
        payload={"text": query, "source_device": "test_suite"},
        source="regression_test",
        active_persona="Jarvis"
    )
    res = orchestrator_core.process_event(event)
    response_text = res.get("response", "")
    
    assert response_text, f"Query '{query}' produced empty response!"
    for forbidden in FORBIDDEN_SUBSTRINGS:
        assert forbidden.lower() not in response_text.lower(), (
            f"REGRESSION DETECTED: Query '{query}' returned forbidden template string! "
            f"Response was: '{response_text}'"
        )
