"""
AI career advisor.

Mirrors the notebook's LangGraph workflow as four explicit steps:

    1. match        - score the candidate against the market
    2. recommend    - rank missing skills by how many jobs they unlock
    3. what_if      - simulate adding the top recommended skills
    4. explain      - Gemini writes the advice (rule-based fallback if no key)

Gemini is called through its REST API, so LangChain is not required.
The key comes from the request or the GEMINI_API_KEY / GOOGLE_API_KEY env var
and is never stored or logged.
"""

from __future__ import annotations

import json
import os
import time

import requests

from .engine import Candidate, JobMarket

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _env_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def gemini_configured() -> bool:
    return bool(_env_key())


def call_gemini(prompt: str, api_key: str | None = None, model: str | None = None) -> str:
    key = (api_key or "").strip() or _env_key()
    if not key:
        raise RuntimeError("No Gemini API key provided.")
    resp = requests.post(
        GEMINI_URL.format(model=model or GEMINI_MODEL),
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1400},
        },
        timeout=60,
    )
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text)
        except ValueError:
            msg = resp.text
        raise RuntimeError(f"Gemini error {resp.status_code}: {msg[:300]}")
    parts = resp.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts).strip()


def _rule_based_advice(c: Candidate, dash: dict, gaps: list[dict], whatif: dict, top_jobs: list[dict]) -> str:
    role = c.target_role or "your target roles"
    lines = [
        f"## Summary",
        f"You are eligible for **{dash['eligible_jobs']:,} of {dash['jobs_analyzed']:,}** jobs "
        f"({dash['eligibility_percent']}%) with an average match score of {dash['average_match_score']}.",
        "",
        "## Strongest matches",
    ]
    for j in top_jobs[:3]:
        lines.append(f"- **{j['job_title']}** at {j['company']} ({j['city']}) — match {j['match_score']}%, "
                     f"{j['application_priority']}.")
    lines += ["", f"## Skills to learn next for {role}"]
    for g in gaps[:5]:
        lines.append(f"- **{g['skill']}** — appears in {g['appears_in_top_jobs']} of your best-matching jobs and "
                     f"would unlock about {g['extra_eligible_jobs']} more eligible jobs on its own.")
    if whatif and whatif["added_skills"]:
        lines += ["", "## What-if",
                  f"Adding {', '.join(whatif['added_skills'])} would move you from "
                  f"{whatif['before']['eligible_jobs']:,} to {whatif['after']['eligible_jobs']:,} eligible jobs "
                  f"(+{whatif['additional_eligible']:,}), and raise the average match score by "
                  f"{whatif['score_improvement']} points."]
    lines += ["", "## Note",
              "Match score measures profile-to-posting compatibility. It is not a probability of being hired — "
              "the dataset contains no hiring outcomes."]
    return "\n".join(lines)


def career_report(market: JobMarket, c: Candidate, api_key: str | None = None, question: str | None = None) -> dict:
    steps = []

    t = time.perf_counter()
    scored = market.score(c)
    dash = market.dashboard(scored)
    top_jobs = market.job_records(scored, c, limit=5)
    steps.append({"step": "match", "ms": round((time.perf_counter() - t) * 1000, 1),
                  "detail": f"Scored {dash['jobs_analyzed']:,} jobs, {dash['eligible_jobs']:,} eligible"})

    t = time.perf_counter()
    gaps = market.skill_gaps(scored, c, top=8)
    steps.append({"step": "recommend", "ms": round((time.perf_counter() - t) * 1000, 1),
                  "detail": "Top gaps: " + ", ".join(g["skill"] for g in gaps[:3]) if gaps else "No gaps found"})

    t = time.perf_counter()
    add = [g["skill"] for g in gaps[:3]]
    whatif = market.what_if(c, add) if add else None
    if whatif:
        whatif.pop("newly_eligible_jobs", None)
    steps.append({"step": "what_if", "ms": round((time.perf_counter() - t) * 1000, 1),
                  "detail": f"+{whatif['additional_eligible']:,} eligible jobs with {', '.join(add)}" if whatif else "Skipped"})

    t = time.perf_counter()
    payload = {
        "candidate": {"skills": c.skills, "experience_years": c.experience, "city": c.city,
                      "work_mode": c.work_mode, "target_role": c.target_role},
        "dashboard": dash,
        "top_jobs": [{k: j[k] for k in ("job_title", "company", "city", "work_mode", "match_score",
                                        "eligible", "matched_skills", "missing_skills",
                                        "eligibility_explanation")} for j in top_jobs],
        "skill_gaps": gaps,
        "what_if": whatif,
        "role_core_skills": market.role_skills(c.target_role)[:10] if c.target_role else [],
    }
    used_ai, error = False, None
    if (api_key or "").strip() or gemini_configured():
        prompt = (
            "You are a career advisor for the Indian tech job market (2026). Using ONLY the JSON analysis below, "
            "write concise, specific advice in Markdown with these sections: Summary, Strongest matches, "
            "Skills to learn next (in order, with why), 30-60-90 day plan, and a short honest note that the match "
            "score is not a hiring probability. Do not invent numbers that are not in the data.\n\n"
            + (f"The candidate also asks: {question}\n\n" if question else "")
            + json.dumps(payload, default=str)
        )
        try:
            advice = call_gemini(prompt, api_key)
            used_ai = True
        except Exception as exc:  # fall back, but surface the reason
            error = str(exc)
            advice = _rule_based_advice(c, dash, gaps, whatif, top_jobs)
    else:
        advice = _rule_based_advice(c, dash, gaps, whatif, top_jobs)
    steps.append({"step": "explain", "ms": round((time.perf_counter() - t) * 1000, 1),
                  "detail": f"Gemini ({GEMINI_MODEL})" if used_ai else "Rule-based advisor"})

    return {"advice": advice, "used_gemini": used_ai, "gemini_error": error, "steps": steps, **payload}
