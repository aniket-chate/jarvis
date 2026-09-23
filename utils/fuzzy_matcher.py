"""Universal Fuzzy Matching & String Normalization Layer for JARVIS.

Consolidates all typo-handling, alias matching, and entity resolution across:
- Applications & Executables (e.g. chrome/the chrome, spotify/spotfy, notepad)
- Websites & Web Services (e.g. whatsapp/whatsup, instagram/instgram, youtube/yt)
- Assistant Personas (e.g. Jarvis, Friday/Fryday, Ultron/Ultran, Omi)
- Follow-up Action Intents (e.g. stop/pause/halt, resume/unpause/play again, close/exit/kill)
- Contact Names & Recipients (e.g. Rahul Sharma, Mom, Boss)
"""

import re
import difflib
import logging
from typing import Sequence, Optional, Tuple, Dict, List, Any

logger = logging.getLogger("JARVIS.FuzzyMatcher")

# Canonical action intent clusters
CANONICAL_INTENTS: Dict[str, List[str]] = {
    "pause": [
        "stop", "pause", "halt", "freeze", "stop it", "pause that", "pause it",
        "stop that", "pause music", "stop music", "stop playing", "pause playback",
        "pause the song", "stop the song", "pause audio", "stop audio", "hold playback"
    ],
    "resume": [
        "resume", "unpause", "play again", "continue", "resume it", "continue playing",
        "resume playback", "start playing again", "keep playing", "resume music",
        "resume song", "unpause playback", "play it again"
    ],
    "close": [
        "close it", "close that", "close the tab", "close tab", "close browser",
        "close page", "close the page", "close the window", "close window", "exit",
        "shut it", "kill page", "terminate page", "close the chrome"
    ],
    "cancel": [
        "cancel", "cancel it", "cancel that", "undo that", "undo", "abort",
        "nevermind", "dismiss"
    ]
}

# Known applications and canonical names
KNOWN_APPLICATIONS: List[str] = [
    "chrome", "google chrome", "notepad", "calculator", "spotify",
    "camera", "settings", "clock", "photos", "maps", "terminal",
    "powershell", "cmd", "explorer", "file explorer", "whatsapp",
    "instagram", "youtube", "discord", "slack", "telegram", "netflix",
    "github", "reddit", "twitter", "linkedin"
]

# Known personas
KNOWN_PERSONAS: List[str] = ["Jarvis", "Friday", "Ultron", "Omi"]


def normalize_query(text: str) -> str:
    """Normalizes input text by removing articles, conversational fluff, and punctuation.
    
    Examples:
        'close the chrome' -> 'chrome'
        'open whatsup for me please' -> 'whatsup'
        'pause that playback' -> 'pause that playback'
    """
    if not text:
        return ""
    
    clean = text.strip().lower()
    
    # Strip common conversational prefixes
    for pfx in [
        "please ", "can you ", "could you ", "jarvis ", "friday ", "ultron ", "omi ",
        "go ahead and ", "open ", "launch ", "start ", "run ", "navigate to ", "browse to ",
        "close ", "exit ", "kill ", "stop ", "terminate "
    ]:
        # Only strip action verbs if followed by more words (to retain intent if word is alone)
        if clean.startswith(pfx) and len(clean) > len(pfx):
            clean = clean[len(pfx):].strip()

    # Strip conversational suffixes
    for sfx in [
        " for me", " please", " on my pc", " on desktop", " on computer",
        " app", " application", " right now", " immediately"
    ]:
        if clean.endswith(sfx) and len(clean) > len(sfx):
            clean = clean[:-len(sfx)].strip()

    # Strip leading articles ("the ", "a ", "an ")
    clean = re.sub(r"^(?:the|a|an)\s+", "", clean).strip()

    # Strip trailing punctuation
    clean = re.sub(r"[?!.,;]+$", "", clean).strip()
    return clean


def calculate_similarity(s1: str, s2: str) -> float:
    """Calculates a normalized similarity score between two strings.
    
    Combines SequenceMatcher ratio with exact-substring and prefix bonuses.
    """
    a = s1.strip().lower()
    b = s2.strip().lower()
    
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0

    # SequenceMatcher edit-ratio
    base_ratio = difflib.SequenceMatcher(None, a, b).ratio()

    # Substring containment bonus (only when lengths are comparable and not tiny fragments)
    if (a in b or b in a) and min(len(a), len(b)) >= 4:
        shorter_len = min(len(a), len(b))
        longer_len = max(len(a), len(b))
        containment_score = shorter_len / longer_len
        if containment_score >= 0.5:
            base_ratio = max(base_ratio, 0.70 + 0.30 * containment_score)

    COMMON_STOPWORDS = {
        "me", "it", "to", "in", "on", "at", "by", "for", "from", "of", "with",
        "is", "am", "are", "was", "were", "and", "or", "the", "a", "an",
        "his", "her", "my", "your", "who", "what", "tell", "show", "this", "that"
    }

    # Token-level similarity for multi-word candidates (e.g. 'Rahull' vs 'Rahul Sharma')
    b_tokens = b.split()
    if len(b_tokens) > 1:
        for tok in b_tokens:
            if tok in COMMON_STOPWORDS or len(tok) < 4:
                continue
            tok_ratio = difflib.SequenceMatcher(None, a, tok).ratio()
            if (tok in a or a in tok) and len(a) >= 4:
                tok_ratio = max(tok_ratio, 0.85)
            base_ratio = max(base_ratio, tok_ratio * 0.95)

    a_tokens = a.split()
    if len(a_tokens) > 1:
        for tok in a_tokens:
            if tok in COMMON_STOPWORDS or len(tok) < 4:
                continue
            tok_ratio = difflib.SequenceMatcher(None, tok, b).ratio()
            if (tok in b or b in tok) and len(b) >= 4:
                tok_ratio = max(tok_ratio, 0.85)
            base_ratio = max(base_ratio, tok_ratio * 0.95)

    # Abbreviation / Prefix check (e.g. 'dr' vs 'doctor')
    if (a.startswith("dr") and b.startswith("doctor")) or (b.startswith("dr") and a.startswith("doctor")):
        base_ratio = max(base_ratio, 0.88)

    return min(1.0, round(base_ratio, 4))


