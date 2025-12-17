"""Configuration management for ArrTheAudio."""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


class PathOverride(BaseModel):
    """Path-specific language priority override."""

    path: str = Field(..., description="Glob pattern for file paths")
    language_priority: List[str] = Field(..., description="Language priority for this path")


class PathMapping(BaseModel):
    """Path mapping for Arr integration."""

    remote: str = Field(..., description="Remote path from Sonarr/Radarr")
    local: str = Field(..., description="Local path on daemon filesystem")


class TMDBConfig(BaseModel):
    """TMDB API configuration."""

    enabled: bool = Field(default=True, description="Enable TMDB integration")
    api_key: Optional[str] = Field(default=None, description="TMDB API key")
    cache_ttl_days: int = Field(default=30, description="Cache TTL in days")
    cache_path: str = Field(default="/config/tmdb_cache.db", description="Cache database path")

    @field_validator("api_key")
    @classmethod
    def validate_api_key(cls, v: Optional[str], info) -> Optional[str]:
        """Validate API key is provided when TMDB is enabled."""
        # Access other field values through info.data
        enabled = info.data.get("enabled", True)
        if enabled and not v:
            raise ValueError("TMDB API key required when TMDB is enabled")
        return v


class ContainersConfig(BaseModel):
    """Container format support configuration."""

    mkv: bool = Field(default=True, description="Enable MKV support")
    mp4: bool = Field(default=True, description="Enable MP4 support")


class APIConfig(BaseModel):
    """API server configuration."""

    host: str = Field(default="0.0.0.0", description="API host")
    port: int = Field(default=9393, description="API port")
    workers: int = Field(default=2, description="Number of workers")
    webhook_secret: Optional[str] = Field(default=None, description="Webhook signature secret")


class ProcessingConfig(BaseModel):
    """Processing configuration."""

    max_queue_size: int = Field(default=100, description="Maximum queue size")
    worker_count: int = Field(default=2, description="Number of worker threads")
    timeout_seconds: int = Field(default=300, description="Processing timeout")
    retry_attempts: int = Field(default=2, description="Number of retry attempts")


class LoggingConfig(BaseModel):
    """Logging configuration."""

    format: str = Field(default="json", description="Log format (json or text)")
    level: str = Field(default="info", description="Log level")
    output: str = Field(default="/logs/arrtheaudio.log", description="Log output path")

    @field_validator("format")
    @classmethod
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        if v not in ("json", "text"):
            raise ValueError("Log format must be 'json' or 'text'")
        return v

    @field_validator("level")
    @classmethod
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        if v.lower() not in ("debug", "info", "warning", "error", "critical"):
            raise ValueError("Invalid log level")
        return v.lower()


class ExecutionConfig(BaseModel):
    """Execution configuration."""

    dry_run: bool = Field(default=False, description="Dry run mode")
    skip_if_correct: bool = Field(default=True, description="Skip if track already correct")


class Config(BaseModel):
    """Main configuration model."""

    language_priority: List[str] = Field(
        default=["eng"], description="Global language priority"
    )
    path_overrides: List[PathOverride] = Field(
        default_factory=list, description="Path-specific language overrides"
    )
    path_mappings: List[PathMapping] = Field(
        default_factory=list, description="Arr path mappings"
    )
    tmdb: TMDBConfig = Field(default_factory=TMDBConfig, description="TMDB configuration")
    containers: ContainersConfig = Field(
        default_factory=ContainersConfig, description="Container support"
    )
    api: APIConfig = Field(default_factory=APIConfig, description="API configuration")
    processing: ProcessingConfig = Field(
        default_factory=ProcessingConfig, description="Processing configuration"
    )
    logging: LoggingConfig = Field(default_factory=LoggingConfig, description="Logging configuration")
    execution: ExecutionConfig = Field(
        default_factory=ExecutionConfig, description="Execution configuration"
    )

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Config instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path) as f:
            raw_config = yaml.safe_load(f)

        if raw_config is None:
            raw_config = {}

        # Substitute environment variables
        raw_config = cls._substitute_env_vars(raw_config)

        return cls(**raw_config)

    @staticmethod
    def _substitute_env_vars(obj: Any) -> Any:
        """Recursively substitute environment variables in configuration.

        Replaces ${VAR_NAME} with os.environ['VAR_NAME'].

        Args:
            obj: Configuration object (dict, list, str, etc.)

        Returns:
            Object with environment variables substituted
        """
        if isinstance(obj, dict):
            return {key: Config._substitute_env_vars(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [Config._substitute_env_vars(item) for item in obj]
        elif isinstance(obj, str):
            # Match ${VAR_NAME} pattern
            pattern = r"\$\{([^}]+)\}"

            def replace_var(match):
                var_name = match.group(1)
                value = os.environ.get(var_name)
                if value is None:
                    raise ValueError(
                        f"Environment variable '{var_name}' not found "
                        f"(referenced in configuration)"
                    )
                return value

            return re.sub(pattern, replace_var, obj)
        else:
            return obj

    @classmethod
    def from_defaults(cls) -> "Config":
        """Create configuration with default values.

        Returns:
            Config instance with defaults
        """
        return cls()


def load_config(path: Optional[str | Path] = None) -> Config:
    """Load configuration from file or use defaults.

    Args:
        path: Optional path to configuration file. If None, uses defaults.

    Returns:
        Config instance
    """
    if path is None:
        return Config.from_defaults()

    return Config.from_yaml(path)
