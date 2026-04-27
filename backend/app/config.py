from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jihye_gateway_url: str = "https://jihye.ucube.lgudax.cool/api/bedrock/us.anthropic.claude-sonnet-4-6"
    jwt_secret: str = "change-me-in-production-min-32-chars"
    jwt_expire_seconds: int = 3600

    database_url: str = "sqlite:///./data/telecom.db"
    chroma_path: str = "./data/chroma"
    documents_path: str = "./data/documents"
    images_path: str = "./data/images"
    markdowns_path: str = "./data/markdowns"

    backend_port: int = 8001
    # 로컬 기본값 — Railway 환경변수 CORS_ORIGINS 로 Vercel URL 추가
    cors_origins: str = "http://localhost:5173,http://localhost:1024,https://telecom-wiki-agent-kbbr.vercel.app,https://telecom-wiki-agent.vercel.app"

    # 전처리 도구
    preprocessor_frontend_url: str = "http://localhost:1024"

    # Supabase Storage (설정 시 로컬 파일시스템 대신 사용)
    # Supabase 대시보드 → Settings → API → service_role 키 사용
    supabase_url: str = ""
    supabase_key: str = ""       # service_role secret key
    supabase_bucket: str = "telecom-wiki"

    threegpp_enabled: bool = True

    # 검색 임계값: 이 이하이면 3GPP 폴백 실행
    relevance_threshold: float = 0.7
    search_top_k: int = 10

    # 청킹 설정
    chunk_max_tokens: int = 512
    chunk_overlap_tokens: int = 64


settings = Settings()
