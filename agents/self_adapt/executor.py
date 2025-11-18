import os
import shutil
from typing import List, Dict, Any, Tuple


ALLOWED_BASE_PATHS = {
    "/opt/motia/agents",
    "/opt/motia/agents/parlant",
    "/opt/motia/agents/superqwen",
    "/opt/motia/agents/platforms",
}


def sanitize_base_path(base_path: str) -> str:
    base_path = os.path.abspath(base_path)
    for allowed in ALLOWED_BASE_PATHS:
        if base_path.startswith(allowed):
            return base_path
    # Default fallback
    return "/opt/motia/agents"


def ensure_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def apply_operations(work_dir: str, operations: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Apply file operations inside a workspace directory.

    Supported ops:
      - upsert: write/overwrite file with provided content (text)
      - delete: delete file if exists
    Returns (applied, errors)
    """
    applied: List[Dict[str, Any]] = []
    errors: List[str] = []
    for op in operations:
        kind = op.get("op")
        rel = op.get("path")
        if not rel or not isinstance(rel, str):
            errors.append("missing path in operation")
            continue
        target = os.path.abspath(os.path.join(work_dir, rel.lstrip("/")))
        if not target.startswith(os.path.abspath(work_dir)):
            errors.append(f"refuse to write outside workspace: {rel}")
            continue
        if kind == "upsert":
            content = op.get("content", "")
            if not isinstance(content, str):
                errors.append(f"invalid content for {rel}")
                continue
            ensure_dir(target)
            with open(target, "w") as f:
                f.write(content)
            applied.append({"op": "upsert", "path": rel, "bytes": len(content)})
        elif kind == "delete":
            if os.path.exists(target):
                os.remove(target)
                applied.append({"op": "delete", "path": rel})
            else:
                applied.append({"op": "delete", "path": rel, "note": "no-op (not found)"})
        else:
            errors.append(f"unknown op {kind} for {rel}")
    return applied, errors


def stage_workspace(base_path: str, jobs_root: str, job_id: str) -> str:
    ws = os.path.join(jobs_root, job_id)
    os.makedirs(ws, exist_ok=True)
    # For MVP we do not mirror full base tree; we write only changed files
    return ws


def apply_to_target(base_path: str, workspace: str, operations: List[Dict[str, Any]]) -> List[str]:
    """Apply the same operations from workspace onto the real base path (with backup)."""
    base_path = sanitize_base_path(base_path)
    notes: List[str] = []
    for op in operations:
        kind = op.get("op")
        rel = op.get("path")
        if not isinstance(rel, str):
            notes.append("skip invalid op")
            continue
        src = os.path.join(workspace, rel.lstrip("/"))
        dst = os.path.join(base_path, rel.lstrip("/"))
        if kind == "upsert":
            ensure_dir(dst)
            # backup if exists
            if os.path.exists(dst):
                shutil.copy2(dst, f"{dst}.bak")
            shutil.copy2(src, dst)
            notes.append(f"upserted {rel}")
        elif kind == "delete":
            if os.path.exists(dst):
                os.remove(dst)
                notes.append(f"deleted {rel}")
            else:
                notes.append(f"delete no-op {rel}")
    return notes

