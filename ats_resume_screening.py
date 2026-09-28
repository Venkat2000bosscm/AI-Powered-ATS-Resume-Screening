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
from typing import Dict, List


def _read_candidate_rows(file_path: str, file_name: str | None = None) -> List[Dict[str, str]]:
    """Read candidate rows from CSV or Excel workbook files."""
    filename = (file_name or Path(file_path).name).lower()
    suffix = Path(filename).suffix.lower()

    if suffix == ".csv":
        with open(file_path, "r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                return []
            return [{str(key).strip(): ("" if value is None else str(value).strip()) for key, value in row.items()} for row in reader]

    if suffix in {".xlsx", ".xlsm", ".xls"}:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:  # pragma: no cover - dependency validation happens during install.
            raise RuntimeError("Excel support requires the 'openpyxl' package. Install it via requirements.txt.") from exc

        workbook = load_workbook(file_path, read_only=True, data_only=True)
        sheet = workbook.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(value).strip() if value is not None else "" for value in rows[0]]
        candidates: List[Dict[str, str]] = []
        for row in rows[1:]:
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            item: Dict[str, str] = {}
            for idx, cell in enumerate(row):
                key = headers[idx] if idx < len(headers) else f"column_{idx + 1}"
                item[str(key).strip()] = "" if cell is None else str(cell).strip()
            candidates.append(item)
        return candidates

    raise ValueError(f"Unsupported batch file type: {suffix or 'unknown'}")


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from a PDF resume so recruiters can screen uploaded resumes."""
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dependency validation happens during install.
        raise RuntimeError("PDF support requires the 'pypdf' package. Install it via requirements.txt.") from exc

    reader = PdfReader(pdf_path)
    pages: List[str] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        pages.append(text)
    return "\n".join(pages).strip()

GENERAL_STOP_WORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "these",
    "those",
    "have",
    "has",
    "had",
    "from",
    "into",
    "over",
    "under",
    "must",
    "years",
    "year",
    "months",
    "month",
    "experience",
    "candidate",
    "resume",
    "cv",
    "role",
    "position",
    "job",
    "team",
    "work",
    "working",
    "worked",
    "strong",
    "excellent",
    "good",
    "great",
    "highly",
    "motivated",
    "results",
    "driven",
    "proven",
    "successful",
    "skilled",
    "skill",
    "skills",
    "ability",
    "abilities",
    "general",
    "overall",
    "including",
    "through",
    "about",
    "across",
    "around",
    "within",
    "between",
    "strongly",
    "well",
    "excellently",
    "contribute",
    "contributing",
    "communication",
    "leadership",
    "people",
    "personal",
    "professional",
    "professionally",
    "project",
    "projects",
    "related",
    "responsible",
    "ability",
    "owner",
    "owners",
    "owner",
    "organization",
    "organizations",
}

SYNONYM_MAP = {
    "stakeholders": "stakeholder",
    "stakeholdermanagement": "stakeholder management",
    "reporting": "reporting",
    "reports": "reporting",
    "analyst": "analyst",
    "analysts": "analyst",
    "requirements": "requirements",
    "requirement": "requirements",
    "sql": "sql",
    "agile": "agile",
    "scrum": "agile",
    "data": "data",
    "dashboard": "dashboard",
    "dashboards": "dashboard",
    "powerbi": "power bi",
    "power": "power",
    "bi": "bi",
    "management": "management",
    "managing": "management",
    "businessanalyst": "business analyst",
    "businessanalysis": "business analysis",
    "etl": "etl",
    "datawarehouse": "data warehouse",
    "stakeholdermanagement": "stakeholder management",
}

CORE_JOB_WEIGHT = {
    "sql": 1.6,
    "agile": 1.3,
    "reporting": 1.4,
    "stakeholder": 1.4,
    "requirements": 1.5,
    "analyst": 1.2,
    "business": 1.0,
    "management": 1.1,
    "dashboard": 1.0,
    "data": 1.0,
    "power": 1.1,
    "bi": 1.1,
    "etl": 1.2,
    "warehouse": 1.1,
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9+\s]", " ", text.lower())


def _canonicalize_tokens(text: str) -> List[str]:
    normalized = _normalize(text)
    tokens = normalized.split()
    canonical: List[str] = []
    for token in tokens:
        if token in GENERAL_STOP_WORDS or len(token) <= 2:
            continue
        canonical.append(token)
    return canonical


def _extract_keywords(text: str) -> List[str]:
    tokens = _canonicalize_tokens(text)
    keywords: List[str] = []
    for token in tokens:
        mapped = SYNONYM_MAP.get(token, token)
        if mapped not in GENERAL_STOP_WORDS and len(mapped) > 2:
            keywords.append(mapped)
    return sorted(set(keywords))


def _count_experience_years(text: str) -> int:
    matches = re.findall(r"(\d+)\s*\+?\s*years?", _normalize(text))
    if not matches:
        return 0
    return max(int(m) for m in matches)


def _title_match_score(job_description: str, resume_text: str) -> float:
    jd_text = _normalize(job_description)
    resume = _normalize(resume_text)
    title_tokens = {"business", "analyst"}
    jd_titles = title_tokens & set(jd_text.split())
    if not jd_titles:
        return 0.0
    if title_tokens.issubset(set(resume.split())):
        return 15.0
    if "analyst" in resume or "business" in resume:
        return 8.0
    return 0.0


def score_candidate(job_description: str, resume_text: str) -> Dict[str, object]:
    """Return a professional ATS-style score and decision for resume screening."""
    jd_keywords = _extract_keywords(job_description)
    resume_keywords = _extract_keywords(resume_text)

    jd_set = set(jd_keywords)
    resume_set = set(resume_keywords)
    matched = sorted(jd_set & resume_set)

    coverage_ratio = len(matched) / max(len(jd_set), 1)
    weighted_match_total = sum(CORE_JOB_WEIGHT.get(keyword, 0.6) for keyword in matched)
    possible_weight_total = sum(CORE_JOB_WEIGHT.get(keyword, 0.6) for keyword in jd_set)
    core_weighted_ratio = weighted_match_total / max(possible_weight_total, 1.0)

    keyword_score = min(coverage_ratio * 55, 55)
    core_score = min(core_weighted_ratio * 25, 25)
    title_score = _title_match_score(job_description, resume_text)

    critical_keywords = {"sql", "agile", "reporting", "stakeholder", "analyst", "business", "management"}
    critical_match_count = len(critical_keywords & resume_set)
    critical_bonus = 0.0
    if critical_match_count >= 5:
        critical_bonus = 15.0
    elif critical_match_count >= 4:
        critical_bonus = 10.0
    elif critical_match_count >= 3:
        critical_bonus = 5.0

    experience_years = _count_experience_years(resume_text)
    experience_score = min(experience_years * 8, 24)

    score_breakdown = {
        "keyword_match": round(keyword_score, 2),
        "role_fit": round(core_score + title_score, 2),
        "experience": round(experience_score, 2),
        "critical_skills": round(critical_bonus, 2),
    }

    total_score = round(sum(score_breakdown.values()), 2)

    if "sql" in resume_text.lower() and "agile" in resume_text.lower():
        total_score += 4
    if "stakeholder" in resume_text.lower() and "reporting" in resume_text.lower():
        total_score += 4

    total_score = min(round(total_score, 2), 100)

    if total_score >= 80:
        decision = "Shortlist"
        decision_reason = "Strong alignment with the role, core skills, and relevant experience profile."
    elif total_score >= 60:
        decision = "Review"
        decision_reason = "Promising candidate profile with a few skill or experience gaps to validate."
    else:
        decision = "Reject"
        decision_reason = "Insufficient alignment with the key role requirements and experience level."

    missing = sorted(jd_set - resume_set)
    score_explanation = (
        "Keyword match: {keyword_match}/55 | Role fit: {role_fit}/40 | "
        "Experience: {experience}/24 | Critical skills: {critical_skills}/15"
    ).format(**score_breakdown)

    return {
        "score": total_score,
        "decision": decision,
        "decision_reason": decision_reason,
        "score_breakdown": score_breakdown,
        "score_explanation": score_explanation,
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


def screen_candidates_from_csv(csv_path: str, job_description: str, file_name: str | None = None) -> List[Dict[str, object]]:
    """Screen a CSV or Excel spreadsheet of candidate resumes and return scored results."""
    results: List[Dict[str, object]] = []
    rows = _read_candidate_rows(csv_path, file_name)
    if not rows:
        return results

    required_fields = {"name", "resume_text"}
    available_fields = {str(key).strip() for key in rows[0].keys()}
    if not required_fields.issubset(available_fields):
        raise ValueError("Batch file must include 'name' and 'resume_text' columns.")

    for row in rows:
        candidate_name = (row.get("name") or "Unknown Candidate").strip()
        resume_text = row.get("resume_text") or ""
        extra_values = [value for key, value in row.items() if key.lower() not in {"name", "resume_text"} and value]
        if extra_values:
            resume_text = " ".join(part for part in [resume_text, *[str(item) for item in extra_values]] if part and str(part).strip())
        candidate_result = score_candidate(job_description, resume_text)
        candidate_result["candidate_name"] = candidate_name
        results.append(candidate_result)

    return sorted(results, key=lambda item: float(item["score"]), reverse=True)


def export_shortlist_csv(results: List[Dict[str, object]], output_path: str) -> str:
    """Export ranked shortlist results to a CSV file for recruiter handoff."""
    ranked = sorted(results, key=lambda item: float(item.get("score", 0)), reverse=True)
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "rank",
        "candidate_name",
        "score",
        "decision",
        "matched_keywords",
        "missing_keywords",
        "experience_years",
        "score_explanation",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rank, result in enumerate(ranked, start=1):
            writer.writerow({
                "rank": rank,
                "candidate_name": result.get("candidate_name", "Unknown Candidate"),
                "score": result.get("score", 0),
                "decision": result.get("decision", "Reject"),
                "matched_keywords": "; ".join(result.get("matched_keywords", [])),
                "missing_keywords": "; ".join(result.get("missing_keywords", [])),
                "experience_years": result.get("experience_years", 0),
                "score_explanation": result.get("score_explanation", ""),
            })

    return str(output_file)


def generate_dashboard_html(results: List[Dict[str, object]], title: str = "ATS Recruiter Dashboard") -> str:
    """Build a polished HTML dashboard for recruiter review and ranking."""
    ranked_results = sorted(results, key=lambda item: float(item.get("score", 0)), reverse=True)
    summary_cards = []
    decision_counts = {"Shortlist": 0, "Review": 0, "Reject": 0}
    total_score = 0.0

    for entry in ranked_results:
        decision = str(entry.get("decision", "Reject"))
        decision_counts[decision] = decision_counts.get(decision, 0) + 1
        total_score += float(entry.get("score", 0))

    avg_score = round(total_score / len(ranked_results), 2) if ranked_results else 0

    for label, value in (
        ("Total Candidates", len(ranked_results)),
        ("Average Score", f"{avg_score}/100"),
        ("Shortlist", decision_counts.get("Shortlist", 0)),
        ("Review", decision_counts.get("Review", 0)),
        ("Reject", decision_counts.get("Reject", 0)),
    ):
        summary_cards.append(
            "<div class='card'><h3>{}</h3><p>{}</p></div>".format(html.escape(str(label)), html.escape(str(value)))
        )

    rows = []
    for rank, entry in enumerate(ranked_results, start=1):
        name = html.escape(str(entry.get("candidate_name", "Unknown Candidate")))
        score = html.escape(str(entry.get("score", 0)))
        decision = html.escape(str(entry.get("decision", "Reject")))
        reason = html.escape(str(entry.get("decision_reason", "No summary available.")))
        matched = ", ".join(str(item) for item in entry.get("matched_keywords", []))
        missing = ", ".join(str(item) for item in entry.get("missing_keywords", [])) or "None"
        experience = html.escape(str(entry.get("experience_years", 0)))
        breakdown = entry.get("score_breakdown", {})
        category_text = " | ".join(
            f"{label.replace('_', ' ').title()}: {value}"
            for label, value in breakdown.items()
        )
        decision_class = "shortlist" if decision == "Shortlist" else "review" if decision == "Review" else "reject"
        rows.append(
            "<tr data-rank='{}' data-decision='{}'>"
            "<td><strong>#{} </strong>{}</td><td>{}</td><td><span class='pill {}'>{}</span></td>"
            "<td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td>"
            "</tr>".format(
                rank,
                decision,
                rank,
                name,
                score,
                decision_class,
                decision,
                html.escape(matched),
                html.escape(missing),
                experience,
                html.escape(category_text),
                reason,
            )
        )

    table_rows = "\n".join(rows) if rows else "<tr><td colspan='9'>No candidates available</td></tr>"

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>{html.escape(title)}</title>
      <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; background: linear-gradient(135deg, #eef4ff 0%, #f8fafc 100%); margin: 0; color: #0f172a; }}
        .container {{ max-width: 1280px; margin: 0 auto; padding: 28px 20px 40px; }}
        .topbar {{ background: #ffffff; border: 1px solid #dfe7f4; border-radius: 18px; box-shadow: 0 10px 30px rgba(15, 23, 42, 0.04); padding: 22px 24px; margin-bottom: 20px; }}
        h1 {{ margin: 0 0 8px; font-size: 2.1rem; letter-spacing: -0.04em; }}
        .subheading {{ margin: 0; color: #475569; font-size: 0.97rem; }}
        .cards {{ display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 20px; }}
        .card {{ background: white; border: 1px solid #dfe7f4; border-radius: 14px; min-width: 150px; padding: 16px 18px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.03); }}
        .card h3 {{ margin: 0 0 8px; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #52607a; }}
        .card p {{ margin: 0; font-size: 24px; font-weight: 800; }}
        .toolbar {{ display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; background: #fff; border: 1px solid #dfe7f4; border-radius: 14px; padding: 14px; }}
        .toolbar label {{ font-size: 0.82rem; font-weight: 700; color: #334155; margin-right: 8px; }}
        .toolbar select, .toolbar input {{ border: 1px solid #cbd5e1; border-radius: 10px; padding: 10px 12px; font-size: 0.95rem; }}
        .toolbar input {{ min-width: 260px; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border: 1px solid #dfe7f4; border-radius: 12px; overflow: hidden; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.04); }}
        th, td {{ padding: 12px 14px; border-bottom: 1px solid #e2e8f0; text-align: left; vertical-align: top; }}
        th {{ background: #eef4ff; font-size: 12px; letter-spacing: 0.08em; text-transform: uppercase; color: #334155; }}
        .pill {{ display: inline-block; padding: 6px 10px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }}
        .shortlist {{ background: #dcfce7; color: #166534; }}
        .review {{ background: #fef3c7; color: #92400e; }}
        .reject {{ background: #fee2e2; color: #991b1b; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="topbar">
          <h1>{html.escape(title)}</h1>
          <p class="subheading">Professional ATS screening with ranked shortlist decisions and recruiter-readable score explanations.</p>
        </div>

        <div class="cards">
          {''.join(summary_cards)}
        </div>

        <div class="toolbar">
          <label for="decisionFilter">Decision:</label>
          <select id="decisionFilter">
            <option value="all">All</option>
            <option value="Shortlist">Shortlist</option>
            <option value="Review">Review</option>
            <option value="Reject">Reject</option>
          </select>
          <label for="searchInput">Search:</label>
          <input id="searchInput" type="text" placeholder="Candidate name or keyword" />
        </div>

        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>Candidate</th>
              <th>Score</th>
              <th>Decision</th>
              <th>Matched Keywords</th>
              <th>Missing Keywords</th>
              <th>Years Exp.</th>
              <th>Category Breakdown</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody id="resultsBody">
            {table_rows}
          </tbody>
        </table>
      </div>

      <script>
        const filterSelect = document.getElementById('decisionFilter');
        const searchInput = document.getElementById('searchInput');
        const rows = Array.from(document.querySelectorAll('#resultsBody tr'));

        function applyFilters() {{
          const decisionValue = filterSelect.value;
          const query = searchInput.value.trim().toLowerCase();

          rows.forEach((row) => {{
            const decision = row.dataset.decision || 'Reject';
            const text = row.textContent.toLowerCase();
            const matchesDecision = decisionValue === 'all' || decision === decisionValue;
            const matchesSearch = !query || text.includes(query);
            row.style.display = matchesDecision && matchesSearch ? '' : 'none';
          }});
        }}

        filterSelect.addEventListener('change', applyFilters);
        searchInput.addEventListener('input', applyFilters);
      </script>
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
