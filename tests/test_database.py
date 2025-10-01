"""Tests for EmailDatabase class."""

import json
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest

from email_labeler.database import EmailDatabase


class TestEmailDatabase:
    """Test cases for EmailDatabase class."""

    def test_init_with_connection(self, mock_sqlite_connection):
        """Test initialization with provided connection."""
        mock_conn, mock_cursor = mock_sqlite_connection

        db = EmailDatabase(conn=mock_conn)

        assert db.conn == mock_conn
        assert not db.owns_connection
        mock_conn.cursor.assert_called_once()

    def test_init_without_connection(self):
        """Test initialization without provided connection."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = EmailDatabase(database_file=tmp.name)

            assert db.conn is not None
            assert db.owns_connection
            assert db.database_file == tmp.name

    def test_initialize_db_creates_tables(self, mock_sqlite_connection):
        """Test that initialize_db creates required tables."""
        mock_conn, mock_cursor = mock_sqlite_connection

        EmailDatabase(conn=mock_conn)

        # Check that tables are created
        expected_tables = ["processed_emails", "email_labels", "label_history", "emails"]

        create_calls = [
            call for call in mock_cursor.execute.call_args_list if "CREATE TABLE" in str(call)
        ]
        assert len(create_calls) >= 4

        # Check specific table names are mentioned
        all_calls_str = str(mock_cursor.execute.call_args_list)
        for table in expected_tables:
            assert table in all_calls_str

    def test_get_unprocessed_emails(self, email_database):
        """Test getting unprocessed emails."""
        expected_emails = [
            ("email1", "Test Subject", "test@example.com", "2024-01-01T12:00:00", "Test content")
        ]
        email_database.cursor.fetchall.return_value = expected_emails

        result = email_database.get_unprocessed_emails(limit=10)

        assert result == expected_emails
        email_database.cursor.execute.assert_called_with(
            """
            SELECT e.id, e.subject, e.sender, e.received_date, e.content
            FROM emails e
            LEFT JOIN processed_emails p ON e.id = p.email_id
            WHERE p.email_id IS NULL
            ORDER BY e.received_date ASC
            LIMIT ?
        """,
            (10,),
        )

    def test_get_unprocessed_emails_default_limit(self, email_database):
        """Test getting unprocessed emails with default limit."""
        email_database.cursor.fetchall.return_value = []

        email_database.get_unprocessed_emails()

        email_database.cursor.execute.assert_called_with(
            """
            SELECT e.id, e.subject, e.sender, e.received_date, e.content
            FROM emails e
            LEFT JOIN processed_emails p ON e.id = p.email_id
            WHERE p.email_id IS NULL
            ORDER BY e.received_date ASC
            LIMIT ?
        """,
            (100,),
        )

    def test_update_email_labels(self, email_database, mock_datetime):
        """Test updating email labels."""
        email_id = "test_email"
        category = "Work"
        label_ids = ["Label_1", "Label_2"]

        # Reset mock to ignore initialization calls
        email_database.cursor.execute.reset_mock()
        email_database.conn.commit.reset_mock()

        email_database.update_email_labels(email_id, category, label_ids)

        expected_time = mock_datetime.now.return_value.isoformat.return_value
        expected_labels_json = json.dumps(label_ids)

        # Check that all three operations are called
        calls = email_database.cursor.execute.call_args_list

        # First call: INSERT OR REPLACE into email_labels
        assert calls[0][0][0].strip().startswith("INSERT OR REPLACE INTO email_labels")
        assert calls[0][0][1] == (email_id, expected_labels_json, category, expected_time)

        # Second call: INSERT into label_history
        assert calls[1][0][0].strip().startswith("INSERT INTO label_history")

        # Third call: INSERT OR REPLACE into processed_emails
        assert calls[2][0][0].strip().startswith("INSERT OR REPLACE INTO processed_emails")
        assert calls[2][0][1] == (email_id, expected_time)

        email_database.conn.commit.assert_called_once()

    def test_is_email_processed_true(self, email_database):
        """Test checking if email is processed - returns True."""
        email_id = "processed_email"
        email_database.cursor.fetchone.return_value = (email_id,)

        result = email_database.is_email_processed(email_id)

        assert result is True
        email_database.cursor.execute.assert_called_with(
            """
            SELECT email_id FROM processed_emails WHERE email_id = ?
        """,
            (email_id,),
        )

    def test_is_email_processed_false(self, email_database):
        """Test checking if email is processed - returns False."""
        email_id = "unprocessed_email"
        email_database.cursor.fetchone.return_value = None

        result = email_database.is_email_processed(email_id)

        assert result is False

    def test_get_email_labels_found(self, email_database):
        """Test getting email labels when they exist."""
        email_id = "test_email"
        category = "Work"
        labels = ["Label_1", "Label_2"]
        labels_json = json.dumps(labels)
        email_database.cursor.fetchone.return_value = (category, labels_json)

        result = email_database.get_email_labels(email_id)

        assert result == (category, labels)
        email_database.cursor.execute.assert_called_with(
            """
            SELECT category, labels FROM email_labels WHERE email_id = ?
        """,
            (email_id,),
        )

    def test_get_email_labels_not_found(self, email_database):
        """Test getting email labels when they don't exist."""
        email_id = "nonexistent_email"
        email_database.cursor.fetchone.return_value = None

        result = email_database.get_email_labels(email_id)

        assert result is None

    def test_get_email_labels_invalid_json(self, email_database):
        """Test getting email labels with invalid JSON."""
        email_id = "test_email"
        category = "Work"
        email_database.cursor.fetchone.return_value = (category, "invalid json")

        with pytest.raises(json.JSONDecodeError):
            email_database.get_email_labels(email_id)

    def test_save_email(self, email_database):
        """Test saving email to database."""
        email_id = "test_email"
        subject = "Test Subject"
        sender = "test@example.com"
        received_date = "2024-01-01T12:00:00"
        content = "Test email content"

        # Reset mock to ignore initialization calls
        email_database.cursor.execute.reset_mock()
        email_database.conn.commit.reset_mock()

        email_database.save_email(email_id, subject, sender, received_date, content)

        email_database.cursor.execute.assert_called_with(
            """
            INSERT OR REPLACE INTO emails (id, subject, sender, received_date, content)
            VALUES (?, ?, ?, ?, ?)
        """,
            (email_id, subject, sender, received_date, content),
        )
        email_database.conn.commit.assert_called_once()

    def test_close_connection_owned(self):
        """Test closing connection when database owns it."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = EmailDatabase(database_file=tmp.name)
            mock_conn = MagicMock()
            db.conn = mock_conn
            db.owns_connection = True

            db.close()

            mock_conn.close.assert_called_once()

    def test_close_connection_not_owned(self, mock_sqlite_connection):
        """Test closing connection when database doesn't own it."""
        mock_conn, mock_cursor = mock_sqlite_connection
        db = EmailDatabase(conn=mock_conn)

        db.close()

        mock_conn.close.assert_not_called()

    def test_database_error_handling(self, email_database):
        """Test database error handling."""
        email_database.cursor.execute.side_effect = sqlite3.Error("Database error")

        with pytest.raises(sqlite3.Error):
            email_database.get_unprocessed_emails()

    def test_concurrent_access(self, temp_database):
        """Test concurrent database access with real connections."""
        conn1, db_file = temp_database
        db1 = EmailDatabase(conn=conn1)

        # Create second connection
        conn2 = sqlite3.connect(db_file)
        db2 = EmailDatabase(conn=conn2)

        # Save emails through both connections
        db1.save_email(
            "email1", "Subject 1", "sender1@test.com", "2024-01-01T12:00:00", "Content 1"
        )
        db2.save_email(
            "email2", "Subject 2", "sender2@test.com", "2024-01-01T12:00:00", "Content 2"
        )

        # Both should be able to see each other's emails
        emails1 = db1.get_unprocessed_emails()
        emails2 = db2.get_unprocessed_emails()

        assert len(emails1) == 2
        assert len(emails2) == 2

        conn2.close()

    @pytest.mark.parametrize(
        "email_id,category,labels",
        [
            ("test1", "Work", ["Label_1"]),
            ("test2", "Personal", ["Label_2", "Label_3"]),
            ("test3", "Newsletter", []),
        ],
    )
    def test_update_various_email_labels(
        self, email_database, mock_datetime, email_id, category, labels
    ):
        """Test updating various email labels."""
        # Reset mock to ignore initialization calls
        email_database.cursor.execute.reset_mock()
        email_database.conn.commit.reset_mock()

        email_database.update_email_labels(email_id, category, labels)

        expected_time = mock_datetime.now.return_value.isoformat.return_value
        expected_labels_json = json.dumps(labels)

        calls = email_database.cursor.execute.call_args_list

        # Check the email_labels insert
        assert calls[0][0][1] == (email_id, expected_labels_json, category, expected_time)

    def test_real_database_integration(self):
        """Test with real SQLite database to ensure actual functionality works."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = EmailDatabase(database_file=tmp.name)

            # Test saving an email
            email_id = "real_test_email"
            subject = "Real Test Subject"
            sender = "real@test.com"
            received_date = "2024-01-01T12:00:00"
            content = "Real test content"

            db.save_email(email_id, subject, sender, received_date, content)

            # Test getting unprocessed emails
            unprocessed = db.get_unprocessed_emails()
            assert len(unprocessed) == 1
            assert unprocessed[0][0] == email_id
            assert unprocessed[0][1] == subject

            # Test checking if email is processed (should be False initially)
            assert not db.is_email_processed(email_id)

            # Test updating labels (which also marks as processed)
            category = "Test Category"
            labels = ["Test_Label_1", "Test_Label_2"]
            db.update_email_labels(email_id, category, labels)

            # Test checking if email is now processed
            assert db.is_email_processed(email_id)

            # Test getting email labels
            result = db.get_email_labels(email_id)
            assert result is not None
            assert result[0] == category
            assert result[1] == labels

            # Test that email is no longer unprocessed
            unprocessed = db.get_unprocessed_emails()
            assert len(unprocessed) == 0

            db.close()

    def test_update_email_labels_with_history_tracking(self):
        """Test that label history is properly tracked."""
        with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
            db = EmailDatabase(database_file=tmp.name)

            email_id = "history_test_email"
            category = "Test"
            labels = ["Label_1"]

            # Update labels
            db.update_email_labels(email_id, category, labels)

            # Check that history was recorded
            db.cursor.execute(
                "SELECT email_id, new_labels FROM label_history WHERE email_id = ?", (email_id,)
            )
            history = db.cursor.fetchone()
            assert history is not None
            assert history[0] == email_id
            assert json.loads(history[1]) == labels

            db.close()

    def test_initialization_with_nonexistent_file(self):
        """Test initialization creates new database file if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = f"{tmp_dir}/new_test.db"
            db = EmailDatabase(database_file=db_path)

            # Should create the file and initialize tables
            assert db.conn is not None
            assert db.owns_connection

            # Test that tables exist by doing a simple operation
            db.save_email("test", "subject", "sender", "date", "content")
            emails = db.get_unprocessed_emails()
            assert len(emails) == 1

            db.close()
