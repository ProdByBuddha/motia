#!/usr/bin/env python3
import os
import time
import json
import shutil
import subprocess
from datetime import datetime
from urllib import request


def run(cmd: list[str], timeout: int = 8) -> tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=timeout, text=True)
        return 0, out
    except subprocess.CalledProcessError as e:
        return e.returncode, e.output
    except Exception as e:
        return 1, str(e)


def get_system_metrics() -> dict:
    # Uptime and load
    try:
        import os as _os
        loads = _os.getloadavg()
    except Exception:
        loads = (0.0, 0.0, 0.0)
    rc, up = run(["uptime", "-p"], timeout=3)
    uptime_pretty = up.strip() if rc == 0 else "unknown"

    # Memory
    mem = {}
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    k = parts[0].strip(); v = parts[1].strip()
                    mem[k] = v
    except Exception:
        pass

    # Disk usage
    disks = {}
    for path in ("/", "/opt"):
        try:
            du = shutil.disk_usage(path)
            disks[path] = {
                "total_gb": round(du.total / 1_000_000_000, 2),
                "used_gb": round((du.total - du.free) / 1_000_000_000, 2),
                "free_gb": round(du.free / 1_000_000_000, 2),
                "used_pct": round((du.total - du.free) * 100.0 / du.total, 1),
            }
        except Exception:
            continue

    return {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "uptime_pretty": uptime_pretty,
        "loadavg": {"1m": loads[0], "5m": loads[1], "15m": loads[2]},
        "meminfo": {
            "MemTotal": mem.get("MemTotal", ""),
            "MemFree": mem.get("MemFree", ""),
            "MemAvailable": mem.get("MemAvailable", ""),
            "SwapTotal": mem.get("SwapTotal", ""),
            "SwapFree": mem.get("SwapFree", ""),
        },
        "disks": disks,
    }


def get_docker_summary() -> dict:
    # docker ps
    rc, out_ps = run(["docker", "ps", "--format", "{{.Names}}|{{.Status}}|{{.Image}}|{{.RunningFor}}|{{.ID}}"], timeout=6)
    containers = []
    if rc == 0:
        for line in out_ps.strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 5:
                containers.append({
                    "name": parts[0],
                    "status": parts[1],
                    "image": parts[2],
                    "uptime": parts[3],
                    "id": parts[4],
                })
    # docker stats
    stats_map = {}
    rc, out_stats = run(["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}|{{.MemPerc}}|{{.MemUsage}}|{{.PIDs}}"], timeout=8)
    if rc == 0:
        for line in out_stats.strip().splitlines():
            parts = line.split("|")
            if len(parts) >= 5:
                stats_map[parts[0]] = {
                    "cpu": parts[1],
                    "mem_pct": parts[2],
                    "mem_usage": parts[3],
                    "pids": parts[4],
                }
    # merge
    for c in containers:
        if c["name"] in stats_map:
            c["stats"] = stats_map[c["name"]]

    return {"containers": containers}


def build_embed(system: dict, docker: dict) -> dict:
    # Format a Discord embed payload
    fields = []
    load = system.get("loadavg", {})
    fields.append({
        "name": "System",
        "value": f"Uptime: {system.get('uptime_pretty','?')}\nLoad: {load.get('1m',0):.2f} {load.get('5m',0):.2f} {load.get('15m',0):.2f}",
        "inline": True
    })
    mi = system.get("meminfo", {})
    fields.append({
        "name": "Memory",
        "value": f"Total: {mi.get('MemTotal','?')}\nAvail: {mi.get('MemAvailable','?')}\nSwap: {mi.get('SwapFree','?')}/{mi.get('SwapTotal','?')}",
        "inline": True
    })
    disks = system.get("disks", {})
    if disks:
        root = disks.get("/", {})
        val = f"/: {root.get('used_gb','?')}/{root.get('total_gb','?')} GB ({root.get('used_pct','?')}%)"
        if "/opt" in disks:
            d = disks["/opt"]
            val += f"\n/opt: {d.get('used_gb','?')}/{d.get('total_gb','?')} GB ({d.get('used_pct','?')}%)"
        fields.append({"name": "Disk", "value": val, "inline": True})

    # Docker summary
    cons = docker.get("containers", [])
    running = [c for c in cons if c.get("status", "").lower().startswith("up")]
    val = f"Running: {len(running)}/{len(cons)}\n"
    for c in cons[:6]:
        stats = c.get("stats", {})
        val += f"• {c['name']} — {c['status']}\n"
        if stats:
            val += f"  CPU {stats.get('cpu','?')} MEM {stats.get('mem_pct','?')} ({stats.get('mem_usage','?')})\n"
    fields.append({"name": "Docker", "value": val or "-", "inline": False})

    embed = {
        "title": "VPS Health",
        "description": f"Updated: {datetime.utcnow().isoformat()}Z",
        "color": 0x2b6cb0,
        "fields": fields,
    }
    return embed


def post_webhook(webhook_url: str, embed: dict):
    payload = json.dumps({"embeds": [embed]})
    req = request.Request(webhook_url, data=payload.encode("utf-8"), headers={"Content-Type": "application/json"})
    with request.urlopen(req, timeout=10) as r:
        r.read()


def main():
    webhook = os.getenv("DISCORD_HEALTH_WEBHOOK_URL", "").strip()
    interval = int(os.getenv("HEALTH_INTERVAL_SECONDS", "120"))
    if not webhook:
        print("[health-reporter] DISCORD_HEALTH_WEBHOOK_URL not set; exiting")
        return
    while True:
        try:
            sysm = get_system_metrics()
            dock = get_docker_summary()
            embed = build_embed(sysm, dock)
            post_webhook(webhook, embed)
            print("[health-reporter] posted")
        except Exception as e:
            print(f"[health-reporter] error: {e}")
        time.sleep(max(30, interval))


if __name__ == "__main__":
    main()

