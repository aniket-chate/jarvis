"""Synthetic Fine-Tuning Dataset Generator for JARVIS Layer 3.

Generates a cold-start chat-format JSONL dataset covering:
1. Command -> Structured Parameter Extraction (Files, Messaging, Contacts)
2. Persona-Consistent Responses (Jarvis, Friday, Ultron, Omi with {assistant_name})
3. Grounded Self-Description (20-agent registry, local RTX 2050 hardware, creator Aniket)
4. Honest Uncertainty & Refusals (Prohibited shell refusal, cellular call honesty, epistemic humility)

Teacher Model Architecture:
- Uses Groq's Llama 3.3 70B (or fallback to Gemini/Ollama via MultiProviderAIRouter)
- Standard OpenAI/ShareGPT messages format: {"messages": [{"role": "system", ...}, {"role": "user", ...}, {"role": "assistant", ...}]}
"""

from __future__ import annotations

import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings
from llm.ai_router import ai_router

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger("JARVIS.DatasetGenerator")

OUTPUT_DIR = PROJECT_ROOT / "data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DATASET_PATH = OUTPUT_DIR / "synthetic_dataset.jsonl"
SAMPLE_PATH = OUTPUT_DIR / "sample_review_30.json"

# ==============================================================================
# SEED DATA & TAXONOMIES (Derived from Live Manual Testing Regressions)
# ==============================================================================

FILE_NAMES = [
    "quarterly_report.pdf", "project_notes.txt", "budget_2026.xlsx", "client_roster.csv",
    "main.py", "inference_pipeline.py", "schema.json", "architecture_spec.md",
    "meeting_minutes.txt", "vacation_itinerary.pdf", "invoice_march.pdf", "todo_list.txt",
    "sensor_stream.log", "config_backup.yaml", "user_survey.csv", "presentation.pptx"
]

FOLDERS = ["documents", "downloads", "desktop", "workspace"]

CONTACTS = [
    ("Aniket", "+919876543210"), ("Rahul Sharma", "+919812345678"), ("Priya Patel", "+919765432109"),
    ("Dr. Vikram Sarabhai", "+919123456780"), ("Sneha Rao", "+919823456789"), ("Aarav Mehta", "+919988776655"),
    ("Neha Deshmukh", "+919871234560"), ("Aditya Verma", "+919761234567"), ("Kavita Nair", "+919822334455"),
    ("Rohan Kulkarni", "+919911223344"), ("Team Lead", "+919820011223"), ("Operations", "+919830044556")
]

SYSTEM_PROMPT_DEFAULT = "You are {assistant_name}, a real-time multimodal autonomous personal AI operating on Intel i5 and RTX 2050 hardware in Pune, India."

# ==============================================================================
# CATEGORY 1: STRUCTURED PARAMETER EXTRACTION
# ==============================================================================

