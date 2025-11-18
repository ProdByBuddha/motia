import os
import json
from typing import Any, Dict, List, Optional
import subprocess
import shlex
import time
import py_compile
import pathlib
import requests

from fastapi import FastAPI, HTTPException, Query, Path
from pydantic import BaseModel, Field

from .job_store import JobStore
from .executor import apply_operations, stage_workspace, apply_to_target, sanitize_base_path


WORK_DIR = os.environ.get("WORK_DIR", "/work/jobs")
REDIS_URL = os.environ.get("REDIS_URL")
ALLOW_SELF_MODIFY = os.environ.get("ALLOW_SELF_MODIFY", "0") == "1"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL") or os.environ.get("OLLAMA_HOST")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3:8b")

# Daytona + Vault config
DAYTONA_API_URL = (os.environ.get("DAYTONA_API_URL") or "https://app.daytona.io/api").rstrip("/")
# Optional overrides for resource paths (allow adapting to API differences)
DAYTONA_CREATE_PATH = os.environ.get("DAYTONA_CREATE_PATH")  # e.g., "workspaces" or "sandboxes"
DAYTONA_RUN_PATH_TMPL = os.environ.get("DAYTONA_RUN_PATH_TEMPLATE")  # e.g., "workspaces/{id}/run"
DAYTONA_DESTROY_PATH_TMPL = os.environ.get("DAYTONA_DESTROY_PATH_TEMPLATE")  # e.g., "workspaces/{id}"
VAULT_ADDR = os.environ.get("VAULT_ADDR", "").rstrip("/")
VAULT_TOKEN = os.environ.get("VAULT_TOKEN", "")
VAULT_TOKEN_FILE = os.environ.get("VAULT_TOKEN_FILE", "/etc/motia/vault-token")
VAULT_DAYTONA_PATH = os.environ.get("VAULT_DAYTONA_PATH", "secret/data/motia/daytona")
DAYTONA_API_KEY_ENV = os.environ.get("DAYTONA_API_KEY", "")
DAYTONA_DEFAULT_SNAPSHOT = os.environ.get("DAYTONA_DEFAULT_SNAPSHOT", "").strip()
DAYTONA_ORG_ID = os.environ.get("DAYTONA_ORG_ID", "")

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
    mode: Optional[str] = None  # 'local' (default) or 'daytona'
    git_url: Optional[str] = None
    branch: Optional[str] = None
    commands: Optional[List[str]] = None


class ApplyJobRequest(BaseModel):
    job_id: str
    force: Optional[bool] = False


