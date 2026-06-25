"""Trigger and report on dbt builds (SPEC §16).

`POST /dbt/run` launches `dbt build` in a background thread and returns immediately.
`GET /dbt/status` reports the latest run: overall status, per-model results parsed
from target/run_results.json, durations, and the raw log.
"""

import json
import os
import subprocess
import threading
from datetime import datetime, timezone

from fastapi import APIRouter

from config import settings

router = APIRouter()

_lock = threading.Lock()
_state = {
    "job_id": None,
    "status": "idle",  # idle | running | success | error
    "started_at": None,
    "finished_at": None,
    "models": [],
    "log": "",
}


def current_state() -> dict:
    with _lock:
        return dict(_state)


def _parse_run_results() -> list:
    path = os.path.join(settings.dbt_project_dir, "target", "run_results.json")
    try:
        with open(path) as f:
            data = json.load(f)
        return [
            {
                "name": r.get("unique_id", "").split(".")[-1],
                "status": r.get("status"),
                "execution_time": round(r.get("execution_time", 0), 2),
            }
            for r in data.get("results", [])
        ]
    except Exception:
        return []


def _run_dbt(job_id: str):
    with _lock:
        _state.update(
            job_id=job_id,
            status="running",
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
            models=[],
            log="",
        )
    try:
        proc = subprocess.run(
            ["dbt", "build", "--project-dir", settings.dbt_project_dir,
             "--profiles-dir", settings.dbt_project_dir],
            cwd=settings.dbt_project_dir,
            capture_output=True,
            text=True,
            env={**os.environ, "DBT_PROFILES_DIR": settings.dbt_project_dir},
        )
        log = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
        status = "success" if proc.returncode == 0 else "error"
        models = _parse_run_results()
    except Exception as exc:
        log, status, models = str(exc), "error", []

    with _lock:
        _state.update(
            status=status,
            finished_at=datetime.now(timezone.utc).isoformat(),
            models=models,
            log=log,
        )


@router.post("/dbt/run")
def dbt_run():
    with _lock:
        if _state["status"] == "running":
            return {"job_id": _state["job_id"], "status": "running",
                    "message": "a build is already in progress"}
    job_id = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    threading.Thread(target=_run_dbt, args=(job_id,), daemon=True).start()
    return {"job_id": job_id, "status": "started"}


@router.get("/dbt/status")
def dbt_status():
    return current_state()
