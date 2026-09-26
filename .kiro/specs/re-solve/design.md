# Design: Re-solve

## Architecture

```
Browser (static/index.html)
   │  POST /api/analyze, /api/post
   ▼
FastAPI backend (app/main.py) ── orchestrator (app/pipeline.py)
   │
   ├─ 1. Pre-check (app/precheck.py)          local Python, no network
   │      normalize → word bank → mask personal info
   │
   ├─ 2a. Azure AI Content Safety  ─┐ run in parallel
   ├─ 2b. Classifier agent (Foundry) ┘
   │
   ├─ 3. Policy: combine severities (app/policy.py)
   │
   ├─ 4a. Rewrite agent (Foundry)    ─┐ run in parallel (skipped if tier = none)
   ├─ 4b. Escalation agent (Foundry) ┘
   │
   └─ 5. Policy guard: final action (agents can raise, never lower)
          → moderator queue (app/store.py)

MCP server (mcp_server/server.py) exposes precheck_text, content_safety_scan,
get_escalation_policy. Attached to the classifier agent in Foundry when a
public URL is set (dev tunnel), so the agent can call the same tools itself.
```

## Agents (Foundry prompt agents, created by `scripts/setup_agents.py`)

| Agent | Role | Input | Output (JSON) |
| --- | --- | --- | --- |
| `st-classifier` | Decide if the comment is bullying and how bad | masked comment, normalized text, word-bank hits, personal info found | `is_bullying, severity, category, target, writer_distress, reason, flagged_phrases` |
| `st-rewriter` | Offer kinder wording that keeps the writer's point | masked comment, category, reason | `alternatives[2-3], tip` |
| `st-escalation` | Choose escalation, write the user message and moderator summary | masked comment, final tier, category, reason, writer_distress | `escalation, user_message, show_crisis_resources, moderator_summary` |

Orchestration is done in Python (deterministic, testable, parallel). Agents are called with `project.get_openai_client(agent_name=...)` and the Responses API. No conversation is kept, so nothing persists between comments.

## Data model

- **PrecheckResult**: `masked_text, normalized_text, lexicon_hits[{phrase, category, severity, floor}], pii_found[types], hint_tier, floor_tier`
- **Analysis** (returned to the browser): `analysis_id, tier, category, reason, flagged_phrases, alternatives, tip, user_message, escalation, can_post_anyway, show_crisis_resources, crisis_resources, degraded, mode, trace[]`
- **Pending analysis** (server memory, 10-minute TTL): `analysis_id → {text_hash, tier, escalation, ...}`. Only a hash of the text is kept.
- **Flag** (moderator queue): `id, created_at, kind (flag_if_posted | alert_and_block), tier, category, masked_text, reason, moderator_summary, status`
- **Comment** (feed): `id, author, text, created_at`

## Severity and escalation logic (app/policy.py)

- Tiers ordered: none < mild < moderate < severe.
- Content Safety floor: any category ≥ 6 → severe, ≥ 4 → moderate. Level 2 is only a hint (avoids flagging "I'll kill this exam").
- Word bank: every hit is a hint for the classifier; only phrases marked `floor` (e.g. "kill yourself", "kys") force a tier.
- Final tier = max(classifier, Content Safety floor, word-bank floor). If the classifier fails: max(floors, hints) and `degraded = true`.
- Escalation baseline: none/mild → `none`; moderate → `flag_if_posted`; severe → `alert_and_block`. Final = max(baseline, agent recommendation).
- Crisis resources shown if the agent says so, the category is self-harm related, the writer is in distress, or Content Safety self-harm ≥ 2.

## Word bank matching (data structure)

A hash map from normalized phrase → entry. Keys and input tokens are normalized the same way (lowercase, look-alikes mapped, repeated letters collapsed), so "stuuupid", "stup1d" and "s t u p i d" all hit `stupid`. Matching slides a window of 1..L tokens (L = longest phrase) over the comment: O(n·L) lookups, each O(1). Asterisk-masked words ("st*pid") are matched with a wildcard against single-word entries of the same length.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/status` | mode (foundry/mock), agent names, MCP attached? |
| GET | `/api/feed` | the post and its comments |
| POST | `/api/analyze` | `{text}` → Analysis |
| POST | `/api/post` | `{text, analysis_id, post_anyway}` → published comment, or 403/409 |
| GET | `/api/moderation` | open flags (expired ones purged) |
| POST | `/api/moderation/{id}/resolve` | resolve a flag |

## UI flow

1. User types a comment and selects Post → "Checking…".
2. Clean → comment appears in the thread.
3. Flagged → the "Re-solve" panel opens under the composer: message, reason, highlighted phrases, alternatives ("Use this"), Edit, Post anyway (not shown for severe), crisis resources when relevant.
4. "Under the hood" column shows the numbered pipeline trace. "Moderator queue" tab shows escalations.

## Backup mode

`DEMO_MODE=mock` swaps Foundry and Content Safety for local heuristics so the demo and tests run offline. The UI shows a clear "Offline backup" label so it is never presented as the live system.
