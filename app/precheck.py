"""Pre-check: fast, local, deterministic. Runs before any cloud call.

1. Mask personal info (emails, phones, street addresses) so it never leaves the server.
2. Normalize disguised spellings (st00pid, s t u p i d, stuuupid, st*pid).
3. Match against the word bank (hash map of normalized phrases).
"""
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

from app.policy import TIERS, max_tier

# ---------- Personal-info masking ----------

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\d)")
_ADDRESS = re.compile(
    r"\b\d{1,5}\s+(?:[A-Za-z0-9]+\s+){1,4}"
    r"(?:street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct|way|place|pl)\b\.?",
    re.IGNORECASE,
)


def mask_personal_info(text: str) -> tuple[str, list[str]]:
    """Replace personal details with placeholders. Returns (masked_text, types_found)."""
    found = []
    for label, pattern in (("EMAIL", _EMAIL), ("PHONE", _PHONE), ("ADDRESS", _ADDRESS)):
        text, count = pattern.subn(f"[{label}]", text)
        if count:
            found.append(label.lower())
    return text, found


# ---------- Normalization ----------

_LOOKALIKES = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s",
                             "7": "t", "@": "a", "$": "s", "!": "i", "|": "l", "+": "t"})
_EDGE_PUNCT = ".,!?;:\"'()[]{}<>“”‘’…-"


def _clean_token(raw: str) -> str:
    """Lowercase, drop apostrophes, undo look-alike characters inside words."""
    token = raw.lower().strip(_EDGE_PUNCT).replace("'", "").replace("’", "")
    if any(ch.isalpha() for ch in token):  # leave pure numbers like "2026" alone
        token = token.translate(_LOOKALIKES)
    return re.sub(r"[^a-z0-9*]", "", token)


def _join_spaced_letters(tokens: list[str]) -> list[str]:
    """Merge runs of 3+ single letters: ['s','t','u','p','i','d'] -> ['stupid']."""
    merged, run = [], []
    for tok in tokens + [""]:  # sentinel flushes the last run
        if len(tok) == 1 and tok.isalpha():
            run.append(tok)
            continue
        merged.extend(["".join(run)] if len(run) >= 3 else run)
        run = []
        if tok:
            merged.append(tok)
    return merged


def _collapse_repeats(word: str) -> str:
    """'stuuupid' -> 'stupid'. Applied to both input and word bank so they match."""
    return re.sub(r"(.)\1+", r"\1", word)


def normalize(text: str) -> list[str]:
    tokens = [t for t in (_clean_token(w) for w in text.split()) if t]
    return _join_spaced_letters(tokens)


# ---------- Word bank ----------

_LEXICON_PATH = Path(__file__).with_name("lexicon.json")


def _load_lexicon() -> tuple[dict, dict, int]:
    entries = json.loads(_LEXICON_PATH.read_text())["entries"]
    by_key, single_words = {}, {}
    for e in entries:
        words = normalize(e["phrase"])
        by_key[" ".join(_collapse_repeats(w) for w in words)] = e
        if len(words) == 1:
            single_words[words[0]] = e
    longest = max(len(k.split()) for k in by_key)
    return by_key, single_words, longest


_BY_KEY, _SINGLE_WORDS, _LONGEST = _load_lexicon()


def _wildcard_hits(tokens: list[str]) -> list[dict]:
    """Match asterisk-masked words like 'st*pid' against single-word entries."""
    hits = []
    for tok in tokens:
        if "*" in tok and len(tok) >= 3:
            pattern = re.compile("^" + re.escape(tok).replace(r"\*", ".") + "$")
            hits += [e for word, e in _SINGLE_WORDS.items() if pattern.match(word)]
    return hits


def match_lexicon(tokens: list[str]) -> list[dict]:
    """Slide windows of 1..L tokens over the comment; each lookup is O(1)."""
    keys = [_collapse_repeats(t) for t in tokens]
    hits = []
    for i in range(len(keys)):
        for size in range(1, _LONGEST + 1):
            if i + size > len(keys):
                break
            entry = _BY_KEY.get(" ".join(keys[i:i + size]))
            if entry:
                hits.append(entry)
    hits += _wildcard_hits(tokens)
    unique = {e["phrase"]: e for e in hits}  # de-duplicate, keep order
    return list(unique.values())


# ---------- Public entry point ----------

@dataclass
class PrecheckResult:
    masked_text: str
    normalized_text: str
    lexicon_hits: list[dict] = field(default_factory=list)
    pii_found: list[str] = field(default_factory=list)
    hint_tier: str = "none"   # highest severity of any hit (a hint only)
    floor_tier: str = "none"  # highest severity of floor phrases (enforced)

    def to_dict(self) -> dict:
        return asdict(self)


def precheck(text: str) -> PrecheckResult:
    masked, pii = mask_personal_info(text)
    tokens = normalize(masked)
    hits = match_lexicon(tokens)
    hint = max_tier(*(h["severity"] for h in hits)) if hits else "none"
    floor = max_tier(*(h["severity"] for h in hits if h.get("floor"))) if hits else "none"
    assert hint in TIERS and floor in TIERS
    return PrecheckResult(masked, " ".join(tokens), hits, pii, hint, floor)