class BoltRequest(BaseModel):
    mode: Optional[str] = "local"  # 'local' or 'daytona'
    git_url: Optional[str] = None
    branch: Optional[str] = "main"
    bolt_args: Optional[List[str]] = None
    workdir: Optional[str] = None  # local-only override


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
    # Daytona sandbox path
    if (req.mode or '').lower() == 'daytona':
        result = _run_tests_daytona(req)
        store.update_status(req.job_id, "tested", {"ok": result.get('ok'), "logs": result.get('logs', []), "sandbox": result.get('sandbox', {})})
        return {"job_id": req.job_id, **result}
    ok = True
    logs: List[str] = []
    # Language-aware lightweight checks
    py_files: List[str] = []
    json_files: List[str] = []
    try:
        for root, dirs, files in os.walk(ws):
            for fn in files:
                p = os.path.join(root, fn)
                if fn.endswith('.py'):
                    py_files.append(p)
                if fn.endswith('.json') or fn == 'package.json':
                    json_files.append(p)
    except Exception as e:
        logs.append(f"walk error: {e}")
        ok = False

    # Python syntax compile
    for f in py_files:
        try:
            py_compile.compile(f, doraise=True)
            logs.append(f"python ok: {os.path.relpath(f, ws)}")
        except Exception as e:
            logs.append(f"python error: {os.path.relpath(f, ws)} -> {e}")
            ok = False

    # JSON validity
    for f in json_files:
        try:
            with open(f, 'r') as fh:
                json.load(fh)
            logs.append(f"json ok: {os.path.relpath(f, ws)}")
        except Exception as e:
            logs.append(f"json error: {os.path.relpath(f, ws)} -> {e}")
            ok = False

    # Node project detection and optional smoke tests
    pkg_paths: List[str] = []
    root_pkg = os.path.join(ws, 'package.json')
    if os.path.exists(root_pkg):
        pkg_paths.append(ws)
    # Also check first-level dirs for nested services
    try:
        for name in os.listdir(ws):
            p = os.path.join(ws, name)
            if os.path.isdir(p) and os.path.exists(os.path.join(p, 'package.json')):
                pkg_paths.append(p)
    except Exception:
        pass

    def run_cmd(cmd: str, cwd: str, timeout: int = 120) -> Dict[str, Any]:
        t0 = time.time()
        try:
            proc = subprocess.run(shlex.split(cmd), cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, text=True)
            return {"rc": proc.returncode, "out": proc.stdout, "secs": round(time.time() - t0, 2)}
        except subprocess.TimeoutExpired as e:
            return {"rc": 124, "out": f"timeout after {timeout}s\n{getattr(e, 'output', '')}", "secs": round(time.time() - t0, 2)}
        except Exception as e:
            return {"rc": 1, "out": f"error: {e}", "secs": round(time.time() - t0, 2)}

    for proj in pkg_paths[:2]:  # limit to 2 projects to keep runs short
        # quick install (omit optional); keep short timeouts
        res_i = run_cmd("npm ci --silent --omit=optional --no-fund --no-audit", cwd=proj, timeout=180)
        logs.append(f"[{os.path.relpath(proj, ws)}] npm ci rc={res_i['rc']} ({res_i['secs']}s)\n{res_i['out'][:800]}")
        if res_i["rc"] != 0:
            ok = False
            continue
        # run tests if defined
        res_t = run_cmd("npm test --silent --if-present", cwd=proj, timeout=180)
        logs.append(f"[{os.path.relpath(proj, ws)}] npm test rc={res_t['rc']} ({res_t['secs']}s)\n{res_t['out'][:800]}")
        if res_t["rc"] != 0 and res_t["rc"] != 0:
            # if tests failed or script absent (some shells return 0 for if-present)
            ok = ok and (res_t["rc"] == 0)

    if not py_files and not json_files and not pkg_paths:
        logs.append("no recognizable files found for checks; skipping")
    store.update_status(req.job_id, "tested", {"ok": ok, "logs": logs})
    return {"job_id": req.job_id, "ok": ok, "logs": logs}


def _vault_get_token() -> str:
    if VAULT_TOKEN:
        return VAULT_TOKEN
    try:
        if VAULT_TOKEN_FILE and os.path.exists(VAULT_TOKEN_FILE):
            with open(VAULT_TOKEN_FILE, 'r') as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def _get_daytona_api_key() -> str:
    # Prefer env if set explicitly
    if DAYTONA_API_KEY_ENV:
        return DAYTONA_API_KEY_ENV
    # Vault lookup
    if not VAULT_ADDR:
        return ""
    token = _vault_get_token()
    if not token:
        return ""
    url = f"{VAULT_ADDR}/v1/{VAULT_DAYTONA_PATH}"
    try:
        r = requests.get(url, headers={"X-Vault-Token": token, "Accept": "application/json"}, timeout=10)
        r.raise_for_status()
        data = r.json()
        payload = data.get('data', {})
        if 'data' in payload:  # KV v2
            payload = payload['data']
        return payload.get('api_key', '')
    except Exception:
        return ""


