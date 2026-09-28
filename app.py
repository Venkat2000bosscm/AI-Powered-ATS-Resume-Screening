from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any

from flask import Flask, render_template, request

from ats_resume_screening import (
    export_shortlist_csv,
    extract_text_from_pdf,
    generate_dashboard_html,
    screen_candidates_from_csv,
    score_candidate,
)

app = Flask(__name__)


@app.route("/", methods=["GET", "POST"])
def index() -> str:
    results: list[dict[str, Any]] = []
    summary_title = "Recruiter Screening Dashboard"
    status_message = "Ready for screening"
    flash_message = ""
    export_path = ""

    if request.method == "POST":
        job_description = (request.form.get("job_description") or "").strip()
        resume_text = (request.form.get("resume_text") or "").strip()
        csv_file = request.files.get("csv_file")
        pdf_file = request.files.get("pdf_file")

        if not job_description:
            flash_message = "Please provide a job description before screening candidates."
        elif csv_file and csv_file.filename:
            uploaded_name = csv_file.filename or "candidates.csv"
            file_suffix = Path(uploaded_name).suffix.lower() or ".csv"
            with tempfile.NamedTemporaryFile("wb", suffix=file_suffix, delete=False) as tmp:
                csv_file.save(tmp.name)
                tmp.flush()
                os.fsync(tmp.fileno())
                temp_path = tmp.name

            try:
                results = screen_candidates_from_csv(temp_path, job_description, file_name=uploaded_name)
                status_message = f"Processed {len(results)} candidates from {csv_file.filename}"
                flash_message = "Batch screening complete."
                export_path = export_shortlist_csv(results, str(Path.cwd() / "shortlist_export.csv"))
            except (RuntimeError, ValueError) as exc:
                results = []
                status_message = "Batch file could not be processed"
                flash_message = str(exc)
            finally:
                with suppress(FileNotFoundError, PermissionError):
                    os.unlink(temp_path)
        elif pdf_file and pdf_file.filename:
            with tempfile.NamedTemporaryFile("wb", suffix=".pdf", delete=False) as tmp:
                pdf_file.save(tmp.name)
                temp_pdf_path = tmp.name

            try:
                resume_text = extract_text_from_pdf(temp_pdf_path)
                result = score_candidate(job_description, resume_text)
                result["candidate_name"] = pdf_file.filename
                results = [result]
                status_message = "PDF resume evaluated successfully"
                flash_message = "PDF resume reviewed successfully."
            finally:
                with suppress(FileNotFoundError, PermissionError):
                    os.unlink(temp_pdf_path)
        elif resume_text:
            result = score_candidate(job_description, resume_text)
            result["candidate_name"] = "Single Candidate"
            results = [result]
            status_message = "Single candidate evaluated"
            flash_message = "Resume reviewed successfully."
        else:
            flash_message = "Enter a resume, upload a PDF, or upload a CSV file to evaluate candidates."

    dashboard_html = generate_dashboard_html(results, title=summary_title)
    return render_template(
        "dashboard.html",
        title=summary_title,
        results=results,
        dashboard_html=dashboard_html,
        status_message=status_message,
        flash_message=flash_message,
        export_path=export_path,
    )


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
