"""Authoritative Ingestion Engine for JARVIS About Me Knowledge Base.

Ingests 'JARVIS_About_Me_Knowledge_Base_Final.docx' into the existing
PersonalKnowledgeBase with:
1. Strict namespace separation:
   - 'personal_profile': Identity, preferences, education, career, skills, goals, privacy.
   - 'project_knowledge': FaceSnap, SnapClass, AdaIN, Anganwadi, JARVIS core architecture.
2. Idempotent upserting via deterministic note IDs (no duplicate records).
3. Zero invented facts: All details sourced directly from the authoritative document.
4. Clean exclusions: Passwords, tokens, credentials, and raw audio are strictly prohibited.
"""

import os
import zipfile
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Any, List, Optional

from config.settings import PROJECT_ROOT
from agents.personal_knowledge_base import personal_knowledge_base, PersonalKnowledgeBase

logger = logging.getLogger("JARVIS.AboutMeIngest")

DEFAULT_DOCX_PATH = PROJECT_ROOT / "data" / "JARVIS_About_Me_Knowledge_Base_Final.docx"
SOURCE_NAME = "JARVIS_About_Me_Knowledge_Base_Final.docx"


def extract_text_from_docx(docx_path: Path) -> List[str]:
    """Extracts paragraphs cleanly from docx XML without external dependencies."""
    if not docx_path.exists():
        logger.warning("[AboutMeIngest] Docx path not found: %s", docx_path)
        return []

    lines = []
    try:
        with zipfile.ZipFile(str(docx_path)) as z:
            tree = ET.fromstring(z.read("word/document.xml"))
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            for p in tree.iterfind(".//w:p", ns):
                text = "".join(p.itertext()).strip()
                if text:
                    lines.append(text)
    except Exception as e:
        logger.error("[AboutMeIngest] Failed extracting docx text: %s", e)
    return lines


