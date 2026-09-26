"""Orchestrator: runs the multi-agent pipeline for one comment and records a trace.

Order:  pre-check -> [Content Safety || Classifier agent] -> policy
        -> [Rewrite agent || Escalation agent] -> policy guard
"""
import asyncio
import time
import uuid

from app import config, content_safety, policy
from app.agents import get_agents
from app.precheck import precheck


class Trace:
    def __init__(self):
        self.steps = []

    def add(self, step, actor, kind, ms, status, summary, output=None):
        self.steps.append({"step": step, "actor": actor, "kind": kind, "ms": round(ms),
                           "status": status, "summary": summary, "output": output})


async def _timed(func, *args):
    """Run a blocking call in a thread. Returns (result_or_exception, elapsed_ms)."""
    start = time.perf_counter()
    try:
        result = await asyncio.to_thread(func, *args)
    except Exception as exc:  # recorded in the trace, never crashes the request
        result = exc
    return result, (time.perf_counter() - start) * 1000


def _agent_kind() -> str:
    return "mock" if config.is_mock() else "foundry-agent"


async def analyze_comment(text: str) -> dict:
    trace = Trace()
    agents = get_agents()

    # 1. Pre-check (local)
    start = time.perf_counter()
    pre = precheck(text)
    trace.add("Pre-check", "Python pre-check", "local", (time.perf_counter() - start) * 1000, "ok",
              f"{len(pre.lexicon_hits)} word-bank hint(s); personal info masked: {', '.join(pre.pii_found) or 'none'}",
              {"normalized": pre.normalized_text, "hits": [h["phrase"] for h in pre.lexicon_hits],
               "floor_tier": pre.floor_tier})

    # 2. Content Safety and Classifier agent in parallel (both see masked text only)
    classifier_input = {"comment": pre.masked_text, "normalized": pre.normalized_text,
                        "lexicon_hits": pre.lexicon_hits, "pii_found": pre.pii_found}
    (cs, cs_ms), (cls, cls_ms) = await asyncio.gather(
        _timed(content_safety.analyze, pre.masked_text),
        _timed(agents.classify, classifier_input),
    )

    if isinstance(cs, Exception):
        trace.add("Harm scoring", "Azure AI Content Safety", "azure", cs_ms, "error", str(cs))
        cs_scores = {}
    else:
        cs_scores = cs
        trace.add("Harm scoring", "Azure AI Content Safety", "mock" if config.is_mock() else "azure",
                  cs_ms, "ok", ", ".join(f"{k} {v}" for k, v in cs.items()), cs)

    if isinstance(cls, Exception):
        trace.add("Classify", config.CLASSIFIER_AGENT, _agent_kind(), cls_ms, "error", str(cls))
        classification = None
    else:
        classification, details = cls
        trace.add("Classify", config.CLASSIFIER_AGENT, _agent_kind(), cls_ms, "ok",
                  f"{classification['severity']} / {classification['category']}",
                  {**classification, **details})

    # 3. Policy: combine signals (each can only raise severity)
    tier, degraded = policy.combine_tiers(
        classification["severity"] if classification else None,
        cs_scores, pre.floor_tier, pre.hint_tier)
    classification = classification or {
        "category": next((h["category"] for h in pre.lexicon_hits), "none"),
        "reason": "", "flagged_phrases": [h["phrase"] for h in pre.lexicon_hits],
        "writer_distress": False, "target": "none", "is_bullying": tier != "none"}
    trace.add("Combine", "Policy (code)", "policy", 0, "ok",
              f"final tier: {tier}" + (" (degraded: classifier unavailable)" if degraded else ""),
              {"classifier": classification.get("severity"), "content_safety_floor": policy.content_safety_floor(cs_scores),
               "word_bank_floor": pre.floor_tier})

    analysis = {
        "analysis_id": uuid.uuid4().hex, "tier": tier, "degraded": degraded,
        "mode": "mock" if config.is_mock() else "foundry",
        "category": classification["category"], "reason": classification["reason"],
        "flagged_phrases": classification["flagged_phrases"],
        "alternatives": [], "tip": "", "user_message": "", "moderator_summary": "",
        "escalation": "none", "can_post_anyway": True, "show_crisis_resources": False,
        "crisis_resources": [], "masked_text": pre.masked_text,
    }
    if tier == "none":
        analysis["trace"] = trace.steps
        return analysis

    # 4. Rewrite and Escalation agents in parallel
    policy_floor = policy.baseline_escalation(tier)
    (rw, rw_ms), (esc, esc_ms) = await asyncio.gather(
        _timed(agents.rewrite, {"comment": pre.masked_text, "category": classification["category"],
                                "reason": classification["reason"]}),
        _timed(agents.escalate, {"comment": pre.masked_text, "tier": tier,
                                 "category": classification["category"], "reason": classification["reason"],
                                 "writer_distress": classification["writer_distress"], "policy": policy_floor}),
    )

    if isinstance(rw, Exception):
        trace.add("Suggest", config.REWRITE_AGENT, _agent_kind(), rw_ms, "error", str(rw))
        analysis["alternatives"] = ["I see this differently, and here's why.",
                                    "I don't agree, but I'm not going to attack you over it."]
    else:
        rewrite, details = rw
        analysis.update(alternatives=rewrite["alternatives"], tip=rewrite["tip"])
        trace.add("Suggest", config.REWRITE_AGENT, _agent_kind(), rw_ms, "ok",
                  f"{len(rewrite['alternatives'])} alternatives", {**rewrite, **details})

    agent_escalation, agent_crisis = None, False
    if isinstance(esc, Exception):
        trace.add("Escalate", config.ESCALATION_AGENT, _agent_kind(), esc_ms, "error", str(esc))
    else:
        escalation, details = esc
        agent_escalation, agent_crisis = escalation["escalation"], escalation["show_crisis_resources"]
        analysis.update(user_message=escalation["user_message"],
                        moderator_summary=escalation["moderator_summary"])
        trace.add("Escalate", config.ESCALATION_AGENT, _agent_kind(), esc_ms, "ok",
                  f"recommends {agent_escalation}", {**escalation, **details})

    # 5. Policy guard: agent can raise the escalation, never lower it
    final = policy.decide_escalation(tier, agent_escalation)
    crisis = policy.needs_crisis_resources(classification["category"], classification["writer_distress"],
                                           agent_crisis, cs_scores)
    analysis.update(escalation=final, can_post_anyway=policy.can_post_anyway(final),
                    show_crisis_resources=crisis,
                    crisis_resources=policy.CRISIS_RESOURCES if crisis else [])
    if not analysis["user_message"]:
        analysis["user_message"] = "This comment could hurt someone. Take a second look before posting."
    if not analysis["moderator_summary"]:
        analysis["moderator_summary"] = f"{tier.title()} {classification['category'].replace('_', ' ')}."
    trace.add("Guard", "Policy (code)", "policy", 0, "ok",
              f"escalation: {final}; post anyway {'allowed' if analysis['can_post_anyway'] else 'blocked'}",
              {"baseline": policy_floor, "agent": agent_escalation, "final": final, "crisis_resources": crisis})

    analysis["trace"] = trace.steps
    return analysis
