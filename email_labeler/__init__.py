"""Email Auto-Labeler package for Gmail."""

from .database import EmailDatabase
from .email_processor import EmailProcessor
from .factory import (
    create_database_connection,
    create_email_auto_labeler,
    create_email_database,
    create_email_processor,
    create_gmail_client,
    create_llm_client,
    create_llm_service,
    create_test_dependencies,
)
from .labeler import EmailAutoLabeler
from .llm_service import LLMService
from .metrics import MetricsTracker

__version__ = "2.1.0"
__all__ = [
    "EmailAutoLabeler",
    "EmailDatabase",
    "LLMService",
    "EmailProcessor",
    "MetricsTracker",
    # Factory functions
    "create_email_auto_labeler",
    "create_email_database",
    "create_email_processor",
    "create_llm_service",
    "create_test_dependencies",
    "create_database_connection",
    "create_gmail_client",
    "create_llm_client",
]
