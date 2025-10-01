"""Configuration module for email auto-labeler."""

import logging
import os
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def get_default_data_dir() -> Path:
    """Get platform-appropriate default data directory.

    Returns:
        Path to default data directory:
        - Linux/Mac: ~/.local/share/gmail-llm-labeler/
        - Windows: %LOCALAPPDATA%/gmail-llm-labeler/
        - Fallback: ./data/
    """
    if os.name == "posix":  # Unix-like systems
        base = Path.home() / ".local" / "share" / "gmail-llm-labeler"
    elif os.name == "nt":  # Windows
        base = (
            Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "gmail-llm-labeler"
        )
    else:
        base = Path("./data")

    return base


def get_default_log_dir() -> Path:
    """Get platform-appropriate default log directory.

    Returns:
        Path to default log directory:
        - Linux/Mac: ~/.local/share/gmail-llm-labeler/logs/
        - Windows: %LOCALAPPDATA%/gmail-llm-labeler/logs/
        - Fallback: ./logs/
    """
    return get_default_data_dir() / "logs"


class PathConfig:
    """Manages configurable file paths for the application.

    Priority order:
    1. Environment variables
    2. YAML configuration file
    3. Default values

    All paths are resolved to absolute paths and parent directories
    are created automatically if they don't exist.
    """

    def __init__(self, config_file: Optional[str] = None):
        """Initialize path configuration.

        Args:
            config_file: Optional path to YAML config file to load paths from.
        """
        # Load from YAML if provided
        yaml_paths = {}
        if config_file and Path(config_file).exists():
            with open(config_file) as f:
                data = yaml.safe_load(f)
                yaml_paths = data.get("paths", {})

        # Get default directories
        default_data_dir = get_default_data_dir()
        default_log_dir = get_default_log_dir()

        # Configure paths with priority: env var > yaml > default
        self.database_file = self._resolve_path(
            os.getenv("DATABASE_FILE"),
            yaml_paths.get("database_file"),
            default_data_dir / "email_pipeline.db",
        )

        self.llm_log_file = self._resolve_path(
            os.getenv("LLM_LOG_FILE"),
            yaml_paths.get("llm_log_file"),
            default_log_dir / "llm_interactions.jsonl",
        )

        self.error_log_file = self._resolve_path(
            os.getenv("ERROR_LOG_FILE"),
            yaml_paths.get("error_log_file"),
            default_log_dir / "categorization_errors.log",
        )

        self.test_output_file = self._resolve_path(
            os.getenv("TEST_OUTPUT_FILE"),
            yaml_paths.get("test_output_file"),
            default_data_dir / "test_results.csv",
        )

        self.test_summary_file = self._resolve_path(
            os.getenv("TEST_SUMMARY_FILE"),
            yaml_paths.get("test_summary_file"),
            default_data_dir / "test_summary.json",
        )

        # Create directories if they don't exist
        self._ensure_directories()

    def _resolve_path(
        self, env_value: Optional[str], yaml_value: Optional[str], default_value: Path
    ) -> Path:
        """Resolve a path from environment, YAML, or default.

        Args:
            env_value: Value from environment variable
            yaml_value: Value from YAML config
            default_value: Default path value

        Returns:
            Resolved absolute Path object
        """
        if env_value:
            return Path(env_value).resolve()
        elif yaml_value:
            return Path(yaml_value).resolve()
        else:
            return default_value.resolve()

    def _ensure_directories(self):
        """Create parent directories for all configured paths if they don't exist."""
        for path_attr in [
            "database_file",
            "llm_log_file",
            "error_log_file",
            "test_output_file",
            "test_summary_file",
        ]:
            path = getattr(self, path_attr)
            path.parent.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        """Export configuration as dictionary.

        Returns:
            Dictionary of path configurations as strings
        """
        return {
            "database_file": str(self.database_file),
            "llm_log_file": str(self.llm_log_file),
            "error_log_file": str(self.error_log_file),
            "test_output_file": str(self.test_output_file),
            "test_summary_file": str(self.test_summary_file),
        }


# Initialize path configuration
# Check for custom config file from environment
_config_file = os.getenv("CONFIG_FILE")
_path_config = PathConfig(config_file=_config_file)

# File paths - backward compatible with old code
DATABASE_FILE = str(_path_config.database_file)
LLM_LOG_FILE = str(_path_config.llm_log_file)
ERROR_LOG_FILE = str(_path_config.error_log_file)
TEST_OUTPUT_FILE = str(_path_config.test_output_file)
TEST_SUMMARY_FILE = str(_path_config.test_summary_file)

# Setup logging
log_level = os.getenv("LOG_LEVEL", "INFO")
logging.basicConfig(
    level=getattr(logging, log_level.upper(), logging.INFO),
    format="%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s",
)

# Gmail labels
PROCESSED_LABEL = "Processed"

# LLM Configuration
LLM_SERVICE = os.getenv("LLM_SERVICE", "OpenAI")  # "OpenAI" or "Ollama"

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1")
GPT_OSS_REASONING = os.getenv("GPT_OSS_REASONING", "medium")

# Email processing limits
MAX_CONTENT_LENGTH = 4000
DEFAULT_BATCH_SIZE = 100

# Modes
PREVIEW_MODE = False
TEST_MODE = False
