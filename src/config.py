import os

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional


_TRUTHY_VALUES = {"1", "true", "yes", "on"}
_REAL_USER_ENVIRONMENTS = {
    "prod",
    "production",
    "staging",
    "beta",
    "closed-beta",
    "closed_beta",
}
_LANGSMITH_ENABLE_ENV_KEYS = (
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
)
_LANGSMITH_HIDE_ENV_KEYS = (
    "LANGCHAIN_HIDE_INPUTS",
    "LANGCHAIN_HIDE_OUTPUTS",
    "LANGCHAIN_HIDE_METADATA",
    "LANGSMITH_HIDE_INPUTS",
    "LANGSMITH_HIDE_OUTPUTS",
    "LANGSMITH_HIDE_METADATA",
)


def _is_truthy(value: object) -> bool:
    return str(value or "").strip().lower() in _TRUTHY_VALUES

class Settings(BaseSettings):
    """
    Uygulama genelindeki tüm ayarları ve ortam değişkenlerini (environment variables) yöneten sınıf.
    Uygulama başlarken Pydantic bu sınıfı ayağa kaldırır, eğer zorunlu olan değişkenler .env içinde yoksa
    uygulama patlar ve geliştiriciyi uyarır. Bu da canlıda (production) sürpriz hataları engeller.
    """
    # Veritabanı
    APP_ENV: str = "development"
    CUREMENU_DB_PATH: str = "healmenu.db"
    CUREMENU_DB_TIMEOUT: int = 30
    DEBUG: bool = False
    ALLOWED_HOSTS: str = "localhost,127.0.0.1,testserver"
    TRUST_PROXY_HEADERS: bool = False
    
    # API Key'ler (canlıda .env ile doldurulmalı)
    GOOGLE_API_KEY: str
    # Backward compatible override. Leave empty to use role-specific model settings.
    GOOGLE_MODEL: Optional[str] = None
    GEMINI_TEXT_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_VISION_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_FAST_MODEL: str = "gemini-3.1-flash-lite"
    GEMINI_EVAL_MODEL: str = "gemini-3.5-flash"
    GEMINI_MODEL_FALLBACKS: str = "gemini-3.5-flash,gemini-2.5-flash,gemini-flash-latest"
    TAVILY_API_KEY: Optional[str] = None
    
    # LangSmith Observability
    # CureMenu opt-in flag. Provider-specific flags below are normalized by
    # configure_langsmith_tracing and cannot enable tracing on their own.
    LANGCHAIN_TRACING: bool = False
    LANGCHAIN_TRACING_V2: Optional[str] = "false"
    LANGSMITH_TRACING: Optional[str] = "false"
    LANGSMITH_TRACING_V2: Optional[str] = "false"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"
    LANGCHAIN_API_KEY: Optional[str] = None
    LANGCHAIN_PROJECT: Optional[str] = "default"

    # CORS Ayarları
    CORS_ORIGINS: str = "*"

    # JWT Güvenlik Ayarları
    JWT_SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    CUREMENU_COOKIE_SECURE: Optional[bool] = None

    # Chroma / log
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    CLINICAL_RAG_COLLECTION: str = "klinik_kutuphane_v2"
    CLINICAL_OFFICIAL_RAG_COLLECTION: str = "clinical_official_evidence_v1"
    EMBEDDINGS_LOCAL_ONLY: bool = True
    LOG_LEVEL: str = "INFO"
    ENABLE_NEMO_GUARDRAILS: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> List[str]:
        """CORS stringini listeye çeviren yardımcı özellik"""
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def allowed_hosts_list(self) -> List[str]:
        return [host.strip() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in {"prod", "production", "staging"}

    @property
    def is_real_user_environment(self) -> bool:
        return self.APP_ENV.strip().lower() in _REAL_USER_ENVIRONMENTS

    def configure_langsmith_tracing(self) -> bool:
        """Apply CureMenu's opt-in and privacy policy before LangChain imports."""
        provider_flag_requested = any(
            _is_truthy(value)
            for value in (
                self.LANGCHAIN_TRACING_V2,
                self.LANGSMITH_TRACING,
                self.LANGSMITH_TRACING_V2,
            )
        )
        explicitly_enabled = bool(self.LANGCHAIN_TRACING)

        if self.is_real_user_environment and (explicitly_enabled or provider_flag_requested):
            for key in _LANGSMITH_ENABLE_ENV_KEYS:
                os.environ[key] = "false"
            raise ValueError(
                "LangSmith tracing must be disabled in production, staging, and closed beta environments."
            )

        enabled = explicitly_enabled and not self.is_real_user_environment
        enabled_value = "true" if enabled else "false"
        for key in _LANGSMITH_ENABLE_ENV_KEYS:
            os.environ[key] = enabled_value

        # Suppression is intentionally stronger than partial redaction: no
        # prompt, response, health context, identifier, or metadata is sent.
        for key in _LANGSMITH_HIDE_ENV_KEYS:
            os.environ[key] = "true"

        self.LANGCHAIN_TRACING_V2 = enabled_value
        self.LANGSMITH_TRACING = enabled_value
        self.LANGSMITH_TRACING_V2 = enabled_value
        return enabled

    @property
    def jwt_secret_key(self) -> str:
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if self.is_production:
            raise ValueError("JWT_SECRET_KEY must be set in production.")
        return "curemenu_local_dev_secret_do_not_use_in_production"

    def validate_startup_security(self) -> None:
        """Fail fast for unsafe production configuration."""
        self.configure_langsmith_tracing()
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY must be set.")
        if self.is_production:
            if not self.JWT_SECRET_KEY:
                raise ValueError("JWT_SECRET_KEY must be set in production.")
            if self.JWT_SECRET_KEY == "curemenu_local_dev_secret_do_not_use_in_production":
                raise ValueError("JWT_SECRET_KEY must not use the development default in production.")
            if "*" in self.cors_origins_list:
                raise ValueError("CORS_ORIGINS must be explicit in production.")
            if self.CUREMENU_COOKIE_SECURE is not True:
                raise ValueError("CUREMENU_COOKIE_SECURE must be true in production.")
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")
            if not self.allowed_hosts_list or "*" in self.allowed_hosts_list:
                raise ValueError("ALLOWED_HOSTS must be explicit in production.")
            if set(self.allowed_hosts_list) == {"localhost", "127.0.0.1", "testserver"}:
                raise ValueError("ALLOWED_HOSTS must be configured for production hosts.")
            if self.CUREMENU_DB_PATH.strip() in {"", "healmenu.db"}:
                raise ValueError("CUREMENU_DB_PATH must be explicit in production.")

    @property
    def text_model_name(self) -> str:
        """Primary text model with old GOOGLE_MODEL override support."""
        return self.GOOGLE_MODEL or self.GEMINI_TEXT_MODEL

    @property
    def model_fallback_list(self) -> List[str]:
        """Deduplicated Gemini fallback chain."""
        candidates = [
            self.text_model_name,
            self.GEMINI_VISION_MODEL,
            self.GEMINI_FAST_MODEL,
            self.GEMINI_EVAL_MODEL,
        ]
        candidates.extend(
            item.strip()
            for item in (self.GEMINI_MODEL_FALLBACKS or "").split(",")
            if item.strip()
        )

        result: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in result:
                result.append(candidate)
        return result

# Uygulama ayağa kalkarken konfigürasyon bir kez oluşturulur (Singleton).
settings = Settings()
settings.configure_langsmith_tracing()
