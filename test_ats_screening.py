from ats_resume_screening import (
    export_shortlist_csv,
    generate_dashboard_html,
    score_candidate,
    screen_candidates_from_csv,
    summarize_result,
)


def test_score_candidate_matches_required_keywords():
    job_description = """
    We are hiring a Senior Business Analyst with experience in stakeholder management,
    SQL, Agile, requirements gathering, and reporting. Must have 5+ years experience.
    """
    resume_text = """
    Senior Business Analyst
    - Stakeholder management
    - Requirements gathering
    - SQL
    - Agile methodologies
    - Reporting
    - 6 years experience in business analysis
    """

    result = score_candidate(job_description, resume_text)

    assert result["score"] >= 70
    assert result["matched_keywords"]
    assert result["decision"] in {"Shortlist", "Review"}
    assert "decision_reason" in result
    assert result["decision_reason"]


def test_general_stop_words_are_excluded_from_keyword_match():
    job_description = "Strong communication and leadership with SQL, Agile, and stakeholder management"
    resume_text = "Strong communication and leadership with SQL, Agile, and stakeholder management"

    result = score_candidate(job_description, resume_text)

    assert "strong" not in result["matched_keywords"]
    assert "sql" in result["matched_keywords"]
    assert result["score"] >= 60


def test_score_candidate_returns_category_breakdown():
    job_description = "Senior Business Analyst with SQL, Agile, reporting, stakeholder management, requirements"
    resume_text = "Business Analyst with SQL, Agile, reporting, stakeholder management, requirements gathering, 6 years experience"

    result = score_candidate(job_description, resume_text)

    assert "score_breakdown" in result
    assert set(result["score_breakdown"]).issuperset({"keyword_match", "role_fit", "experience", "critical_skills"})
    assert result["score_breakdown"]["keyword_match"] > 0
    assert result["score_breakdown"]["role_fit"] > 0


def test_export_shortlist_csv_writes_ranked_candidates(tmp_path):
    export_path = tmp_path / "shortlist.csv"
    results = [
        {"candidate_name": "Alice", "score": 88, "decision": "Shortlist", "matched_keywords": ["SQL", "Agile"], "missing_keywords": []},
        {"candidate_name": "Bob", "score": 72, "decision": "Review", "matched_keywords": ["SQL"], "missing_keywords": ["Stakeholder"]},
    ]

    exported = export_shortlist_csv(results, str(export_path))

    assert exported == str(export_path)
    assert export_path.exists()
    content = export_path.read_text(encoding="utf-8")
    assert "candidate_name" in content
    assert "Alice" in content
    assert "Bob" in content


def test_summarize_result_provides_hr_ready_summary():
    summary = summarize_result(
        candidate_name="Alicia Moore",
        score=82,
        decision="Shortlist",
        matched_keywords=["SQL", "Agile", "Reporting"],
        missing_keywords=["Power BI"],
    )

    assert "Alicia Moore" in summary
    assert "Shortlist" in summary
    assert "SQL" in summary
    assert "Power BI" in summary


def test_screen_candidates_from_csv_returns_scored_rows(tmp_path):
    csv_path = tmp_path / "candidates.csv"
    csv_path.write_text(
        "name,resume_text\n"
        "Alice,Senior Business Analyst with SQL, Agile, and reporting experience\n"
        "Bob,Customer support specialist with no SQL or business analysis\n",
        encoding="utf-8",
    )

    results = screen_candidates_from_csv(
        csv_path=str(csv_path),
        job_description="Senior Business Analyst with SQL, Agile, reporting, and stakeholder management",
    )

    assert len(results) == 2
    assert results[0]["decision"] in {"Shortlist", "Review"}
    assert results[1]["decision"] in {"Shortlist", "Review", "Reject"}


def test_generate_dashboard_html_contains_summary_sections(tmp_path):
    results = [
        {
            "candidate_name": "Alice",
            "score": 92,
            "decision": "Shortlist",
            "matched_keywords": ["SQL", "Agile"],
            "missing_keywords": [],
            "experience_years": 6,
            "decision_reason": "Strong match across core role requirements.",
        },
        {
            "candidate_name": "Bob",
            "score": 45,
            "decision": "Reject",
            "matched_keywords": ["Support"],
            "missing_keywords": ["SQL"],
            "experience_years": 1,
            "decision_reason": "Does not meet several required skills.",
        },
    ]

    html = generate_dashboard_html(results, title="Recruiter Dashboard")

    assert "Recruiter Dashboard" in html
    assert "Alice" in html
    assert "Bob" in html
    assert "Shortlist" in html
    assert "Reject" in html
    assert "Strong match" in html
