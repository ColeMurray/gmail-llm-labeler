"""Tests for factory functions."""

import sqlite3
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from email_labeler.database import EmailDatabase
from email_labeler.email_processor import EmailProcessor
from email_labeler.factory import (
    create_database_connection,
    create_email_auto_labeler,
    create_email_database,
    create_email_processor,
    create_gmail_client,
    create_llm_client,
    create_llm_service,
    create_test_dependencies,
)
from email_labeler.labeler import EmailAutoLabeler
from email_labeler.llm_service import LLMService


class TestFactoryFunctions:
    """Test cases for factory functions."""

    def test_create_database_connection_default(self):
        """Test creating database connection with default file."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            with patch("email_labeler.factory.DATABASE_FILE", tmp.name):
                conn = create_database_connection()

                assert isinstance(conn, sqlite3.Connection)
                conn.close()

    def test_create_database_connection_custom(self):
        """Test creating database connection with custom file."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = create_database_connection(tmp.name)

            assert isinstance(conn, sqlite3.Connection)
            conn.close()

    def test_create_gmail_client_success(self):
        """Test successful Gmail client creation."""
        with patch("email_labeler.factory.get_gmail_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            client = create_gmail_client(port=8080)

            assert client == mock_client
            mock_get_client.assert_called_once_with(port=8080)

    def test_create_gmail_client_default_port(self):
        """Test Gmail client creation with default port."""
        with patch("email_labeler.factory.get_gmail_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = mock_client

            create_gmail_client()

            mock_get_client.assert_called_once_with(port=8080)

    def test_create_llm_client_openai(self):
        """Test creating OpenAI LLM client."""
        with (
            patch("email_labeler.factory.OPENAI_API_KEY", "test-key"),
            patch("email_labeler.factory.OpenAI") as mock_openai,
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_llm_client("OpenAI")

            assert client == mock_client
            mock_openai.assert_called_once_with(api_key="test-key")

    def test_create_llm_client_ollama(self):
        """Test creating Ollama LLM client."""
        with (
            patch("email_labeler.factory.LLM_SERVICE", "Ollama"),
            patch("email_labeler.factory.OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            patch("email_labeler.factory.OpenAI") as mock_openai,
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_llm_client("Ollama")

            assert client == mock_client
            mock_openai.assert_called_once_with(
                base_url="http://localhost:11434/v1", api_key="ollama"
            )

    def test_create_llm_client_invalid_service(self):
        """Test creating LLM client with invalid service defaults to OpenAI."""
        with (
            patch("email_labeler.factory.OPENAI_API_KEY", "test-key"),
            patch("email_labeler.factory.OpenAI") as mock_openai,
        ):
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            client = create_llm_client("InvalidService")

            # Should default to OpenAI for invalid service
            assert client == mock_client
            mock_openai.assert_called_once_with(api_key="test-key")

    def test_create_email_database_with_connection(self):
        """Test creating EmailDatabase with provided connection."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            conn = sqlite3.connect(tmp.name)

            db = create_email_database(conn=conn)

            assert isinstance(db, EmailDatabase)
            assert db.conn == conn
            assert not db.owns_connection

            conn.close()

    def test_create_email_database_without_connection(self):
        """Test creating EmailDatabase without connection."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = create_email_database(database_file=tmp.name)

            assert isinstance(db, EmailDatabase)
            # create_email_database always passes a connection, so owns_connection is False
            assert not db.owns_connection

            db.close()

    def test_create_email_processor_with_dependencies(self):
        """Test creating EmailProcessor with provided dependencies."""
        mock_gmail_client = MagicMock()

        processor = create_email_processor(gmail_client=mock_gmail_client)

        assert isinstance(processor, EmailProcessor)
        assert processor.gmail == mock_gmail_client

    def test_create_email_processor_without_dependencies(self):
        """Test creating EmailProcessor without dependencies."""
        with patch("email_labeler.factory.create_gmail_client") as mock_create_gmail:
            mock_gmail_client = MagicMock()
            mock_create_gmail.return_value = mock_gmail_client

            processor = create_email_processor()

            assert isinstance(processor, EmailProcessor)
            mock_create_gmail.assert_called_once_with(8080)

    def test_create_llm_service_with_client(self):
        """Test creating LLMService with provided client."""
        mock_client = MagicMock()
        model = "gpt-4"
        test_categories = ["Work", "Personal", "Other"]

        service = create_llm_service(
            categories=test_categories, llm_client=mock_client, model=model
        )

        assert isinstance(service, LLMService)
        assert service.llm_client == mock_client
        assert service.model == model
        assert service.categories == test_categories

    def test_create_llm_service_without_client(self):
        """Test creating LLMService without client."""
        test_categories = ["Work", "Personal", "Other"]

        with patch("email_labeler.factory.create_llm_client") as mock_create_client:
            mock_client = MagicMock()
            mock_create_client.return_value = mock_client

            with (
                patch("email_labeler.factory.OPENAI_MODEL", "gpt-3.5-turbo"),
                patch("email_labeler.factory.LLM_SERVICE", "OpenAI"),
            ):
                service = create_llm_service(categories=test_categories)

                assert isinstance(service, LLMService)
                assert service.categories == test_categories
                mock_create_client.assert_called_once()

    def test_create_email_auto_labeler_with_dependencies(self):
        """Test creating EmailAutoLabeler with provided dependencies."""
        mock_processor = MagicMock()
        mock_llm_service = MagicMock()
        mock_metrics = MagicMock()
        mock_database = MagicMock()
        test_categories = ["Work", "Personal", "Other"]

        labeler = create_email_auto_labeler(
            categories=test_categories,
            database=mock_database,
            email_processor=mock_processor,
            llm_service=mock_llm_service,
            metrics_tracker=mock_metrics,
        )

        assert isinstance(labeler, EmailAutoLabeler)
        assert labeler.categories == test_categories
        assert labeler.database == mock_database
        assert labeler.email_processor == mock_processor
        assert labeler.llm_service == mock_llm_service
        assert labeler.metrics == mock_metrics

    def test_create_email_auto_labeler_without_dependencies(self):
        """Test creating EmailAutoLabeler without dependencies."""
        from email_labeler.config import DATABASE_FILE, LLM_SERVICE

        test_categories = ["Work", "Personal", "Other"]

        with (
            patch("email_labeler.factory.create_email_database") as mock_create_db,
            patch("email_labeler.factory.create_email_processor") as mock_create_processor,
            patch("email_labeler.factory.create_llm_service") as mock_create_llm,
        ):
            mock_database = MagicMock()
            mock_processor = MagicMock()
            mock_llm_service = MagicMock()

            mock_create_db.return_value = mock_database
            mock_create_processor.return_value = mock_processor
            mock_create_llm.return_value = mock_llm_service

            labeler = create_email_auto_labeler(categories=test_categories)

            assert isinstance(labeler, EmailAutoLabeler)
            assert labeler.categories == test_categories
            mock_create_db.assert_called_once_with(database_file=DATABASE_FILE)
            mock_create_processor.assert_called_once_with(port=8080)
            mock_create_llm.assert_called_once_with(
                categories=test_categories, max_content_length=4000, service=LLM_SERVICE
            )

    def test_create_test_dependencies(self):
        """Test creating test dependencies."""
        with (
            patch("email_labeler.factory.create_llm_client") as mock_create_client,
            patch("email_labeler.email_processor.get_gmail_client") as mock_get_gmail,
        ):
            mock_client = MagicMock()
            mock_gmail_client = MagicMock()
            mock_create_client.return_value = mock_client
            mock_get_gmail.return_value = mock_gmail_client

            test_deps = create_test_dependencies()

            # Should return tuple of (database, llm_service, email_processor, metrics_tracker)
            assert len(test_deps) == 4
            database, llm_service, email_processor, metrics_tracker = test_deps

            # Verify types
            assert isinstance(database, EmailDatabase)
            assert isinstance(llm_service, LLMService)
            assert isinstance(email_processor, EmailProcessor)
            # metrics_tracker should be an instance (not mocked in this test)

    def test_create_test_dependencies_with_in_memory_db(self):
        """Test that create_test_dependencies uses in-memory database."""
        with (
            patch("email_labeler.factory.create_llm_client") as mock_create_client,
            patch("email_labeler.email_processor.get_gmail_client") as mock_get_gmail,
        ):
            mock_client = MagicMock()
            mock_gmail_client = MagicMock()
            mock_create_client.return_value = mock_client
            mock_get_gmail.return_value = mock_gmail_client

            test_deps = create_test_dependencies()
            database, _, _, _ = test_deps

            assert isinstance(database, EmailDatabase)
            # Should use in-memory database
            assert database.database_file == ":memory:"

    def test_dependency_injection_chain(self):
        """Test that dependencies are properly injected through the chain."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            # Create a database connection
            conn = create_database_connection(tmp.name)

            # Create database with connection
            database = create_email_database(conn=conn)

            # Create other dependencies
            with patch("email_labeler.factory.get_gmail_client") as mock_get_gmail:
                mock_gmail_client = MagicMock()
                mock_get_gmail.return_value = mock_gmail_client
                gmail_client = create_gmail_client()

                # Create processor with gmail client
                processor = create_email_processor(gmail_client=gmail_client)

                # Verify the chain
                assert processor.gmail == mock_gmail_client
                assert database.conn == conn

                conn.close()

    def test_error_handling_in_factories(self):
        """Test error handling in factory functions."""
        # Test database connection error
        with pytest.raises((sqlite3.Error, OSError)):
            create_database_connection("/nonexistent/path/database.db")

        # Test Gmail client error
        with patch(
            "email_labeler.factory.get_gmail_client", side_effect=Exception("Gmail auth failed")
        ):
            with pytest.raises(Exception):
                create_gmail_client()

    def test_factory_configuration_override(self):
        """Test overriding configuration in factory functions."""
        # Test LLM service override
        with patch("email_labeler.factory.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            # Override service type
            create_llm_client("OpenAI")
            mock_openai.assert_called_once_with(api_key=None)  # Will use config default

    def test_factory_caching_behavior(self):
        """Test that factories create new instances (no caching)."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            # Create two database instances
            db1 = create_email_database(database_file=tmp.name)
            db2 = create_email_database(database_file=tmp.name)

            # Should be different instances
            assert db1 is not db2

            db1.close()
            db2.close()

    @pytest.mark.parametrize("service_type", ["OpenAI", "Ollama"])
    def test_create_llm_client_different_services(self, service_type):
        """Test creating LLM clients for different services."""
        with patch("email_labeler.factory.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client

            if service_type == "OpenAI":
                with patch("email_labeler.factory.OPENAI_API_KEY", "test-key"):
                    client = create_llm_client(service_type)
                    mock_openai.assert_called_once_with(api_key="test-key")
            else:  # Ollama
                with patch("email_labeler.factory.OLLAMA_BASE_URL", "http://localhost:11434/v1"):
                    client = create_llm_client(service_type)
                    mock_openai.assert_called_once_with(
                        base_url="http://localhost:11434/v1", api_key="ollama"
                    )

            assert client == mock_client

    def test_factory_resource_cleanup(self):
        """Test that factory functions handle resource cleanup."""
        # Test database connection cleanup
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = create_email_database(database_file=tmp.name)

            # Should be able to close properly
            db.close()

            # Create another instance after closing
            db2 = create_email_database(database_file=tmp.name)
            db2.close()

    def test_concurrent_factory_calls(self):
        """Test concurrent factory function calls."""
        import concurrent.futures

        def create_db():
            with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                return create_email_database(database_file=tmp.name)

        # Create multiple databases concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(create_db) for _ in range(5)]

            databases = []
            for future in concurrent.futures.as_completed(futures):
                db = future.result()
                databases.append(db)

            # All should be valid database instances
            assert len(databases) == 5
            assert all(isinstance(db, EmailDatabase) for db in databases)

            # Cleanup
            for db in databases:
                db.close()

    def test_factory_with_mock_dependencies(self):
        """Test factories work correctly with mock dependencies."""
        mock_conn = MagicMock(spec=sqlite3.Connection)
        mock_gmail = MagicMock()
        mock_llm = MagicMock()
        test_categories = ["Work", "Personal", "Other"]

        # Create components with mocks
        database = create_email_database(conn=mock_conn)
        processor = create_email_processor(gmail_client=mock_gmail)

        llm_service = create_llm_service(categories=test_categories, llm_client=mock_llm)

        labeler = create_email_auto_labeler(
            categories=test_categories,
            database=database,
            email_processor=processor,
            llm_service=llm_service,
        )

        # Verify mock integration
        assert labeler.database == database
        assert labeler.email_processor == processor
        assert labeler.llm_service == llm_service
        assert processor.gmail == mock_gmail
