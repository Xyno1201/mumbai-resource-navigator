import os
import sys
import json
import uuid
from typing import Optional
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from src.workflow import mumbai_navigator_workflow, run_navigator

app = FastAPI(title="ReliefNet API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], 
                   allow_methods=["*"], allow_headers=["*"])

session_service = InMemorySessionService()
runner = Runner(agent=mumbai_navigator_workflow, 
                app_name="app", 
                session_service=session_service)

class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

def load_resource_by_id(resource_id: str) -> dict:
    """Load full resource details from resources.json by ID."""
    resources_path = os.path.join(project_root, "mcp_server", "resources.json")
    try:
        with open(resources_path, encoding="utf-8") as f:
            data = json.load(f)
        for r in data.get("resources", []):
            if r.get("resource_id") == resource_id:
                return r
    except Exception:
        pass
    return {}

@app.post("/chat")
async def chat(request: ChatRequest):
    session_id = request.session_id or str(uuid.uuid4())
    
    result = await run_navigator(
        request.query, session_id, runner, session_service
    )
    
    # Read enriched data from session state
    try:
        session = await session_service.get_session(
            app_name="app", 
            user_id="test_user", 
            session_id=session_id
        )
        intake_data = session.state.get("intake_data", {}) if session else {}
        matcher_data = session.state.get("matcher_data", {}) if session else {}
    except Exception:
        intake_data = {}
        matcher_data = {}
    
    detected_language = intake_data.get("detected_language", "english")
    response_type = result.get("response_type", "")
    fallback = result.get("fallback_used", {})
    resources_included = result.get("resources_included", [])
    
    # Build pipeline steps
    if response_type in ["crisis_redirect", "clarification_request"]:
        matcher_status = "skipped"
        matcher_detail = "bypassed"
    else:
        count = len(resources_included)
        matcher_status = "fallback" if fallback.get("matcher") else "done"
        matcher_detail = f"{count} result{'s' if count != 1 else ''} found"
    
    pipeline_steps = [
        {
            "name": "Intake",
            "status": "fallback" if fallback.get("intake") else "done",
            "detail": f"{detected_language.replace('_', ' ')} detected"
        },
        {
            "name": "Matcher",
            "status": matcher_status,
            "detail": matcher_detail
        },
        {
            "name": "Guardrail",
            "status": "fallback" if fallback.get("guardrail") else "done",
            "detail": response_type.replace("_", " ")
        }
    ]
    
    # Build full resource cards from resources.json
    resource_cards = []
    for rid in resources_included:
        full = load_resource_by_id(rid)
        if full:
            # Find eligibility_unconfirmed from matcher results
            eligibility_unconfirmed = False
            for r in matcher_data.get("results", []):
                if r.get("resource_id") == rid:
                    eligibility_unconfirmed = r.get("eligibility_unconfirmed", False)
                    break
            resource_cards.append({
                "resource_id": rid,
                "name": full.get("name", ""),
                "description": full.get("short_description", ""),
                "hours": full.get("operating_hours", ""),
                "phone": full.get("contact", {}).get("phone", ""),
                "address": full.get("contact", {}).get("address", ""),
                "website": full.get("contact", {}).get("website", ""),
                "eligibility_unconfirmed": eligibility_unconfirmed,
                "docs_required": full.get("eligibility", {}).get(
                    "documentation_required", []),
                "application_process": full.get("application_process", []),
                "special_notes": full.get("eligibility", {}).get("special_notes", "")
            })
    
    return {
        **result,
        "session_id": session_id,
        "detected_language": detected_language,
        "pipeline_steps": pipeline_steps,
        "resource_cards": resource_cards
    }

@app.get("/")
async def serve_ui():
    ui_path = os.path.join(project_root, "ui", "index.html")
    with open(ui_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.get("/health")
async def health():
    return {"status": "ok", "service": "ReliefNet API"}

if __name__ == "__main__":
    uvicorn.run(
        "src.api:app", 
        host="0.0.0.0", 
        port=8080, 
        reload=False,
        log_level="info"
    )