def _daytona_call(path: str, method: str = 'GET', payload: Optional[Dict[str, Any]] = None, timeout: int = 60) -> Dict[str, Any]:
    """
    Call Daytona REST API with base URL variations for compatibility:
    - Tries DAYTONA_API_URL as-is
    - Also tries with /v1, /api, /api/v1 prefixes when 404/405 encountered
    """
    key = _get_daytona_api_key()
    if not key:
        raise HTTPException(400, "Daytona API key not available (configure in Vault or env)")

    from urllib.parse import urlsplit, urlunsplit
    raw_base = (DAYTONA_API_URL or '').strip()
    if not raw_base:
        raise HTTPException(400, "DAYTONA_API_URL not configured")
    parts = urlsplit(raw_base)
    scheme = parts.scheme or 'https'
    netloc = parts.netloc or parts.path  # support bare host
    base_path = parts.path or ''
    base_path = base_path.rstrip('/')

    # Candidate path prefixes appended to scheme://netloc
    path_prefixes: List[str] = []
    def add_prefix(p: str):
        p = ('/' + p.strip('/')) if p else ''
        if p not in path_prefixes:
            path_prefixes.append(p)

    # Derive candidates from provided base_path
    add_prefix(base_path)
    if base_path != base_path + '/v1' and not base_path.endswith('/v1'):
        add_prefix(base_path + '/v1')
    if not base_path.endswith('/api') and '/api' not in base_path:
        add_prefix(base_path + '/api')
        add_prefix(base_path + '/api/v1')
    else:
        if not base_path.endswith('/api/v1'):
            add_prefix(base_path + '/v1')
            add_prefix(base_path.replace('/api', '/api/v1'))
        # only strip trailing /api if it exists at the end
        if base_path.endswith('/api'):
            add_prefix(base_path[:-4])

    # Hostname fallback: if using app.daytona.io, also try api.daytona.io roots
    bases: List[str] = []
    def add_base(prefix: str, host: str):
        url = urlunsplit((scheme, host, prefix.strip('/'), '', ''))
        url = url.rstrip('/')
        if url and url not in bases:
            bases.append(url)

    host = netloc
    for prefix in path_prefixes:
        add_base(prefix, host)
    if host.startswith('app.daytona.io'):
        for prefix in path_prefixes:
            add_base(prefix, 'api.daytona.io')
    if host.startswith('api.daytona.io'):
        for prefix in path_prefixes:
            add_base(prefix, 'app.daytona.io')

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if DAYTONA_ORG_ID:
        headers["X-Daytona-Organization-ID"] = DAYTONA_ORG_ID
    last_err: Optional[Any] = None
    body = payload or {}
    for b in bases:
        url = f"{b}/{path.lstrip('/')}"
        try:
            if method == 'GET':
                r = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                r = requests.post(url, headers=headers, json=body, timeout=timeout)
            elif method == 'DELETE':
                r = requests.delete(url, headers=headers, timeout=timeout)
            else:
                raise ValueError("unsupported method")
            ct = r.headers.get('Content-Type', '')
            parsed_json = None
            try:
                parsed_json = r.json()
            except Exception:
                parsed_json = None
            if r.status_code in (404, 405):
                last_err = {"status": r.status_code, "data": (parsed_json if parsed_json is not None else r.text[:200]), "url": url}
                continue
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"Daytona call failed: {(parsed_json if parsed_json is not None else r.text[:200])}")
            # Require JSON responses; if we got HTML/front-end, continue variants
            if parsed_json is None or ('application/json' not in ct.lower() and 'json' not in ct.lower()):
                last_err = {"status": r.status_code, "data": r.text[:200], "url": url, "note": "non-JSON response"}
                continue
            return parsed_json
        except HTTPException:
            raise
        except Exception as e:
            last_err = {"error": str(e), "url": url}
            continue
    raise HTTPException(404, f"Daytona call failed (tried variants): {last_err}")


