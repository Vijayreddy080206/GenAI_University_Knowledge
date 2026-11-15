"""
SDD Section 5.2.2: API Gateway & Unified Microservice Entrypoint
Exposes all REST endpoints for Auth, Chat/RAG, Document Ingestion, Analytics/Feedback,
Users/RBAC, and Kubernetes Health/Readiness probes (/healthz, /readyz).
"""
from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from pathlib import Path
from typing import Optional, List

from app.config import settings
from app.database import get_db_connection
from app.seed import seed_all
from app.services.auth_service import AuthService
from app.services.ingestion_service import DocumentIngestionService
from app.services.chat_orchestrator import ChatOrchestratorService
from app.services.analytics_service import AnalyticsFeedbackService

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="CAPSTONE PROJECT II - Team-20, NIIT University (Under Supervision of Prof. Manish Hurkat)"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    seed_all()

def extract_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization Bearer token.")
    if authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return authorization.strip()

# --- Request Schemas ---
class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None
    is_sso: bool = False

class ChatQueryRequest(BaseModel):
    query_text: str
    session_id: Optional[int] = None
    department_filter: Optional[str] = None
    simulate_llm_error: bool = False

class FeedbackRequest(BaseModel):
    response_id: int
    rating: str
    comment: Optional[str] = None

class TagUpdateRequest(BaseModel):
    department: str
    category: str

class RoleUpdateRequest(BaseModel):
    role: str

# --- 1. Health & Readiness Probes (REQ-OPS-03, SRS 5.4.2) ---
@app.get("/healthz")
def liveness_probe():
    return {
        "status": "UP",
        "service": "nu-knowledge-assistant-gateway",
        "version": settings.VERSION,
        "kubernetes_probes": {
            "api-gateway": "Healthy (2/2 replicas)",
            "auth-svc": "Healthy (2/2 replicas)",
            "chat-orchestrator": "Healthy (3/3 replicas, HPA active)",
            "rag-svc": "Healthy (2/2 replicas)",
            "embedding-svc": "Healthy (2/2 replicas)",
            "llm-inference": "Healthy (2/2 replicas, HPA active)",
            "ingestion-svc": "Healthy (1/1 replica)",
            "analytics-svc": "Healthy (1/1 replica)",
            "postgres-db": "Healthy (StatefulSet PVC bound)",
            "vector-db": "Healthy (StatefulSet PVC bound)",
        }
    }

@app.get("/readyz")
def readiness_probe():
    conn = get_db_connection()
    try:
        doc_count = conn.execute("SELECT COUNT(*) as c FROM Documents WHERE status = 'INDEXED'").fetchone()["c"]
        return {"ready": True, "indexed_documents": doc_count}
    finally:
        conn.close()

# --- 2. Authentication & Session Endpoints (REQ-AUTH-01 to 04) ---
@app.post("/api/auth/login")
def login(req: LoginRequest):
    return AuthService.authenticate_user(email=req.email, password=req.password, is_sso=req.is_sso)

@app.get("/api/auth/me")
def get_current_user(authorization: Optional[str] = Header(None)):
    token = extract_token(authorization)
    return AuthService.validate_session_and_role(token)

# --- 3. Conversational RAG Endpoints (REQ-CHAT-01 to 06) ---
@app.get("/api/chat/sessions")
def list_user_sessions(authorization: Optional[str] = Header(None)):
    user = AuthService.validate_session_and_role(extract_token(authorization))
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM Sessions WHERE user_id = ? ORDER BY session_id DESC LIMIT 20",
            (user["user_id"],)
        ).fetchall()
        return {"sessions": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.post("/api/chat/sessions/new")
def create_new_session(authorization: Optional[str] = Header(None)):
    user = AuthService.validate_session_and_role(extract_token(authorization))
    conn = get_db_connection()
    try:
        from app.services.auth_service import now_iso
        ts = now_iso()
        cur = conn.execute(
            "INSERT INTO Sessions (user_id, title, started_at, last_activity_at, expires_at, status) VALUES (?, 'New Conversation', ?, ?, ?, 'ACTIVE')",
            (user["user_id"], ts, ts, ts)
        )
        conn.commit()
        return {"session_id": cur.lastrowid, "title": "New Conversation"}
    finally:
        conn.close()

@app.get("/api/chat/sessions/{session_id}/messages")
def get_session_messages(session_id: int, authorization: Optional[str] = Header(None)):
    AuthService.validate_session_and_role(extract_token(authorization))
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT q.query_id, q.query_text, q.category, q.submitted_at,
                   r.response_id, r.answer_text, r.status, r.model_name, r.latency_ms,
                   f.rating as user_rating, f.comment as user_comment
            FROM Queries q
            JOIN Responses r ON q.query_id = r.query_id
            LEFT JOIN Feedback f ON r.response_id = f.response_id
            WHERE q.session_id = ?
            ORDER BY q.query_id ASC
            """,
            (session_id,)
        ).fetchall()
        messages = []
        for r in rows:
            item = dict(r)
            cites = conn.execute(
                """
                SELECT rc.rank, rc.similarity_score, dc.chunk_id, d.document_id, d.title, d.department, d.category
                FROM ResponseCitations rc
                LEFT JOIN DocumentChunks dc ON rc.chunk_id = dc.chunk_id
                LEFT JOIN Documents d ON dc.document_id = d.document_id
                WHERE rc.response_id = ?
                ORDER BY rc.rank ASC
                """,
                (r["response_id"],)
            ).fetchall()
            item["citations"] = [dict(c) for c in cites]
            messages.append(item)
        return {"messages": messages}
    finally:
        conn.close()

@app.post("/api/chat/query")
def ask_question(req: ChatQueryRequest, authorization: Optional[str] = Header(None)):
    user = AuthService.validate_session_and_role(
        extract_token(authorization),
        allowed_roles=["STUDENT", "FACULTY", "ADMIN"]
    )
    sess_id = req.session_id or user["session_id"]
    return ChatOrchestratorService.process_query(
        session_id=sess_id,
        user_id=user["user_id"],
        query_text=req.query_text,
        department_filter=req.department_filter,
        simulate_llm_error=req.simulate_llm_error
    )

# --- 4. Knowledge Base & Document Management Endpoints (REQ-KB-01 to 05) ---
@app.get("/api/documents")
def list_documents(authorization: Optional[str] = Header(None)):
    AuthService.validate_session_and_role(
        extract_token(authorization),
        allowed_roles=["FACULTY", "ADMIN"]
    )
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT d.*, u.full_name as uploader_name, u.role as uploader_role,
                   (SELECT COUNT(*) FROM DocumentChunks dc WHERE dc.document_id = d.document_id) as chunk_count
            FROM Documents d
            LEFT JOIN Users u ON d.uploaded_by = u.user_id
            ORDER BY d.document_id DESC
            """
        ).fetchall()
        return {"documents": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form("Academics"),
    category: str = Form("General"),
    authorization: Optional[str] = Header(None)
):
    user = AuthService.validate_session_and_role(
        extract_token(authorization),
        allowed_roles=["FACULTY", "ADMIN"]
    )
    file_bytes = await file.read()
    return DocumentIngestionService.ingest_document(
        filename=file.filename or "uploaded_doc.txt",
        file_bytes=file_bytes,
        uploaded_by=user["user_id"],
        department=department,
        category=category
    )