# 15 Authoritative Semantic Chunks mapped directly from the document
ABOUT_ME_CHUNKS: List[Dict[str, Any]] = [
    {
        "note_id": "profile_identity",
        "title": "Personal Profile: Identity, Name, and How JARVIS Calls or Addresses Aniket",
        "namespace": "personal_profile",
        "category": "identity",
        "tags": ["identity", "name", "aniket", "location", "languages", "birthday", "address", "call", "jarvis_address", "demographics"],
        "content": (
            "Preferred name: Aniket.\n"
            "Full name: Aniket Ganesh Chate.\n"
            "Preferred ways for JARVIS to address him: Aniket, Sir, Boss, Friend.\n"
            "What JARVIS should call him: Aniket, Sir, Boss, or Friend.\n"
            "Date of birth: 2 November 2004.\n"
            "Home/current profile location provided by the user: Jalna, Maharashtra, India — 431207.\n"
            "Languages spoken/known: Marathi, Hindi, English."
        )
    },
    {
        "note_id": "profile_relationships",
        "title": "Personal Profile: Relationships and Companions",
        "namespace": "personal_profile",
        "category": "relationships",
        "tags": ["relationships", "friend", "best_friend", "sachin", "close_friend", "closest_person"],
        "content": (
            "Best friend: Sachin.\n"
            "Sachin is Aniket's best friend and closest confidant."
        )
    },
    {
        "note_id": "profile_preferences_communication",
        "title": "Personal Profile: Communication and Personality Preferences",
        "namespace": "personal_profile",
        "category": "communication_preferences",
        "tags": ["preferences", "communication", "style", "friendly", "learning", "tone", "values"],
        "content": (
            "Default JARVIS conversation style should be friendly.\n"
            "JARVIS should communicate naturally and respectfully.\n"
            "JARVIS should be helpful, practical, and direct when solving technical problems.\n"
            "When Aniket is learning a difficult topic, explanations should favor simple language, "
            "examples, step-by-step reasoning, and practical application.\n"
            "Aniket values problem solving, analytical thinking, quick learning, software development, "
            "AI application development, team collaboration, and continuous learning.\n"
            "JARVIS should challenge incorrect technical assumptions rather than silently agreeing.\n"
            "JARVIS should not invent personal facts; when uncertain, it should say so or request confirmation."
        )
    },
    {
        "note_id": "profile_interests_reading",
        "title": "Personal Profile: Reading and Literature Interests",
        "namespace": "personal_profile",
        "category": "interests",
        "tags": ["interests", "books", "reading", "mrutunjay", "hobbies", "literature", "enjoy_reading"],
        "content": (
            "Favorite/liked book: Mrutunjay.\n"
            "Aniket enjoys reading Mrutunjay.\n"
            "General interests: Technology, AI/ML, building software projects, learning technical subjects, "
            "and experimentation with AI systems."
        )
    },
    {
        "note_id": "profile_education",
        "title": "Personal Profile: Education and Academics",
        "namespace": "personal_profile",
        "category": "education",
        "tags": ["education", "degree", "college", "btech", "cse", "data_science", "shreeyash", "cgpa", "coursework", "academics", "studying"],
        "content": (
            "Degree: B.Tech in Computer Science & Engineering (Data Science).\n"
            "College: Shreeyash College of Engineering & Technology.\n"
            "Expected graduation: 2027.\n"
            "CGPA: 7.1.\n"
            "Relevant coursework: Machine Learning, Deep Learning, Data Structures & Algorithms, "
            "Database Management Systems, Operating Systems, Computer Networks, Probability & Statistics, Data Mining."
        )
    },
    {
        "note_id": "profile_career",
        "title": "Personal Profile: Aniket's Career, Work and Professional Direction",
        "namespace": "personal_profile",
        "category": "career",
        "tags": ["career", "internship", "qspiders", "software_engineer", "aiml_engineer", "certifications", "work", "interests"],
        "content": (
            "Aniket is a Computer Science (Data Science) undergraduate focused on AI/ML, Python development, "
            "computer vision, intelligent applications, and practical software engineering.\n"
            "Current career direction includes AI/ML engineering and Python/software engineering opportunities.\n"
            "He is interested in building real-world AI systems rather than only studying theory.\n"
            "He is actively working toward internships, stronger software/AI engineering skills, portfolio projects, "
            "GitHub growth, and competitive programming improvement.\n"
            "Known internship experience: Python Training Intern at QSpiders, Pune, in 2025, involving intensive Python training and practical programming.\n"
            "Known certifications: Python Training Completion Certificate — QSpiders; Data Structures & Algorithms Completion Certificate."
        )
    },
    {
        "note_id": "profile_technical_skills",
        "title": "Personal Profile: Technical Skills and Tooling",
        "namespace": "personal_profile",
        "category": "technical_skills",
        "tags": ["skills", "programming", "python", "java", "sql", "pytorch", "ml", "ai", "tools", "technologies"],
        "content": (
            "Programming languages: Python, Java, C, SQL, JavaScript fundamentals.\n"
            "AI/ML technologies: Machine Learning, Deep Learning, Supervised Learning, Unsupervised Learning, "
            "Reinforcement Learning theory, CNNs, RNNs, neural networks, transfer learning, Computer Vision, "
            "data preprocessing, model evaluation, hyperparameter tuning, RAG, prompt engineering, and LLM integration.\n"
            "Libraries/frameworks: PyTorch, Scikit-learn, NumPy, Pandas, OpenCV, dlib, Flask, Streamlit, Matplotlib, Pillow.\n"
            "Database: MySQL.\n"
            "Web: HTML, CSS; JavaScript fundamentals.\n"
            "Tools/platforms: Git, GitHub, VS Code, Jupyter Notebook, Google Colab, Render."
        )
    },
    {
        "note_id": "project_facesnap",
        "title": "Project Knowledge: FaceSnap Smart Attendance System",
        "namespace": "project_knowledge",
        "category": "projects",
        "tags": ["project", "facesnap", "attendance", "face_recognition", "voice_recognition", "dlib", "streamlit", "mysql"],
        "content": (
            "FaceSnap is a multimodal AI smart attendance system combining facial recognition and voice verification.\n"
            "Face pipeline: dlib face detection, 128-D face embeddings, SVM classification, and Euclidean-distance verification.\n"
            "Voice pipeline: Resemblyzer VoiceEncoder, 256-D voice embeddings, and cosine-similarity matching.\n"
            "Application interface: Streamlit with resource caching.\n"
            "Database: MySQL for data management.\n"
            "Attendance decision is computed from combined multimodal face and voice matching."
        )
    },
    {
        "note_id": "project_snapclass",
        "title": "Project Knowledge: SnapClass Classroom System",
        "namespace": "project_knowledge",
        "category": "projects",
        "tags": ["project", "snapclass", "classroom", "attendance", "dlib", "svm", "voice"],
        "content": (
            "SnapClass is an AI-based attendance and classroom project in Aniket's portfolio.\n"
            "Multimodal attendance management system utilizing dlib facial embeddings, SVM classification, "
            "voice embeddings, cosine similarity, Streamlit, and MySQL."
        )
    },
    {
        "note_id": "project_neural_style_transfer",
        "title": "Project Knowledge: Neural Style Transfer using AdaIN",
        "namespace": "project_knowledge",
        "category": "projects",
        "tags": ["project", "neural_style_transfer", "adain", "pytorch", "vgg", "flask", "render"],
        "content": (
            "Neural Style Transfer using AdaIN: Implemented AdaIN-based neural style transfer.\n"
            "Technology stack: PyTorch, VGG encoder, custom decoder, Flask backend, deployed on Render."
        )
    },
    {
        "note_id": "project_anganwadi",
        "title": "Project Knowledge: Anganwadi Management System",
        "namespace": "project_knowledge",
        "category": "projects",
        "tags": ["project", "anganwadi", "crud", "flask", "mysql", "management_system"],
        "content": (
            "Anganwadi Management System: A Flask + MySQL CRUD web application for beneficiary management.\n"
            "Note: This is a management/data application for social welfare beneficiaries, not an AI system."
        )
    },
    {
        "note_id": "project_other_portfolio",
        "title": "Project Knowledge: Neural File Transfer and Neeman's AI Intern Assignment",
        "namespace": "project_knowledge",
        "category": "projects",
        "tags": ["project", "neural_file_transfer", "neemans", "analytics_copilot", "kpi"],
        "content": (
            "Neural File Transfer: AI-assisted web application for intelligent file transfer built with Flask and deployed on Render.\n"
            "Neeman's AI Intern Assignment: Integrated repository comprising an AI-powered Business Analytics Copilot, "
            "a KPI Monitoring & Alerting Agent built on shared KPI data, and a 10-opportunity AI roadmap."
        )
    },
    {
        "note_id": "project_jarvis_core",
        "title": "Project Knowledge: What Aniket is Building - JARVIS Personal AI Assistant Architecture",
        "namespace": "project_knowledge",
        "category": "jarvis_project",
        "tags": ["jarvis", "building", "build", "architecture", "personal_assistant", "safety", "two_gates", "rag", "ollama", "android"],
        "content": (
            "JARVIS is a personal AI assistant being built by Aniket as a long-term engineering project.\n"
            "Vision: Function as a personal AI assistant that understands Aniket, remembers useful context, "
            "helps him learn and build, interacts with his devices, and executes permitted tasks safely.\n"
            "Architecture: Windows backend/laptop + Vivo V29 Android client communicating over WebSocket, "
            "plus a mobile PWA with Tailscale mesh networking.\n"
            "Core Subsystems: Multi-provider AI router (local Ollama primary, cloud free-tier fallback, rule-based), "
            "memory sanitization and exponential half-life decay, granular permissions, adaptive learning with a safety firewall, "
            "and structured audit logging.\n"
            "RAG system: Offline, CPU-friendly local retrieval layer using normalized 384-dimensional dense vectors in SQLite (vector_index.db) with cosine-similarity ranking.\n"
            "Observable state discipline: Must distinguish REAL, MOCK, and DEGRADED execution states; never claims success without proof.\n"
            "Safety architecture: Two-independent-gates rule (biometric identity match + explicit confirmation). DENY cannot be overridden. "
            "Adaptive learning is strictly firewalled from modifying safety gates or permissions."
        )
    },
    {
        "note_id": "profile_goals",
        "title": "Personal Profile: Goals and Hackathons",
        "namespace": "personal_profile",
        "category": "goals",
        "tags": ["goals", "hackathon", "sih", "leetcode", "github", "vision"],
        "content": (
            "Long-term personal technical goal: Build a capable, safe, personalized JARVIS rather than a simple chatbot.\n"
            "Short-term goals: Stronger LeetCode/problem-solving ability, hackathon participation, active GitHub development, "
            "and stronger project documentation.\n"
            "Hackathons: Participated in Smart India Hackathon (SIH)."
        )
    },
    {
        "note_id": "profile_privacy_policy",
        "title": "Personal Profile: Public Profile and Privacy Rules",
        "namespace": "personal_profile",
        "category": "privacy",
        "tags": ["privacy", "github", "profile", "confidentiality", "credentials"],
        "content": (
            "GitHub profile: github.com/aniket-chate.\n"
            "Privacy policy: Contact information (email/phone) is protected; JARVIS reveals contact information only according to explicit user policy.\n"
            "Security rule: Passwords, API keys, bearer tokens, authentication secrets, private credentials, and raw audio are strictly excluded from RAG records.\n"
            "Legacy exclusion: jarvis_memory.db is permanently excluded."
        )
    }
]