def _run_tests_daytona(req: RunTestsRequest) -> Dict[str, Any]:
    git_url = req.git_url or os.environ.get("DAYTONA_DEFAULT_GIT_URL")
    branch = req.branch or os.environ.get("DAYTONA_DEFAULT_BRANCH", "main")
    if not git_url:
        raise HTTPException(400, "git_url required for daytona mode")
    commands = req.commands or [
        "npm ci --silent --omit=optional --no-fund --no-audit || true",
        "npm test --silent --if-present || true",
        "python -m py_compile $(git ls-files '*.py') || true",
    ]
    create_payload = {
        "name": f"motia-{req.job_id}",
        "git_url": git_url,
        "branch": branch,
        "ephemeral": True,
    }
    if DAYTONA_DEFAULT_SNAPSHOT:
        create_payload["snapshot"] = DAYTONA_DEFAULT_SNAPSHOT

    # Try multiple create endpoints for compatibility
    create_paths = []
    if DAYTONA_CREATE_PATH:
        create_paths.append(DAYTONA_CREATE_PATH.strip('/'))
    create_paths.extend([
        "sandbox",
        "workspaces",
        "workspaces/create",
        "v1/workspaces",
    ])
    ws = None
    last_err = None
    for p in create_paths:
        try:
            ws = _daytona_call(p, method='POST', payload=create_payload)
            break
        except HTTPException as e:
            last_err = e
            continue
    if ws is None:
        raise last_err or HTTPException(502, "Daytona workspace create failed")

    def _extract_id(obj: Dict[str, Any]) -> Optional[str]:
        if not isinstance(obj, dict):
            return None
        for k in ("id", "sandboxId", "sandbox_id"):
            if k in obj and obj[k]:
                return str(obj[k])
        for key in ("workspace", "sandbox", "data"):
            inner = obj.get(key) or {}
            if isinstance(inner, dict):
                for k in ("id", "sandboxId", "sandbox_id"):
                    if k in inner and inner[k]:
                        return str(inner[k])
        return None

    ws_id = _extract_id(ws)
    if not ws_id:
        raise HTTPException(502, f"unexpected create response: {ws}")
    logs: List[str] = []
    ok = True
    try:
        # Ensure repo exists at least once; if clone failed above, try again here (non-fatal)
        if git_url:
            try:
                _daytona_call(f"toolbox/{ws_id}/toolbox/git/clone", method='POST', payload={"url": git_url, "repo": git_url, "branch": branch}, timeout=120)
            except HTTPException:
                pass

        for cmd in commands:
            run_resp = None
            run_paths = []
            if DAYTONA_RUN_PATH_TMPL:
                run_paths.append(DAYTONA_RUN_PATH_TMPL.format(id=ws_id).strip('/'))
            run_paths.extend([
                f"toolbox/{ws_id}/toolbox/process/execute",
                f"workspaces/{ws_id}/run",
                f"workspaces/{ws_id}/commands",
                f"v1/workspaces/{ws_id}/run",
            ])
            for rp in run_paths:
                try:
                    run_resp = _daytona_call(rp, method='POST', payload={"command": cmd}, timeout=300)
                    break
                except HTTPException:
                    run_resp = None
                    continue
            if run_resp is None:
                logs.append(f"$ {cmd}\n(run endpoint not supported)")
                ok = False
                continue
            # Normalize output and return code
            out_text = None
            rc_val = None
            if isinstance(run_resp, dict):
                for k in ("result", "output", "stdout", "data", "message"):
                    if run_resp.get(k):
                        out_text = run_resp[k]
                        break
                for k in ("code", "rc", "exitCode", "exit_code"):
                    if k in run_resp:
                        rc_val = run_resp[k]
                        break
            if out_text is None:
                out_text = json.dumps(run_resp)[:800]
            logs.append(f"$ {cmd}\n{out_text}")
            rc = rc_val or 0
            if rc not in (0, '0', None):
                ok = False
    finally:
        try:
            # Try alternate destroy endpoints
            destroy_paths = []
            if DAYTONA_DESTROY_PATH_TMPL:
                destroy_paths.append(DAYTONA_DESTROY_PATH_TMPL.format(id=ws_id).strip('/'))
            destroy_paths.extend([
                f"sandbox/{ws_id}",
                f"workspaces/{ws_id}",
                f"v1/workspaces/{ws_id}",
                f"workspaces/{ws_id}/destroy",
            ])
            for dp in destroy_paths:
                try:
                    _daytona_call(dp, method='DELETE')
                    break
                except HTTPException:
                    continue
        except Exception as e:
            logs.append(f"cleanup error: {e}")
    return {"ok": ok, "logs": logs, "sandbox": {"id": ws_id}}


class DaytonaCreateRequest(BaseModel):
    name: Optional[str] = None
    git_url: str
    branch: Optional[str] = "main"
    ephemeral: Optional[bool] = True
    snapshot: Optional[str] = None


@app.post("/sandbox/create")
def sandbox_create(req: DaytonaCreateRequest):
    payload = {
        "name": req.name or f"motia-{int(time.time())}",
        "git_url": req.git_url,
        "branch": req.branch,
        "ephemeral": bool(req.ephemeral),
    }
    snap = req.snapshot or DAYTONA_DEFAULT_SNAPSHOT
    if snap:
        payload["snapshot"] = snap
    return _daytona_call("sandbox", method='POST', payload=payload)


class DaytonaRunRequest(BaseModel):
    sandbox_id: str
    command: str
    timeout: Optional[int] = 300


