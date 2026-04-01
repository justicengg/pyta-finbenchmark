from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./pyta_eval.db"
    anthropic_api_key: str = ""
    judge_model: str = "claude-opus-4-6"
    main_backend_webhook_secret: str = ""
    # Price data sources (fallback order: akshare → tushare → yfinance)
    tushare_token: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
