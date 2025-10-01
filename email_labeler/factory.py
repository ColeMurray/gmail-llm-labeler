"""Factory functions for creating dependency-injected instances."""

import logging
import sqlite3
from typing import Optional

from googleapiclient.discovery import Resource
from openai import OpenAI

from .config import (
    DATABASE_FILE,
    LLM_SERVICE,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)
from .database import EmailDatabase
from .email_processor import EmailProcessor
from .gmail_utils import get_gmail_client
from .labeler import EmailAutoLabeler
from .llm_service import LLMService
from .metrics import MetricsTracker


def create_database_connection(database_file: str = DATABASE_FILE) -> sqlite3.Connection:
    """Create a SQLite database connection.

    Args:
        database_file: Path to the database file.

    Returns:
        SQLite connection object.
    """
    return sqlite3.connect(database_file)


def create_gmail_client(port: int = 8080) -> Resource:
    """Create an authenticated Gmail API client.

    Args:
        port: Port for OAuth flow.

    Returns:
        Gmail API client resource.
    """
    return get_gmail_client(port=port)


def create_llm_client(service: str = LLM_SERVICE) -> OpenAI:
    """Create an LLM client based on configuration.

    Args:
        service: LLM service type ("OpenAI" or "Ollama").

    Returns:
        OpenAI client instance.
    """
    if service == "Ollama":
        logging.info(f"Creating Ollama client at {OLLAMA_BASE_URL}")
        return OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama")  # Dummy key for Ollama
    else:
        logging.info("Creating OpenAI client")
        return OpenAI(api_key=OPENAI_API_KEY)


def create_email_database(
    conn: Optional[sqlite3.Connection] = None, database_file: str = DATABASE_FILE
) -> EmailDatabase:
    """Create an EmailDatabase instance with optional connection injection.

    Args:
        conn: Optional SQLite connection to inject.
        database_file: Database file path (used if conn is None).

    Returns:
        EmailDatabase instance.
    """
    if conn is None:
        conn = create_database_connection(database_file)
    return EmailDatabase(conn=conn, database_file=database_file)


def create_email_processor(
    gmail_client: Optional[Resource] = None, port: int = 8080
) -> EmailProcessor:
    """Create an EmailProcessor instance with optional Gmail client injection.

    Args:
        gmail_client: Optional Gmail API client to inject.
        port: Port for OAuth flow (used if gmail_client is None).

    Returns:
        EmailProcessor instance.
    """
    if gmail_client is None:
        gmail_client = create_gmail_client(port)
    return EmailProcessor(gmail_client=gmail_client)


def create_llm_service(
    categories: list[str],
    max_content_length: int = 4000,
    llm_client: Optional[OpenAI] = None,
    model: Optional[str] = None,
    service: str = LLM_SERVICE,
) -> LLMService:
    """Create an LLMService instance with optional client injection.

    Args:
        categories: List of category labels for email classification.
        max_content_length: Maximum length of email content before truncation.
        llm_client: Optional OpenAI client to inject.
        model: Optional model name override.
        service: LLM service type (used if llm_client is None).

    Returns:
        LLMService instance.
    """
    if llm_client is None:
        llm_client = create_llm_client(service)
        if model is None:
            model = OLLAMA_MODEL if service == "Ollama" else OPENAI_MODEL
    return LLMService(
        categories=categories,
        max_content_length=max_content_length,
        llm_client=llm_client,
        model=model,
    )


def create_email_auto_labeler(
    categories: list[str],
    max_content_length: int = 4000,
    database: Optional[EmailDatabase] = None,
    llm_service: Optional[LLMService] = None,
    email_processor: Optional[EmailProcessor] = None,
    metrics_tracker: Optional[MetricsTracker] = None,
    test_mode: bool = False,
    preview_mode: bool = False,
    # Configuration options
    database_file: str = DATABASE_FILE,
    gmail_port: int = 8080,
    llm_service_type: str = LLM_SERVICE,
) -> EmailAutoLabeler:
    """Create a fully configured EmailAutoLabeler instance.

    This factory function allows for easy creation of EmailAutoLabeler
    with all dependencies properly injected. It supports both:
    1. Providing pre-configured dependencies for testing
    2. Creating default dependencies from configuration

    Args:
        categories: List of category labels for email classification.
        max_content_length: Maximum length of email content before truncation.
        database: Optional EmailDatabase instance.
        llm_service: Optional LLMService instance.
        email_processor: Optional EmailProcessor instance.
        metrics_tracker: Optional MetricsTracker instance.
        test_mode: Whether to run in test mode.
        preview_mode: Whether to run in preview mode.
        database_file: Database file path (for creating database).
        gmail_port: Gmail OAuth port (for creating email processor).
        llm_service_type: LLM service type (for creating LLM service).

    Returns:
        Fully configured EmailAutoLabeler instance.
    """
    # Create dependencies if not provided
    if database is None:
        database = create_email_database(database_file=database_file)

    if llm_service is None:
        llm_service = create_llm_service(
            categories=categories, max_content_length=max_content_length, service=llm_service_type
        )

    if email_processor is None:
        email_processor = create_email_processor(port=gmail_port)

    if metrics_tracker is None and test_mode:
        metrics_tracker = MetricsTracker()

    return EmailAutoLabeler(
        categories=categories,
        max_content_length=max_content_length,
        database=database,
        llm_service=llm_service,
        email_processor=email_processor,
        metrics_tracker=metrics_tracker,
        test_mode=test_mode,
        preview_mode=preview_mode,
    )


def create_test_dependencies(categories: list[str] = None, max_content_length: int = 4000):
    """Create a set of test dependencies with in-memory database.

    This is useful for unit testing.

    Args:
        categories: Optional list of category labels. If not provided, uses defaults.
        max_content_length: Maximum length of email content before truncation.

    Returns:
        Tuple of (database, llm_service, email_processor, metrics_tracker)
    """
    # Use default categories if not provided
    if categories is None:
        from .pipeline.config import TransformConfig

        categories = TransformConfig().categories

    # Create in-memory database
    conn = sqlite3.connect(":memory:")
    database = EmailDatabase(conn=conn, database_file=":memory:")

    # Create mock LLM service (you could also use a mock client here)
    llm_client = create_llm_client("OpenAI")  # Or use a mock
    llm_service = LLMService(
        categories=categories,
        max_content_length=max_content_length,
        llm_client=llm_client,
        model="gpt-3.5-turbo",
    )

    # Create email processor (you might want to mock the Gmail client)
    email_processor = EmailProcessor(gmail_client=None)  # Will create its own

    # Create metrics tracker
    metrics_tracker = MetricsTracker()

    return database, llm_service, email_processor, metrics_tracker