def fuzzy_match(
    target: str,
    candidates: Sequence[str],
    threshold: float = 0.72
) -> Optional[str]:
    """Matches target against candidates and returns the best candidate above threshold."""
    if not target or not candidates:
        return None

    clean_target = target.strip().lower()
    best_match = None
    highest_score = 0.0

    for candidate in candidates:
        cand_clean = candidate.strip().lower()
        score = calculate_similarity(clean_target, cand_clean)
        if score > highest_score:
            highest_score = score
            best_match = candidate

    if highest_score >= threshold and best_match:
        logger.debug("[FuzzyMatcher] Matched '%s' -> '%s' (score=%.2f)", target, best_match, highest_score)
        return best_match

    return None


def match_app_or_site(
    query: str,
    candidates: Optional[Sequence[str]] = None,
    threshold: float = 0.68
) -> Optional[str]:
    """Resolves an app or website query with article stripping and typo tolerance.
    
    Examples:
        'the chrome' -> 'chrome'
        'whatsup' -> 'whatsapp'
        'instgram' -> 'instagram'
        'spotfy' -> 'spotify'
    """
    normalized = normalize_query(query)
    cands = candidates or KNOWN_APPLICATIONS
    return fuzzy_match(normalized, cands, threshold=threshold)


def match_persona(
    name: str,
    candidates: Optional[Sequence[str]] = None,
    threshold: float = 0.72
) -> Optional[str]:
    """Resolves a persona name with typo tolerance.
    
    Examples:
        'fryday' -> 'Friday'
        'ultran' -> 'Ultron'
        'jarvis' -> 'Jarvis'
    """
    clean = normalize_query(name)
    cands = candidates or KNOWN_PERSONAS
    matched = fuzzy_match(clean, cands, threshold=threshold)
    if matched:
        for p in cands:
            if p.lower() == matched.lower():
                return p
    return None


def match_contact(
    name: str,
    contacts: Sequence[str],
    threshold: float = 0.70
) -> Optional[str]:
    """Resolves contact names with typo tolerance."""
    clean = normalize_query(name)
    return fuzzy_match(clean, contacts, threshold=threshold)


def match_intent_action(
    text: str,
    threshold: float = 0.75
) -> Optional[str]:
    """Matches user input against canonical action intent clusters (pause, resume, close, cancel).
    
    Examples:
        'stop it' -> 'pause'
        'pause that' -> 'pause'
        'freeze playback' -> 'pause'
        'resume' -> 'resume'
        'play again' -> 'resume'
        'close the tab' -> 'close'
        'close the chrome' -> 'close'
    """
    lower = text.strip().lower()

    # 0. Initial playback requests ('play <song>', 'play a song', 'listen to...') are new tasks, NOT follow-up control intents
    if (lower.startswith("play ") or lower.startswith("listen to ")) and not any(
        lower.startswith(p) or p in lower for p in ["play again", "play it again", "play once more"]
    ):
        return None

    # Informational or conversational queries ('who is...', 'tell me...', 'show me...') are never media control intents
    QUESTION_STARTERS = (
        "who ", "what ", "when ", "where ", "why ", "how ",
        "tell me ", "show me ", "explain ", "can you tell ", "could you tell ",
        "who's ", "what's ", "where's ", "why's ", "how's ", "call ", "message "
    )
    if any(lower.startswith(q) for q in QUESTION_STARTERS):
        return None

    # Volume commands are system actions, not playback pause/resume
    if "volume" in lower:
        return None

    # Follow-up action commands are short conversational phrases (e.g. 'pause', 'stop it', 'resume', 'close the tab')
    if len(lower.split()) > 5:
        return None
    
    # 1. Direct fast-path check
    for canonical, phrases in CANONICAL_INTENTS.items():
        if lower in phrases:
            return canonical
        for p in phrases:
            if lower == p or lower.startswith(p + " ") or lower.endswith(" " + p):
                return canonical

    # 2. Normalized query matching
    clean = normalize_query(text)
    for canonical, phrases in CANONICAL_INTENTS.items():
        if clean in phrases:
            return canonical

    # 3. Fuzzy similarity across candidate phrases
    best_canonical = None
    highest_score = 0.0

    for canonical, phrases in CANONICAL_INTENTS.items():
        for phrase in phrases:
            score = calculate_similarity(lower, phrase)
            if score > highest_score:
                highest_score = score
                best_canonical = canonical

    if highest_score >= threshold and best_canonical:
        logger.info("[FuzzyMatcher] Intent '%s' mapped to canonical '%s' (score=%.2f)", text, best_canonical, highest_score)
        return best_canonical

    return None
