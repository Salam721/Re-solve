"""FastAPI backend. Run:  uvicorn app.main:app --reload   then open http://localhost:8000"""
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import config, store
from app.pipeline import analyze_comment

app = FastAPI(title="Re-solve")


class AnalyzeRequest(BaseModel):
    text: str


class PostRequest(BaseModel):
    text: str
    analysis_id: str
    post_anyway: bool = False


def _validate_text(text: str) -> str:
    text = text.strip()
    if not text:
        raise HTTPException(400, "Write a comment first.")
    if len(text) > config.MAX_COMMENT_CHARS:
        raise HTTPException(400, f"Comments can be up to {config.MAX_COMMENT_CHARS} characters.")
    return text


@app.get("/api/status")
def status():
    return {"mode": "mock" if config.is_mock() else "foundry",
            "agents": [config.CLASSIFIER_AGENT, config.REWRITE_AGENT, config.ESCALATION_AGENT],
            "mcp_attached": bool(config.MCP_PUBLIC_URL) and not config.is_mock(),
            "retention_hours": config.FLAG_RETENTION_HOURS}


@app.get("/api/feed")
def feed():
    return store.FEED


@app.post("/api/analyze")
async def analyze(req: AnalyzeRequest):
    text = _validate_text(req.text)
    analysis = await analyze_comment(text)
    store.save_pending(analysis["analysis_id"], text, analysis)
    if analysis["escalation"] == "alert_and_block":
        store.add_flag("alert_and_block", store.get_pending(analysis["analysis_id"]))
    analysis.pop("masked_text", None)  # the browser already has the original
    return analysis


@app.post("/api/post")
def post(req: PostRequest):
    text = _validate_text(req.text)
    pending = store.get_pending(req.analysis_id)
    if not pending or pending["text_hash"] != store.text_hash(text):
        raise HTTPException(409, "This comment changed since it was checked. Post it again to re-check.")
    if pending["escalation"] == "alert_and_block":
        raise HTTPException(403, "This comment can't be posted because it could put someone at risk.")
    if pending["tier"] != "none" and not req.post_anyway:
        raise HTTPException(409, "Choose a suggestion, edit your comment, or post anyway.")

    flagged = False
    if req.post_anyway and pending["escalation"] == "flag_if_posted":
        store.add_flag("flag_if_posted", pending)
        flagged = True
    comment = store.add_comment(text)
    store.drop_pending(req.analysis_id)
    return {"comment": comment, "sent_to_moderator": flagged}


@app.get("/api/moderation")
def moderation():
    return {"items": store.list_flags(), "retention_hours": config.FLAG_RETENTION_HOURS}


@app.post("/api/moderation/{flag_id}/resolve")
def resolve(flag_id: str):
    if not store.resolve_flag(flag_id):
        raise HTTPException(404, "That item is no longer in the queue.")
    return {"resolved": flag_id}


app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "static", html=True), name="static")
