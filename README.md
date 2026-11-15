# Generative AI-Based University Knowledge Assistant
**A Retrieval-Augmented Generation (RAG) Chatbot for Academic & Administrative Queries (Deployed on Kubernetes)**

* **Course:** Capstone Project – II (B.Tech. Computer Science & Engineering — Data Science, NIIT University, Neemrana)
* **Supervisor:** Prof. Manish Hurkat
* **Team-20 Members:**
  * **Bandi Ananthagari Bharadwaj (`BT23GCS244`)** — Project Lead; Backend API & Authentication (JWT, RBAC)
  * **Gottam Jithendar Reddy (`BT23GCS425`)** — RAG Pipeline & LLM Integration (Retrieval, Prompt Design)
  * **Eedara Sai Deep (`BT23GCS246`)** — Frontend (React) — Chat UI, Login Screens, Admin Console UI/UX
  * **Yammanuru Vijay Vardhan Reddy (`BT23GCS245`)** — Database (8-Table Schema) & Document Ingestion; Testing & QA

---

## Quick Start (One-Click Windows Execution)
1. Double-click **`START_NU_ASSISTANT.bat`** (or open `backend/app/index.html` directly in any browser for instant standalone mode).
2. Or run from terminal:
   ```bash
   cd backend
   pip install -r requirements.txt
   python -m unittest discover -s tests -p "test_*.py" -v
   uvicorn app.main:app --reload --port 8000
   ```
3. Visit **`http://127.0.0.1:8000`**.

## Demo Login Credentials (`REQ-AUTH-01` & `REQ-AUTH-02`)
| Role | Email | Password | Permissions (`SRS 5.5` & `SDD 6.2`) |
| :--- | :--- | :--- | :--- |
| **Student** | `vijay.reddy23@st.niituniversity.in` | `student123` | Ask questions, view session chat history, rate answers (Thumbs Up/Down + comment) |
| **Faculty** | `manish.hurkat@niituniversity.in` | `faculty123` | All Student features + upload course/departmental documents (`PDF`, `DOCX`, `TXT` ≤ 25 MB) |
| **Admin Staff** | `admin@niituniversity.in` | `admin123` | Full access: tag/delete documents (`UC-03`), manage user roles, view Analytics & Kubernetes Health |
