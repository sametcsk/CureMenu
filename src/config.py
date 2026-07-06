from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

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
    LANGCHAIN_TRACING_V2: Optional[str] = "false"
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
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() in {"prod", "production", "staging"}

    @property
    def jwt_secret_key(self) -> str:
        if self.JWT_SECRET_KEY:
            return self.JWT_SECRET_KEY
        if self.is_production:
            raise ValueError("JWT_SECRET_KEY must be set in production.")
        return "curemenu_local_dev_secret_do_not_use_in_production"

    def validate_startup_security(self) -> None:
        """Fail fast for unsafe production configuration."""
        if not self.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY must be set.")
        if self.is_production and not self.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY must be set in production.")
        if self.is_production and self.CORS_ORIGINS.strip() == "*":
            raise ValueError("CORS_ORIGINS must be explicit in production.")

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
