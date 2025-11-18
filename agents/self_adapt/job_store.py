import os
import json
import time
import uuid
from typing import Any, Dict, Optional, List

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None


class JobStore:
    def __init__(self, namespace: str = "builder", redis_url: Optional[str] = None, base_dir: str = "/work/jobs"):
        self.ns = namespace
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)
        self.r = None
        if redis_url and redis is not None:
            try:
                self.r = redis.Redis.from_url(redis_url, decode_responses=True)
                self.r.ping()
            except Exception:
                self.r = None

    def _key(self, job_id: str) -> str:
        return f"{self.ns}:job:{job_id}"

    def new_job(self, kind: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        job_id = uuid.uuid4().hex[:12]
        now = int(time.time())
        rec = {
            "id": job_id,
            "kind": kind,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "payload": payload,
            "result": None,
        }
        self.save_job(rec)
        return rec

    def save_job(self, job: Dict[str, Any]) -> None:
        job["updated_at"] = int(time.time())
        if self.r is not None:
            self.r.set(self._key(job["id"]), json.dumps(job))
        else:
            with open(os.path.join(self.base_dir, f"{job['id']}.json"), "w") as f:
                json.dump(job, f)

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        if self.r is not None:
            data = self.r.get(self._key(job_id))
            if not data:
                return None
            return json.loads(data)
        p = os.path.join(self.base_dir, f"{job_id}.json")
        if not os.path.exists(p):
            return None
        with open(p, "r") as f:
            return json.load(f)

    def update_status(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None):
        job = self.get_job(job_id)
        if not job:
            return None
        job["status"] = status
        if result is not None:
            job["result"] = result
        self.save_job(job)
        return job

    def list_jobs(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """List recent jobs, optionally filtered by status."""
        items: List[Dict[str, Any]] = []
        if self.r is not None:
            try:
                # For small scale, KEYS is acceptable
                for key in self.r.keys(f"{self.ns}:job:*"):
                    try:
                        data = self.r.get(key)
                        if not data:
                            continue
                        rec = json.loads(data)
                        if status and rec.get("status") != status:
                            continue
                        items.append(rec)
                    except Exception:
                        continue
            except Exception:
                pass
        else:
            try:
                for fn in os.listdir(self.base_dir):
                    if not fn.endswith(".json"):
                        continue
                    try:
                        with open(os.path.join(self.base_dir, fn), "r") as f:
                            rec = json.load(f)
                        if status and rec.get("status") != status:
                            continue
                        items.append(rec)
                    except Exception:
                        continue
            except Exception:
                pass
        items.sort(key=lambda x: x.get("updated_at") or 0, reverse=True)
        return items[: max(1, min(limit, 200))]
