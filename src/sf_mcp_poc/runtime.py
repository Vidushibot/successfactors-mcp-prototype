from functools import lru_cache

from .audit import AuditRepository
from .config import get_settings
from .provider import (
    ConfiguredOAuthTokenProvider,
    MockProvider,
    ODataProvider,
    SuccessFactorsProvider,
)
from .service import HRToolService


@lru_cache
def get_service() -> HRToolService:
    settings = get_settings()
    audit = AuditRepository(settings.database_url)
    if settings.app_mode == "real":
        provider: SuccessFactorsProvider = ODataProvider(
            settings.sf_api_base_url,
            ConfiguredOAuthTokenProvider(),
            settings.sf_request_timeout_seconds,
            settings.sf_verify_tls,
            settings.sf_max_page_size,
        )
    else:
        provider = MockProvider()
    return HRToolService(provider, audit, settings.sf_max_page_size)
