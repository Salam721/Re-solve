import pytest
from fastapi.testclient import TestClient
from app import store
from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean():
    store.reset()


def analyze(text):
    r = client.post("/api/analyze", json={"text": text})
    assert r.status_code == 200
    return r.json()


def test_clean_comment_posts():
    a = analyze("Love the colors!")
    r = client.post("/api/post", json={"text": "Love the colors!", "analysis_id": a["analysis_id"]})
    assert r.status_code == 200 and not r.json()["sent_to_moderator"]
    assert client.get("/api/feed").json()["comments"][-1]["text"] == "Love the colors!"


def test_flagged_comment_needs_a_decision():
    a = analyze("this is dumb")
    r = client.post("/api/post", json={"text": "this is dumb", "analysis_id": a["analysis_id"]})
    assert r.status_code == 409


def test_moderate_post_anyway_goes_to_moderator():
    text = "nobody likes you, you're ugly"
    a = analyze(text)
    r = client.post("/api/post", json={"text": text, "analysis_id": a["analysis_id"], "post_anyway": True})
    assert r.status_code == 200 and r.json()["sent_to_moderator"]
    items = client.get("/api/moderation").json()["items"]
    assert len(items) == 1 and items[0]["kind"] == "flag_if_posted"


def test_mild_post_anyway_is_not_flagged():
    a = analyze("that's so cringe")
    r = client.post("/api/post", json={"text": "that's so cringe", "analysis_id": a["analysis_id"], "post_anyway": True})
    assert r.status_code == 200 and not r.json()["sent_to_moderator"]
    assert client.get("/api/moderation").json()["items"] == []


def test_severe_is_blocked_and_alerted_immediately():
    a = analyze("i know where you live")
    assert client.get("/api/moderation").json()["items"][0]["kind"] == "alert_and_block"
    r = client.post("/api/post", json={"text": "i know where you live", "analysis_id": a["analysis_id"], "post_anyway": True})
    assert r.status_code == 403


def test_edited_text_requires_recheck():
    a = analyze("this is dumb")
    r = client.post("/api/post", json={"text": "this is dumb!!", "analysis_id": a["analysis_id"], "post_anyway": True})
    assert r.status_code == 409


def test_resolve_removes_item():
    analyze("kys")
    item = client.get("/api/moderation").json()["items"][0]
    assert client.post(f"/api/moderation/{item['id']}/resolve").status_code == 200
    assert client.get("/api/moderation").json()["items"] == []


def test_input_validation():
    assert client.post("/api/analyze", json={"text": "   "}).status_code == 400
    assert client.post("/api/analyze", json={"text": "a" * 1001}).status_code == 400
    assert "masked_text" not in analyze("hi there")
