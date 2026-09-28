"""Simple ATS-style resume screening utilities for HR use.

This module evaluates a resume against a job description using keyword overlap,
minimum years-of-experience heuristic, and a simple score model. It also supports
CSV batch processing and recruiter-friendly dashboard output.
"""

from __future__ import annotations

import csv
import html
import re
from pathlib import Path
from typing import Dict, List, Tuple


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower())


def _extract_keywords(text: str) -> List[str]:
    words = _normalize(text).split()
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "have",
        "from",
        "into",
        "must",
        "years",
        "year",
        "experience",
        "skills",
        "role",
        "candidate",
        "resume",
    }
    return [word for word in words if word and word not in stop_words and len(word) > 2]


def _count_experience_years(text: str) -> int:
    matches = re.findall(r"(\d+)\s*\+?\s*years?", _normalize(text))
    if not matches:
        return 0
    return max(int(m) for m in matches)


def score_candidate(job_description: str, resume_text: str) -> Dict[str, object]:
    """Return a score and decision for an ATS-style screening evaluation."""
    jd_keywords = _extract_keywords(job_description)
    resume_keywords = _extract_keywords(resume_text)

    jd_set = set(jd_keywords)
    resume_set = set(resume_keywords)
    matched = sorted(jd_set & resume_set)

    core_keywords = {"sql", "agile", "reporting", "stakeholder", "management", "requirements", "analyst", "business"}
    core_match_count = len(core_keywords & resume_set)
    keyword_coverage = (len(matched) / max(len(jd_set), 1)) * 100
    weighted_keyword_score = min(keyword_coverage * 0.85, 75)
    core_bonus = min(core_match_count * 12, 30)

    experience_years = _count_experience_years(resume_text)
    experience_score = min(experience_years * 10, 40)

    total_score = round(weighted_keyword_score + core_bonus + experience_score, 2)

    if "agile" in resume_text.lower() and "sql" in resume_text.lower():
        total_score += 5
    if "reporting" in resume_text.lower() and "stakeholder" in resume_text.lower():
        total_score += 5

    total_score = min(round(total_score, 2), 100)

    if total_score >= 80:
        decision = "Shortlist"
        decision_reason = "Strong match across the key job requirements and experience level."
    elif total_score >= 55:
        decision = "Review"
        decision_reason = "Candidate is promising but needs a closer review for missing skills or experience gaps."
    else:
        decision = "Reject"
        decision_reason = "Candidate does not sufficiently match the role requirements for this position."

    missing = sorted(jd_set - resume_set)
    return {
        "score": total_score,
        "decision": decision,
        "decision_reason": decision_reason,
        "matched_keywords": matched,
        "missing_keywords": missing,
        "experience_years": experience_years,
    }


def summarize_result(candidate_name: str, score: int, decision: str,
                     matched_keywords: List[str], missing_keywords: List[str],
                     decision_reason: str | None = None) -> str:
    """Produce an HR-ready summary string for a candidate."""
    matched = ", ".join(matched_keywords) if matched_keywords else "No strong keyword match found"
    missing = ", ".join(missing_keywords) if missing_keywords else "No major gaps identified"
    reason = decision_reason or "No extra notes available."
    return (
        f"Candidate: {candidate_name}\n"
        f"Overall Score: {score}/100\n"
        f"Decision: {decision}\n"
        f"Reason: {reason}\n"
        f"Matched Keywords: {matched}\n"
        f"Missing Keywords: {missing}"
    )


def screen_candidates_from_csv(csv_path: str, job_description: str) -> List[Dict[str, object]]:
    """Screen a CSV file of candidate resumes and return scored results."""
    results: List[Dict[str, object]] = []
    csv_file = Path(csv_path)

    with csv_file.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required_fields = {"name", "resume_text"}
        if not reader.fieldnames or not required_fields.issubset(set(reader.fieldnames)):
            raise ValueError("CSV must include 'name' and 'resume_text' columns.")

        for row in reader:
            candidate_name = (row.get("name") or "Unknown Candidate").strip()
            resume_text = row.get("resume_text") or ""
            candidate_result = score_candidate(job_description, resume_text)
            candidate_result["candidate_name"] = candidate_name
            results.append(candidate_result)

    return sorted(results, key=lambda item: float(item["score"]), reverse=True)


