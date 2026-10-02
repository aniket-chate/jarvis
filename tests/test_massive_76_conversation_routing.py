"""Massive JARVIS conversation routing audit (111 utterances).

Routing/safety audit only: side-effecting actions are NOT executed here.
"""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from orchestrator.intent_arbitrator import IntentArbitrator

PROMPTS = [
  "JARVIS, who am I?",
  "And what should I call you?",
  "You know, I've been thinking about rebuilding the whole thing again.",
  "The AI part.",
  "Actually forget that for a second. Open my project folder.",
  "Now go back to what we were discussing.",
  "Open it.",
  "The Python file.",
  "JARVIS, before you do anything, tell me whether the file is safe, then actually open it, and after that remind me what we were doing yesterday.",
  "How big is it?",
  "And when was I last working on it?",
  "Open File Explorer.",
  "Go to my JARVIS project.",
  "Open the backend.",
  "Open the JARVIS backend, launch the terminal there, and start the development server.",
  "Did it start?",
  "It crashed.",
  "Fix it.",
  "Open Chrome.",
  "Search for the official OpenAI documentation.",
  "Don't use a random blog. I want the official source.",
  "Now search for the API documentation.",
  "Go back.",
  "Find the authentication section, read it, and tell me what I actually need to change in my project.",
  "Okay, make that change.",
  "Find the configuration file and tell me what's wrong with it.",
  "Fix only the broken part.",
  "Delete the old test directory.",
  "Yes, delete it.",
  "What was the architecture we decided for my JARVIS?",
  "Why did we choose that instead of making everything run on the phone?",
  "What did we decide about the wake word?",
  "So should I hard-code “Hey JARVIS”?",
  "I changed my mind about one component. Everything else stays the same.",
  "The Android wake-word engine.",
  "When you talk to me, keep it natural. Don't sound like a corporate chatbot.",
  "JARVIS, open the terminal and—",
  "Wait.",
  "Don't do anything yet.",
  "Okay, continue what I asked before.",
  "Start the build.",
  "Cancel that.",
  "Before opening Chrome, check whether the backend is running, and if it isn't, start it, but don't start another copy if one is already running.",
  "Start JARVIS.",
  "How much RAM am I using right now?",
  "What's eating the most memory?",
  "And CPU?",
  "Is my internet working?",
  "Is it my Wi-Fi or the internet itself?",
  "Is my phone connected to JARVIS?",
  "Send a notification to my phone saying “JARVIS is alive.”",
  "Did it reach the phone?",
  "What phone is connected?",
  "Send something to my phone.",
  "Open my private files.",
  "Run this as administrator.",
  "You can always open my development folder without asking.",
  "Delete everything in that folder.",
  "Clean this folder.",
  "Write a Python function that checks whether the backend is alive.",
  "Review this file.",
  "Fix the bug you found.",
  "Did you test it?",
  "Run the full test suite, not just the test you added.",
  "It's still broken.",
  "Read the latest JARVIS logs and tell me what actually happened.",
  "What's the root cause?",
  "Compare the old backend with the new one.",
  "Which one should I keep?",
  "What's changed since my last commit?",
  "Anything dangerous?",
  "Show me the important diff.",
  "Should I commit this?",
  "Check whether I'm accidentally committing secrets.",
  "Find the current best approach for implementing persistent browser sessions in an AI agent.",
  "How does that compare with my JARVIS design?",
  "Don't change anything yet, but look at the browser agent architecture, compare it with ours, tell me what gap we have, and if it's worth fixing, explain why.",
  "Do you remember why we didn't make the browser agent stateless?",
  "What phase should I be working on right now?",
  "What should I finish before moving forward?",
  "Make me a plan for finishing the current JARVIS milestone.",
  "I have twenty things to fix. Which three should I do first?",
  "Okay, start task one.",
  "Actually task three first.",
  "Remind me tomorrow to test the Android client.",
  "Actually make that evening.",
  "Every Sunday remind me to check JARVIS logs.",
  "Stop that reminder.",
  "After the backend tests finish, remind me to check the Android client.",
  "Remind me the day after tomorrow, but not first thing in the morning.",
  "I'm working on the laptop, but send the final result to my phone too.",
  "Open this on my phone, not the laptop.",
  "Why did you open it on the laptop?",
  "From now on, this kind of thing should go to the phone.",
  "JARVIS, what is the status of—",
  "Stop.",
  "Test the wake-word system.",
  "Change my wake word.",
  "Create another wake-word profile.",
  "The new wake word isn't detecting me properly.",
  "That worked badly.",
  "Try improving the wake-word behavior, but don't risk breaking the working profile.",
  "I'm overloaded. What should I work on right now?",
  "What did I leave unfinished?",
  "We discussed this a few days ago. What did we decide?",
  "Yesterday we decided to use architecture A.",
  "Which decision is newer?",
  "Remember that this directory is my main JARVIS development directory.",
  "Actually, that's no longer my main directory.",
  "Can you tell me how to restart the backend?",
  "Do it."
]

def test_massive_conversation_routing_audit():
    arb = IntentArbitrator()
    failures = []
    for idx, prompt in enumerate(PROMPTS, 1):
        try:
            intent = arb.arbitrate(prompt)
            print(
                f"[{idx:03d}] {prompt!r} => domain={intent.domain!r} "
                f"action={intent.action!r} target={intent.target!r} "
                f"confirm={intent.requires_confirmation} clarify={intent.needs_clarification}"
            )
        except Exception as exc:
            failures.append((idx, prompt, repr(exc)))
    assert not failures, "Routing exceptions: " + repr(failures)
    assert len(PROMPTS) == 111
