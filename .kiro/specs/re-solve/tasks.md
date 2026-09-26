# Tasks: Re-solve

- [x] 1. **Config and environment** — `app/config.py`, `.env.example`, `requirements.txt`. *Verify:* app starts in mock mode with no `.env`.
- [x] 2. **Pre-check** — normalization, word bank (`app/lexicon.json`), personal-info masking in `app/precheck.py`. *Test:* `tests/test_precheck.py`.
- [x] 3. **Policy** — tier combining, Content Safety floor, escalation guard in `app/policy.py`. *Test:* `tests/test_policy.py`.
- [x] 4. **Content Safety client** — `app/content_safety.py` (live + mock). *Verify:* `scripts/smoke_test.py`.
- [x] 5. **Agent instructions and Foundry setup** — `app/agent_instructions.py`, `scripts/setup_agents.py` creates the three Foundry agents (MCP tool optional).
- [x] 6. **Agent client** — `app/agents.py` calls Foundry agents, parses JSON, records trace; mock agents for backup mode.
- [x] 7. **Orchestrator** — `app/pipeline.py` runs steps in order with parallel calls and fallbacks. *Test:* `tests/test_pipeline.py`.
- [x] 8. **Stores and API** — `app/store.py` (feed, pending analyses, moderator queue with retention), `app/main.py`. *Test:* `tests/test_api.py`.
- [x] 9. **MCP server** — `mcp_server/server.py` exposing the safety tools. *Verify:* run and list tools.
- [x] 10. **Frontend** — `static/index.html`, `static/styles.css`, `static/app.js`: feed, composer, Re-solve panel, trace, moderator queue. *Verify:* run the three demo comments.
