# Project steering: Re-solve

- Purpose: a multi-agent system that checks social media comments before they are posted, warns about cyberbullying, suggests kinder alternatives, and escalates by severity. Built for the Code for Change hackathon (Microsoft Foundry Agents).
- Microsoft Foundry is required: all three agents are Foundry prompt agents; harm scoring uses Azure AI Content Safety.
- Backend: Python 3.11+, FastAPI. Frontend: plain HTML/CSS/vanilla JS served by the backend (no build step).
- Secrets live only in `.env` (never in the browser, never committed).
- Privacy by default: mask personal info before any cloud call; store only escalated comments, masked, with a retention limit.
- Safety rules are enforced in code (`app/policy.py`); agents may raise an escalation, never lower one.
- Small, well-named functions with short comments. Tests with pytest.
