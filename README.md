# ATS Resume Screening Project

This project includes:

1. A full HR-focused ATS resume screening guide in Markdown
2. A Python implementation for ATS-style candidate scoring
3. A CSV batch screening workflow for multiple resumes
4. A recruiter dashboard HTML view for HR teams
5. Automated tests to validate the screening logic

## Files

- [ATS_Resume_Screening_Guide_for_HR.md](ATS_Resume_Screening_Guide_for_HR.md) — complete HR guide
- [ats_resume_screening.py](ats_resume_screening.py) — scoring, CSV processing, and dashboard generation
- [main.py](main.py) — command-line entry point
- [test_ats_screening.py](test_ats_screening.py) — unit tests
- [sample_candidates.csv](sample_candidates.csv) — example batch file
- [recruiter_dashboard.html](recruiter_dashboard.html) — generated recruiter dashboard
- [plan.md](plan.md) — implementation plan tracking

## Single candidate screening

```bash
py main.py --job "Senior Business Analyst with SQL, Agile, and reporting" --resume "Senior Business Analyst with 6 years experience in SQL, Agile, stakeholder management, reporting"
```

## CSV batch screening

```bash
py main.py --csv sample_candidates.csv --job "Senior Business Analyst with SQL, Agile, reporting, and stakeholder management" --dashboard recruiter_dashboard.html
```

## Open the dashboard in a web browser

Open the generated file:

```text
recruiter_dashboard.html
```

## Run the tests

```bash
py -m pytest -q test_ats_screening.py
```

## Output

The tool returns:

- candidate score
- decision (`Shortlist`, `Review`, or `Reject`)
- matched keywords
- missing keywords
- years of experience
- recruiter dashboard summary cards and table
