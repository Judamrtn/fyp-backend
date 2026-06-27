from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "FYP Topic Repository"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "changeme"
    allowed_origins: str = "http://localhost:3000,http://localhost:8081"

    # Database
    database_url: str = "postgresql://postgres:password@localhost:5432/fyp_repository"
    async_database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/fyp_repository"

    # JWT
    jwt_secret_key: str = "changeme-jwt"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    # File Storage
    storage_provider: str = "local"          # s3 | minio | local
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "fyp-documents"
    s3_endpoint_url: str = ""                # MinIO or custom
    signed_url_expire_seconds: int = 900

    # File upload
    max_file_size_mb: int = 10
    allowed_file_types: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )

    # Similarity
    default_similarity_threshold: int = 80
    similarity_flag_threshold: int = 80

    # Password Reset
    reset_token_expire_minutes: int = 30
    frontend_url: str = "http://localhost:8081"

    # ── Derived helpers ─────────────────────────────────────────────────────────

    
    # HuggingFace Similarity API
    hf_api_key: str = ""
    hf_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    hf_api_url: str = "https://api-inference.huggingface.co/pipeline/feature-extraction"
    use_ai_similarity: bool = True

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def allowed_file_types_list(self) -> List[str]:
        return [t.strip() for t in self.allowed_file_types.split(",")]

    @property
    def max_file_size_bytes(self) -> int:
        return self.max_file_size_mb * 1024 * 1024


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere."""
    return Settings()


settings = get_settings()