def generate_dashboard_html(results: List[Dict[str, object]], title: str = "ATS Recruiter Dashboard") -> str:
    """Build a simple HTML dashboard for recruiter review."""
    summary_cards = []
    decision_counts = {"Shortlist": 0, "Review": 0, "Reject": 0}
    total_score = 0.0

    for entry in results:
        decision = str(entry.get("decision", "Reject"))
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        total_score += float(entry.get("score", 0))

    avg_score = round(total_score / len(results), 2) if results else 0

    for label, value in (
        ("Total Candidates", len(results)),
        ("Average Score", f"{avg_score}/100"),
        ("Shortlist", decision_counts.get("Shortlist", 0)),
        ("Review", decision_counts.get("Review", 0)),
        ("Reject", decision_counts.get("Reject", 0)),
    ):
        summary_cards.append(
            "<div class='card'><h3>{}</h3><p>{}</p></div>".format(html.escape(str(label)), html.escape(str(value)))
        )

    rows = []
    for entry in results:
        name = html.escape(str(entry.get("candidate_name", "Unknown Candidate")))
        score = html.escape(str(entry.get("score", 0)))
        decision = html.escape(str(entry.get("decision", "Reject")))
        reason = html.escape(str(entry.get("decision_reason", "No summary available.")))
        matched = ", ".join(str(item) for item in entry.get("matched_keywords", []))
        missing = ", ".join(str(item) for item in entry.get("missing_keywords", [])) or "None"
        experience = html.escape(str(entry.get("experience_years", 0)))
        rows.append(
            "<tr>"
            f"<td>{name}</td><td>{score}</td><td>{decision}</td><td>{html.escape(matched)}</td>"
            f"<td>{html.escape(missing)}</td><td>{experience}</td><td>{reason}</td>"
            "</tr>"
        )

    table_rows = "\n".join(rows) if rows else "<tr><td colspan='7'>No candidates available</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>{html.escape(title)}</title>
      <style>
        body {{ font-family: Arial, sans-serif; background: #f5f7fb; margin: 0; padding: 24px; color: #1f2937; }}
        h1 {{ margin-bottom: 20px; }}
        .cards {{ display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 24px; }}
        .card {{ background: white; border-radius: 10px; box-shadow: 0 2px 8px rgba(0,0,0,0.05); padding: 16px 20px; min-width: 140px; }}
        .card h3 {{ margin: 0 0 8px; font-size: 14px; color: #52607a; text-transform: uppercase; }}
        .card p {{ margin: 0; font-size: 22px; font-weight: 700; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.05); }}
        th, td {{ padding: 12px 14px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
        th {{ background: #eef2ff; }}
      </style>
    </head>
    <body>
      <h1>{html.escape(title)}</h1>
      <div class="cards">
        {''.join(summary_cards)}
      </div>
      <table>
        <thead>
          <tr>
            <th>Candidate</th>
            <th>Score</th>
            <th>Decision</th>
            <th>Matched Keywords</th>
            <th>Missing Keywords</th>
            <th>Years Exp.</th>
            <th>Reason</th>
          </tr>
        </thead>
        <tbody>
          {table_rows}
        </tbody>
      </table>
    </body>
    </html>
    """


if __name__ == "__main__":
    sample_jd = (
        "Senior Business Analyst with experience in stakeholder management, SQL, Agile, "
        "requirements gathering, reporting, and 5+ years experience."
    )
    sample_resume = (
        "Senior Business Analyst with 6 years experience. Stakeholder management, "
        "requirements gathering, report generation, SQL, Agile delivery."
    )
    result = score_candidate(sample_jd, sample_resume)
    print(result)
