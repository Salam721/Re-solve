"""MCP server: exposes Re-solve's safety tools over the Model Context Protocol.

Run:   python -m mcp_server.server        (serves http://localhost:8001/mcp)
To let the Foundry classifier agent call these tools, expose port 8001 publicly
(e.g. VS Code port forwarding / dev tunnel, visibility "Public"), put the URL
ending in /mcp in MCP_PUBLIC_URL, and re-run  python -m scripts.setup_agents
"""
from mcp.server.fastmcp import FastMCP

from app import content_safety, policy
from app.precheck import precheck

mcp = FastMCP("re-solve-safety", host="0.0.0.0", port=8001,
              stateless_http=True, json_response=True)


@mcp.tool()
def precheck_text(text: str) -> dict:
    """Normalize disguised spellings, match the cyberbullying word bank, and mask personal info.
    Returns masked_text, normalized_text, lexicon_hits, pii_found, hint_tier, floor_tier."""
    return precheck(text).to_dict()


@mcp.tool()
def content_safety_scan(text: str) -> dict:
    """Score text with Azure AI Content Safety (Hate, Violence, Sexual, SelfHarm; 0/2/4/6).
    Personal info is masked before scanning."""
    masked = precheck(text).masked_text
    scores = content_safety.analyze(masked)
    return {"scores": scores, "floor_tier": policy.content_safety_floor(scores)}


@mcp.tool()
def get_escalation_policy() -> dict:
    """Return the platform's severity tiers and the minimum escalation for each."""
    return {
        "tiers": {
            "none": "No bullying. Post normally.",
            "mild": "Rude or teasing. Warn and suggest; the writer may post anyway.",
            "moderate": "Targeted insult, harassment, exclusion, body shaming, slur. "
                        "Warn and suggest; if posted anyway a moderator reviews it.",
            "severe": "Threat, encouraging self-harm, doxxing, sexual harassment. "
                      "Cannot be posted; a moderator is alerted.",
        },
        "minimum_escalation": {t: policy.baseline_escalation(t) for t in policy.TIERS},
        "rule": "Escalation may be raised above the minimum, never lowered.",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
