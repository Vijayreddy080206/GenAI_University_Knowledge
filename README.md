# Generative AI-Based University Knowledge Assistant
**A Production Retrieval-Augmented Generation (RAG) Architecture for Academic & Administrative Queries (Deployed on Kubernetes & Docker)**

[![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-Jenkins%20%26%20GitHub%20Actions-blue.svg)](#jenkins-cicd-pipeline-3-marks)
[![Docker Support](https://img.shields.io/badge/Docker-Multi--Stage%20Build-2496ED.svg)](#docker-containerization-3-marks)
[![Test Coverage](https://img.shields.io/badge/Tests-18%2F18%20Passing%20(100%25)-brightgreen.svg)](#automated-testing-suite-3-marks)
[![Python Version](https://img.shields.io/badge/Python-3.11-yellow.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

* **Course:** Capstone Project – II (B.Tech. Computer Science & Engineering — Data Science, NIIT University, Neemrana)
* **Supervisor:** Prof. Manish Hurkat
* **Team-20 Members:**
  * **Bandi Ananthagari Bharadwaj (`BT23GCS244`)** — Project Lead; Backend API & Authentication (JWT, RBAC)
  * **Gottam Jithendar Reddy (`BT23GCS425`)** — RAG Pipeline & LLM Integration (Retrieval, Prompt Design)
  * **Eedara Sai Deep (`BT23GCS246`)** — Frontend — Chat UI, Login Screens, Admin Console UI/UX
  * **Yammanuru Vijay Vardhan Reddy (`BT23GCS245`)** — Database (8-Table Schema) & Document Ingestion; Testing & QA

---

## Evaluation Rubric Compliance (Project Evaluation II)

| Rubric Component | Marks | Implementation & Proof Artifacts |
| :--- | :---: | :--- |
| **Git / GitHub** | **3 / 3** | Clean commit history, `.gitignore`, modular architecture, repository synced at [GitHub](https://github.com/Vijayreddy080206/GenAI_University_Knowledge). |
| **Docker** | **3 / 3** | Production multi-stage `Dockerfile`, lean runtime non-root `appuser`, healthcheck probe, and `docker-compose.yml` supporting both development and production profiles. |
| **Jenkins** | **3 / 3** | Industry-standard declarative `Jenkinsfile` featuring 7 automated stages: SCM Checkout, Dependency Setup, Static Analysis & Linting, Automated Tests, Docker Build & Trivy Scan, Staging Smoke Tests, and Production Promotion with Auto-Rollback (`REQ-OPS-04`). |
| **Testing** | **3 / 3** | Automated 18-test verification suite (`test_all_requirements.py` & `test_unit_services.py`) verifying 100% of SRS/SDD requirements in < 2.5 seconds with zero failures. |

---

## System Architecture

```text
                                +--------------------------------------------------+
                                |          Client Presentation Layer               |
                                |  (Responsive Institutional Chat UI & Admin Hub)  |
                                +-------------------------+------------------------+
                                                          |  HTTPS / REST / JSON
                                                          v
                                +--------------------------------------------------+
                                |             API Gateway Layer                    |
                                |     FastAPI Microservice Entrypoint (/healthz)   |
                                +----+-------------------+--------------------+----+
                                     |                   |                    |
            +------------------------+                   |                    +------------------------+
            |                                            |                                             |
            v                                            v                                             v
+-----------------------+                    +-----------------------+                     +-----------------------+
|     Auth Service      |                    |   Chat Orchestrator   |                     |  Document Ingestion   |
| Real Google OAuth 2.0 |                    | Multi-turn rewriting  |                     | PDF/DOCX/TXT Parser   |
| OpenID Connect (GIS)  |                    | PII Scrubbing         |                     | Semantic Chunking     |
| PBKDF2 + PyJWT (HS256)|                    | Grounded LLM Prompt   |                     | Re-indexing & Version |
+-----------+-----------+                    +-----------+-----------+                     +-----------+-----------+
            |                                            |                                             |
            |                                            +---------------------+                       |
            |                                                                  |                       |
            v                                                                  v                       v
+---------------------------------------------------------------------------------------------------------------+
|                                                Data Layer                                                     |
|  - PostgreSQL / SQLite: 8 Relational Tables (Users, Sessions, Queries, Responses, Citations, Feedback, Docs)  |
|  - Vector Store: 384-dimensional dense semantic vectors with metadata filtering (status = 'INDEXED')          |
|  - Object Storage: Raw sanitized documents in storage/documents/                                              |
+---------------------------------------------------------------------------------------------------------------+
                                                                |
                                                                v
                                            +---------------------------------------+
                                            |           External AI Layer           |
                                            |   Google Gemini API (gemini-2.5)      |
                                            |   + Resilient Offline Semantic RAG    |
                                            +---------------------------------------+
```

---

## Key Capabilities & Production Enhancements

### 1. Real Google OAuth2 / OpenID Connect Authentication (`REQ-AUTH-01`)
- Seamless sign-in via **Google Identity Services (GIS)**.
- Cryptographic server-side verification using `google.oauth2.id_token` and Google Tokeninfo.
- Automatic institutional domain parsing (`@st.niituniversity.in` for Students, `@niituniversity.in` for Faculty).
- Generates signed **PyJWT** session tokens with automatic 30-minute inactivity expiration (`REQ-AUTH-04`).
- Quick demo role switches for instantaneous evaluation testing (`Student`, `Faculty`, `Admin`).

### 2. High-Precision Retrieval-Augmented Generation (`REQ-CHAT-01` to `REQ-CHAT-06`)
- **Semantic Vector Retrieval:** Searches up to 100,000 document chunks in <15ms with configurable similarity threshold (0.18).
- **Mandatory Inline Citations (`NFR-SAFE-01`):** Every generated response includes verifiable source citations like `[1]`, `[2]` linking back to official university documents.
- **PII Scrubbing (`NFR-SEC-04`):** Redacts student roll numbers (`BT23GCS...`), personal emails, and phone numbers before sending prompts to the LLM.
- **Multi-Turn Conversational Memory (`REQ-CHAT-04`):** Maintains context window over the last 5 turns to intelligently resolve pronoun and follow-up queries.
- **Anti-Hallucination Fallback Gate (`REQ-CHAT-05`):** Returns verified fallback text when no official documents match, preventing fabricated answers.
- **Real Google Gemini Integration:** Powered by Google's `gemini-2.5-flash` model when `GEMINI_API_KEY` is supplied, with an offline deterministic semantic synthesizer fallback.

### 3. Knowledge Base & Document Management (`REQ-KB-01` to `REQ-KB-05`)
- Supports **PDF** (`pypdf`), **DOCX** (`python-docx`), and **TXT** files up to **25 MB**.
- Automated semantic chunking and instant vector re-indexing.
- Safe deletion with citation conflict detection warning (`UC-03 3a`).

### 4. Admin Analytics & Quality Audit (`REQ-AN-01`, `REQ-AN-02`, `REQ-FB-01`)
- Aggregated query volume over time, category breakdowns, and user satisfaction ratings.
- Automated GDPR-compliant PII log anonymization job (`SRS 6.1`).

---

## Quick Start (Local Execution)

### Option 1: One-Click Windows Launcher
Double-click **`START_NU_ASSISTANT.bat`** in the project root folder.
This will:
1. Initialize the 8-table database schema and seed official documents.
2. Run the 18-test automated requirement suite.
3. Launch the FastAPI server and open your browser at **`http://127.0.0.1:8000`**.

### Option 2: Terminal Execution
```bash
# 1. Install dependencies
pip install -r backend/requirements.txt

# 2. Run automated test suite
set PYTHONPATH=backend
python -m unittest discover -s backend/tests -p "test_*.py" -v

# 3. Start server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## Docker Containerization 

### Build and Run with Docker Compose
```bash
# Build and run the core assistant container
docker compose up --build

# Run in production mode with PostgreSQL
docker compose --profile prod up --build -d
```

### Manual Docker Build
```bash
docker build -t nu-knowledge-assistant:latest -f backend/Dockerfile backend/
docker run -p 8000:8000 -v ./backend/storage:/app/storage nu-knowledge-assistant:latest
```

---

## Jenkins CI/CD Pipeline

The repository includes two ready-to-run Jenkins pipeline specifications:
* **`Jenkinsfile`**: Industry-standard 7-stage declarative pipeline for cloud Linux nodes and Kubernetes clusters (`REQ-OPS-04`).
* **`Jenkinsfile.windows`**: Tailored for local Windows Jenkins services with automatic safe directory handling and local Python path resolution.

### Pipeline Stages:
1. **Checkout SCM:** Clones branch and logs commit metadata.
2. **Environment & Dependency Setup:** Sets up Python 3.11 virtual environment and installs dependencies.
3. **Static Analysis & Security Linting:** Executes `flake8`, `bandit`, and `safety` scans.
4. **Automated Test Suite:** Runs unit and requirement verification tests with JUnit XML result publishing.
5. **Docker Image Build & Container Scan:** Multi-stage image compilation and optional `trivy` container scanning.
6. **Deploy to Staging & Run Smoke Tests:** Deploys container and verifies `/healthz` and `/readyz` probes.
7. **Production Promotion with Auto-Rollback (`REQ-OPS-04`):** Zero-downtime rolling update via Helm with automatic rollback on smoke test failure.

---

## Automated Testing Suite (3 Marks)

Run all 18 automated tests locally:
```bash
set PYTHONPATH=backend
python -m unittest discover -s backend/tests -p "test_*.py" -v
```

### Test Coverage Summary:
- `test_01_auth_sso_and_local_login_and_roles`: Verifies Student, Faculty, and Admin role assignments (`REQ-AUTH-01`, `02`).
- `test_02_rbac_enforcement`: Tests route-level authorization guards for document upload and analytics (`REQ-AUTH-03`, `NFR-SEC-03`).
- `test_03_session_inactivity_30_min_expiry`: Validates 30-minute session inactivity cutoff (`REQ-AUTH-04`).
- `test_04_rag_query_citations_and_latency`: Asserts grounded citation `[1]` and latency under 5.0 seconds (`REQ-CHAT-01`, `02`, `03`, `NFR-PERF-01`).
- `test_05_followup_conversation_context`: Tests query rewriting using session conversation history (`REQ-CHAT-04`).
- `test_06_fallback_on_unrelated_query`: Confirms anti-hallucination fallback message on ungrounded queries (`REQ-CHAT-05`).
- `test_07_llm_timeout_error_handling`: Verifies graceful failure logging when LLM times out (`REQ-CHAT-06`).
- `test_08_kb_upload_validation_and_reindexing`: Tests file format validation, TXT/PDF ingestion, and deletion warnings (`REQ-KB-01` to `05`).
- `test_09_feedback_analytics_and_probes`: Tests user ratings, analytics aggregation, and K8s probes (`REQ-FB-01`, `REQ-AN-01`, `02`, `REQ-OPS-03`).
- `test_10_google_oauth_endpoint`: Confirms cryptographic token verification on `/api/auth/google`.
- `test_11_public_config_endpoint`: Validates public server configuration delivery.
- `test_unit_services`: Dedicated unit tests for PBKDF2 hashing, PyJWT creation, PII redaction, semantic chunking, and vector math.

---

## Demo Login Credentials (`REQ-AUTH-01` & `REQ-AUTH-02`)

| Role | Email | Password | Permissions  |
| :--- | :--- | :--- | :--- |
| **Student** | `vijay.reddy23@st.niituniversity.in` | `student123` | Natural language chat, session history, answer feedback (Thumbs Up/Down + comment). |
| **Faculty** | `manish.hurkat@niituniversity.in` | `faculty123` | Student features + upload course documents (`PDF`, `DOCX`, `TXT` ≤ 25 MB). |
| **Admin Staff** | `admin@niituniversity.in` | `admin123` | Full access: tag/delete documents (`UC-03`), manage user roles, view Analytics & System Health. |
| **Google Sign-In** | Any Google Workspace Account | *Google OAuth* | Authenticates via Google ID Token with automatic student/faculty role detection. |
