"""
SDD Section 5.4.1: Configurable Design Parameters (loaded from Kubernetes ConfigMaps & Secrets)
"""
import os

class Settings:
    PROJECT_NAME: str = "Generative AI-Based University Knowledge Assistant"
    VERSION: str = "1.0.0"
    UNIVERSITY_NAME: str = "NIIT University"

    # SDD Section 5.4.1 Parameters
    CHUNK_SIZE_TOKENS: int = int(os.getenv("CHUNK_SIZE_TOKENS", "500"))
    CHUNK_OVERLAP_TOKENS: int = int(os.getenv("CHUNK_OVERLAP_TOKENS", "50"))
    TOP_K_CHUNKS: int = int(os.getenv("TOP_K_CHUNKS", "5"))
    SIMILARITY_METRIC: str = os.getenv("SIMILARITY_METRIC", "cosine")
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.18"))
    CONVERSATION_WINDOW_TURNS: int = int(os.getenv("CONVERSATION_WINDOW_TURNS", "5"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    LLM_REQUEST_TIMEOUT_SEC: int = int(os.getenv("LLM_REQUEST_TIMEOUT_SEC", "20"))
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024
    SESSION_INACTIVITY_TIMEOUT_MIN: int = int(os.getenv("SESSION_INACTIVITY_TIMEOUT_MIN", "30"))
    DATA_RETENTION_DAYS: int = int(os.getenv("DATA_RETENTION_DAYS", "90"))

    # Secrets & Providers (NFR-SEC-02: Injected from K8s Secrets at runtime)
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "nu-capstone-team20-k8s-secret-key-2026")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///storage/nu_knowledge_assistant.db")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "gemini-2.5-flash")

    # Real Google OAuth 2.0 Credentials (REQ-AUTH-01, TBD-3)
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    SUPPORTED_FILE_TYPES = {"PDF", "DOCX", "TXT"}
    FALLBACK_MESSAGE = "I don't have information on that in the official NIIT University knowledge base. Please contact the relevant university department or Academic Office."

settings = Settings()
