"""Tests for EmailProcessor class."""

from unittest.mock import MagicMock, patch

from email_labeler.email_processor import EmailProcessor


class TestEmailProcessor:
    """Test cases for EmailProcessor class."""

    def test_init_with_gmail_client(self, mock_gmail_client):
        """Test EmailProcessor initialization with provided gmail client."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        assert processor.gmail == mock_gmail_client
        assert not processor._owns_gmail_client

    @patch("email_labeler.email_processor.get_gmail_client")
    def test_init_without_gmail_client(self, mock_get_gmail_client):
        """Test EmailProcessor initialization without gmail client."""
        mock_client = MagicMock()
        mock_get_gmail_client.return_value = mock_client

        processor = EmailProcessor()

        assert processor.gmail == mock_client
        assert processor._owns_gmail_client
        mock_get_gmail_client.assert_called_once_with(port=8080)

    def test_strip_html(self, mock_gmail_client):
        """Test HTML stripping functionality."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        html_content = (
            "<html><body><h1>Hello</h1><p>World!</p><div>  Extra   spaces  </div></body></html>"
        )
        expected = "Hello World! Extra spaces"

        result = processor.strip_html(html_content)

        assert result == expected

    @patch("email_labeler.email_processor.fetch_emails")
    @patch("email_labeler.email_processor.get_email_content")
    def test_fetch_emails_from_gmail_success(
        self, mock_get_email_content, mock_fetch_emails, mock_gmail_client
    ):
        """Test successful fetching of emails from Gmail."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        # Mock the fetch_emails function
        mock_fetch_emails.return_value = [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"},
        ]

        # Mock the get_email_content function
        def mock_get_content_side_effect(gmail, email_id):
            return {
                "subject": f"Subject {email_id}",
                "from": f"sender{email_id}@example.com",
                "date": "2024-01-01T12:00:00Z",
                "body": f"Body content for {email_id}",
            }

        mock_get_email_content.side_effect = mock_get_content_side_effect

        emails = processor.fetch_emails_from_gmail(query="is:unread", limit=10)

        assert len(emails) == 2
        assert emails[0][0] == "msg1"
        assert emails[0][1] == "Subject msg1"
        assert emails[0][2] == "sendermsg1@example.com"
        assert emails[1][0] == "msg2"

        mock_fetch_emails.assert_called_once_with(mock_gmail_client, "is:unread", max_results=10)

    @patch("email_labeler.email_processor.fetch_emails")
    @patch("email_labeler.email_processor.get_email_content")
    def test_fetch_emails_from_gmail_with_error(
        self, mock_get_email_content, mock_fetch_emails, mock_gmail_client
    ):
        """Test fetching emails when one email fails to retrieve."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        # Mock the fetch_emails function
        mock_fetch_emails.return_value = [
            {"id": "msg1", "threadId": "thread1"},
            {"id": "msg2", "threadId": "thread2"},
        ]

        # Mock the get_email_content function to fail for second email
        def mock_get_content_side_effect(gmail, email_id):
            if email_id == "msg2":
                raise Exception("Failed to fetch email")
            return {
                "subject": f"Subject {email_id}",
                "from": f"sender{email_id}@example.com",
                "date": "2024-01-01T12:00:00Z",
                "body": f"Body content for {email_id}",
            }

        mock_get_email_content.side_effect = mock_get_content_side_effect

        emails = processor.fetch_emails_from_gmail()

        # Should only return the first email since second failed
        assert len(emails) == 1
        assert emails[0][0] == "msg1"

    @patch("email_labeler.email_processor.get_or_create_label")
    def test_get_or_create_label(self, mock_get_or_create_label, mock_gmail_client):
        """Test getting or creating a Gmail label."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        mock_get_or_create_label.return_value = "Label_123"

        label_id = processor.get_or_create_label("Test Label")

        assert label_id == "Label_123"
        mock_get_or_create_label.assert_called_once_with(mock_gmail_client, "Test Label")

    @patch("email_labeler.email_processor.add_labels_to_email")
    def test_add_labels_to_email(self, mock_add_labels, mock_gmail_client):
        """Test adding labels to an email."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        mock_add_labels.return_value = True

        result = processor.add_labels_to_email("msg123", ["Label_1", "Label_2"])

        assert result is True
        mock_add_labels.assert_called_once_with(mock_gmail_client, "msg123", ["Label_1", "Label_2"])

    @patch("email_labeler.email_processor.remove_from_inbox")
    def test_remove_from_inbox(self, mock_remove_from_inbox, mock_gmail_client):
        """Test removing an email from inbox."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        mock_remove_from_inbox.return_value = True

        result = processor.remove_from_inbox("msg123")

        assert result is True
        mock_remove_from_inbox.assert_called_once_with(mock_gmail_client, "msg123")

    def test_prepare_email_content(self, mock_gmail_client):
        """Test preparing email content for categorization."""
        processor = EmailProcessor(gmail_client=mock_gmail_client)

        email_tuple = (
            "msg123",
            "Test Subject",
            "sender@example.com",
            "2024-01-01T12:00:00Z",
            "<html><body>Test <b>content</b></body></html>",
        )

        result = processor.prepare_email_content(email_tuple)

        expected = "Subject: Test Subject\nFrom: sender@example.com\n\nTest content"
        assert result == expected
