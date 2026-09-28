import argparse
from pathlib import Path

from ats_resume_screening import (
    generate_dashboard_html,
    score_candidate,
    screen_candidates_from_csv,
    summarize_result,
)


def run_single_candidate(job_description: str, resume_text: str) -> None:
    result = score_candidate(job_description, resume_text)
    summary = summarize_result(
        candidate_name="Candidate",
        score=int(result["score"]),
        decision=result["decision"],
        matched_keywords=result["matched_keywords"],
        missing_keywords=result["missing_keywords"],
    )
    print(summary)
    print("\nDetailed result:")
    print(result)


def run_batch_screen(job_description: str, csv_path: str, dashboard_path: str | None = None) -> None:
    results = screen_candidates_from_csv(csv_path=csv_path, job_description=job_description)
    for item in results:
        summary = summarize_result(
            candidate_name=str(item["candidate_name"]),
            score=int(item["score"]),
            decision=str(item["decision"]),
            matched_keywords=item["matched_keywords"],
            missing_keywords=item["missing_keywords"],
        )
        print(f"\n--- {item['candidate_name']} ---")
        print(summary)

    if dashboard_path:
        dashboard_html = generate_dashboard_html(results, title="Recruiter Dashboard")
        out = Path(dashboard_path)
        out.write_text(dashboard_html, encoding="utf-8")
        print(f"\nDashboard saved to: {out.resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ATS resume screening for HR teams.")
    parser.add_argument("--job", dest="job_description", help="Job description text.")
    parser.add_argument("--resume", dest="resume_text", help="Single resume text to evaluate.")
    parser.add_argument("--csv", dest="csv_path", help="CSV file with 'name' and 'resume_text' columns.")
    parser.add_argument("--dashboard", dest="dashboard_path", help="Optional path to write recruiter dashboard HTML.")
    args = parser.parse_args()

    if args.csv_path:
        if not args.job_description:
            raise SystemExit("--job is required when using --csv.")
        run_batch_screen(args.job_description, args.csv_path, args.dashboard_path)
        return

    if args.job_description and args.resume_text:
        run_single_candidate(args.job_description, args.resume_text)
        return

    parser.print_help()
    raise SystemExit(1)


if __name__ == "__main__":
    main()
