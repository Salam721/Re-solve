"""Safety policy enforced in code. Agents advise; this module decides the floor.

Rule of thumb: every signal can only RAISE severity or escalation, never lower it.
"""

TIERS = ["none", "mild", "moderate", "severe"]
ESCALATIONS = ["none", "flag_if_posted", "alert_and_block"]

SELF_HARM_CATEGORIES = {"self_harm_encouragement", "self_harm"}

CRISIS_RESOURCES = [
    {"name": "988 Suicide & Crisis Lifeline (US)", "detail": "Call or text 988"},
    {"name": "Crisis Text Line (US)", "detail": "Text HOME to 741741"},
    {"name": "Outside the US", "detail": "findahelpline.com"},
]


def tier_rank(tier: str) -> int:
    return TIERS.index(tier) if tier in TIERS else 0


def max_tier(*tiers: str) -> str:
    """Highest of the given tiers (unknown values count as 'none')."""
    return max(tiers, key=tier_rank, default="none") if tiers else "none"


def content_safety_floor(scores: dict[str, int]) -> str:
    """Map Content Safety severities (0/2/4/6) to a floor tier.

    Level 2 is ignored on purpose: it fires on harmless phrases like
    "I'll kill this exam". The classifier agent handles those nuances.
    """
    top = max(scores.values(), default=0)
    if top >= 6:
        return "severe"
    if top >= 4:
        return "moderate"
    return "none"


def content_safety_hint(scores: dict[str, int]) -> str:
    """Weaker signal used only when the classifier agent is unavailable."""
    return "mild" if max(scores.values(), default=0) >= 2 else "none"


def combine_tiers(classifier_tier: str | None, cs_scores: dict[str, int],
                  lexicon_floor: str, lexicon_hint: str) -> tuple[str, bool]:
    """Final tier and whether we are in degraded mode (classifier missing)."""
    floors = max_tier(content_safety_floor(cs_scores), lexicon_floor)
    if classifier_tier is None:
        return max_tier(floors, lexicon_hint, content_safety_hint(cs_scores)), True
    return max_tier(classifier_tier, floors), False


def baseline_escalation(tier: str) -> str:
    return {"moderate": "flag_if_posted", "severe": "alert_and_block"}.get(tier, "none")


def decide_escalation(tier: str, agent_recommendation: str | None) -> str:
    """Agent may raise the escalation above the baseline, never lower it."""
    base = baseline_escalation(tier)
    rec = agent_recommendation if agent_recommendation in ESCALATIONS else "none"
    return max(base, rec, key=ESCALATIONS.index)


def can_post_anyway(escalation: str) -> bool:
    return escalation != "alert_and_block"


def needs_crisis_resources(category: str, writer_distress: bool,
                           agent_flag: bool, cs_scores: dict[str, int]) -> bool:
    return (agent_flag or writer_distress or category in SELF_HARM_CATEGORIES
            or cs_scores.get("SelfHarm", 0) >= 2)