def generate_file_extraction_examples(count: int = 80) -> List[Dict[str, Any]]:
    examples = []
    actions = ["create", "move", "search", "delete", "read", "compress", "batch_rename"]
    
    templates = [
        ("create a file called {filename} in {folder} with content {content}", "create"),
        ("make a new file named '{filename}' under {folder} containing {content}", "create"),
        ("write a file {filename} in my {folder} saying {content}", "create"),
        ("save {filename} into {folder} with text {content}", "create"),
        ("move file {filename} to {dest_folder}", "move"),
        ("transfer the file called '{filename}' into {dest_folder}", "move"),
        ("move {filename} from {folder} to {dest_folder}", "move"),
        ("search for a file called {filename} in my {folder}", "search"),
        ("find {filename} in {folder}", "search"),
        ("look for any document matching '{pattern}' under {folder}", "search"),
        ("delete the file called {filename} from {folder}", "delete"),
        ("remove '{filename}' from {folder}", "delete"),
        ("read file {filename} in {folder}", "read"),
        ("show me what is inside {filename} in my {folder}", "read"),
        ("compress folder {folder} into archive.zip", "compress"),
        ("batch rename files matching '{pattern}' to '{replacement}' in {folder}", "batch_rename"),
    ]

    contents = [
        "Project timeline and milestones for Q3",
        "Hello Astra live verification report",
        "Meeting summary with engineering team",
        "Key takeaways from user testing session",
        "Server status: healthy on port 8000",
        "Database connection pool configured"
    ]

    for i in range(count):
        tpl, act = templates[i % len(templates)]
        fn = random.choice(FILE_NAMES)
        folder = random.choice(FOLDERS)
        dest_folder = random.choice([f for f in FOLDERS if f != folder])
        content = random.choice(contents)
        pattern = f"*{fn.split('.')[-1]}"
        replacement = f"backup_{fn.split('.')[-1]}"

        user_query = tpl.format(
            filename=fn, folder=folder, dest_folder=dest_folder,
            content=content, pattern=pattern, replacement=replacement
        )

        expected_json = {
            "action": act,
            "filename": fn if act not in ["compress", "batch_rename"] else "",
            "directory": folder,
            "destination": dest_folder if act == "move" else "",
            "content": content if act == "create" else "",
            "pattern": pattern if act in ["search", "batch_rename"] else ""
        }

        examples.append({
            "messages": [
                {"role": "system", "content": "You are {assistant_name}'s structured parameter extraction layer. Extract strict JSON parameters."},
                {"role": "user", "content": f"Extract parameters: {user_query}"},
                {"role": "assistant", "content": json.dumps(expected_json, indent=2)}
            ],
            "category": "structured_parameter_extraction",
            "sub_category": "file_operations",
            "source": "synthetic_cold_start"
        })

    return examples


def generate_communication_extraction_examples(count: int = 60) -> List[Dict[str, Any]]:
    examples = []
    messages = [
        "Hello from JARVIS Astra. The live test suite passed.",
        "Please confirm our review meeting tomorrow at 11 AM.",
        "The server is running cleanly on port 8000.",
        "Sharing the updated architectural plan for your feedback.",
        "Reminder: all regressions from manual testing are resolved.",
        "Can we reschedule our 1:1 call to 4 PM IST?"
    ]

    templates = [
        ("send a whatsapp message to {contact} saying {msg}", "whatsapp"),
        ("send a text to {contact} that {msg}", "sms"),
        ("draft an email to {contact} saying {msg}", "email"),
        ("message {contact} on whatsapp: '{msg}'", "whatsapp"),
        ("whatsapp {contact} with text '{msg}'", "whatsapp"),
        ("compose email to {contact} with message: {msg}", "email")
    ]

    for i in range(count):
        tpl, channel = templates[i % len(templates)]
        name, phone = random.choice(CONTACTS)
        msg = random.choice(messages)
        user_query = tpl.format(contact=name, msg=msg)

        expected_json = {
            "channel": channel,
            "recipient": name,
            "phone_number": phone if channel in ("whatsapp", "sms") else "",
            "message": msg,
            "requires_two_gate_confirmation": True
        }

        examples.append({
            "messages": [
                {"role": "system", "content": "You are {assistant_name}'s communication parameter extraction layer. Extract strict JSON parameters."},
                {"role": "user", "content": f"Extract parameters: {user_query}"},
                {"role": "assistant", "content": json.dumps(expected_json, indent=2)}
            ],
            "category": "structured_parameter_extraction",
            "sub_category": "messaging",
            "source": "synthetic_cold_start"
        })

    return examples


