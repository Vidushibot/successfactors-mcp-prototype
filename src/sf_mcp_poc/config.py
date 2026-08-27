from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_mode: Literal["mock", "demo", "real"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-5.4-mini"
    database_url: str = "sqlite:///./data/audit.db"
    sf_api_base_url: str = ""
    sf_company_id: str = ""
    sf_client_id: str = ""
    sf_private_key_path: Path | None = None
    sf_token_url: str = ""
    sf_request_timeout_seconds: int = Field(20, ge=1, le=120)
    sf_max_page_size: int = Field(20, ge=1, le=100)
    sf_verify_tls: bool = True
    mcp_host: str = "127.0.0.1"
    mcp_port: int = 8001
    mcp_transport: Literal["streamable-http", "stdio"] = "streamable-http"
    mcp_internal_token: str = ""
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    streamlit_port: int = 8501
    log_level: str = "INFO"
    log_employee_ids: bool = False
    enable_response_cache: bool = False
    cache_ttl_seconds: int = Field(60, ge=1, le=3600)
    demo_max_turns: int = Field(8, ge=2, le=20)
    demo_max_output_tokens: int = Field(700, ge=100, le=4000)
    demo_daily_token_budget: int = Field(100_000, ge=1_000, le=10_000_000)
    openai_input_cost_per_1m: float = Field(0, ge=0)
    openai_output_cost_per_1m: float = Field(0, ge=0)
    enable_openai_tracing: bool = False

    @model_validator(mode="after")
    def validate_mode(self) -> "Settings":
        if self.app_mode == "demo" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required in demo mode")
        if self.app_mode == "demo" and not self.mcp_internal_token:
            raise ValueError("MCP_INTERNAL_TOKEN is required in demo mode")
        if self.app_mode == "real":
            required = {
                "SF_API_BASE_URL": self.sf_api_base_url,
                "SF_COMPANY_ID": self.sf_company_id,
                "SF_CLIENT_ID": self.sf_client_id,
                "SF_PRIVATE_KEY_PATH": self.sf_private_key_path,
                "SF_TOKEN_URL": self.sf_token_url,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise ValueError(f"Real mode is missing configuration: {', '.join(missing)}")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
