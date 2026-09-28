from __future__ import annotations

import os
import tempfile
from typing import Any

from flask import Flask, render_template, request

from ats_resume_screening import generate_dashboard_html, screen_candidates_from_csv, score_candidate

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    results: list[dict[str, Any]] = []
    summary_title = "Recruiter Screening Dashboard"
    status_message = "Ready for screening"
    flash_message = ""

    if request.method == "POST":
        job_description = (request.form.get("job_description") or "").strip()
        resume_text = (request.form.get("resume_text") or "").strip()
        csv_file = request.files.get("csv_file")

        if not job_description:
            flash_message = "Please provide a job description before screening candidates."
        elif csv_file and csv_file.filename:
            with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False, encoding="utf-8") as tmp:
                csv_file.save(tmp.name)
                try:
                    results = screen_candidates_from_csv(tmp.name, job_description)
                    status_message = f"Processed {len(results)} candidates from {csv_file.filename}"
                    flash_message = "Batch screening complete."
                finally:
                    os.unlink(tmp.name)
        elif resume_text:
            result = score_candidate(job_description, resume_text)
            result["candidate_name"] = "Single Candidate"
            results = [result]
            status_message = "Single candidate evaluated"
            flash_message = "Resume reviewed successfully."
        else:
            flash_message = "Enter a resume or upload a CSV file to evaluate candidates."

    dashboard_html = generate_dashboard_html(results, title=summary_title)
    return render_template(
        "dashboard.html",
        title=summary_title,
        results=results,
        dashboard_html=dashboard_html,
        status_message=status_message,
        flash_message=flash_message,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
