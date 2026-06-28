from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "info"
    coordinator_base_url: str = "http://localhost:8080"

    use_fake_storage: bool = True

    web_api_key: str = "dev-web-key"
    worker_api_key: str = "dev-worker-key"

    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_audio_bucket: str = "inference-audio"
    supabase_photo_bucket: str = "inference-photos"

    onemap_email: str = ""
    onemap_password: str = ""
    onemap_base_url: str = "https://www.onemap.gov.sg"

    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def onemap_configured(self) -> bool:
        return bool(self.onemap_email and self.onemap_password)


settings = Settings()
