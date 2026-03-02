import os
import argparse
import pandas as pd

from text_parser import process_json
from semantic_scoring import add_relevance_and_coherence_scores
from fuzzy_score import (
    generate_crisp_scores,
    round_scores,
    calculate_total_marks,
    convert_to_100,
    assign_grades,
    calculate_confidence,
)


def collect_parsed_rows(json_dir: str) -> pd.DataFrame:
    if not os.path.exists(json_dir):
        raise RuntimeError(f"JSON directory does not exist: {json_dir}")

    rows = []
    found_any_json = False
    for fname in os.listdir(json_dir):
        if not fname.lower().endswith(".json"):
            continue
        
        found_any_json = True
        # Skip model answers file if present in same directory
        if fname.lower() in {"model_answer.json", "model_answers.json"}:
            continue

        fpath = os.path.join(json_dir, fname)
        try:
            items = process_json(fpath)
            # Basic shape validation: expect dict-like entries with keys
            valid_items = [
                it for it in items
                if isinstance(it, dict)
                and {"StudentID", "Question Number", "Answer"}.issubset(it.keys())
            ]
            if not valid_items:
                print(f"⚠️  Warning: {fname} contained no valid Question/Answer entries (ensure structured answers were extracted from the PDF).")
                continue
            rows.extend(valid_items)
            print(f"✅ Parsed {len(valid_items)} rows from {fname}")
        except Exception as exc:
            print(f"❌ Error processing {fname}: {exc}")

    if not found_any_json:
        raise RuntimeError(f"No .json files found in {json_dir}. Ensure you have run ocr_extraction.py first.")

    if not rows:
        raise RuntimeError(
            f"No parsed question/answer rows collected from {json_dir}. "
            "Files were found but extraction may have failed due to unclear OCR output. "
            "Ensure the JSON files have 'student_id' and 'answers' keys."
        )
    return pd.DataFrame(rows)


def _print_console_summary(confident_excel: str, semantic_excel: str):
    # Compute similarity percent per student from semantic stage
    df_sem = pd.read_excel(semantic_excel)
    df_sem["Final Similarity Score"] = pd.to_numeric(df_sem.get("Final Similarity Score"), errors="coerce")
    sim_series = (df_sem.groupby("StudentID")["Final Similarity Score"].mean() * 100).round(2)

    # Build per-student summary (StudentID + Avg Similarity % only)
    summaries = []
    for student_id, sim_pct in sim_series.dropna().items():
        summaries.append({
            "StudentID": student_id,
            "avg_similarity_percent": float(sim_pct),
        })

    # Print a simple table
    headers = ["StudentID", "Avg Similarity %"]
    print("\n=== Summary ===")
    print(f"{headers[0]:<12} {headers[1]:>18}")
    for s in summaries:
        print(f"{str(s['StudentID']):<12} {str(s['avg_similarity_percent']):>18}")

    # Also print the raw list of dicts for programmatic consumption
    print("\nSummaries as dictionaries:")
    print(summaries)


def main():
    parser = argparse.ArgumentParser(description="Run digitization scoring pipeline")
    parser.add_argument("json_dir", help="Directory containing student JSON files (from OCR step)")
    parser.add_argument("model_answer_json", help="Path to model_answer.json")
    parser.add_argument("--out_dir", default="outputs", help="Output directory for Excel artifacts")
    parser.add_argument("--print_summary", action="store_true", help="Print per-student summary and dictionaries to console")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    # 1) Parse JSON → Excel
    df_parsed = collect_parsed_rows(args.json_dir)
    parsed_excel = os.path.join(args.out_dir, "01_parsed.xlsx")
    df_parsed.to_excel(parsed_excel, index=False)
    print(f"Saved parsed QA rows → {parsed_excel}")

    # 2) Add semantic relevance & coherence
    semantic_excel = os.path.join(args.out_dir, "02_semantic.xlsx")
    add_relevance_and_coherence_scores(parsed_excel, args.model_answer_json, semantic_excel)

    # 3) Fuzzy grading pipeline
    crisp_excel = os.path.join(args.out_dir, "03_crisp.xlsx")
    rounded_excel = os.path.join(args.out_dir, "04_rounded.xlsx")
    total50_excel = os.path.join(args.out_dir, "05_total50.xlsx")
    total100_excel = os.path.join(args.out_dir, "06_total100.xlsx")
    graded_excel = os.path.join(args.out_dir, "07_graded.xlsx")
    confident_excel = os.path.join(args.out_dir, "08_confidence.xlsx")

    generate_crisp_scores(semantic_excel, crisp_excel)
    round_scores(crisp_excel, rounded_excel)
    calculate_total_marks(rounded_excel, total50_excel)
    convert_to_100(total50_excel, total100_excel)
    assign_grades(total100_excel, graded_excel)
    calculate_confidence(graded_excel, confident_excel)

    if args.print_summary:
        _print_console_summary(confident_excel, semantic_excel)

    print("Pipeline completed.")
    print(f"Final output files written under: {args.out_dir}")


if __name__ == "__main__":
    main()


