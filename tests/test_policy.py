from app import policy


def test_content_safety_floor_ignores_level_two():
    assert policy.content_safety_floor({"Violence": 2}) == "none"
    assert policy.content_safety_floor({"Hate": 4}) == "moderate"
    assert policy.content_safety_floor({"SelfHarm": 6}) == "severe"


def test_classifier_can_be_raised_by_floors_not_lowered():
    assert policy.combine_tiers("mild", {"Violence": 6}, "none", "none") == ("severe", False)
    assert policy.combine_tiers("none", {}, "severe", "severe") == ("severe", False)
    assert policy.combine_tiers("moderate", {}, "none", "mild") == ("moderate", False)


def test_degraded_mode_uses_hints():
    assert policy.combine_tiers(None, {}, "none", "mild") == ("mild", True)


def test_agent_can_raise_but_never_lower_escalation():
    assert policy.decide_escalation("severe", "none") == "alert_and_block"
    assert policy.decide_escalation("moderate", "alert_and_block") == "alert_and_block"
    assert policy.decide_escalation("mild", "bogus") == "none"
    assert policy.decide_escalation("moderate", None) == "flag_if_posted"


def test_post_anyway_blocked_only_for_alerts():
    assert policy.can_post_anyway("flag_if_posted")
    assert not policy.can_post_anyway("alert_and_block")


def test_crisis_resources_triggers():
    assert policy.needs_crisis_resources("self_harm_encouragement", False, False, {})
    assert policy.needs_crisis_resources("insult", True, False, {})
    assert policy.needs_crisis_resources("insult", False, False, {"SelfHarm": 2})
    assert not policy.needs_crisis_resources("insult", False, False, {"SelfHarm": 0})
