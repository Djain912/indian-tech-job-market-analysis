"""
AI-Assisted Indian Tech Job Market Analysis - 2026
Core analytics + candidate-job matching engine.

Ported from DAVmp.ipynb. Scoring rules are unchanged:

    Match Score = 50% Skills + 25% Experience + 10% Role Relevance
                + 10% Location + 5% Work Mode

    Eligible    = experience met AND >= 50% core skill match
                  AND job title relevant to the target role

Match Score is NOT a probability of being hired: the dataset has no
selected/rejected outcomes, so none is produced.

Differences from the notebook:
  * Jobs are pre-indexed once, so a candidate is scored against every job
    with numpy arrays instead of DataFrame.iterrows() (~100x faster).
  * The duplicate normalize_skill_list() definition is merged into one.
  * Saving role scores no longer crashes (Series.reset_index(names=...)).
  * Skill-gap ranking also reports how many extra jobs each skill unlocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

# =============================================================================
# SCHEMA
# =============================================================================

REQUIRED_COLUMNS = [
    "job_id", "job_title", "company_name", "location", "role_category",
    "experience_raw", "experience_min_yrs", "experience_max_yrs",
    "skills_required", "skills_count", "work_mode", "company_size_bucket",
    "primary_city", "skill_domain", "salary_midpoint_lpa", "is_fresher_friendly",
]

TEXT_COLUMNS = [
    "job_title", "company_name", "location", "scraped_city", "role_category",
    "experience_raw", "skills_required", "job_description", "posted_date_raw",
    "work_mode", "company_size_bucket", "salary_raw", "salary_tier",
    "experience_tier", "primary_city", "skill_domain", "data_source", "scraped_at",
]

NUMERIC_COLUMNS = [
    "company_rating", "experience_min_yrs", "experience_max_yrs", "salary_min_lpa",
    "salary_max_lpa", "skills_count", "salary_midpoint_lpa", "days_since_posted",
]

BOOLEAN_COLUMNS = ["salary_disclosed", "is_senior", "is_fresher_friendly", "salary_negotiable"]

# =============================================================================
# SKILL TAXONOMY
# =============================================================================

TECHNICAL_SKILLS = {
    "python", "java", "javascript", "typescript", "c", "c++", "c#", "r", "sql",
    "html", "css",
    "excel", "power bi", "tableau",
    "data analysis", "data visualization", "data modeling", "data management",
    "data quality", "business intelligence", "statistics",
    "data science", "machine learning", "deep learning", "artificial intelligence",
    "natural language processing", "nlp", "generative ai", "gen ai", "llm",
    "large language model", "rag", "retrieval augmented generation", "agentic ai",
    "predictive modeling",
    "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch",
    "data engineering", "spark", "pyspark", "kafka", "airflow",
    "aws", "azure", "gcp", "cloud",
    "docker", "kubernetes", "git",
    "mlops", "ci/cd",
    "automation",
}

BUSINESS_SKILLS = {
    "business analysis", "business analyst", "project management", "agile",
    "consulting", "change management", "market research",
    "stakeholder management", "erp", "sap",
}

GENERIC_SKILLS = {
    "data", "analysis", "analytical", "analytics", "coding", "basic",
    "computer science", "management", "communication", "leadership", "teamwork",
    "planning", "support", "operations", "reporting", "technical", "professional",
    "knowledge", "experience", "research", "development", "skills",
    "responsibilities",
}

SKILL_ALIASES = {
    "python programming": "python",
    "python 3": "python",
    "sql server": "sql",
    "structured query language": "sql",
    "ml": "machine learning",
    "machine-learning": "machine learning",
    "ai": "artificial intelligence",
    "powerbi": "power bi",
    "power-bi": "power bi",
    "ms power bi": "power bi",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "advanced excel": "excel",
    "genai": "generative ai",
    "gen-ai": "generative ai",
    "llms": "llm",
    "large language models": "large language model",
    "scikit learn": "scikit-learn",
    "sklearn": "scikit-learn",
    "amazon web services": "aws",
    "google cloud": "gcp",
    "microsoft azure": "azure",
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "k8s": "kubernetes",
    "dl": "deep learning",
    "natural language processing (nlp)": "nlp",
    "data visualisation": "data visualization",
}

NULL_TOKENS = {"", "nan", "none", "<na>", "na", "n/a", "not available", "not applicable"}

_SPLIT_RE = re.compile(r"[,;|]")


def normalize_skill_name(skill: Any) -> str:
    if skill is None:
        return ""
    try:
        if pd.isna(skill):
            return ""
    except (TypeError, ValueError):
        pass
    skill = re.sub(r"\s+", " ", str(skill).lower().strip())
    if skill in NULL_TOKENS:
        return ""
    return SKILL_ALIASES.get(skill, skill)


def normalize_skill_list(skills: Any) -> set[str]:
    if skills is None:
        return set()
    if isinstance(skills, str):
        if not skills.strip():
            return set()
        skills = _SPLIT_RE.split(skills)
    elif not isinstance(skills, (list, tuple, set, np.ndarray)):
        try:
            if pd.isna(skills):
                return set()
        except (TypeError, ValueError):
            pass
        skills = [skills]
    return {s for s in (normalize_skill_name(x) for x in skills) if s}


def skill_weight(skill: str) -> float:
    skill = normalize_skill_name(skill)
    if skill in TECHNICAL_SKILLS:
        return 1.0
    if skill in BUSINESS_SKILLS:
        return 0.5
    return 0.0


def skill_category(skill: str) -> str:
    if skill in TECHNICAL_SKILLS:
        return "technical"
    if skill in BUSINESS_SKILLS:
        return "business"
    if skill in GENERIC_SKILLS:
        return "generic"
    return "other"


CORE_SKILLS = sorted(TECHNICAL_SKILLS | BUSINESS_SKILLS)

# =============================================================================
# ROLE / CITY / WORK MODE
# =============================================================================

ROLE_TITLE_KEYWORDS = {
    "Data Analyst": [
        "data analyst", "data analysis", "data analytics", "analytics analyst",
        "business intelligence analyst", "bi analyst", "reporting analyst",
        "mis analyst", "data reporting", "data insights", "data visualization analyst",
    ],
    "Data Scientist": ["data scientist", "data science", "applied scientist", "research scientist"],
    "Data Engineer": [
        "data engineer", "data engineering", "big data engineer", "etl developer",
        "etl engineer", "data pipeline engineer", "data platform engineer",
        "spark developer",
    ],
    "Machine Learning Engineer": [
        "machine learning engineer", "ml engineer", "machine learning", "ai engineer",
        "artificial intelligence engineer", "deep learning engineer", "mlops engineer",
        "genai engineer",
    ],
    "Business Analyst": [
        "business analyst", "business analysis", "business systems analyst",
        "functional analyst", "requirements analyst", "product analyst",
    ],
    "Python Developer": [
        "python developer", "python programmer", "python engineer", "django developer",
        "flask developer", "python backend",
    ],
}

CITY_ALIASES = {
    "bangalore": ["bangalore", "bengaluru"],
    "mumbai": ["mumbai", "bombay"],
    "kolkata": ["kolkata", "calcutta"],
    "chennai": ["chennai", "madras"],
    "gurgaon": ["gurgaon", "gurugram"],
}


def normalize_city(city: str | None) -> str:
    if not city:
        return ""
    city = str(city).lower().strip()
    for canonical, aliases in CITY_ALIASES.items():
        if city in aliases:
            return canonical
    return city


def normalize_work_mode(mode: Any) -> str:
    mode = str(mode).lower().strip()
    return "on-site" if mode in ("onsite", "on site") else mode


def normalize_work_modes(value: Any) -> list[str]:
    if not value:
        return []
    values = list(value) if isinstance(value, (list, tuple, set)) else re.split(
        r",|/|\bor\b", str(value), flags=re.IGNORECASE
    )
    result: list[str] = []
    for v in values:
        mode = normalize_work_mode(v)
        if mode in ("remote", "hybrid", "on-site") and mode not in result:
            result.append(mode)
    return result


# =============================================================================
# CLEANING
# =============================================================================

def _clean_boolean(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    mapping = {"true": True, "false": False, "yes": True, "no": False, "1": True, "0": False,
               "1.0": True, "0.0": False}
    return series.astype(str).str.lower().str.strip().map(mapping).fillna(False).astype(bool)


_RANGE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)")
_PLUS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:year|years|yr|yrs)")


def parse_min_experience(raw_value: Any, existing_value: Any) -> float:
    if raw_value is None or pd.isna(raw_value):
        return np.nan if pd.isna(existing_value) else float(existing_value)
    text = str(raw_value).lower().strip()
    if "fresher" in text:
        return 0.0
    for pattern in (_RANGE_RE, _PLUS_RE, _YEARS_RE):
        m = pattern.search(text)
        if m:
            return float(m.group(1))
    return np.nan if pd.isna(existing_value) else float(existing_value)


def _experience_tier(lo: float) -> str:
    if pd.isna(lo):
        return "Unknown"
    if lo == 0:
        return "Fresher (0 yrs)"
    if lo <= 2:
        return "Junior (1-2 yrs)"
    if lo <= 5:
        return "Mid (3-5 yrs)"
    if lo <= 9:
        return "Senior (6-9 yrs)"
    return "Lead (10+ yrs)"


def clean_dataset(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    missing = [c for c in REQUIRED_COLUMNS if c not in df_raw.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    quality = {
        "raw_rows": int(len(df_raw)),
        "raw_columns": int(len(df_raw.columns)),
        "duplicate_rows": int(df_raw.duplicated().sum()),
        "duplicate_job_ids": int(df_raw["job_id"].duplicated().sum()),
        "missing_values": {k: int(v) for k, v in df_raw.isnull().sum().sort_values(ascending=False).items() if v > 0},
    }

    df = df_raw.drop_duplicates().drop_duplicates(subset=["job_id"], keep="first").copy()

    for col in TEXT_COLUMNS:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in BOOLEAN_COLUMNS:
        if col in df.columns:
            df[col] = _clean_boolean(df[col])

    df["clean_experience_min_yrs"] = [
        parse_min_experience(raw, existing)
        for raw, existing in zip(df["experience_raw"], df["experience_min_yrs"])
    ]
    if "experience_tier" not in df.columns:
        df["experience_tier"] = df["clean_experience_min_yrs"].map(_experience_tier)
    df["experience_tier"] = df["experience_tier"].fillna("Unknown")

    df["salary_available"] = df["salary_midpoint_lpa"].notna() & (df["salary_midpoint_lpa"] > 0)
    df["remote_or_hybrid"] = df["work_mode"].astype(str).str.lower().isin(["remote", "hybrid"])

    for col in ("job_title", "company_name", "location", "primary_city", "work_mode", "role_category"):
        df[col] = df[col].fillna("Unknown")

    quality["clean_rows"] = int(len(df))
    return df.reset_index(drop=True), quality


# =============================================================================
# MATCHING ENGINE
# =============================================================================

def _fit_category(score: float) -> str:
    if score >= 80:
        return "Excellent Fit"
    if score >= 65:
        return "Good Fit"
    if score >= 50:
        return "Potential Fit"
    if score >= 30:
        return "Low Fit"
    return "Very Low Fit"


def _priority(eligible: bool, score: float) -> str:
    if eligible:
        return "High Priority" if score >= 80 else "Recommended" if score >= 65 else "Possible"
    return "Improve Before Applying" if score >= 50 else "Low Priority"


@dataclass
class Candidate:
    skills: list[str]
    experience: float = 0.0
    city: str | None = None
    work_mode: str | list[str] | None = None
    target_role: str | None = None
    role_only: bool = False  # restrict to jobs in the target role category

    @property
    def core_skills(self) -> set[str]:
        return {s for s in normalize_skill_list(self.skills) if skill_weight(s) > 0}


@dataclass
class JobMarket:
    df: pd.DataFrame
    quality: dict
    source: str
    skill_long: pd.DataFrame = field(init=False)
    _job_skills: list[set[str]] = field(init=False)
    _total_weight: np.ndarray = field(init=False)

    @classmethod
    def from_csv(cls, path: str | Path, source: str | None = None) -> "JobMarket":
        raw = pd.read_csv(path)
        df, quality = clean_dataset(raw)
        return cls(df=df, quality=quality, source=source or Path(path).name)

    def __post_init__(self) -> None:
        df = self.df
        # ---- long-format skill table --------------------------------------------
        long = (
            df[["job_id", "role_category", "skills_required", "primary_city", "work_mode",
                "experience_tier", "salary_midpoint_lpa", "salary_available",
                "is_fresher_friendly"]]
            .assign(skill=df["skills_required"].fillna("").astype(str).str.split(r"[,;|]"))
            .explode("skill")
        )
        long["skill"] = long["skill"].map(normalize_skill_name)
        long = long[long["skill"] != ""].drop_duplicates(subset=["job_id", "skill"])
        long["skill_category"] = long["skill"].map(skill_category)
        long["skill_weight"] = long["skill"].map(skill_weight)
        self.skill_long = long.reset_index(drop=True)

        # ---- job skill cache (core skills only) ---------------------------------
        self._job_skills = [
            {s for s in normalize_skill_list(t) if skill_weight(s) > 0}
            for t in df["skills_required"]
        ]
        self._total_weight = np.array(
            [sum(skill_weight(s) for s in skills) for skills in self._job_skills], dtype=float
        )

        # ---- vectorised job attributes ------------------------------------------
        self._min_exp = df["clean_experience_min_yrs"].to_numpy(dtype=float)
        self._location = df["location"].astype(str).str.lower().to_numpy()
        self._mode = df["work_mode"].map(normalize_work_mode).to_numpy()
        self._role = df["role_category"].astype(str).to_numpy()
        titles = df["job_title"].astype(str).str.lower()
        self._role_relevance = {
            role: titles.map(lambda t, kw=kws: any(k in t for k in kw)).to_numpy()
            for role, kws in ROLE_TITLE_KEYWORDS.items()
        }
        self._skill_index: dict[str, np.ndarray] = {}
        for i, skills in enumerate(self._job_skills):
            for s in skills:
                self._skill_index.setdefault(s, []).append(i)  # type: ignore[arg-type]
        self._skill_index = {k: np.array(v) for k, v in self._skill_index.items()}

    # ------------------------------------------------------------------ scoring

    def _skill_scores(self, cand: set[str]) -> tuple[np.ndarray, np.ndarray]:
        matched_w = np.zeros(len(self.df))
        for s in cand:
            idx = self._skill_index.get(s)
            if idx is not None:
                matched_w[idx] += skill_weight(s)
        with np.errstate(divide="ignore", invalid="ignore"):
            score = np.where(self._total_weight > 0, matched_w / self._total_weight * 100, 0.0)
        return score, matched_w

    def score(self, c: Candidate) -> pd.DataFrame:
        """Score the candidate against every job. Returns one row per job."""
        n = len(self.df)
        cand = c.core_skills
        skill_score, _ = self._skill_scores(cand)

        # Role relevance
        target = c.target_role or None
        if target is None:
            role_rel = np.full(n, 50.0)
        else:
            role_rel = np.where(self._role_relevance.get(target, np.zeros(n, bool)), 100.0, 0.0)

        # Experience
        exp = float(c.experience or 0)
        min_exp = self._min_exp
        no_exp = np.isnan(min_exp)
        exp_ok = no_exp | (exp >= np.nan_to_num(min_exp, nan=0))
        exp_partial = np.clip(exp / np.maximum(np.nan_to_num(min_exp, nan=1), 1) * 100, 0, 100)
        exp_score = np.where(no_exp, 50.0, np.where(exp_ok, 100.0, exp_partial))

        # Location
        if not c.city:
            loc_score = np.full(n, 50.0)
        else:
            canon = normalize_city(c.city)
            aliases = CITY_ALIASES.get(canon, [canon])
            hit = np.array([any(a in loc for a in aliases) for loc in self._location])
            loc_score = np.where(hit, 100.0, 25.0)

        # Work mode
        prefs = normalize_work_modes(c.work_mode)
        if not prefs:
            mode_score = np.full(n, 50.0)
        else:
            mode = self._mode
            mode_score = np.full(n, 25.0)
            if "remote" in prefs:
                mode_score[mode == "hybrid"] = 75.0
            if "hybrid" in prefs:
                mode_score[mode == "remote"] = 75.0
            mode_score[np.isin(mode, prefs)] = 100.0

        match = 0.50 * skill_score + 0.25 * exp_score + 0.10 * role_rel + 0.10 * loc_score + 0.05 * mode_score
        skill_ok = skill_score >= 50.0
        role_ok = np.ones(n, bool) if target is None else role_rel >= 100.0
        eligible = skill_ok & exp_ok & role_ok

        out = pd.DataFrame({
            "idx": np.arange(n),
            "job_id": self.df["job_id"].to_numpy(),
            "job_title": self.df["job_title"].astype(str).to_numpy(),
            "company": self.df["company_name"].astype(str).to_numpy(),
            "role": self._role,
            "city": self.df["primary_city"].astype(str).to_numpy(),
            "location": self.df["location"].astype(str).to_numpy(),
            "work_mode": self.df["work_mode"].astype(str).to_numpy(),
            "required_experience": min_exp,
            "skill_match_percent": skill_score.round(2),
            "_skill_raw": skill_score,
            "experience_match_percent": exp_score.round(2),
            "role_relevance_percent": role_rel,
            "location_match_percent": loc_score,
            "work_mode_match_percent": mode_score,
            "match_score": match.round(2),
            "_match_raw": match,
            "eligible": eligible,
            "_skill_ok": skill_ok,
            "_exp_ok": exp_ok,
            "_role_ok": role_ok,
            "salary_lpa": np.where(self.df["salary_available"].to_numpy(),
                                   self.df["salary_midpoint_lpa"].to_numpy(dtype=float), np.nan),
        })
        if c.role_only and target:
            out = out[out["role"] == target]
        return out.sort_values(["eligible", "match_score"], ascending=[False, False]).reset_index(drop=True)

    def explain(self, row: pd.Series, c: Candidate) -> dict:
        """Matched/missing skills and the human-readable eligibility reason for one job."""
        cand = c.core_skills
        required = self._job_skills[int(row["idx"])]
        matched, missing = sorted(cand & required), sorted(required - cand)
        exp = float(c.experience or 0)
        min_exp = row["required_experience"]
        if pd.isna(min_exp):
            exp_reason = "No reliable minimum experience requirement was available."
        elif row["_exp_ok"]:
            exp_reason = f"Experience requirement satisfied: {exp:g} years candidate; {min_exp:g} years required."
        else:
            exp_reason = f"Candidate has {exp:g} years but the job requires at least {min_exp:g} years."

        if row["eligible"]:
            explanation = (f"Eligible because the candidate has {row['skill_match_percent']:.1f}% core skill match, "
                           "meets the experience requirement, and the job title is relevant to the target role.")
        else:
            reasons = []
            if not row["_skill_ok"]:
                reasons.append(f"core skill match is only {row['skill_match_percent']:.1f}%")
            if not row["_exp_ok"]:
                reasons.append(exp_reason)
            if c.target_role and not row["_role_ok"]:
                reasons.append(f"the job title is not sufficiently relevant to {c.target_role}")
            explanation = "Not eligible because " + "; ".join(reasons) + "."
        return {
            "matched_skills": matched,
            "missing_skills": missing,
            "required_core_skill_count": len(required),
            "experience_reason": exp_reason,
            "eligibility_explanation": explanation,
        }

    def job_records(self, scored: pd.DataFrame, c: Candidate, limit: int = 50) -> list[dict]:
        records = []
        for _, row in scored.head(limit).iterrows():
            rec = {k: _py(v) for k, v in row.items() if not k.startswith("_") and k != "idx"}
            rec["fit_category"] = _fit_category(row["_match_raw"])
            rec["application_priority"] = _priority(bool(row["eligible"]), row["_match_raw"])
            rec.update(self.explain(row, c))
            records.append(rec)
        return records

    @staticmethod
    def dashboard(scored: pd.DataFrame) -> dict:
        total = len(scored)
        if total == 0:
            return {"jobs_analyzed": 0, "eligible_jobs": 0, "not_eligible_jobs": 0,
                    "eligibility_percent": 0, "average_match_score": 0, "fit_breakdown": {}}
        eligible = int(scored["eligible"].sum())
        fits = scored["_match_raw"].map(_fit_category).value_counts()
        order = ["Excellent Fit", "Good Fit", "Potential Fit", "Low Fit", "Very Low Fit"]
        return {
            "jobs_analyzed": total,
            "eligible_jobs": eligible,
            "not_eligible_jobs": total - eligible,
            "eligibility_percent": round(eligible / total * 100, 2),
            "average_match_score": round(float(scored["match_score"].mean()), 2),
            "top_match_score": round(float(scored["match_score"].max()), 2),
            "fit_breakdown": {k: int(fits.get(k, 0)) for k in order},
        }

    def skill_gaps(self, scored: pd.DataFrame, c: Candidate, max_jobs: int = 1000, top: int = 10) -> list[dict]:
        """Missing core skills ranked by frequency in the best-matching jobs,
        with the number of extra eligible jobs each one would unlock alone."""
        cand = c.core_skills
        counter: dict[str, int] = {}
        for i in scored["idx"].head(max_jobs):
            for s in self._job_skills[int(i)] - cand:
                counter[s] = counter.get(s, 0) + 1
        ranked = sorted(counter.items(), key=lambda kv: kv[1], reverse=True)[: top * 2]

        # Adding one skill only changes the skill score of jobs that list it,
        # so update those rows instead of re-scoring the whole market.
        by_idx = scored.set_index("idx")
        skill_pct = by_idx["_skill_raw"]
        others_ok = by_idx["_exp_ok"] & by_idx["_role_ok"]
        n = len(scored)
        out = []
        for skill, freq in ranked:
            idx = self._skill_index.get(skill, np.array([], int))
            idx = idx[np.isin(idx, by_idx.index)]
            gain = skill_weight(skill) / self._total_weight[idx] * 100
            new_pct = skill_pct.loc[idx].to_numpy() + gain
            was = by_idx["eligible"].loc[idx].to_numpy()
            now = (new_pct >= 50.0 - 1e-9) & others_ok.loc[idx].to_numpy()
            out.append({
                "skill": skill,
                "category": skill_category(skill),
                "appears_in_top_jobs": freq,
                "extra_eligible_jobs": int((now & ~was).sum()),
                "avg_score_gain": round(float(0.5 * gain.sum() / max(n, 1)), 2),
            })
        out.sort(key=lambda r: (r["extra_eligible_jobs"], r["appears_in_top_jobs"]), reverse=True)
        return out[:top]

    def what_if(self, c: Candidate, added: Iterable[str]) -> dict:
        before = self.score(c)
        after_c = Candidate(**{**c.__dict__, "skills": list(c.skills) + list(added)})
        after = self.score(after_c)
        b, a = self.dashboard(before), self.dashboard(after)
        newly = after[after["eligible"] & ~after["job_id"].isin(before.loc[before["eligible"], "job_id"])]
        return {
            "added_skills": sorted(normalize_skill_list(list(added))),
            "before": b,
            "after": a,
            "additional_eligible": a["eligible_jobs"] - b["eligible_jobs"],
            "score_improvement": round(a["average_match_score"] - b["average_match_score"], 2),
            "newly_eligible_jobs": self.job_records(newly, after_c, limit=10),
        }

    # ------------------------------------------------------------------ market

    def overview(self) -> dict:
        df, sal = self.df, self.df[self.df["salary_available"]]
        top = (self.skill_long.groupby("skill")["job_id"].nunique().sort_values(ascending=False).head(20))
        core_top = (self.skill_long[self.skill_long["skill_weight"] > 0]
                    .groupby("skill")["job_id"].nunique().sort_values(ascending=False).head(20))
        return {
            "source": self.source,
            "quality": self.quality,
            "kpis": {
                "total_jobs": int(len(df)),
                "companies": int(df["company_name"].nunique()),
                "job_titles": int(df["job_title"].nunique()),
                "cities": int(df["primary_city"].nunique()),
                "roles": int(df["role_category"].nunique()),
                "salary_records": int(len(sal)),
                "avg_salary_lpa": round(float(sal["salary_midpoint_lpa"].mean()), 2) if len(sal) else None,
                "fresher_jobs": int(df["is_fresher_friendly"].sum()),
                "remote_hybrid_jobs": int(df["remote_or_hybrid"].sum()),
            },
            "roles": _counts(df["role_category"]),
            "cities": _counts(df["primary_city"], 15),
            "work_modes": _counts(df["work_mode"]),
            "experience_tiers": _counts(df["experience_tier"]),
            "company_sizes": _counts(df["company_size_bucket"]),
            "fresher_rate_by_role": {k: round(float(v) * 100, 2) for k, v in
                                     df.groupby("role_category")["is_fresher_friendly"].mean().sort_values(ascending=False).items()},
            "salary_by_role": [
                {"role": r, "count": int(g.size), "mean": round(float(g.mean()), 2), "median": round(float(g.median()), 2)}
                for r, g in sal.groupby("role_category")["salary_midpoint_lpa"]
            ],
            "top_skills": [{"skill": s, "jobs": int(n), "demand_percent": round(n / len(df) * 100, 2)} for s, n in top.items()],
            "top_core_skills": [{"skill": s, "jobs": int(n), "demand_percent": round(n / len(df) * 100, 2)} for s, n in core_top.items()],
            "skill_categories": _counts(self.skill_long["skill_category"]),
            "role_opportunity": self.role_opportunity(),
        }

    def role_opportunity(self) -> list[dict]:
        df, sal = self.df, self.df[self.df["salary_available"]]
        ra = df.groupby("role_category").agg(
            job_count=("job_id", "count"),
            fresher_rate=("is_fresher_friendly", "mean"),
            flexibility_rate=("remote_or_hybrid", "mean"),
        )
        if len(sal):
            ra = ra.join(sal.groupby("role_category")["salary_midpoint_lpa"].mean().rename("avg_salary"), how="left")
            ra["avg_salary"] = ra["avg_salary"].fillna(sal["salary_midpoint_lpa"].median())
        else:
            ra["avg_salary"] = 0.0
        ra["opportunity_score"] = (
            0.45 * _minmax(ra["job_count"]) + 0.25 * _minmax(ra["avg_salary"])
            + 0.20 * ra["fresher_rate"].clip(0, 1) + 0.10 * ra["flexibility_rate"].clip(0, 1)
        ) * 100
        ra = ra.sort_values("opportunity_score", ascending=False).round(3)
        return [{"role": r, **{k: _py(v) for k, v in row.items()}} for r, row in ra.iterrows()]

    def role_skills(self, role: str, top: int = 15) -> list[dict]:
        sl = self.skill_long
        sub = sl[(sl["role_category"].astype(str).str.lower() == role.lower()) & (sl["skill_weight"] > 0)]
        n_jobs = max(int((self.df["role_category"] == role).sum()), 1)
        counts = sub.groupby("skill")["job_id"].nunique().sort_values(ascending=False).head(top)
        return [{"skill": s, "jobs": int(n), "share_percent": round(n / n_jobs * 100, 2)} for s, n in counts.items()]

    def search_jobs(self, q: str = "", role: str = "", city: str = "", mode: str = "",
                    fresher: bool = False, salary_only: bool = False, page: int = 1, size: int = 25) -> dict:
        df = self.df
        mask = np.ones(len(df), bool)
        if q:
            ql = q.lower()
            mask &= (df["job_title"].str.lower().str.contains(ql, regex=False, na=False)
                     | df["company_name"].str.lower().str.contains(ql, regex=False, na=False)
                     | df["skills_required"].fillna("").str.lower().str.contains(ql, regex=False, na=False)).to_numpy()
        if role:
            mask &= (df["role_category"] == role).to_numpy()
        if city:
            mask &= (df["primary_city"] == city).to_numpy()
        if mode:
            mask &= (df["work_mode"].str.lower() == mode.lower()).to_numpy()
        if fresher:
            mask &= df["is_fresher_friendly"].to_numpy()
        if salary_only:
            mask &= df["salary_available"].to_numpy()
        sub = df[mask]
        cols = ["job_id", "job_title", "company_name", "role_category", "primary_city", "work_mode",
                "experience_raw", "clean_experience_min_yrs", "salary_midpoint_lpa", "skills_required",
                "is_fresher_friendly", "company_size_bucket"]
        cols = [c for c in cols if c in sub.columns]
        page_df = sub.iloc[(page - 1) * size: page * size][cols]
        return {
            "total": int(len(sub)),
            "page": page,
            "size": size,
            "jobs": [{k: _py(v) for k, v in r.items()} for r in page_df.to_dict("records")],
        }

    def export(self, folder: Path) -> list[str]:
        folder.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(folder / "cleaned_job_market_data.csv", index=False)
        self.skill_long.to_csv(folder / "job_skills_long_format.csv", index=False)
        pd.DataFrame(self.role_opportunity()).to_csv(folder / "role_opportunity_scores.csv", index=False)
        return sorted(p.name for p in folder.iterdir())


# =============================================================================
# HELPERS
# =============================================================================

def _minmax(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    if s.max() == s.min():
        return pd.Series(1.0, index=s.index)
    return (s - s.min()) / (s.max() - s.min())


def _counts(s: pd.Series, top: int | None = None) -> dict:
    vc = s.astype(str).value_counts()
    if top:
        vc = vc.head(top)
    return {k: int(v) for k, v in vc.items()}


def _py(v: Any) -> Any:
    """Convert numpy/pandas scalars to JSON-safe Python values."""
    if v is None:
        return None
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if np.isnan(v) else round(float(v), 3)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v if isinstance(v, (int, str, list, dict)) else str(v)
