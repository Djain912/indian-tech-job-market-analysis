"""
FastAPI server: JSON API + static frontend.

Run:  python -m uvicorn backend.app:app --port 8000
"""

from __future__ import annotations

import io
import threading
import time
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import ai
from .engine import CORE_SKILLS, ROLE_TITLE_KEYWORDS, Candidate, JobMarket, clean_dataset

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"
REAL_DATASET = DATA / "indian_tech_jobs_2026.csv"
SAMPLE_DATASET = DATA / "sample_jobs.csv"

app = FastAPI(title="Indian Tech Job Market Analysis 2026", version="2.0")
_lock = threading.Lock()
_market: JobMarket | None = None


def _load_default() -> JobMarket:
    if REAL_DATASET.exists():
        return JobMarket.from_csv(REAL_DATASET)
    if not SAMPLE_DATASET.exists():
        from scripts.generate_sample_data import main as generate
        generate(8000)
    return JobMarket.from_csv(SAMPLE_DATASET, source="sample_jobs.csv (synthetic sample)")


def market() -> JobMarket:
    global _market
    with _lock:
        if _market is None:
            _market = _load_default()
        return _market


class CandidateIn(BaseModel):
    skills: list[str] = Field(default_factory=list)
    experience: float = 0
    city: str | None = None
    work_mode: list[str] | None = None
    target_role: str | None = None
    role_only: bool = False

    def to_candidate(self) -> Candidate:
        return Candidate(
            skills=[s for s in self.skills if s.strip()],
            experience=max(0.0, self.experience),
            city=(self.city or "").strip() or None,
            work_mode=self.work_mode or None,
            target_role=self.target_role or None,
            role_only=self.role_only,
        )


class WhatIfIn(CandidateIn):
    added_skills: list[str] = Field(default_factory=list)


class AdvisorIn(CandidateIn):
    api_key: str | None = None
    question: str | None = None


# ------------------------------------------------------------------------- API

@app.get("/api/meta")
def meta():
    m = market()
    return {
        "source": m.source,
        "rows": len(m.df),
        "roles": sorted(m.df["role_category"].dropna().astype(str).unique().tolist()),
        "target_roles": list(ROLE_TITLE_KEYWORDS),
        "cities": m.df["primary_city"].astype(str).value_counts().head(40).index.tolist(),
        "work_modes": sorted(m.df["work_mode"].astype(str).unique().tolist()),
        "core_skills": CORE_SKILLS,
        "gemini_configured": ai.gemini_configured(),
        "gemini_model": ai.GEMINI_MODEL,
    }


@app.get("/api/overview")
def overview():
    return market().overview()


@app.get("/api/role-skills")
def role_skills(role: str, top: int = 15):
    return market().role_skills(role, top)


@app.get("/api/jobs")
def jobs(q: str = "", role: str = "", city: str = "", mode: str = "", fresher: bool = False,
         salary_only: bool = False, page: int = 1, size: int = 25):
    return market().search_jobs(q, role, city, mode, fresher, salary_only, max(page, 1), min(max(size, 1), 100))


@app.post("/api/match")
def match(body: CandidateIn, limit: int = 30):
    m, c = market(), body.to_candidate()
    if not c.skills:
        raise HTTPException(400, "Add at least one skill.")
    t = time.perf_counter()
    scored = m.score(c)
    return {
        "dashboard": m.dashboard(scored),
        "jobs": m.job_records(scored, c, limit=min(limit, 200)),
        "skill_gaps": m.skill_gaps(scored, c),
        "recognised_skills": sorted(c.core_skills),
        "ignored_skills": sorted(set(s.lower().strip() for s in c.skills) - c.core_skills - {""}),
        "elapsed_ms": round((time.perf_counter() - t) * 1000, 1),
    }


@app.post("/api/what-if")
def what_if(body: WhatIfIn):
    if not body.added_skills:
        raise HTTPException(400, "Choose at least one skill to add.")
    return market().what_if(body.to_candidate(), body.added_skills)


@app.post("/api/advisor")
def advisor(body: AdvisorIn):
    c = body.to_candidate()
    if not c.skills:
        raise HTTPException(400, "Add at least one skill.")
    return ai.career_report(market(), c, body.api_key, body.question)


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    global _market
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file.")
    content = await file.read()
    try:
        raw = pd.read_csv(io.BytesIO(content))
        df, quality = clean_dataset(raw)
        new_market = JobMarket(df=df, quality=quality, source=file.filename)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    with _lock:
        _market = new_market
    DATA.mkdir(exist_ok=True)
    (DATA / "uploaded_latest.csv").write_bytes(content)
    return {"ok": True, "source": file.filename, "rows": len(df)}


@app.post("/api/reset")
def reset():
    global _market
    with _lock:
        _market = None
    return {"ok": True, "source": market().source}


@app.post("/api/export")
def export():
    files = market().export(ROOT / "job_market_backend")
    return {"folder": "job_market_backend", "files": files}


# -------------------------------------------------------------------- frontend

app.mount("/static", StaticFiles(directory=FRONTEND), name="static")


@app.get("/")
def index():
    return FileResponse(FRONTEND / "index.html")
