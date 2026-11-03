# TechJobs India 2026 — AI-Assisted Job Market Analysis

Web app built from `DAVmp.ipynb`. For a candidate profile it finds which jobs they are eligible for, scores how well they match each job, explains each decision, ranks the skills to learn next, and simulates "what if I learn X?". An optional Gemini model writes the career advice.

## Run

```
run.bat
```
or
```
pip install -r requirements.txt
python -m uvicorn backend.app:app --port 8000
```
Then open http://localhost:8000

## Dataset

- Put the real dataset at `data/indian_tech_jobs_2026.csv`, or upload it from the **Dataset** tab.
- If it is missing, the app uses `data/sample_jobs.csv`, a synthetic dataset with the same columns (`python scripts/generate_sample_data.py` rebuilds it).

## Gemini (optional)

Paste a key in the **AI Advisor** tab, or set `GEMINI_API_KEY` before starting. `GEMINI_MODEL` changes the model (default `gemini-3.6-flash`). Without a key, a rule-based advisor is used.

## Scoring (same rules as the notebook)

| Component | Weight |
|---|---|
| Core skill match (technical = 1.0, business = 0.5, generic = 0) | 50% |
| Experience | 25% |
| Role / title relevance | 10% |
| Location | 10% |
| Work mode | 5% |

**Eligible** = minimum experience met, at least 50% core skill match, and a job title relevant to the target role.
The match score is **not** a hiring probability, because the dataset has no hiring outcomes.

## Project layout

```
backend/engine.py    cleaning, skill taxonomy, matching engine, market analytics
backend/ai.py        4-step advisor workflow (match -> recommend -> what-if -> explain) + Gemini REST
backend/app.py       FastAPI JSON API + static frontend
frontend/            dashboard UI (HTML/CSS/JS + Chart.js)
scripts/             sample dataset generator
DAVmp.ipynb          original notebook
```

## Changes from the notebook

- Runs as a standalone web app, with no Google Colab dependency (`google.colab.files`, `getpass`).
- Matching is vectorized: one candidate is scored against every job in milliseconds, instead of looping with `DataFrame.iterrows()`.
- Fixed the crash at "SAVING BACKEND" (`Series.reset_index(names=...)`), and merged the duplicate `normalize_skill_list` definition.
- Each skill gap shows how many extra jobs that skill would make the candidate eligible for on its own.
- The what-if simulator lists the jobs that become eligible.
- Added more skill aliases (sklearn, k8s, apache spark, amazon web services, and others).
- Option to analyse only jobs in the target role category.
- You can upload a CSV, see a data-quality report, and export the cleaned backend files.
