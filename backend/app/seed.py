"""
Seeds the 8 PostgreSQL/SQLite tables and Vector Store with:
- Team-20 & Supervisor user accounts (Student, Faculty, Admin)
- 5 Official NIIT University Documents (PDF, DOCX, TXT)
- Realistic historical queries, cited responses, and feedback for the Admin Analytics Dashboard
"""
from pathlib import Path
from datetime import datetime, timedelta, timezone

from app.database import init_db, get_db_connection
from app.services.auth_service import hash_password
from app.services.ingestion_service import DocumentIngestionService, STORAGE_DIR
from app.services.chat_orchestrator import ChatOrchestratorService
from app.services.analytics_service import AnalyticsFeedbackService

def seed_all(db_path=None, vstore=None) -> None:
    init_db(db_path)
    conn = get_db_connection(db_path)
    try:
        user_cnt = conn.execute("SELECT COUNT(*) as cnt FROM Users").fetchone()["cnt"]
        if user_cnt > 0:
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        users_to_seed = [
            ("vijay.reddy23@st.niituniversity.in", "Yammanuru Vijay Vardhan Reddy (BT23GCS245)", "STUDENT", "LOCAL", hash_password("student123"), "CSE (Data Science)"),
            ("bharadwaj.bandi23@st.niituniversity.in", "Bandi Ananthagari Bharadwaj (BT23GCS244)", "STUDENT", "SSO", hash_password("student123"), "CSE"),
            ("jithendar.gottam23@st.niituniversity.in", "Gottam Jithendar Reddy (BT23GCS425)", "STUDENT", "SSO", hash_password("student123"), "CSE"),
            ("saideep.eedara23@st.niituniversity.in", "Eedara Sai Deep (BT23GCS246)", "STUDENT", "SSO", hash_password("student123"), "CSE"),
            ("manish.hurkat@niituniversity.in", "Prof. Manish Hurkat", "FACULTY", "LOCAL", hash_password("faculty123"), "CSE"),
            ("admin@niituniversity.in", "NU Campus Knowledge Admin", "ADMIN", "LOCAL", hash_password("admin123"), "Administration"),
        ]
        for email, name, role, src, pwd, dept in users_to_seed:
            conn.execute(
                """
                INSERT INTO Users (email, full_name, role, auth_source, password_hash, department, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (email, name, role, src, pwd, dept, now)
            )
        conn.commit()
    finally:
        conn.close()

    # Ingest the 5 official NIIT University documents
    docs_meta = [
        ("Academic_Handbook_2026.pdf", 6, "Academics", "Academics"),
        ("Fee_Circular_2026.pdf", 6, "Accounts", "Fees"),
        ("Hostel_Rules_2026.docx", 6, "Student Affairs", "Hostel"),
        ("CSE_Data_Science_Syllabus.txt", 5, "CSE", "Courses"),
        ("Exam_Datesheet_Sem6.txt", 5, "COE", "Exams"),
    ]
    for fname, uploader_id, dept, cat in docs_meta:
        fpath = STORAGE_DIR / fname
        if fpath.exists():
            DocumentIngestionService.ingest_document(
                filename=fname,
                file_bytes=fpath.read_bytes(),
                uploaded_by=uploader_id,
                department=dept,
                category=cat,
                db_path=db_path,
                vstore=vstore
            )

    # Create sample sessions, queries, responses, and feedback across the past 7 days
    conn = get_db_connection(db_path)
    try:
        now_dt = datetime.now(timezone.utc)
        cur = conn.execute(
            """
            INSERT INTO Sessions (user_id, title, started_at, last_activity_at, expires_at, status)
            VALUES (1, 'Fee payment deadline & Hostel rules', ?, ?, ?, 'ACTIVE')
            """,
            (
                now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                now_dt.strftime("%Y-%m-%d %H:%M:%S"),
                (now_dt + timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        sess_id = cur.lastrowid
        conn.commit()
    finally:
        conn.close()

    sample_queries = [
        ("When is the last date to pay the semester fees and what is the late fine?", "UP", "Exact circular deadline and late fine cited clearly."),
        ("What documents are needed for hostel room allotment and what is the curfew time?", "UP", "Very helpful checklist for reporting to the hostel warden."),
        ("What is the minimum attendance requirement at NIIT University and what happens below 75%?", "UP", "Clear explanation of the AW grade policy."),
        ("When are the Mid-Semester exams for Deep Learning (CS3041) and Big Data Analytics?", "UP", "Got the exact October 2026 dates and lecture hall venues."),
        ("How many credits is Capstone Project II under Prof. Manish Hurkat?", "UP", "Accurate CSE curriculum breakdown."),
    ]
    for idx, (q_text, rating, comment) in enumerate(sample_queries):
        res = ChatOrchestratorService.process_query(
            session_id=sess_id,
            user_id=1,
            query_text=q_text,
            db_path=db_path,
            vstore=vstore
        )
        AnalyticsFeedbackService.submit_feedback(
            response_id=res["response_id"],
            user_id=1,
            rating=rating,
            comment=comment,
            db_path=db_path
        )
        # Spread query timestamps over the last 5 days for the line chart
        day_offset = 4 - (idx % 5)
        shifted_ts = (datetime.now(timezone.utc) - timedelta(days=day_offset)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection(db_path)
        conn.execute("UPDATE Queries SET submitted_at = ? WHERE query_id = ?", (shifted_ts, res["query_id"]))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    seed_all()
    print("Database & Vector Store seeded successfully.")
