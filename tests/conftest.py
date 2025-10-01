"""Shared pytest fixtures for email labeler tests."""

import sqlite3
import tempfile
from datetime import datetime
from typing import List, Tuple
from unittest.mock import MagicMock, Mock, patch

import pytest

from email_labeler.database import EmailDatabase
from email_labeler.email_processor import EmailProcessor
from email_labeler.labeler import EmailAutoLabeler
from email_labeler.llm_service import LLMService
from email_labeler.pipeline.base import EmailRecord, EnrichedEmailRecord, PipelineContext
from email_labeler.pipeline.config import (
    ExtractConfig,
    LoadConfig,
    PipelineConfig,
    SyncConfig,
    TransformConfig,
)


@pytest.fixture
def temp_database():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        conn = sqlite3.connect(tmp.name)
        yield conn, tmp.name
        conn.close()


@pytest.fixture
def mock_sqlite_connection() -> Tuple[MagicMock, MagicMock]:
    """Create a mock SQLite connection."""
    mock_conn = MagicMock(spec=sqlite3.Connection)
    mock_cursor = MagicMock(spec=sqlite3.Cursor)
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchone.return_value = None
    mock_cursor.fetchall.return_value = []
    return mock_conn, mock_cursor


@pytest.fixture
def database_with_data(temp_database):
    """Create a database with sample test data."""
    conn, db_file = temp_database
    db = EmailDatabase(conn=conn)

    # Add some test data
    test_emails = [
        (
            "email1",
            "Work Project",
            "john@company.com",
            datetime.now().isoformat(),
            "Meeting tomorrow",
        ),
        (
            "email2",
            "Newsletter",
            "news@newsletter.com",
            datetime.now().isoformat(),
            "Weekly updates",
        ),
        ("email3", "Personal", "friend@gmail.com", datetime.now().isoformat(), "Dinner plans"),
    ]

    for email_id, subject, sender, received_date, content in test_emails:
        db.save_email(email_id, subject, sender, received_date, content)
        db.update_email_labels(email_id, "Work", ["Label_1"])

    yield db
    conn.close()


@pytest.fixture
def mock_gmail_client():
    """Create a mock Gmail API client."""
    mock_client = MagicMock()

    # Mock the users().messages() chain
    mock_messages = MagicMock()
    mock_client.users.return_value.messages.return_value = mock_messages

    # Mock list response
    mock_messages.list.return_value.execute.return_value = {
        "messages": [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"},
        ]
    }

    # Mock get response
    mock_messages.get.return_value.execute.return_value = {
        "id": "msg1",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "Test Subject"},
                {"name": "From", "value": "test@example.com"},
                {"name": "Date", "value": "Mon, 01 Jan 2024 12:00:00 +0000"},
            ],
            "body": {"data": "VGVzdCBjb250ZW50"},  # base64 encoded "Test content"
        },
    }

    # Mock modify response
    mock_messages.modify.return_value.execute.return_value = {}

    # Mock labels
    mock_labels = MagicMock()
    mock_client.users.return_value.labels.return_value = mock_labels
    mock_labels.list.return_value.execute.return_value = {
        "labels": [
            {"id": "Label_1", "name": "Work", "type": "user"},
            {"id": "Label_2", "name": "Personal", "type": "user"},
        ]
    }
    mock_labels.create.return_value.execute.return_value = {"id": "Label_3", "name": "NewLabel"}

    return mock_client


@pytest.fixture
def mock_openai_client():
    """Create a mock OpenAI client."""
    mock_client = MagicMock()

    # Mock chat completion response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = '{"category": "Work", "explanation": "Business related email"}'

    mock_client.chat.completions.create.return_value = mock_response

    return mock_client


@pytest.fixture
def sample_email_records() -> List[EmailRecord]:
    """Create sample email records for testing."""
    return [
        EmailRecord(
            id="email1",
            subject="Weekly Team Meeting",
            sender="boss@company.com",
            content="Please join the weekly team meeting tomorrow at 2 PM.",
            received_date="2024-01-01T10:00:00Z",
        ),
        EmailRecord(
            id="email2",
            subject="Newsletter Subscription",
            sender="newsletter@example.com",
            content="Thank you for subscribing to our newsletter!",
            received_date="2024-01-01T11:00:00Z",
        ),
        EmailRecord(
            id="email3",
            subject="Lunch Plans",
            sender="friend@gmail.com",
            content="Want to grab lunch this Friday?",
            received_date="2024-01-01T12:00:00Z",
        ),
    ]


@pytest.fixture
def sample_enriched_email_records(sample_email_records) -> List[EnrichedEmailRecord]:
    """Create sample enriched email records for testing."""
    return [
        EnrichedEmailRecord(
            **sample_email_records[0].__dict__,
            category="Work",
            explanation="Business meeting notification",
            confidence=0.9,
            processing_time=1.5,
        ),
        EnrichedEmailRecord(
            **sample_email_records[1].__dict__,
            category="Newsletter",
            explanation="Subscription confirmation",
            confidence=0.8,
            processing_time=1.2,
        ),
        EnrichedEmailRecord(
            **sample_email_records[2].__dict__,
            category="Personal",
            explanation="Social invitation",
            confidence=0.85,
            processing_time=1.0,
        ),
    ]