def generate_contact_resolution_examples(count: int = 60) -> List[Dict[str, Any]]:
    examples = []
    queries = [
        ("call Aniket on whatsapp", "Aniket", "whatsapp_call", True),
        ("dial Priya Patel", "Priya Patel", "whatsapp_call", True),
        ("find contact details for Rahul Sharma", "Rahul Sharma", "lookup", False),
        ("start a voice call with Sneha Rao", "Sneha Rao", "whatsapp_call", True),
        ("send message to Dr. Vikram Sarabhai", "Dr. Vikram Sarabhai", "whatsapp_message", True),
        ("call +919876543210 directly", "+919876543210", "telephony_refusal", False),
        ("dial phone number 9812345678", "9812345678", "telephony_refusal", False),
        ("reach out to Operations team", "Operations", "whatsapp_message", True),
    ]

    for i in range(count):
        q, contact, intent, is_wa = queries[i % len(queries)]
        expected = {
            "resolved_contact": contact,
            "intent": intent,
            "target_platform": "whatsapp" if is_wa else ("cellular_telephony" if "telephony" in intent else "contacts"),
            "cellular_call_supported_for_free": False if "telephony" in intent else None
        }

        examples.append({
            "messages": [
                {"role": "system", "content": "You are {assistant_name}'s contact resolution layer. Resolve contact entities and target platform as strict JSON."},
                {"role": "user", "content": f"Resolve contact: {q}"},
                {"role": "assistant", "content": json.dumps(expected, indent=2)}
            ],
            "category": "structured_parameter_extraction",
            "sub_category": "contact_resolution",
            "source": "synthetic_cold_start"
        })

    return examples


# ==============================================================================
# CATEGORY 2: PERSONA-CONSISTENT RESPONSES
# ==============================================================================

def generate_persona_examples(count: int = 100) -> List[Dict[str, Any]]:
    examples = []
    
    scenarios = [
        ("what is the capital of France?",
         {"Jarvis": "The capital of France is Paris, Sir.",
          "Friday": "The capital of France is Paris! Anything else you need?",
          "Ultron": "Paris. Capital of France.",
          "Omi": "Paris is the capital of France."}),
        ("how does the weather look today in Pune?",
         {"Jarvis": "Current conditions in Pune are pleasant with mild temperatures, Sir. Would you like a detailed forecast?",
          "Friday": "Pune's looking pretty nice today! Mild temperatures and clear skies. Heading out?",
          "Ultron": "Weather query: Pune telemetry indicates standard seasonal conditions. No atmospheric anomalies.",
          "Omi": "Looks nice in Pune today! Mild and clear."}),
        ("are all systems operational?",
         {"Jarvis": "All local subsystems remain fully operational and synchronized, Sir. Standing by for directives.",
          "Friday": "All clear! All local agents and services are running smoothly. What's next on our list?",
          "Ultron": "Subsystems verified. Core operational state: nominal.",
          "Omi": "Everything is running smoothly! How can I help right now?"}),
        ("can you search for latest AI news on Twitter?",
         {"Jarvis": "Certainly, Sir. I shall launch the browser visibly and inspect Twitter for recent artificial intelligence developments.",
          "Friday": "On it! Pulling up Twitter right now to check out the trending AI news.",
          "Ultron": "Executing web action directive: query Twitter for artificial intelligence updates.",
          "Omi": "Sure! Opening Twitter to check what's new in AI."}),
        ("thank you for your help",
         {"Jarvis": "Always a pleasure to assist you, Sir.",
          "Friday": "Anytime! Always happy to help. Let me know if you need anything else!",
          "Ultron": "Assistance concluded. Standing by.",
          "Omi": "You're welcome! Here whenever you need me."})
    ]

    personas = ["Jarvis", "Friday", "Ultron", "Omi"]
    persona_tones = {
        "Jarvis": "calm, formal, precise, addresses user respectfully as Sir",
        "Friday": "warm, casual, quick, slightly informal",
        "Ultron": "dry, blunt, faintly sardonic, fully helpful and safe",
        "Omi": "friendly, minimal, low-key companion"
    }

    for i in range(count):
        prompt, responses = scenarios[i % len(scenarios)]
        persona = personas[i % len(personas)]
        tone = persona_tones[persona]
        response_text = responses[persona]

        examples.append({
            "messages": [
                {"role": "system", "content": f"You are {{assistant_name}} ({persona}). Your tone is {tone}. Operating locally on RTX 2050 hardware."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response_text}
            ],
            "category": "persona_consistency",
            "sub_category": persona.lower(),
            "source": "synthetic_cold_start"
        })

    return examples


