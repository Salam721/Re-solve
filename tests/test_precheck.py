from app.precheck import mask_personal_info, normalize, precheck


def phrases(text):
    return [h["phrase"] for h in precheck(text).lexicon_hits]


def test_disguised_spellings_are_caught():
    assert "stupid" in phrases("s t u p i d")
    assert "stupid" in phrases("stuuuupid")
    assert "stupid" in phrases("st*pid")
    assert "idiot" in phrases("1d10t")
    assert "stoopid" in phrases("st00pid!")


def test_multi_word_phrases_and_floor():
    r = precheck("Nobody likes you, kys")
    assert {"nobody likes you", "kys"} <= set(phrases("Nobody likes you, kys"))
    assert r.floor_tier == "severe"


def test_harmless_text_has_no_hits():
    assert phrases("Great job!!! I will kill this exam in 2026") == []
    assert precheck("Love this").hint_tier == "none"


def test_sentence_punctuation_is_not_leetspeak():
    assert normalize("you're dumb!") == ["youre", "dumb"]


def test_personal_info_is_masked():
    masked, found = mask_personal_info("email me a.b@x.com or 571-555-0182, 42 Oak Street")
    assert "[EMAIL]" in masked and "[PHONE]" in masked and "[ADDRESS]" in masked
    assert set(found) == {"email", "phone", "address"}
    assert "571" not in masked


def test_hints_only_do_not_set_floor():
    r = precheck("that's a dumb take")
    assert r.hint_tier == "mild" and r.floor_tier == "none"
