"""
Unit Test Suite for Microservices Layer (SDD Section 5)
Focuses on individual component functions:
- AuthService: PBKDF2 hashing, JWT signing/decoding, Role validation
- IngestionService: Chunking logic, format validation, token counting
- ChatOrchestrator: PII scrubbing, Follow-up query rewriting, Category classification
- EmbeddingService: Semantic vector calculation and unit normalization
"""
import unittest
from datetime import datetime, timezone, timedelta
from app.services.auth_service import hash_password, verify_password, create_jwt_token, decode_jwt_token
from app.services.chat_orchestrator import scrub_pii, classify_query_category, ChatOrchestratorService
from app.services.ingestion_service import DocumentIngestionService
from app.services.embedding_vector_service import EmbeddingService

class TestUnitServices(unittest.TestCase):
    def test_password_hashing_and_verification(self):
        pwd = "SecureUniversityPassword2026!"
        h1 = hash_password(pwd)
        self.assertTrue(h1.startswith("pbkdf2_sha256$"))
        self.assertTrue(verify_password(pwd, h1))
        self.assertFalse(verify_password("WrongPassword", h1))

    def test_jwt_token_creation_and_decoding(self):
        payload = {
            "user_id": 42,
            "email": "vijay.test@st.niituniversity.in",
            "role": "STUDENT",
            "session_id": 999
        }
        token = create_jwt_token(payload)
        self.assertIsInstance(token, str)
        decoded = decode_jwt_token(token)
        self.assertEqual(decoded["user_id"], 42)
        self.assertEqual(decoded["email"], "vijay.test@st.niituniversity.in")
        self.assertEqual(decoded["role"], "STUDENT")

    def test_pii_scrubbing(self):
        """NFR-SEC-04: Ensure personal identifiable info is redacted before LLM prompt assembly."""
        raw_text = "Student Vijay (BT23GCS245) with email vijay.reddy23@st.niituniversity.in and phone 9876543210 submitted a query."
        scrubbed = scrub_pii(raw_text)
        self.assertNotIn("vijay.reddy23@st.niituniversity.in", scrubbed)
        self.assertNotIn("9876543210", scrubbed)
        self.assertNotIn("BT23GCS245", scrubbed)
        self.assertIn("[REDACTED_EMAIL]", scrubbed)
        self.assertIn("[REDACTED_PHONE]", scrubbed)
        self.assertIn("[REDACTED_ROLL_NO]", scrubbed)

    def test_query_rewriting_for_followup(self):
        """REQ-CHAT-04: Verify conversational context is injected into pronoun follow-ups."""
        history = [{"query_text": "When is the semester fee deadline?", "answer_text": "Sept 30, 2026"}]
        rewritten = ChatOrchestratorService.rewrite_followup_query("what about the penalty for it?", history)
        self.assertIn("When is the semester fee deadline?", rewritten)
        self.assertIn("penalty", rewritten)

    def test_category_classification(self):
        self.assertEqual(classify_query_category("What is the hostel gate curfew timing?"), "Hostel")
        self.assertEqual(classify_query_category("When are the mid-sem exams for CS3041?"), "Exams")
        self.assertEqual(classify_query_category("How much is the mess and tuition fee installment?"), "Fees")
        self.assertEqual(classify_query_category("What is the attendance policy for 75%?"), "Academics")

    def test_semantic_chunking(self):
        sample_doc = (
            "NIIT UNIVERSITY ACADEMIC GUIDELINES\n\n"
            "Paragraph one describes the fundamental attendance requirements and grading scale for B.Tech students. " * 8 + "\n\n"
            "Paragraph two outlines capstone project guidelines, supervisor allocation, and industry practice. " * 8
        )
        chunks = DocumentIngestionService.split_into_semantic_chunks(sample_doc, chunk_size=50, overlap=10)
        self.assertTrue(len(chunks) >= 2)
        for c in chunks:
            self.assertIn("chunk_index", c)
            self.assertIn("chunk_text", c)
            self.assertGreater(c["token_count"], 0)

    def test_embedding_generation_unit_vector(self):
        vec = EmbeddingService.embed_text("NIIT University Capstone Project II")
        self.assertEqual(len(vec), 384)
        # Vector should be approximately unit length
        import numpy as np
        norm = np.linalg.norm(vec)
        self.assertAlmostEqual(float(norm), 1.0, places=2)

if __name__ == "__main__":
    unittest.main()