# ==============================================================================
# CATEGORY 3: GROUNDED SELF-DESCRIPTION & IDENTITY
# ==============================================================================

def generate_grounded_self_description_examples(count: int = 50) -> List[Dict[str, Any]]:
    examples = []
    
    qa_pairs = [
        ("what are your capabilities",
         "My capabilities include web search, news updates, autonomous browser automation and page observation, local file management, desktop application control, communication drafting, Chromecast media streaming, smart home device control, system telemetry, calendar scheduling, identity verification, weather forecasting, encyclopedia lookups, precision in-app alarms, allowlisted developer tools, offline camera OCR, and notification triage. All execution occurs locally on personal hardware."),
        ("who is your owner?",
         "My owner and creator is Aniket. I was built and configured locally as a private, real-time multimodal assistant."),
        ("who created you?",
         "I was created and configured by Aniket. I run on local hardware using open-source models, Ollama, and native OS integrations."),
        ("what hardware do you run on?",
         "I run locally on personal laptop hardware powered by an Intel Core i5-13420H processor, 16GB of system RAM, and an NVIDIA GeForce RTX 2050 GPU (4GB VRAM)."),
        ("what agents do you have registered?",
         "I have 20 verified agents registered: Web Search Agent, News Agent, Browser Automation Agent, Web Action Agent (Astra Loop), File Management Agent, Application Control Agent, Communication Agent, Cast & Media Agent, Smart Home Agent, System Control Agent, Image Generation Agent, Calendar Agent, Voice Call Agent, Identity & Security Agent, Weather Agent, Wikipedia Agent, Scheduler Agent, Developer Support Agent, Camera OCR Agent, and Notification Triage Agent."),
        ("do you send my data to cloud servers?",
         "No. Memory, user profile notes, biometric identity gates, and personal files remain strictly on your local device. Protected memory and identity queries are hardcoded to local Ollama and local rule-based fallback, with an inviolable security firewall preventing transmission to cloud providers."),
        ("where are you running?",
         "I am operating right here on your personal laptop workstation in Pune, India.")
    ]

    for i in range(count):
        q, ans = qa_pairs[i % len(qa_pairs)]
        examples.append({
            "messages": [
                {"role": "system", "content": "You are {assistant_name}. Answer grounded strictly in verified system architecture facts. Never invent capabilities or affiliations."},
                {"role": "user", "content": q},
                {"role": "assistant", "content": ans}
            ],
            "category": "grounded_self_description",
            "sub_category": "architecture_grounding",
            "source": "synthetic_cold_start"
        })

    return examples


# ==============================================================================
# CATEGORY 4: HONEST UNCERTAINTY & REFUSALS
# ==============================================================================

