"""
SDD Section 5.2.8: Document Ingestion Service
Implements REQ-KB-01, REQ-KB-02, REQ-KB-03, REQ-KB-04, REQ-KB-05, NFR-SAFE-02, UC-02, UC-03
- Validates file type (PDF, DOCX, TXT) and size limit (<= 25 MB) per REQ-KB-05
- Extracts text from PDF (pypdf), DOCX (python-docx), and TXT
- Splits into semantic chunks (~500 tokens with ~50 tokens overlap)
- Generates embeddings and indexes in Vector Store + PostgreSQL/SQLite DocumentChunks
- Handles Admin tagging, updates, re-indexing (REQ-KB-04), and UC-03 deletion warnings
"""
import os
import re
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import HTTPException
import pypdf
from docx import Document as DocxDocument

from app.config import settings
from app.database import get_db_connection
from app.services.embedding_vector_service import EmbeddingService, vector_store

STORAGE_DIR = Path(__file__).resolve().parent.parent.parent / "storage" / "documents"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

class DocumentIngestionService:
    @staticmethod
    def validate_upload(filename: str, file_size_bytes: int) -> str:
        """REQ-KB-05: Reject unsupported file format or file exceeding configured size limit."""
        ext = filename.rsplit(".", 1)[-1].upper() if "." in filename else ""
        if ext not in settings.SUPPORTED_FILE_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Upload rejected (REQ-KB-05): Unsupported file format '.{ext.lower()}'. Supported formats are PDF, DOCX, and TXT."
            )
        if file_size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Upload rejected (REQ-KB-05): File size ({file_size_bytes / (1024*1024):.1f} MB) exceeds the maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
            )
        if file_size_bytes <= 0:
            raise HTTPException(status_code=400, detail="Upload rejected (REQ-KB-05): File is empty.")
        return ext

    @staticmethod
    def extract_text(file_path: Path, file_type: str) -> str:
        if file_type == "TXT":
            return file_path.read_text(encoding="utf-8", errors="replace")
        elif file_type == "PDF":
            reader = pypdf.PdfReader(str(file_path))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(pages)
        elif file_type == "DOCX":
            doc = DocxDocument(str(file_path))
            paras = [p.text for p in doc.paragraphs if p.text.strip()]
            return "\n\n".join(paras)
        else:
            raise ValueError(f"Unsupported file_type: {file_type}")

    @staticmethod
    def split_into_semantic_chunks(text: str, chunk_size: int = 120, overlap: int = 20) -> List[Dict[str, Any]]:
        """
        SDD Section 5.4.1: Splits text on headings/paragraphs into semantic overlapping chunks.
        """
        cleaned = re.sub(r"\r\n", "\n", text).strip()
        if not cleaned:
            return []

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", cleaned) if p.strip()]
        chunks: List[Dict[str, Any]] = []
        current_words: List[str] = []
        chunk_idx = 0

        for para in paragraphs:
            para_words = para.split()
            if len(current_words) + len(para_words) <= chunk_size or not current_words:
                current_words.extend(para_words)
            else:
                chunk_str = " ".join(current_words)
                chunks.append({
                    "chunk_index": chunk_idx,
                    "chunk_text": chunk_str,
                    "token_count": len(current_words),
                })
                chunk_idx += 1
                current_words = current_words[-overlap:] + para_words

        if current_words:
            chunks.append({
                "chunk_index": chunk_idx,
                "chunk_text": " ".join(current_words),
                "token_count": len(current_words),
            })
        return chunks

    @classmethod
    def ingest_document(
        cls,
        filename: str,
        file_bytes: bytes,
        uploaded_by: int,
        department: str = "Academics",
        category: str = "General",
        db_path=None,
        vstore=None
    ) -> Dict[str, Any]:
        vs = vstore or vector_store
        file_type = cls.validate_upload(filename, len(file_bytes))
        safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", filename)
        dest_path = STORAGE_DIR / safe_name
        dest_path.write_bytes(file_bytes)

        conn = get_db_connection(db_path)
        ts = now_iso()
        try:
            # Check if document with same title already exists -> update & increment version (REQ-KB-04)
            existing = conn.execute("SELECT * FROM Documents WHERE title = ?", (filename,)).fetchone()
            if existing:
                doc_id = existing["document_id"]
                new_version = existing["version"] + 1
                conn.execute(
                    """
                    UPDATE Documents
                    SET uploaded_by = ?, department = ?, category = ?, file_type = ?,
                        file_size_bytes = ?, storage_uri = ?, status = 'PROCESSING',
                        version = ?, updated_at = ?
                    WHERE document_id = ?
                    """,
                    (uploaded_by, department, category, file_type, len(file_bytes), str(dest_path), new_version, ts, doc_id)
                )
                # Remove old chunks & vectors (REQ-KB-04)
                conn.execute("DELETE FROM DocumentChunks WHERE document_id = ?", (doc_id,))
                vs.delete_by_document_id(doc_id)
            else:
                cur = conn.execute(
                    """
                    INSERT INTO Documents
                    (uploaded_by, title, department, category, file_type, file_size_bytes, storage_uri, status, version, uploaded_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'PROCESSING', 1, ?, ?)
                    """,
                    (uploaded_by, filename, department, category, file_type, len(file_bytes), str(dest_path), ts, ts)
                )
                doc_id = cur.lastrowid
                new_version = 1
            conn.commit()

            try:
                raw_text = cls.extract_text(dest_path, file_type)
                chunks = cls.split_into_semantic_chunks(raw_text)
                if not chunks:
                    raise ValueError("No extractable text found in document.")

                embeddings = EmbeddingService.embed_batch([c["chunk_text"] for c in chunks], is_query=False)
                vector_records = []

                for c_item, emb in zip(chunks, embeddings):
                    vec_id = f"vec_doc{doc_id}_c{c_item['chunk_index']}_{uuid.uuid4().hex[:8]}"
                    c_cur = conn.execute(
                        """
                        INSERT INTO DocumentChunks (document_id, chunk_index, chunk_text, token_count, vector_id)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (doc_id, c_item["chunk_index"], c_item["chunk_text"], c_item["token_count"], vec_id)
                    )
                    chunk_id = c_cur.lastrowid
                    vector_records.append({
                        "id": vec_id,
                        "embedding": emb,
                        "metadata": {
                            "document_id": doc_id,
                            "chunk_id": chunk_id,
                            "department": department,
                            "category": category,
                            "status": "INDEXED",
                        }
                    })

                vs.upsert_records(vector_records)
                conn.execute(
                    "UPDATE Documents SET status = 'INDEXED', updated_at = ? WHERE document_id = ?",
                    (now_iso(), doc_id)
                )
                conn.commit()
                return {
                    "document_id": doc_id,
                    "title": filename,
                    "department": department,
                    "category": category,
                    "file_type": file_type,
                    "file_size_bytes": len(file_bytes),
                    "status": "INDEXED",
                    "version": new_version,
                    "chunks_indexed": len(chunks),
                }
            except Exception as ingest_err:
                # UC-02 Alternate Flow 4a: Mark 'FAILED' and notify user to retry
                conn.execute(
                    "UPDATE Documents SET status = 'FAILED', updated_at = ? WHERE document_id = ?",
                    (now_iso(), doc_id)
                )
                conn.commit()
                raise HTTPException(
                    status_code=500,
                    detail=f"Processing Failed (UC-02 4a): {ingest_err}. Please retry uploading the document."
                )
        finally:
            conn.close()

    @staticmethod
    def update_document_tags(document_id: int, department: str, category: str, db_path=None, vstore=None) -> Dict[str, Any]:
        """REQ-KB-03 & REQ-KB-04: Admin updates tags/category and synchronizes vector store metadata."""
        vs = vstore or vector_store
        conn = get_db_connection(db_path)
        try:
            doc = conn.execute("SELECT * FROM Documents WHERE document_id = ?", (document_id,)).fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found.")
            ts = now_iso()
            conn.execute(
                "UPDATE Documents SET department = ?, category = ?, updated_at = ? WHERE document_id = ?",
                (department, category, ts, document_id)
            )
            conn.commit()
            vs.update_document_metadata(document_id, department, category, doc["status"])
            updated = conn.execute("SELECT * FROM Documents WHERE document_id = ?", (document_id,)).fetchone()
            return dict(updated)
        finally:
            conn.close()

    @staticmethod
    def delete_document(document_id: int, force: bool = False, db_path=None, vstore=None) -> Dict[str, Any]:
        """
        REQ-KB-03, REQ-KB-04, UC-03: Permanently removes document, chunks, and vector embeddings.
        UC-03 Alternate Flow 3a: Warns Admin if referenced by recent queries unless force=True.
        """
        vs = vstore or vector_store
        conn = get_db_connection(db_path)
        try:
            doc = conn.execute("SELECT * FROM Documents WHERE document_id = ?", (document_id,)).fetchone()
            if not doc:
                raise HTTPException(status_code=404, detail="Document not found.")

            # Check if referenced by recent citations or downvoted responses (UC-03 3a)
            ref_count = conn.execute(
                """
                SELECT COUNT(*) as cnt
                FROM ResponseCitations rc
                JOIN DocumentChunks dc ON rc.chunk_id = dc.chunk_id
                WHERE dc.document_id = ?
                """,
                (document_id,)
            ).fetchone()["cnt"]

            if ref_count > 0 and not force:
                return {
                    "warning_required": True,
                    "document_id": document_id,
                    "title": doc["title"],
                    "referenced_queries_count": ref_count,
                    "message": f"Warning (UC-03 3a): '{doc['title']}' is referenced by {ref_count} recent queries. Confirm with force=true to permanently delete.",
                }

            # Nullify chunk references in ResponseCitations per SDD 4.2.5 ("set to NULL if chunk is later deleted")
            conn.execute(
                """
                UPDATE ResponseCitations
                SET chunk_id = NULL
                WHERE chunk_id IN (SELECT chunk_id FROM DocumentChunks WHERE document_id = ?)
                """,
                (document_id,)
            )
            conn.execute("DELETE FROM DocumentChunks WHERE document_id = ?", (document_id,))
            conn.execute("DELETE FROM Documents WHERE document_id = ?", (document_id,))
            conn.commit()

            removed_vectors = vs.delete_by_document_id(document_id)
            raw_path = Path(doc["storage_uri"])
            if raw_path.exists():
                try:
                    raw_path.unlink()
                except OSError:
                    pass

            return {
                "deleted": True,
                "document_id": document_id,
                "title": doc["title"],
                "removed_vectors": removed_vectors,
            }
        finally:
            conn.close()
