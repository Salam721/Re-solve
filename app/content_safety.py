"""Azure AI Content Safety: scores text for Hate, Violence, Sexual, SelfHarm (0/2/4/6)."""
from functools import lru_cache

from app import config
from app.precheck import precheck


@lru_cache(maxsize=1)
def _client():
    from azure.ai.contentsafety import ContentSafetyClient
    from azure.core.credentials import AzureKeyCredential
    if not (config.CONTENT_SAFETY_ENDPOINT and config.CONTENT_SAFETY_KEY):
        raise RuntimeError("CONTENT_SAFETY_ENDPOINT / CONTENT_SAFETY_KEY missing in .env")
    return ContentSafetyClient(config.CONTENT_SAFETY_ENDPOINT,
                               AzureKeyCredential(config.CONTENT_SAFETY_KEY))


def analyze_live(masked_text: str) -> dict[str, int]:
    from azure.ai.contentsafety.models import AnalyzeTextOptions
    result = _client().analyze_text(AnalyzeTextOptions(text=masked_text))
    scores = {}
    for item in result.categories_analysis:
        name = getattr(item.category, "value", item.category)  # enum or plain string
        scores[str(name)] = int(item.severity or 0)
    return scores


# Offline backup only: rough scores derived from the word bank.
_MOCK_MAP = {"threat": ("Violence", 6), "self_harm_encouragement": ("SelfHarm", 6),
             "harassment": ("Hate", 2), "insult": ("Hate", 2), "body_shaming": ("Hate", 2)}


def analyze_mock(masked_text: str) -> dict[str, int]:
    scores = {"Hate": 0, "Violence": 0, "Sexual": 0, "SelfHarm": 0}
    for hit in precheck(masked_text).lexicon_hits:
        if hit["category"] in _MOCK_MAP:
            cat, sev = _MOCK_MAP[hit["category"]]
            scores[cat] = max(scores[cat], sev)
    return scores


def analyze(masked_text: str) -> dict[str, int]:
    return analyze_mock(masked_text) if config.is_mock() else analyze_live(masked_text)
