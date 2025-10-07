"""
Configuration management for Text2SQL Analytics System.
Loads environment variables and provides configuration settings.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database Configuration
    db_host: str = Field(default="localhost", env="DB_HOST")
    db_port: int = Field(default=5432, env="DB_PORT")
    db_name: str = Field(default="northwind", env="DB_NAME")
    db_user: str = Field(default="northwind_user", env="DB_USER")
    db_password: str = Field(default="", env="DB_PASSWORD")
    
    # Admin Database User (for setup)
    db_admin_user: str = Field(default="postgres", env="DB_ADMIN_USER")
    db_admin_password: str = Field(default="", env="DB_ADMIN_PASSWORD")
    
    # Read-only Database User (for query execution)
    db_readonly_user: str = Field(default="northwind_readonly", env="DB_READONLY_USER")
    db_readonly_password: str = Field(default="", env="DB_READONLY_PASSWORD")
    
    # Test Database
    test_db_name: str = Field(default="northwind_test", env="TEST_DB_NAME")
    
    # Google Gemini API
    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")
    
    # Application Configuration
    query_timeout: int = Field(default=5, env="QUERY_TIMEOUT")
    max_result_rows: int = Field(default=1000, env="MAX_RESULT_ROWS")
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    cache_enabled: bool = Field(default=True, env="CACHE_ENABLED")
    cache_url: str = Field(default="", env="CACHE_URL")
    cache_ttl_seconds: int = Field(default=300, env="CACHE_TTL_SECONDS")
    history_store_path: str = Field(default="data/query_history.db", env="HISTORY_STORE_PATH")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
    
    @property
    def database_url(self) -> str:
        """Get database connection URL (read-only user for queries)."""
        return f"postgresql://{self.db_readonly_user}:{self.db_readonly_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def admin_database_url(self) -> str:
        """Get admin database connection URL."""
        return f"postgresql://{self.db_admin_user}:{self.db_admin_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def readonly_database_url(self) -> str:
        """Get read-only database connection URL."""
        return f"postgresql://{self.db_readonly_user}:{self.db_readonly_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    @property
    def test_database_url(self) -> str:
        """Get test database connection URL."""
        return f"postgresql://{self.db_admin_user}:{self.db_admin_password}@{self.db_host}:{self.db_port}/{self.test_db_name}"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings
