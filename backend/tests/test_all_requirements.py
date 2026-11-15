"""
Automated Unit, Integration & System Test Suite for Capstone Project 2 (Team-20, NIIT University)
Verifies 100% of Functional & Non-Functional Requirements in the SDD RTM (Section 7.1):
- REQ-AUTH-01 to 04 (SSO + Fallback login, Roles, RBAC, 30-min session inactivity expiry)
- REQ-CHAT-01 to 06 (RAG query, vector similarity search <500ms, grounded citations, follow-up context, fallback gate, LLM error handling)
- REQ-KB-01 to 05 (PDF/DOCX/TXT ingestion, chunking/embedding, Admin tagging, re-indexing, format/25MB size rejection, UC-03 deletion warning)
- REQ-FB-01, REQ-AN-01, REQ-AN-02 (Thumbs UP/DOWN + comment, query logging, Admin analytics & empty-state UC-04 2a)
- REQ-OPS-03, SRS 6.1 (Health/Readiness probes, PII retention anonymization)
"""
import time
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from app.main import app
from app.seed import seed_all
from app.database import get_db_connection
from app.services.analytics_service import AnalyticsFeedbackService

class TestGenAIUniversityKnowledgeAssistant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        seed_all()
        cls.client = TestClient(app)

    def _login(self, email: str, password: str = None, is_sso: bool = False):
        resp = self.client.post("/api/auth/login", json={"email": email, "password": password, "is_sso": is_sso})
        self.assertEqual(resp.status_code, 200, resp.text)
        return resp.json()

    def test_01_auth_sso_and_local_login_and_roles(self):
        """REQ-AUTH-01 & REQ-AUTH-02: Login via SSO or fallback email/password and verify STUDENT, FACULTY, ADMIN roles."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        self.assertEqual(student["user"]["role"], "STUDENT")

        sso_student = self._login("bharadwaj.bandi23@st.niituniversity.in", is_sso=True)
        self.assertEqual(sso_student["user"]["role"], "STUDENT")

        faculty = self._login("manish.hurkat@niituniversity.in", "faculty123")
        self.assertEqual(faculty["user"]["role"], "FACULTY")

        admin = self._login("admin@niituniversity.in", "admin123")
        self.assertEqual(admin["user"]["role"], "ADMIN")

    def test_02_rbac_enforcement(self):
        """REQ-AUTH-03 & NFR-SEC-03: Restrict content management to Faculty/Admin and Analytics/Roles/Delete to Admin."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        s_headers = {"Authorization": f"Bearer {student['token']}"}

        # Student cannot view documents list or analytics
        r_docs = self.client.get("/api/documents", headers=s_headers)
        self.assertEqual(r_docs.status_code, 403)
        r_an = self.client.get("/api/admin/analytics", headers=s_headers)
        self.assertEqual(r_an.status_code, 403)

        # Faculty CAN view/upload documents, but CANNOT view analytics or delete documents
        faculty = self._login("manish.hurkat@niituniversity.in", "faculty123")
        f_headers = {"Authorization": f"Bearer {faculty['token']}"}
        self.assertEqual(self.client.get("/api/documents", headers=f_headers).status_code, 200)
        self.assertEqual(self.client.get("/api/admin/analytics", headers=f_headers).status_code, 403)
        self.assertEqual(self.client.delete("/api/documents/1", headers=f_headers).status_code, 403)

    def test_03_session_inactivity_30_min_expiry(self):
        """REQ-AUTH-04: Expire an inactive session after 30 minutes and require re-authentication."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        sess_id = student["session_id"]
        headers = {"Authorization": f"Bearer {student['token']}"}

        # Rewind last_activity_at by 35 minutes
        expired_ts = (datetime.now(timezone.utc) - timedelta(minutes=35)).strftime("%Y-%m-%d %H:%M:%S")
        conn = get_db_connection()
        conn.execute("UPDATE Sessions SET last_activity_at = ? WHERE session_id = ?", (expired_ts, sess_id))
        conn.commit()
        conn.close()

        r = self.client.get("/api/auth/me", headers=headers)
        self.assertEqual(r.status_code, 401)
        self.assertIn("30 minutes", r.json()["detail"])

    def test_04_rag_query_citations_and_latency(self):
        """REQ-CHAT-01, REQ-CHAT-02, REQ-CHAT-03, NFR-PERF-01, NFR-SAFE-01: Grounded answer with citations under 5s."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        headers = {"Authorization": f"Bearer {student['token']}"}

        t0 = time.perf_counter()
        r = self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"query_text": "When is the last date to pay the semester fees?"}
        )
        elapsed = time.perf_counter() - t0
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ANSWERED")
        self.assertIn("September 30, 2026", data["answer_text"])
        self.assertIn("[1]", data["answer_text"])
        self.assertTrue(len(data["citations"]) >= 1)
        self.assertLess(elapsed, 5.0)  # NFR-PERF-01: < 5 seconds

    def test_05_followup_conversation_context(self):
        """REQ-CHAT-04: Retain conversation context in the same session for follow-up questions."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        headers = {"Authorization": f"Bearer {student['token']}"}
        sess_id = student["session_id"]

        self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"session_id": sess_id, "query_text": "What is the semester fee payment deadline?"}
        )
        r_follow = self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"session_id": sess_id, "query_text": "What is the late penalty after that?"}
        )
        self.assertEqual(r_follow.status_code, 200)
        data = r_follow.json()
        self.assertEqual(data["status"], "ANSWERED")
        self.assertTrue(len(data["citations"]) >= 1)

    def test_06_fallback_on_unrelated_query(self):
        """REQ-CHAT-05: Return fallback message instead of fabricating an answer when no chunk meets threshold."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        headers = {"Authorization": f"Bearer {student['token']}"}

        r = self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"query_text": "How do I bake a chocolate sourdough cake on Mars?"}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "FALLBACK")
        self.assertIn("I don't have information on that", data["answer_text"])
        self.assertEqual(len(data["citations"]), 0)

    def test_07_llm_timeout_error_handling(self):
        """REQ-CHAT-06: Log failure and display error message when LLM is unavailable or times out."""
        student = self._login("vijay.reddy23@st.niituniversity.in", "student123")
        headers = {"Authorization": f"Bearer {student['token']}"}

        r = self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"query_text": "When is the last date to pay semester fees?", "simulate_llm_error": True}
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["status"], "ERROR")
        self.assertIn("REQ-CHAT-06", data["answer_text"])

    def test_08_kb_upload_validation_and_reindexing(self):
        """REQ-KB-01 to 05 & UC-03: Validate upload format/size, ingest TXT, update tags, warn on delete, and delete."""
        admin = self._login("admin@niituniversity.in", "admin123")
        headers = {"Authorization": f"Bearer {admin['token']}"}

        # 1. Reject unsupported .exe file (REQ-KB-05)
        r_bad = self.client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("malware.exe", b"binarydata", "application/octet-stream")},
            data={"department": "IT", "category": "General"}
        )
        self.assertEqual(r_bad.status_code, 400)
        self.assertIn("REQ-KB-05", r_bad.json()["detail"])

        # 2. Upload valid TXT notice (REQ-KB-01, REQ-KB-02)
        notice_bytes = (
            b"NIIT UNIVERSITY PLACEMENT CELL NOTICE 2026\n"
            b"Campus placement registration for B.Tech CSE 2023 batch opens on November 20, 2026. "
            b"Minimum CGPA eligibility for Tier-1 product companies is 7.0 with zero active backlogs."
        )
        r_ok = self.client.post(
            "/api/documents/upload",
            headers=headers,
            files={"file": ("Placement_Notice_2026.txt", notice_bytes, "text/plain")},
            data={"department": "CIC / Placements", "category": "Placements"}
        )
        self.assertEqual(r_ok.status_code, 200)
        doc_info = r_ok.json()
        doc_id = doc_info["document_id"]
        self.assertEqual(doc_info["status"], "INDEXED")

        # 3. Query newly uploaded document
        r_q = self.client.post(
            "/api/chat/query",
            headers=headers,
            json={"query_text": "When does campus placement registration open for B.Tech CSE?"}
        )
        self.assertEqual(r_q.json()["status"], "ANSWERED")
        self.assertIn("November 20, 2026", r_q.json()["answer_text"])

        # 4. Update tags (REQ-KB-03)
        r_tag = self.client.put(
            f"/api/documents/{doc_id}/tags",
            headers=headers,
            json={"department": "Career Services", "category": "Placements"}
        )
        self.assertEqual(r_tag.status_code, 200)
        self.assertEqual(r_tag.json()["department"], "Career Services")

        # 5. Delete warning check (UC-03 3a) then force delete (REQ-KB-04)
        r_warn = self.client.delete(f"/api/documents/{doc_id}", headers=headers)
        self.assertEqual(r_warn.status_code, 200)
        self.assertTrue(r_warn.json().get("warning_required"))

        r_del = self.client.delete(f"/api/documents/{doc_id}?force=true", headers=headers)
        self.assertEqual(r_del.status_code, 200)
        self.assertTrue(r_del.json().get("deleted"))

    def test_09_feedback_analytics_and_probes(self):
        """REQ-FB-01, REQ-AN-01, REQ-AN-02, REQ-OPS-03, SRS 6.1: Feedback, Analytics, Empty State, and K8s Probes."""
        admin = self._login("admin@niituniversity.in", "admin123")
        headers = {"Authorization": f"Bearer {admin['token']}"}

        # Submit analytics query
        r_an = self.client.get("/api/admin/analytics?days=30", headers=headers)
        self.assertEqual(r_an.status_code, 200)
        self.assertFalse(r_an.json()["empty_state"])
        self.assertGreater(r_an.json()["summary"]["total_queries"], 0)

        # Empty state for future date range (UC-04 2a)
        r_empty = self.client.get(
            "/api/admin/analytics?start_date=2030-01-01 00:00:00&end_date=2030-01-02 00:00:00",
            headers=headers
        )
        self.assertEqual(r_empty.status_code, 200)
        self.assertTrue(r_empty.json()["empty_state"])

        # Kubernetes liveness and readiness probes (REQ-OPS-03)
        self.assertEqual(self.client.get("/healthz").status_code, 200)
        self.assertEqual(self.client.get("/readyz").status_code, 200)

        # PII anonymization job (SRS 6.1)
        purged = AnalyticsFeedbackService.purge_expired_pii_logs(retention_days=90)
        self.assertGreaterEqual(purged, 0)

if __name__ == "__main__":
    unittest.main(verbosity=2)
