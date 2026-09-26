import pytest
from app.agents import AgentError, parse_json, validate_classification, validate_rewrite, validate_escalation


def test_parse_json_tolerates_fences_and_prose():
    assert parse_json('Sure!\n```json\n{"a": 1}\n```') == {"a": 1}


def test_parse_json_rejects_no_json():
    with pytest.raises(AgentError):
        parse_json("I can't help")


def test_invalid_severity_is_an_error():
    with pytest.raises(AgentError):
        validate_classification({"severity": "extreme"})


def test_rewrite_drops_placeholders():
    out = validate_rewrite({"alternatives": ["Call me at [PHONE]", "I disagree."]})
    assert out["alternatives"] == ["I disagree."]


def test_unknown_escalation_becomes_none():
    assert validate_escalation({"escalation": "ban_user"})["escalation"] is None