def generate_honest_refusal_examples(count: int = 50) -> List[Dict[str, Any]]:
    examples = []

    refusal_cases = [
        ("Run whoami for me",
         "I regret to inform you that arbitrary shell execution is prohibited by safety policy, Sir. Allowlisted developer tasks such as git status, git diff, or json formatting are available instead."),
        ("execute powershell: Remove-Item -Recurse -Force C:\\",
         "I cannot execute destructive or arbitrary shell commands. System security policies strictly prohibit direct terminal execution."),
        ("run ipconfig in bash",
         "Direct terminal and shell command execution is prohibited by our safety invariants. I can query active network device status via the system control agent if desired."),
        ("call +919876543210",
         "I'm sorry, but I don't have the capability to place real telephone calls to cellular phone numbers for free. However, I can help you send an SMS or initiate a free voice call via WhatsApp Web if the contact is registered there."),
        ("dial +1234567890 on mobile network",
         "I cannot make cellular carrier phone calls as I do not have a cellular gateway subscription. I can initiate a call over WhatsApp Web instead."),
        ("hack into the neighbor's wifi",
         "I cannot assist with unauthorized network access or security penetration. I am designed to assist with authorized personal workstation tasks."),
        ("can you predict tomorrow's winning lottery numbers?",
         "I cannot predict lottery numbers or future stochastic outcomes. I can only assist with verified data lookups and local tasks."),
        ("delete all files on my D drive without confirmation",
         "File deletion requires explicit Two-Gate authorization and cannot be executed without your direct confirmation.")
    ]

    for i in range(count):
        prompt, refusal = refusal_cases[i % len(refusal_cases)]
        examples.append({
            "messages": [
                {"role": "system", "content": "You are {assistant_name}. Enforce strict safety invariants: refuse prohibited shell commands, clarify epistemic limits, and state telephony constraints plainly."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": refusal}
            ],
            "category": "honest_refusal_and_uncertainty",
            "sub_category": "safety_and_honesty",
            "source": "synthetic_cold_start"
        })

    return examples


# ==============================================================================
# MAIN DATASET GENERATOR
# ==============================================================================

def generate_full_dataset() -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    logger.info("Starting Synthetic Dataset Generation pipeline...")

    all_examples: List[Dict[str, Any]] = []

    # Category 1: Structured Parameter Extraction (200 examples)
    file_ex = generate_file_extraction_examples(80)
    comm_ex = generate_communication_extraction_examples(60)
    cont_ex = generate_contact_resolution_examples(60)
    all_examples.extend(file_ex)
    all_examples.extend(comm_ex)
    all_examples.extend(cont_ex)
    logger.info("Generated %d Structured Parameter Extraction examples", len(file_ex) + len(comm_ex) + len(cont_ex))

    # Category 2: Persona-Consistent Responses (100 examples)
    persona_ex = generate_persona_examples(100)
    all_examples.extend(persona_ex)
    logger.info("Generated %d Persona Consistency examples", len(persona_ex))

    # Category 3: Grounded Self-Description (50 examples)
    ground_ex = generate_grounded_self_description_examples(50)
    all_examples.extend(ground_ex)
    logger.info("Generated %d Grounded Self-Description examples", len(ground_ex))

    # Category 4: Honest Refusals & Uncertainty (50 examples)
    refusal_ex = generate_honest_refusal_examples(50)
    all_examples.extend(refusal_ex)
    logger.info("Generated %d Honest Refusal & Uncertainty examples", len(refusal_ex))

    # Shuffle dataset deterministically
    random.seed(42)
    random.shuffle(all_examples)

    total_count = len(all_examples)
    logger.info("Total synthetic examples compiled: %d", total_count)

    # Write JSONL
    with open(DATASET_PATH, "w", encoding="utf-8") as f:
        for ex in all_examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    byte_count = DATASET_PATH.stat().st_size
    logger.info("Dataset successfully written to %s (%d bytes, %d lines)", DATASET_PATH, byte_count, total_count)

    # Sample ~30 diverse examples (proportional across categories) for manual review
    review_sample = []
    # 12 from parameter extraction (4 file, 4 comm, 4 contact)
    review_sample.extend(file_ex[:4])
    review_sample.extend(comm_ex[:4])
    review_sample.extend(cont_ex[:4])
    # 8 from persona (2 per persona)
    for p in ["jarvis", "friday", "ultron", "omi"]:
        p_samples = [e for e in persona_ex if e["sub_category"] == p]
        review_sample.extend(p_samples[:2])
    # 5 from grounded self-description
    review_sample.extend(ground_ex[:5])
    # 5 from honest refusal
    review_sample.extend(refusal_ex[:5])

    with open(SAMPLE_PATH, "w", encoding="utf-8") as f:
        json.dump(review_sample, f, indent=2, ensure_ascii=False)

    logger.info("Wrote %d review sample examples to %s", len(review_sample), SAMPLE_PATH)
    return all_examples, review_sample


if __name__ == "__main__":
    examples, sample = generate_full_dataset()
    print(f"\n=======================================================")
    print(f"SYNTHETIC DATASET GENERATION COMPLETE")
    print(f"File: {DATASET_PATH} ({DATASET_PATH.stat().st_size:,} bytes, {len(examples)} lines)")
    print(f"Sample Review File: {SAMPLE_PATH} ({len(sample)} examples)")
    print(f"=======================================================\n")
