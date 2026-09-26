"""Settings loaded from .env. Nothing secret is ever sent to the browser."""
import os
from dotenv import load_dotenv

load_dotenv()

DEMO_MODE = os.getenv("DEMO_MODE", "foundry").strip().lower()  # "foundry" or "mock"
FOUNDRY_PROJECT_ENDPOINT = os.getenv("FOUNDRY_PROJECT_ENDPOINT", "")
MODEL_DEPLOYMENT = os.getenv("MODEL_DEPLOYMENT", "gpt-5-mini")
CONTENT_SAFETY_ENDPOINT = os.getenv("CONTENT_SAFETY_ENDPOINT", "")
CONTENT_SAFETY_KEY = os.getenv("CONTENT_SAFETY_KEY", "")
MCP_PUBLIC_URL = os.getenv("MCP_PUBLIC_URL", "").strip()
FLAG_RETENTION_HOURS = float(os.getenv("FLAG_RETENTION_HOURS", "24"))

MAX_COMMENT_CHARS = 1000
PENDING_TTL_SECONDS = 600  # an analysis must be used within 10 minutes

# Foundry agent names (created by scripts/setup_agents.py)
CLASSIFIER_AGENT = "st-classifier"
REWRITE_AGENT = "st-rewriter"
ESCALATION_AGENT = "st-escalation"


def is_mock() -> bool:
    return DEMO_MODE == "mock"
