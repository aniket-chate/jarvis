"""Shared Google Cloud OAuth Helper for Calendar and Gmail APIs.

Provides a unified authentication manager using one Google Cloud OAuth Desktop App
covering both Calendar (read) and Gmail (read/compose) scopes.
Stores resulting token file in credentials/token.json.
"""

import os
import logging
from pathlib import Path
from typing import Optional

from config.settings import settings, CREDENTIALS_DIR

logger = logging.getLogger("JARVIS.Skills.GoogleAuth")

TOKEN_PATH = CREDENTIALS_DIR / "token.json"
CREDENTIALS_PATH = CREDENTIALS_DIR / "credentials.json"

# Shared scopes covering both Calendar read and Gmail read/draft creation
SHARED_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def get_shared_credentials():
    """Retrieves or refreshes shared Google OAuth credentials.

    Returns valid Credentials object or None if authorization is required.
    """
    if not settings.google_oauth_configured:
        logger.warning("[Google Auth] OAuth credentials not configured in .env or credentials/")
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request

        creds = None
        if TOKEN_PATH.exists():
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SHARED_SCOPES)

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            logger.info("[Google Auth] Refreshing expired token...")
            creds.refresh(Request())
            with open(TOKEN_PATH, "w", encoding="utf-8") as f:
                f.write(creds.to_json())
            logger.info("[Google Auth] Token successfully refreshed and persisted.")
            return creds

    except Exception as e:
        logger.error("[Google Auth Error] Credential retrieval failed: %s", str(e))

    return None


def run_oauth_flow(port: int = 0) -> bool:
    """Executes the desktop OAuth browser flow to authorize Google Calendar and Gmail."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS_PATH.exists():
        logger.error("[Google Auth] credentials.json not found at %s", CREDENTIALS_PATH)
        return False

    try:
        logger.info("[Google Auth] Launching local server for OAuth consent flow...")
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SHARED_SCOPES)
        creds = flow.run_local_server(port=port)

        CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_PATH, "w", encoding="utf-8") as f:
            f.write(creds.to_json())

        logger.info("[Google Auth] OAuth token successfully saved to %s", TOKEN_PATH)
        return True
    except Exception as e:
        logger.error("[Google Auth Error] OAuth flow failed: %s", str(e))
        return False
