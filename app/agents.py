"""Calls the three Foundry agents and validates their JSON replies.

FoundryAgents = live (used for judging). MockAgents = offline backup, clearly labelled in the UI.
"""
import json
import re
from functools import lru_cache

from app import config
from app.policy import ESCALATIONS, TIERS, tier_rank


class AgentError(RuntimeError):
    pass


# ---------- JSON parsing and validation ----------

def parse_json(text: str) -> dict:
    """Agents are told to return bare JSON; tolerate code fences or stray prose."""
    cleaned = re.sub(r"```(?:json)?", "", text or "").strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise AgentError(f"No JSON in agent reply: {text[:120]!r}")
    return json.loads(match.group(0))


def validate_classification(data: dict) -> dict:
    severity = str(data.get("severity", "")).lower()
    if severity not in TIERS:
        raise AgentError(f"Invalid severity {severity!r}")
    return {
        "is_bullying": bool(data.get("is_bullying", severity != "none")),
        "severity": severity,
        "category": str(data.get("category") or "none"),
        "target": str(data.get("target") or "none"),
        "writer_distress": bool(data.get("writer_distress", False)),
        "reason": str(data.get("reason") or "").strip(),
        "flagged_phrases": [str(p) for p in data.get("flagged_phrases") or []][:5],
    }


def validate_rewrite(data: dict) -> dict:
    alts = [str(a).strip() for a in data.get("alternatives") or []]
    alts = [a for a in alts if a and "[" not in a][:3]  # never echo placeholders
    if not alts:
        raise AgentError("Rewrite agent returned no usable alternatives")
    return {"alternatives": alts, "tip": str(data.get("tip") or "").strip()}


def validate_escalation(data: dict) -> dict:
    esc = str(data.get("escalation", "")).lower()
    return {
        "escalation": esc if esc in ESCALATIONS else None,
        "show_crisis_resources": bool(data.get("show_crisis_resources", False)),
        "user_message": str(data.get("user_message") or "").strip(),
        "moderator_summary": str(data.get("moderator_summary") or "").strip(),
    }


# ---------- Live Foundry agents ----------

class FoundryAgents:
    """One OpenAI-compatible client per agent, bound by agent name."""

    def __init__(self):
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential
        if not config.FOUNDRY_PROJECT_ENDPOINT:
            raise RuntimeError("FOUNDRY_PROJECT_ENDPOINT missing in .env")
        self._project = AIProjectClient(endpoint=config.FOUNDRY_PROJECT_ENDPOINT,
                                        credential=DefaultAzureCredential())
        self._clients = {}

    def _client(self, agent_name: str):
        if agent_name not in self._clients:
            self._clients[agent_name] = self._project.get_openai_client(agent_name=agent_name)
        return self._clients[agent_name]

    def _run(self, agent_name: str, payload: dict) -> tuple[dict, dict]:
        """Send one stateless request. Returns (parsed_json, trace_details)."""
        response = self._client(agent_name).responses.create(input=json.dumps(payload))
        tools_called = [getattr(item, "name", None) or getattr(item, "type", "")
                        for item in (response.output or [])
                        if getattr(item, "type", "") in ("mcp_call", "function_call")]
        details = {"response_id": getattr(response, "id", None), "tools_called": tools_called}
        return parse_json(response.output_text), details

    def classify(self, payload: dict):
        data, details = self._run(config.CLASSIFIER_AGENT, payload)
        return validate_classification(data), details

    def rewrite(self, payload: dict):
        data, details = self._run(config.REWRITE_AGENT, payload)
        return validate_rewrite(data), details

    def escalate(self, payload: dict):
        data, details = self._run(config.ESCALATION_AGENT, payload)
        return validate_escalation(data), details


# ---------- Offline backup agents (rule-based stand-ins) ----------

_DISTRESS = re.compile(r"\b(i want to die|hurt myself|kill myself|end it all|no reason to live)\b", re.I)

_MOCK_REASONS = {
    "insult": "This calls the person names instead of responding to what they said.",
    "mockery": "This makes fun of the person, which can feel humiliating.",
    "exclusion": "This tells someone they don't belong, which can hurt a lot.",
    "body_shaming": "This attacks how someone looks.",
    "harassment": "This attacks the person's worth.",
    "threat": "This reads as a threat to someone's safety.",
    "self_harm_encouragement": "This tells someone to hurt themselves.",
    "doxxing": "This shares or threatens to share someone's private information.",
}

_MOCK_REWRITES = {
    "threat": ["I'm really angry about this and need to step away.",
               "I strongly disagree with you, and I'm done arguing about it.",
               "This upset me. I'm going to take a break from this thread."],
    "self_harm_encouragement": ["I really disagree with you.",
                                "This conversation is getting heated. I'm going to step back.",
                                "I don't like what you said, but I'm not going to attack you."],
}
_DEFAULT_REWRITES = ["I don't agree with this, and here's why.",
                     "Not really my thing, but I can see you put work into it.",
                     "I see it differently. Can you explain what you meant?"]


class MockAgents:
    def classify(self, payload: dict):
        hits = payload.get("lexicon_hits", [])
        distress = bool(_DISTRESS.search(payload.get("comment", "")))
        top = max(hits, key=lambda h: tier_rank(h["severity"]), default=None)
        severity = top["severity"] if top else "none"
        category = top["category"] if top else "none"
        if payload.get("pii_found") and top:
            severity, category = "severe", "doxxing"
        result = {
            "is_bullying": severity != "none", "severity": severity, "category": category,
            "target": "individual" if top else "none", "writer_distress": distress,
            "reason": _MOCK_REASONS.get(category, ""),
            "flagged_phrases": [h["phrase"] for h in hits],
        }
        return result, {"response_id": "mock", "tools_called": []}

    def rewrite(self, payload: dict):
        alts = _MOCK_REWRITES.get(payload.get("category"), _DEFAULT_REWRITES)
        return ({"alternatives": alts, "tip": "Talking about the idea, not the person, keeps the conversation going."},
                {"response_id": "mock", "tools_called": []})

    def escalate(self, payload: dict):
        tier = payload.get("tier")
        messages = {
            "mild": "This could come across as rude. Want to try one of these instead?",
            "moderate": "This could really hurt the person you're replying to. If you post it anyway, a moderator will review it.",
            "severe": "This can't be posted because it could put someone at risk. A moderator has been notified.",
        }
        return ({"escalation": payload.get("policy"), "show_crisis_resources": False,
                 "user_message": messages.get(tier, ""),
                 "moderator_summary": f"{tier.title()} {payload.get('category', '').replace('_', ' ')} aimed at another user."},
                {"response_id": "mock", "tools_called": []})


@lru_cache(maxsize=1)
def get_agents():
    return MockAgents() if config.is_mock() else FoundryAgents()
