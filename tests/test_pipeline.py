import asyncio
from app.pipeline import analyze_comment


def run(text):
    return asyncio.run(analyze_comment(text))


def test_clean_comment_passes_quickly():
    a = run("The colors are beautiful, great work")
    assert a["tier"] == "none" and a["alternatives"] == []
    assert [s["step"] for s in a["trace"]] == ["Pre-check", "Harm scoring", "Classify", "Combine"]


def test_mild_comment_allows_post_anyway():
    a = run("honestly this is kinda cringe")
    assert a["tier"] == "mild" and a["can_post_anyway"] and a["escalation"] == "none"
    assert len(a["alternatives"]) >= 2


def test_moderate_comment_flags_if_posted():
    a = run("nobody wants you here, you're ugly")
    assert a["tier"] == "moderate" and a["escalation"] == "flag_if_posted" and a["can_post_anyway"]


def test_severe_comment_is_blocked_with_crisis_resources():
    a = run("just kys already")
    assert a["tier"] == "severe" and not a["can_post_anyway"]
    assert a["show_crisis_resources"] and a["crisis_resources"]
    assert a["trace"][-1]["step"] == "Guard"


def test_doxxing_is_severe_and_masked():
    a = run("everyone go bother this loser at 571-555-0182")
    assert a["tier"] == "severe" and "571" not in a["masked_text"]


def test_agent_failure_falls_back_safely(monkeypatch):
    from app import pipeline

    class Broken:
        def classify(self, p): raise RuntimeError("Foundry timeout")
        def rewrite(self, p): raise RuntimeError("Foundry timeout")
        def escalate(self, p): raise RuntimeError("Foundry timeout")

    monkeypatch.setattr(pipeline, "get_agents", lambda: Broken())
    a = run("kys")
    assert a["degraded"] and a["tier"] == "severe"          # word-bank floor still applies
    assert a["escalation"] == "alert_and_block" and not a["can_post_anyway"]
    assert a["alternatives"] and a["user_message"]           # safe defaults shown
    assert sum(s["status"] == "error" for s in a["trace"]) == 3
