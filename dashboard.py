import streamlit as st
import pandas as pd
import plotly.express as px
import os
import json
import shutil
from ocr_extraction import save_model_answer, process_batch
from main import collect_parsed_rows
from semantic_scoring import add_relevance_and_coherence_scores
from fuzzy_score import (
    generate_crisp_scores,
    round_scores,
    calculate_total_marks,
    convert_to_100,
    assign_grades,
    calculate_confidence,
)
from security import license_sidebar

# Page configuration
st.set_page_config(
    page_title="Subjective Answer Evaluator Dashboard",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for a premium look
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .stTable {
        background-color: #ffffff;
        border-radius: 10px;
    }
    h1, h2, h3 {
        color: #1e3a8a;
        font-family: 'Inter', sans-serif;
    }
</style>
""", unsafe_allow_html=True)

# Helper function to find latest output files
def get_latest_outputs(base_dir="outputs"):
    files = {
        "Summary": os.path.join(base_dir, "08_confidence.xlsx"),
        "Detailed": os.path.join(base_dir, "02_semantic.xlsx"),
        "Confidence": os.path.join(base_dir, "08_confidence.xlsx")
    }
    found_files = {k: v for k, v in files.items() if os.path.exists(v)}
    return found_files

# Sidebar License Check
license_sidebar()

# Main Header
st.title("🎓 Online Subjective Answer Evaluator")

# Tabs for Teacher Workflow and Dashboard
tab1, tab2 = st.tabs(["📝 New Evaluation", "📊 Analysis Dashboard"])

with tab1:
    st.header("Upload Materials")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("1. Model Answer Sheet")
        model_file = st.file_uploader("Upload Model Answer Sheet (PDF)", type=["pdf"], key="model")
    
    with col2:
        st.subheader("2. Student Answer Sheets")
        student_files = st.file_uploader("Upload Student Answers (PDFs)", type=["pdf"], accept_multiple_files=True, key="students")

    if st.button("🚀 Start Evaluation Pipeline", use_container_width=True):
        if not st.session_state.get("is_licensed"):
            st.warning("⚠️ Access Restricted: Please activate a valid license key in the sidebar to process evaluations.")
        elif model_file and student_files:
            with st.status("Processing... 🛠️", expanded=True) as status:
                st.write("📁 Setting up directories...")
                temp_pdf_dir = "data/temp_pdf"
                temp_json_dir = "data/temp_json"
                os.makedirs(temp_pdf_dir, exist_ok=True)
                os.makedirs(temp_json_dir, exist_ok=True)
                
                # Save Model Answer
                model_pdf_path = os.path.join(temp_pdf_dir, "model_answer.pdf")
                with open(model_pdf_path, "wb") as f:
                    f.write(model_file.getbuffer())
                
                # Save Student Answers
                for sf in student_files:
                    with open(os.path.join(temp_pdf_dir, sf.name), "wb") as f:
                        f.write(sf.getbuffer())

                st.write("🔍 Running OCR on Model Answer...")
                model_json_path = "data/model_answer.json"
                save_model_answer(model_pdf_path, model_json_path)

                st.write("🔍 Running OCR on Student Answers...")
                # Remove model_answer.pdf from the student batch to avoid double processing
                # Actually, we should just move students to a separate subfolder
                student_pdf_dir = os.path.join(temp_pdf_dir, "students")
                os.makedirs(student_pdf_dir, exist_ok=True)
                for sf in student_files:
                    shutil.move(os.path.join(temp_pdf_dir, sf.name), os.path.join(student_pdf_dir, sf.name))
                
                process_batch(student_pdf_dir, temp_json_dir)

                st.write("🧠 Evaluating Semantic Relevance...")
                out_dir = "outputs"
                os.makedirs(out_dir, exist_ok=True)
                
                df_parsed = collect_parsed_rows(temp_json_dir)
                parsed_excel = os.path.join(out_dir, "01_parsed.xlsx")
                df_parsed.to_excel(parsed_excel, index=False)
                
                semantic_excel = os.path.join(out_dir, "02_semantic.xlsx")
                add_relevance_and_coherence_scores(parsed_excel, model_json_path, semantic_excel)

                st.write("⚖️ Applying Fuzzy Logic Grading...")
                # Pipeline steps
                crisp_excel = os.path.join(out_dir, "03_crisp.xlsx")
                rounded_excel = os.path.join(out_dir, "04_rounded.xlsx")
                total50_excel = os.path.join(out_dir, "05_total50.xlsx")
                total100_excel = os.path.join(out_dir, "06_total100.xlsx")
                graded_excel = os.path.join(out_dir, "07_graded.xlsx")
                confident_excel = os.path.join(out_dir, "08_confidence.xlsx")

                generate_crisp_scores(semantic_excel, crisp_excel)
                round_scores(crisp_excel, rounded_excel)
                calculate_total_marks(rounded_excel, total50_excel)
                convert_to_100(total50_excel, total100_excel)
                assign_grades(total100_excel, graded_excel)
                calculate_confidence(graded_excel, confident_excel)

                status.update(label="✅ Evaluation Complete!", state="complete", expanded=False)
            
            st.success("🎉 All documents processed successfully!")
            
            # Show Detailed Table right away
            st.divider()
            st.subheader("📋 Evaluation Results (Per Student Summary)")
            df_res = pd.read_excel(confident_excel)
            
            # Create a simple summary by dropping duplicates of StudentID
            # (since graded_excel has one row per question but calculates total marks)
            df_summary_view = df_res[["StudentID", "Grade", "Total_Marks_50", "Total_Marks_100", "Confidence Score"]].drop_duplicates()
            st.dataframe(df_summary_view, use_container_width=True, hide_index=True)
            
            st.subheader("📝 Detailed Question-wise Scores")
            # Pivot to show Question Number as columns
            try:
                df_pivot = df_res.pivot(index="StudentID", columns="Question Number", values="Final Score")
                st.dataframe(df_pivot, use_container_width=True)
            except Exception as e:
                st.warning(f"Could not generate detailed score table: {e}")
                st.dataframe(df_res[["StudentID", "Question Number", "Final Score"]], use_container_width=True)
            
        else:
            st.error("❌ Please upload both a Model Answer Sheet and at least one Student Answer Sheet.")

with tab2:
    output_dir = "outputs"
    outputs = get_latest_outputs(output_dir)
    
    if not outputs:
        st.info("👋 No evaluation data found. Use the 'New Evaluation' tab to get started.")
    elif not st.session_state.get("is_licensed"):
        st.warning("🔒 Dashboard Locked: Please activate your license to view the full analysis.")
    else:
        # Load data
        df_full_summary = pd.read_excel(outputs["Summary"])
        df_detailed = pd.read_excel(outputs["Detailed"])
        
        # Deduplicate to get student-level metrics
        df_summary = df_full_summary.drop_duplicates("StudentID")
        
        # Overview Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Students", len(df_summary))
        with col2:
            avg_score = df_summary["Total_Marks_100"].mean()
            st.metric("Avg Score (100)", f"{avg_score:.2f}")
        with col3:
            pass_rate = (df_summary["Grade"] != "F").mean() * 100
            st.metric("Pass Rate", f"{pass_rate:.1f}%")
        with col4:
            avg_sim = df_detailed["Final Similarity Score"].mean() * 100
            st.metric("Avg Similarity", f"{avg_sim:.1f}%")

        st.divider()

        # Visualizations row
        c1, c2 = st.columns(2)
        
        with c1:
            st.subheader("📝 Grade Distribution")
            grade_order = ['O', 'A+', 'A', 'B+', 'B', 'C', 'P', 'F']
            fig_grade = px.histogram(
                df_summary, 
                x="Grade", 
                category_orders={"Grade": grade_order},
                color="Grade",
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            st.plotly_chart(fig_grade, use_container_width=True)

        with c2:
            st.subheader("📈 Score Ranges")
            fig_scores = px.box(
                df_summary, 
                y="Total_Marks_100", 
                points="all", 
                labels={"Total_Marks_100": "Score / 100"},
                color_discrete_sequence=['#1e3a8a']
            )
            st.plotly_chart(fig_scores, use_container_width=True)

        st.divider()

        # Detailed Table
        st.subheader("👩‍🎓 Student Performance Table")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

        # Student Drill-down
        st.divider()
        st.subheader("🔍 Individual Student Drill-down")
        student_ids = df_summary["StudentID"].unique()
        selected_student = st.selectbox("Select Student ID", student_ids)
        
        student_data = df_detailed[df_detailed["StudentID"] == selected_student]
        
        sc1, sc2 = st.columns([1, 2])
        with sc1:
            student_summary = df_summary[df_summary["StudentID"] == selected_student].iloc[0]
            st.write(f"**Overall Grade:** {student_summary['Grade']}")
            st.write(f"**Total Marks (50):** {student_summary['Total_Marks_50']}")
            st.write(f"**Total Marks (100):** {student_summary['Total_Marks_100']}")
        
        with sc2:
            fig_student = px.bar(
                student_data, 
                x="Question Number", 
                y="Final Similarity Score",
                title=f"Similarity per Question for {selected_student}",
                labels={"Final Similarity Score": "Hybrid Score (0-1)"},
                range_y=[0, 1]
            )
            st.plotly_chart(fig_student, use_container_width=True)
        
        st.write("**Detailed Answer Breakdown:**")
        st.dataframe(
            student_data[["Question Number", "Answer", "Final Similarity Score"]], 
            use_container_width=True, 
            hide_index=True
        )