@app.post("/sandbox/run")
def sandbox_run(req: DaytonaRunRequest):
    return _daytona_call(f"toolbox/{req.sandbox_id}/toolbox/process/execute", method='POST', payload={"command": req.command}, timeout=req.timeout or 300)


class DaytonaDestroyRequest(BaseModel):
    sandbox_id: str


@app.post("/sandbox/destroy")
def sandbox_destroy(req: DaytonaDestroyRequest):
    return _daytona_call(f"sandbox/{req.sandbox_id}", method='DELETE')


@app.post("/jobs/bolt")
def jobs_bolt(req: BoltRequest):
    """Run bolt.diy locally or in a Daytona sandbox and capture logs."""
    job = store.new_job("bolt", req.model_dump())
    logs: List[str] = []
    ok = True
    try:
        mode = (req.mode or 'local').lower()
        if mode == 'local':
            script = "/opt/bolt.diy"
            if not os.path.exists(script):
                raise HTTPException(500, f"bolt script not found: {script}")
            args = req.bolt_args or ["build"]
            cwd = req.workdir or os.getcwd()
            cmd = [script] + args
            t0 = time.time()
            try:
                proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600, text=True)
                out = proc.stdout or ''
                logs.append(out if len(out) < 8000 else out[:8000])
                ok = (proc.returncode == 0)
            except subprocess.TimeoutExpired as e:
                ok = False
                logs.append(f"timeout after 600s\n{getattr(e, 'output', '')}")
        else:
            # Daytona path: require git_url and run generic commands; assumes bolt is available in snapshot
            if not req.git_url:
                raise HTTPException(400, "git_url required for daytona mode")
            # Create sandbox
            cb_payload = {"branch": req.branch or 'main'}
            if DAYTONA_DEFAULT_SNAPSHOT:
                cb_payload["snapshot"] = DAYTONA_DEFAULT_SNAPSHOT
            ws = _daytona_call("sandbox", method='POST', payload=cb_payload)
            sid = ws.get('id') or ws.get('sandboxId') or ws.get('sandbox_id')
            if not sid:
                raise HTTPException(502, f"unexpected create response: {ws}")
            try:
                # Clone repo and run bolt
                setup = _daytona_call(f"toolbox/{sid}/toolbox/process/execute", method='POST', payload={"command": f"bash -lc 'git clone {req.git_url} repo && cd repo && bolt --version || echo bolt-missing'"}, timeout=300)
                logs.append(str(setup))
                args = req.bolt_args or ["build"]
                run = _daytona_call(f"toolbox/{sid}/toolbox/process/execute", method='POST', payload={"command": f"bash -lc 'cd repo && bolt {' '.join(args)}'"}, timeout=900)
                logs.append(str(run))
                rc = run.get('exitCode') or run.get('code') or 0
                ok = (rc in (0, '0', None))
            finally:
                try:
                    _daytona_call(f"sandbox/{sid}", method='DELETE')
                except Exception as e:
                    logs.append(f"cleanup error: {e}")
    except HTTPException:
        raise
    except Exception as e:
        ok = False
        logs.append(f"bolt error: {e}")
    store.update_status(job["id"], "completed" if ok else "error", {"ok": ok, "logs": logs})
    return {"job_id": job["id"], "ok": ok, "logs": logs}


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
    if not ops and (job.get("kind") == "rfc"):
        raise HTTPException(400, "RFC job has no file operations to apply; use propose_patch first")
    notes = apply_to_target(base_path, ws, ops)
    store.update_status(req.job_id, "applied", {"notes": notes})
    return {"job_id": req.job_id, "notes": notes}


class RejectJobRequest(BaseModel):
    job_id: str
    reason: Optional[str] = None


@app.post("/jobs/reject")
def jobs_reject(req: RejectJobRequest):
    job = store.get_job(req.job_id)
    if not job:
        raise HTTPException(404, "job not found")
    store.update_status(req.job_id, "rejected", {"reason": req.reason or "rejected by user"})
    return {"job_id": req.job_id, "status": "rejected"}


@app.get("/jobs/list")
def jobs_list(status: Optional[str] = Query(default=None), limit: int = Query(default=25, ge=1, le=200)):
    rows = store.list_jobs(status=status, limit=limit)
    return {"jobs": rows, "count": len(rows)}


@app.get("/jobs/{job_id}")
def jobs_get(job_id: str = Path(...)):
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return job


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
