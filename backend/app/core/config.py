from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from pathlib import Path
from decimal import Decimal


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://movewise:movewise_local@localhost:5432/movewise"
    session_secret: str = "development-only-change-me"
    cors_origins: str = "http://localhost:3000"
    private_upload_dir: str = "./private_uploads"
    max_upload_bytes: int = 10_485_760
    embedding_provider: str = "openai"
    embedding_model: str = "text-embedding-3-small"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: str | None = None
    run_max_tool_steps: int = 18
    run_max_seconds: int = 120
    run_max_tokens: int = 40000
    environment: str = "development"
    auth_mode: str = "development"
    oidc_metadata_url: str | None = None
    oidc_client_id: str | None = None
    oidc_client_secret: str | None = None
    oidc_issuer: str | None = None
    frontend_url: str = "http://localhost:3000"
    public_api_url: str = "http://localhost:8000"
    ai_requests_per_minute: int = 20
    uploads_per_hour: int = 10
    max_workspace_upload_bytes: int = 104857600
    evaluation_mock_mode: bool = False
    llm_input_usd_per_1m: Decimal | None = None
    llm_output_usd_per_1m: Decimal | None = None

    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True, extra="ignore")

    @model_validator(mode="after")
    def production_guard(self):
        if self.auth_mode not in {"development", "oidc"}:
            raise ValueError("AUTH_MODE must be development or oidc")
        if self.llm_provider == 'ollama' or self.embedding_provider == 'ollama':
            if not (self.ollama_base_url.startswith('http://localhost:') or
                    self.ollama_base_url.startswith('http://127.0.0.1:')):
                raise ValueError('OLLAMA_BASE_URL must point to local loopback for this configuration')
        if self.environment == "production":
            if self.evaluation_mock_mode or self.embedding_provider == 'mock' or self.llm_provider != 'openai':
                raise ValueError('Production cannot use evaluation mock providers')
            if self.auth_mode != "oidc":
                raise ValueError("Production requires AUTH_MODE=oidc")
            if not all([self.oidc_metadata_url,self.oidc_client_id,self.oidc_client_secret,self.oidc_issuer]):
                raise ValueError("Production OIDC configuration is incomplete")
            if len(self.session_secret) < 32 or self.session_secret == "development-only-change-me":
                raise ValueError("Production SESSION_SECRET must be a long random value")
            if not self.frontend_url.startswith("https://") or not self.public_api_url.startswith("https://") or any(not origin.strip().startswith("https://") for origin in self.cors_origins.split(",")):
                raise ValueError("Production frontend and CORS origins require HTTPS")
            if not Path(self.private_upload_dir).is_absolute():
                raise ValueError("Production PRIVATE_UPLOAD_DIR must be an absolute durable path")
        return self


settings = Settings()
