# Re-solve

A multi-agent system built on **Microsoft Foundry** that checks social media comments *before* they're posted. When a comment looks like cyberbullying, it explains why, offers kinder ways to say it, and escalates by severity. Mild comments can still be posted, moderate ones go to a moderator if posted anyway, and severe ones are blocked and alerted.

Spec: `.kiro/specs/re-solve/` (requirements, design, tasks).

## How it works

```
Comment → Pre-check (Python: mask personal info, undo disguised spellings, word bank)
        → Azure AI Content Safety  ║  Classifier agent (Foundry)      [parallel]
        → Policy: final severity = highest signal
        → Rewrite agent (Foundry)  ║  Escalation agent (Foundry)      [parallel]
        → Policy guard: agents may raise escalation, never lower it
        → Post / Post anyway / Blocked + moderator queue
```

| Component | Where | Job |
| --- | --- | --- |
| `st-classifier` | Foundry agent | Is this bullying? Category, severity, reason, flagged words |
| `st-rewriter` | Foundry agent | 3 kinder alternatives that keep the writer's point |
| `st-escalation` | Foundry agent | Escalation choice, message to the writer, moderator summary |
| Content Safety | Azure AI (Foundry) | Hate / Violence / Sexual / SelfHarm scores |
| MCP server | `mcp_server/` | Exposes the safety tools to the classifier agent over MCP |
| Policy | `app/policy.py` | Safety floor enforced in code |

## Setup (about 20 minutes)

1. **Foundry project.** In the Foundry portal (ai.azure.com, new Foundry), create a project and deploy a chat model such as `gpt-5-mini`. Copy the **project endpoint** (Overview) and **deployment name** (Build > Deployments).
2. **Content Safety.** In the Azure portal, open your Foundry resource > **Keys and Endpoint** and copy the endpoint and a key. If Content Safety calls fail with that resource, create a separate Content Safety resource and use its values.
3. **Local environment.**
   ```bash
   az login
   python -m venv .venv
   source .venv/bin/activate            # Windows: .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   cp .env.example .env                 # Windows: copy .env.example .env
   ```
   Fill in `.env`. Your account needs the **Azure AI User** role on the project.
4. **Create the agents in Foundry.**
   ```bash
   python -m scripts.setup_agents
   ```
   They appear in the Foundry portal under Agents. Re-run after changing `app/agent_instructions.py`.
5. **Smoke test.**
   ```bash
   python -m scripts.smoke_test
   ```
   Every line should end in `ok`.
6. **Run the app.**
   ```bash
   uvicorn app.main:app --reload
   ```
   Open http://localhost:8000. The header should say **Live on Microsoft Foundry**.

### Optional: let the classifier agent call MCP tools (Foundry + MCP credit)

Foundry calls MCP servers from the cloud, so the server needs a public URL.

1. Run `python -m mcp_server.server` (port 8001).
2. Expose port 8001 publicly, for example with VS Code's **Ports** panel (Forward a Port, then set visibility to Public) or a dev tunnel.
3. Set `MCP_PUBLIC_URL=https://<your-tunnel>/mcp` in `.env` and re-run `python -m scripts.setup_agents`.

The header then says **+ MCP tools**, and tool calls appear in the classifier's trace output. The tunnel URL is public, so shut it down after the demo.

### Backup mode

`DEMO_MODE=mock` runs everything offline with rule-based stand-ins. The header shows **Offline backup (mock agents)**. Use it only if Foundry is unreachable, and say so to the judges.

## Tests

```bash
DEMO_MODE=mock python -m pytest -q
```
31 tests cover the pre-check, policy rules, agent-output validation, the pipeline (including agent failures), and the API.

## Demo script (about 5 minutes)

| Time | What to do | What to say |
| --- | --- | --- |
| 0:00 | Show the feed | "Cyberbullying happens in the moment. Platforms react after the harm. Re-solve steps in before the post." Name the audience: any social platform, with teens and young adults as the most affected group. |
| 0:30 | Post `Love the colors in the sky!` | "Clean comments post instantly. Nobody gets interrupted." |
| 0:50 | Post `this is so st00pid lol` | "Disguised spelling is caught. Mild tier: a warning, alternatives, and the writer keeps the choice." Select **Use this**, then **Post**. |
| 1:40 | Post `nobody wants you here, ur so ugly` | "Moderate: targeted exclusion and body shaming." Select **Post anyway**, then open **Moderator queue**. |
| 2:30 | Post `watch your back. I know where you live` | "Severe: a threat. Post anyway is gone and a moderator was alerted." |
| 3:00 | Point at **Under the hood**, then switch to the Foundry portal | "Three Foundry agents with separate roles, Content Safety, and a policy guard in code. The escalation agent can raise the response but never lower it." Show traces in the portal. |
| 4:00 | Safety slide | Personal info masked before any cloud call; only escalated comments stored, deleted after 24h; crisis resources for self-harm; limitations below. |
| 4:45 | Close | "Next: patterns across multiple comments, more languages, and a moderator appeal flow." |

Rehearse with the exact comments above, and record a backup video.

## Safety and privacy

- Emails, phone numbers, and addresses are masked before Content Safety or any agent sees the text.
- Nothing is stored unless it's posted or escalated. Pending checks keep a hash of the text for 10 minutes.
- Moderator items are deleted when resolved or after `FLAG_RETENTION_HOURS`.
- Keys stay in `.env` on the server; the browser never sees them.
- Severity floors and escalation rules are enforced in code, so a wrong or failed agent reply can't weaken them.
- Crisis resources (988, Crisis Text Line, findahelpline.com) appear for self-harm content or a writer in distress.

## Limitations

- It can misread sarcasm, slang, reclaimed words, and non-English text.
- It judges one comment at a time, not harassment patterns.
- The word bank is intentionally small; Content Safety and the classifier carry most of the detection.
- It supports human moderators rather than replacing them.
- The demo uses in-memory storage, so data resets when the server restarts.
