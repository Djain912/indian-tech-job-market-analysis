"""
Generate a synthetic sample dataset with the same schema as
indian_tech_jobs_2026.csv so the app runs out of the box.

Drop the real dataset at data/indian_tech_jobs_2026.csv (or upload it from
the UI) and the app will use it instead.

Usage:
    python scripts/generate_sample_data.py [rows]
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sample_jobs.csv"

rng = np.random.default_rng(2026)

ROLES = {
    "Data Scientist": {
        "weight": 0.28,
        "titles": ["Data Scientist", "Senior Data Scientist", "Lead Data Scientist",
                   "Applied Scientist", "Data Scientist - NLP", "Junior Data Scientist",
                   "Research Scientist", "Data Science Manager", "Analytics Consultant"],
        "skills": ["python", "machine learning", "statistics", "sql", "deep learning",
                   "data science", "pandas", "numpy", "scikit-learn", "tensorflow",
                   "pytorch", "nlp", "artificial intelligence", "generative ai", "llm",
                   "predictive modeling", "aws", "data visualization", "r", "spark"],
        "salary": (8, 32),
        "domain": "Data Science & AI",
    },
    "Data Analyst": {
        "weight": 0.20,
        "titles": ["Data Analyst", "Junior Data Analyst", "Senior Data Analyst",
                   "BI Analyst", "Reporting Analyst", "MIS Analyst", "Lead Data Analyst",
                   "Data Analytics Engineer", "Analytics Analyst", "Operations Executive"],
        "skills": ["data analysis", "sql", "excel", "power bi", "tableau", "python",
                   "data visualization", "statistics", "business intelligence",
                   "data management", "data quality", "pandas", "automation",
                   "business analysis", "project management"],
        "salary": (3, 16),
        "domain": "Analytics & BI",
    },
    "Business Analyst": {
        "weight": 0.19,
        "titles": ["Business Analyst", "Senior Business Analyst", "Business Systems Analyst",
                   "Functional Analyst", "Requirements Analyst", "IT Business Analyst",
                   "Product Analyst", "Associate Consultant"],
        "skills": ["business analysis", "sql", "excel", "agile", "project management",
                   "stakeholder management", "consulting", "power bi", "data analysis",
                   "sap", "erp", "change management", "market research", "tableau"],
        "salary": (5, 22),
        "domain": "Business & Consulting",
    },
    "Machine Learning Engineer": {
        "weight": 0.17,
        "titles": ["Machine Learning Engineer", "ML Engineer", "Senior ML Engineer",
                   "AI Engineer", "Deep Learning Engineer", "GenAI Engineer",
                   "Sr. Artificial Intelligence Engineer", "MLOps Engineer"],
        "skills": ["python", "machine learning", "deep learning", "pytorch", "tensorflow",
                   "mlops", "docker", "kubernetes", "aws", "gcp", "azure", "llm",
                   "generative ai", "rag", "agentic ai", "nlp", "git", "ci/cd",
                   "scikit-learn", "artificial intelligence"],
        "salary": (7, 30),
        "domain": "Data Science & AI",
    },
    "Data Engineer": {
        "weight": 0.09,
        "titles": ["Data Engineer", "Senior Data Engineer", "Big Data Engineer",
                   "ETL Developer", "Data Platform Engineer", "Spark Developer",
                   "Cloud Data Engineer"],
        "skills": ["python", "sql", "spark", "pyspark", "kafka", "airflow",
                   "data engineering", "aws", "azure", "gcp", "data modeling",
                   "docker", "git", "ci/cd", "data quality"],
        "salary": (6, 28),
        "domain": "Data Engineering",
    },
    "Python Developer": {
        "weight": 0.07,
        "titles": ["Python Developer", "Senior Python Developer", "Python Engineer",
                   "Django Developer", "Python Backend Developer", "Flask Developer",
                   "Software Engineer - Python"],
        "skills": ["python", "sql", "git", "docker", "aws", "javascript", "html",
                   "css", "automation", "ci/cd", "kubernetes", "pandas", "typescript"],
        "salary": (4, 24),
        "domain": "Software Development",
    },
}

GENERIC = ["communication", "analytical", "teamwork", "leadership", "reporting",
           "problem solving", "stakeholder communication", "documentation"]

CITIES = [("Bengaluru", 0.27), ("Hyderabad", 0.14), ("Pune", 0.11), ("Mumbai", 0.10),
          ("Gurugram", 0.08), ("Chennai", 0.08), ("Noida", 0.06), ("Delhi", 0.04),
          ("Kolkata", 0.03), ("Ahmedabad", 0.03), ("Jaipur", 0.02), ("Kochi", 0.02),
          ("Indore", 0.01), ("Chandigarh", 0.01)]

COMPANIES = ["Cisco", "Morningstar", "Accenture", "TCS", "Infosys", "Wipro", "HCLTech",
             "Deloitte", "EY", "KPMG", "PwC", "Amazon", "Microsoft", "Google", "Flipkart",
             "Swiggy", "Zomato", "Paytm", "PhonePe", "Razorpay", "Fractal Analytics",
             "Mu Sigma", "Tiger Analytics", "LatentView", "Tech Mahindra", "Capgemini",
             "Cognizant", "IBM", "Oracle", "SAP Labs", "Walmart Global Tech", "Target",
             "American Express", "JP Morgan", "Goldman Sachs", "Myntra", "Meesho",
             "Ola", "Zepto", "CRED", "Freshworks", "Zoho", "Juspay", "Groww", "Nykaa",
             "Genpact", "EXL", "WNS", "Publicis Sapient", "Thoughtworks"]

SIZES = ["Startup (1-50)", "Small (51-200)", "Mid (201-1000)", "Large (1001-10000)",
         "Enterprise (10000+)"]


def experience_tier(lo):
    if lo == 0:
        return "Fresher (0 yrs)"
    if lo <= 2:
        return "Junior (1-2 yrs)"
    if lo <= 5:
        return "Mid (3-5 yrs)"
    if lo <= 9:
        return "Senior (6-9 yrs)"
    return "Lead (10+ yrs)"


def main(n):
    role_names = list(ROLES)
    role_p = np.array([ROLES[r]["weight"] for r in role_names])
    role_p /= role_p.sum()
    city_names = [c for c, _ in CITIES]
    city_p = np.array([p for _, p in CITIES])
    city_p /= city_p.sum()
    now = datetime(2026, 10, 30)

    rows = []
    for job_id in range(1, n + 1):
        role = rng.choice(role_names, p=role_p)
        spec = ROLES[role]
        title = str(rng.choice(spec["titles"]))
        title_l = title.lower()

        if any(k in title_l for k in ["junior", "associate", "executive"]):
            lo = int(rng.choice([0, 0, 1, 1, 2]))
        elif any(k in title_l for k in ["senior", "sr.", "lead", "manager"]):
            lo = int(rng.choice([4, 5, 6, 7, 8, 10]))
        else:
            lo = int(rng.choice([0, 1, 2, 2, 3, 3, 4, 5, 6], p=[.14, .14, .16, .12, .14, .1, .08, .07, .05]))
        hi = lo + int(rng.choice([2, 3, 4, 5]))
        exp_raw = "Fresher" if lo == 0 and rng.random() < 0.3 else f"{lo}-{hi} Yrs"

        k = int(rng.integers(4, 11))
        core = list(rng.choice(spec["skills"], size=min(k, len(spec["skills"])), replace=False))
        extra = list(rng.choice(GENERIC, size=int(rng.integers(0, 3)), replace=False))
        skills = [s.title() if len(s) > 3 else s.upper() for s in core + extra]
        rng.shuffle(skills)

        city = str(rng.choice(city_names, p=city_p))
        location = city if rng.random() > 0.15 else f"{city}, {rng.choice(city_names)}"
        mode = str(rng.choice(["On-site", "Hybrid", "Remote"], p=[0.78, 0.15, 0.07]))

        disclosed = rng.random() < 0.13
        smin, smax = spec["salary"]
        bump = 1 + lo * 0.12
        if disclosed:
            s_lo = round(float(rng.uniform(smin, smax * 0.7)) * bump * 0.6, 1)
            s_hi = round(s_lo * float(rng.uniform(1.2, 1.7)), 1)
            mid = round((s_lo + s_hi) / 2, 2)
            salary_raw = f"{s_lo}-{s_hi} Lacs PA"
            tier = "Low (<6 LPA)" if mid < 6 else "Mid (6-15 LPA)" if mid < 15 else "High (15-30 LPA)" if mid < 30 else "Very High (30+ LPA)"
        else:
            s_lo = s_hi = mid = np.nan
            salary_raw = "Not disclosed"
            tier = "Not Disclosed"

        days = int(rng.integers(0, 60))
        company = str(rng.choice(COMPANIES))
        rows.append({
            "job_id": job_id,
            "job_title": title,
            "company_name": company,
            "company_rating": round(float(rng.uniform(3.0, 4.8)), 1),
            "location": location,
            "scraped_city": city,
            "role_category": role,
            "experience_raw": exp_raw,
            "experience_min_yrs": lo,
            "experience_max_yrs": hi,
            "salary_raw": salary_raw,
            "salary_min_lpa": s_lo,
            "salary_max_lpa": s_hi,
            "salary_midpoint_lpa": mid,
            "salary_disclosed": disclosed,
            "skills_required": ", ".join(skills),
            "skills_count": len(skills),
            "job_description": f"{company} is hiring a {title} in {city}. Key skills: {', '.join(core[:4])}.",
            "posted_date_raw": f"{days} days ago" if days else "Today",
            "days_since_posted": days,
            "work_mode": mode,
            "company_size_bucket": str(rng.choice(SIZES)),
            "salary_tier": tier,
            "experience_tier": experience_tier(lo),
            "primary_city": city,
            "skill_domain": spec["domain"],
            "is_senior": lo >= 6,
            "is_fresher_friendly": lo == 0,
            "salary_negotiable": bool(rng.random() < 0.2),
            "job_url": f"https://example.com/jobs/{job_id}",
            "data_source": "synthetic-sample",
            "scraped_at": (now - timedelta(days=days)).isoformat(),
        })

    OUT.parent.mkdir(exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"Wrote {len(rows)} rows -> {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8000)