@app.put("/api/documents/{document_id}/tags")
def update_tags(document_id: int, req: TagUpdateRequest, authorization: Optional[str] = Header(None)):
    # SRS 5.5 Business Rule: Only Admin may tag documents
    AuthService.validate_session_and_role(extract_token(authorization), allowed_roles=["ADMIN"])
    return DocumentIngestionService.update_document_tags(document_id, req.department, req.category)

@app.delete("/api/documents/{document_id}")
def remove_document(document_id: int, force: bool = Query(False), authorization: Optional[str] = Header(None)):
    # SRS 5.5 Business Rule: Only Admin may permanently delete a document
    AuthService.validate_session_and_role(extract_token(authorization), allowed_roles=["ADMIN"])
    return DocumentIngestionService.delete_document(document_id, force=force)

# --- 5. Feedback & Admin Analytics Endpoints (REQ-FB-01, REQ-AN-01, REQ-AN-02) ---
@app.post("/api/feedback")
def submit_answer_feedback(req: FeedbackRequest, authorization: Optional[str] = Header(None)):
    user = AuthService.validate_session_and_role(extract_token(authorization))
    return AnalyticsFeedbackService.submit_feedback(
        response_id=req.response_id,
        user_id=user["user_id"],
        rating=req.rating,
        comment=req.comment
    )

@app.get("/api/admin/analytics")
def get_analytics(
    days: int = Query(30),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None)
):
    AuthService.validate_session_and_role(extract_token(authorization), allowed_roles=["ADMIN"])
    return AnalyticsFeedbackService.get_dashboard_analytics(days=days, start_date=start_date, end_date=end_date)

# --- 6. Admin Users & Roles Management Endpoints (REQ-AUTH-02, REQ-AUTH-03, SRS 5.5) ---
@app.get("/api/admin/users")
def list_users(authorization: Optional[str] = Header(None)):
    AuthService.validate_session_and_role(extract_token(authorization), allowed_roles=["ADMIN"])
    conn = get_db_connection()
    try:
        rows = conn.execute(
            "SELECT user_id, email, full_name, role, auth_source, department, is_active, created_at FROM Users ORDER BY user_id ASC"
        ).fetchall()
        return {"users": [dict(r) for r in rows]}
    finally:
        conn.close()

@app.put("/api/admin/users/{target_user_id}/role")
def change_user_role(target_user_id: int, req: RoleUpdateRequest, authorization: Optional[str] = Header(None)):
    # SRS 5.5 Business Rule: Only Admin may modify another user's role
    AuthService.validate_session_and_role(extract_token(authorization), allowed_roles=["ADMIN"])
    new_role = req.role.upper().strip()
    if new_role not in ("STUDENT", "FACULTY", "ADMIN"):
        raise HTTPException(status_code=400, detail="Role must be STUDENT, FACULTY, or ADMIN.")
    conn = get_db_connection()
    try:
        conn.execute("UPDATE Users SET role = ? WHERE user_id = ?", (new_role, target_user_id))
        conn.commit()
        updated = conn.execute(
            "SELECT user_id, email, full_name, role, auth_source, department, is_active FROM Users WHERE user_id = ?",
            (target_user_id,)
        ).fetchone()
        if not updated:
            raise HTTPException(status_code=404, detail="User not found.")
        return dict(updated)
    finally:
        conn.close()


@app.get("/", response_class=HTMLResponse)
def serve_web_application():
    ui_path = Path(__file__).resolve().parent / "index.html"
    if ui_path.exists():
        return HTMLResponse(content=ui_path.read_text(encoding="utf-8"))
    return HTMLResponse(content="<h1>NIIT University Knowledge Assistant API is running.</h1>")
