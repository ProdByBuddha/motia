import os
import json
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .job_store import JobStore
from .executor import apply_operations, stage_workspace, apply_to_target, sanitize_base_path


WORK_DIR = os.environ.get("WORK_DIR", "/work/jobs")
REDIS_URL = os.environ.get("REDIS_URL")
ALLOW_SELF_MODIFY = os.environ.get("ALLOW_SELF_MODIFY", "0") == "1"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")

app = FastAPI(title="Motia Builder API", version="0.1.0")
store = JobStore(namespace="builder", redis_url=REDIS_URL, base_dir=WORK_DIR)


class RFCRequest(BaseModel):
    topic: str
    context: Optional[str] = None


class Operation(BaseModel):
    op: str = Field(description="upsert|delete")
    path: str
    content: Optional[str] = None


class ProposePatchRequest(BaseModel):
    base_path: Optional[str] = Field(default="/opt/motia/agents")
    description: Optional[str] = None
    operations: List[Operation] = Field(default_factory=list)


class RunTestsRequest(BaseModel):
    job_id: str


class ApplyJobRequest(BaseModel):
    job_id: str
    force: Optional[bool] = False


def call_llm(system: str, user: str) -> str:
    """Call OpenAI-compatible chat completions to draft an RFC. Minimal impl."""
    import requests
    base = OLLAMA_BASE_URL
    if not base:
        return "LLM base URL not configured; cannot draft RFC."
    try:
        payload: Dict[str, Any] = {
            "model": OLLAMA_MODEL,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 1200,
            "temperature": 0.5,
            "stream": False,
        }
        r = requests.post(f"{base.rstrip('/')}/v1/chat/completions", json=payload, timeout=90)
        r.raise_for_status()
        data = r.json()
        choice = (data.get("choices") or [{}])[0]
        msg = (choice.get("message") or {}).get("content") or ""
        return msg
    except Exception as e:
        return f"Error calling LLM: {e}"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs/rfc")
def jobs_rfc(req: RFCRequest):
    system = (
        "You are a senior software architect. Draft a concise RFC with: Title, Summary, Motivation, Goals, Non-Goals, Design (components, data, APIs), Risks, Test Plan, Rollout Plan, and Acceptance Criteria. Avoid chain-of-thought; present only final conclusions."
    )
    user = f"Topic: {req.topic}\n\nContext:\n{req.context or ''}"
    rfc = call_llm(system, user)
    job = store.new_job("rfc", {"topic": req.topic, "context": req.context, "rfc": rfc})
    store.update_status(job["id"], "completed", {"rfc": rfc})
    return {"job_id": job["id"], "rfc": rfc}


@app.post("/jobs/propose_patch")
def jobs_propose_patch(req: ProposePatchRequest):
    base_path = sanitize_base_path(req.base_path or "/opt/motia/agents")
    job = store.new_job("propose_patch", {"base_path": base_path, "description": req.description})
    ws = stage_workspace(base_path, WORK_DIR, job["id"])
    ops = [op.model_dump() for op in req.operations]
    applied, errors = apply_operations(ws, ops)
    result = {"workspace": ws, "applied": applied, "errors": errors}
    store.update_status(job["id"], "staged" if not errors else "error", result)
    return {"job_id": job["id"], **result}


@app.post("/jobs/run_tests")
def jobs_run_tests(req: RunTestsRequest):
    job = store.get_job(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    ws = os.path.join(WORK_DIR, req.job_id)
    ok = True
    logs: List[str] = []
    # MVP: no-op test runner; extend later
    logs.append("no tests configured; skipping")
    store.update_status(req.job_id, "tested", {"ok": ok, "logs": logs})
    return {"job_id": req.job_id, "ok": ok, "logs": logs}


@app.post("/jobs/apply")
def jobs_apply(req: ApplyJobRequest):
    job = store.get_job(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    if not ALLOW_SELF_MODIFY and not req.force:
        raise HTTPException(403, "self-modify disabled; set ALLOW_SELF_MODIFY=1 or pass force=true after approval")
    ws = os.path.join(WORK_DIR, req.job_id)
    payload = job.get("payload") or {}
    base_path = sanitize_base_path(payload.get("base_path") or "/opt/motia/agents")
    ops = ((job.get("result") or {}).get("applied") or [])
    notes = apply_to_target(base_path, ws, ops)
    store.update_status(req.job_id, "applied", {"notes": notes})
    return {"job_id": req.job_id, "notes": notes}


class ScaffoldRequest(BaseModel):
    name: str
    lang: str = Field(pattern="^(python|node)$")
    base_path: Optional[str] = "/opt/motia/agents"


@app.post("/jobs/scaffold")
def jobs_scaffold(req: ScaffoldRequest):
    base_path = sanitize_base_path(req.base_path or "/opt/motia/agents")
    job = store.new_job("scaffold", req.model_dump())
    ws = stage_workspace(base_path, WORK_DIR, job["id"])
    svc_dir = os.path.join(ws, req.name)
    os.makedirs(svc_dir, exist_ok=True)
    files: List[Dict[str, Any]] = []
    if req.lang == "python":
        main_py = os.path.join(svc_dir, "main.py")
        with open(main_py, "w") as f:
            f.write("""from fastapi import FastAPI\napp = FastAPI()\n@app.get('/health')\ndef health(): return {'status':'ok'}\n""")
        files.append({"path": f"{req.name}/main.py"})
        with open(os.path.join(svc_dir, "requirements.txt"), "w") as f:
            f.write("fastapi\nuvicorn[standard]\n")
        files.append({"path": f"{req.name}/requirements.txt"})
        with open(os.path.join(svc_dir, "Dockerfile"), "w") as f:
            f.write("""FROM python:3.11-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install -r requirements.txt\nCOPY . .\nEXPOSE 8080\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]\n""")
        files.append({"path": f"{req.name}/Dockerfile"})
    else:
        pkg = os.path.join(svc_dir, "package.json")
        with open(pkg, "w") as f:
            f.write(json.dumps({
                "name": req.name,
                "private": True,
                "scripts": {"start": "node server.js"}
            }, indent=2))
        files.append({"path": f"{req.name}/package.json"})
        with open(os.path.join(svc_dir, "server.js"), "w") as f:
            f.write("""const http=require('http');const s=http.createServer((q,r)=>{r.end('ok')});s.listen(8080,'0.0.0.0');""")
        files.append({"path": f"{req.name}/server.js"})
        with open(os.path.join(svc_dir, "Dockerfile"), "w") as f:
            f.write("""FROM node:20-alpine\nWORKDIR /app\nCOPY package.json .\nRUN npm install --omit=dev || true\nCOPY . .\nEXPOSE 8080\nCMD [\"node\", \"server.js\"]\n""")
        files.append({"path": f"{req.name}/Dockerfile"})
    store.update_status(job["id"], "staged", {"workspace": ws, "files": files})
    return {"job_id": job["id"], "workspace": ws, "files": files}


class RegisterToolRequest(BaseModel):
    tool: Dict[str, Any]


@app.post("/jobs/register_tool")
def jobs_register_tool(req: RegisterToolRequest):
    tools_path = "/opt/motia/agents/superqwen/.qwen/tools.json"
    # backup
    try:
        with open(tools_path, "r") as f:
            tools = json.load(f)
    except Exception as e:
        raise HTTPException(500, f"failed to load tools.json: {e}")
    tools.append(req.tool)
    tmp = f"{tools_path}.tmp"
    with open(tmp, "w") as f:
        json.dump(tools, f, indent=2)
    os.replace(tmp, tools_path)
    return {"status": "ok", "count": len(tools)}