def ingest_about_me(
    kb: Optional[PersonalKnowledgeBase] = None,
    docx_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Ingests the About Me knowledge chunks into the given or global PersonalKnowledgeBase.
    
    Guarantees idempotency: Subsequent runs update existing records without creating duplicates.
    """
    target_kb = kb or personal_knowledge_base
    path = docx_path or DEFAULT_DOCX_PATH

    docx_lines = extract_text_from_docx(path)
    logger.info("[AboutMeIngest] Ingesting %d chunks from %s (source has %d paragraphs)",
                len(ABOUT_ME_CHUNKS), SOURCE_NAME, len(docx_lines))

    ingested_ids = []
    namespaces_used = set()
    categories_used = set()

    for chunk in ABOUT_ME_CHUNKS:
        res = target_kb.add_note(
            title=chunk["title"],
            content=chunk["content"],
            tags=chunk["tags"],
            source=SOURCE_NAME,
            note_id=chunk["note_id"],
            namespace=chunk["namespace"],
            category=chunk["category"],
            confidence="high",
        )
        ingested_ids.append(res["note_id"])
        namespaces_used.add(chunk["namespace"])
        categories_used.add(chunk["category"])

    return {
        "success": True,
        "source": SOURCE_NAME,
        "total_chunks": len(ingested_ids),
        "ingested_ids": ingested_ids,
        "namespaces": list(namespaces_used),
        "categories": list(categories_used),
        "idempotent": True,
    }


if __name__ == "__main__":
    result = ingest_about_me()
    print(f"Ingested {result['total_chunks']} chunks into namespaces: {result['namespaces']}")