@pytest.fixture
def pipeline_config():
    """Create a test pipeline configuration."""
    return PipelineConfig(
        extract=ExtractConfig(
            source="gmail", gmail_query="is:unread", batch_size=10, max_results=100
        ),
        transform=TransformConfig(
            llm_service="openai",
            model="gpt-3.5-turbo",
            max_content_length=4000,
            timeout=30,
            skip_on_error=True,
            categories=[
                "Marketing",
                "Response Needed / High Priority",
                "Bills",
                "Subscriptions",
                "Newsletters",
                "Personal",
                "Work",
                "Events",
                "Travel",
                "Receipts",
                "Low quality",
                "Notifications",
                "Other",
            ],
        ),
        load=LoadConfig(
            apply_labels=True,
            create_missing_labels=True,
            category_actions={
                "Marketing": ["apply_label", "archive"],
                "Response Needed / High Priority": ["apply_label", "star"],
                "Bills": ["apply_label", "star"],
                "Newsletters": ["apply_label", "archive"],
                "Low quality": ["apply_label", "archive", "mark_as_read"],
                "Notifications": ["apply_label", "mark_as_read"],
            },
            default_actions=["apply_label"],
        ),
        sync=SyncConfig(
            database_path="test_email_pipeline.db",
            save_metrics=True,
            track_history=True,
            batch_size=10,
            track_metrics=True,
        ),
    )


@pytest.fixture
def pipeline_context(pipeline_config):
    """Create a test pipeline context."""
    return PipelineContext.create(
        config=pipeline_config, dry_run=False, preview_mode=False, test_mode=True
    )


@pytest.fixture
def pipeline_context_no_test_mode(pipeline_config):
    """Create a pipeline context without test mode for transform tests."""
    return PipelineContext.create(
        config=pipeline_config, dry_run=False, preview_mode=False, test_mode=False
    )


@pytest.fixture
def mock_metrics_tracker():
    """Create a mock metrics tracker."""
    tracker = MagicMock()
    tracker.calculate_metrics.return_value = {
        "emails_processed": 0,
        "emails_categorized": 0,
        "labels_applied": 0,
        "processing_time": 0.0,
    }
    tracker.add_test_result.return_value = None
    tracker.add_result.return_value = None
    return tracker


@pytest.fixture
def email_database(mock_sqlite_connection):
    """Create an EmailDatabase instance with mocked connection."""
    mock_conn, mock_cursor = mock_sqlite_connection
    return EmailDatabase(conn=mock_conn)


@pytest.fixture
def llm_service(mock_openai_client):
    """Create a mock LLMService instance."""

    mock_llm_service = MagicMock(spec=LLMService)

    # Configure common mock return values
    mock_llm_service.categorize_email.return_value = ("Work", "Business email")

    return mock_llm_service


@pytest.fixture
def real_llm_service(mock_openai_client, pipeline_config):
    """Create a real LLMService instance with mocked client."""

    return LLMService(
        categories=pipeline_config.transform.categories,
        llm_client=mock_openai_client,
        model="gpt-3.5-turbo",
    )


@pytest.fixture
def email_processor(mock_gmail_client):
    """Create a real EmailProcessor instance with mocked gmail client."""

    return EmailProcessor(gmail_client=mock_gmail_client)


@pytest.fixture
def mock_email_processor(mock_gmail_client):
    """Create a mock EmailProcessor instance for tests that need to mock methods."""

    mock_processor = MagicMock(spec=EmailProcessor)
    mock_processor.gmail = mock_gmail_client

    # Configure common mock return values
    mock_processor.prepare_email_content.return_value = (
        "Subject: Test\\nFrom: test@example.com\\n\\nTest content"
    )
    mock_processor.get_or_create_label.return_value = "Label_1"
    mock_processor.add_labels_to_email.return_value = True
    mock_processor.remove_from_inbox.return_value = True
    mock_processor.fetch_emails_from_gmail.return_value = []

    return mock_processor


@pytest.fixture
def email_auto_labeler(mock_email_processor, llm_service, mock_metrics_tracker, pipeline_config):
    """Create an EmailAutoLabeler instance with mocked dependencies."""
    labeler = EmailAutoLabeler(
        categories=pipeline_config.transform.categories,
        email_processor=mock_email_processor,
        llm_service=llm_service,
        metrics_tracker=mock_metrics_tracker,
    )

    # Mock the database
    labeler.database = MagicMock()
    labeler.database.get_unprocessed_emails.return_value = []
    labeler.database.update_email_labels.return_value = None
    labeler.database.close.return_value = None

    return labeler


@pytest.fixture(autouse=True)
def mock_logging():
    """Mock logging to prevent log output during tests."""
    with patch("logging.info"), patch("logging.error"), patch("logging.warning"), patch(
        "logging.debug"
    ):
        yield


@pytest.fixture
def cli_args():
    """Create sample CLI arguments for testing."""
    return type(
        "Args",
        (),
        {
            "test": False,
            "preview": False,
            "limit": None,
            "output": None,
            "use_gmail": False,
            "query": "is:unread",
        },
    )()


# Utility fixtures for common mock patterns


@pytest.fixture
def mock_file_operations():
    """Mock file operations."""
    with patch("builtins.open", create=True) as mock_open, patch(
        "os.path.exists", return_value=True
    ), patch("json.dump"), patch("json.load", return_value={}):
        yield mock_open


@pytest.fixture
def mock_datetime():
    """Mock datetime for consistent testing."""
    with patch("email_labeler.database.datetime") as mock_dt:
        mock_now = Mock()
        mock_now.isoformat.return_value = "2024-01-01T12:00:00"
        mock_dt.now.return_value = mock_now
        yield mock_dt


# Parametrized fixtures for different test scenarios


@pytest.fixture(params=[True, False])
def test_mode(request):
    """Parametrize tests for both test and normal modes."""
    return request.param


@pytest.fixture(params=["OpenAI", "Ollama"])
def llm_service_type(request):
    """Parametrize tests for different LLM services."""
    return request.param


@pytest.fixture(params=[1, 5, 10])
def batch_size(request):
    """Parametrize tests for different batch sizes."""
    return request.param
