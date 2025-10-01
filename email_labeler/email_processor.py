"""Email processing utilities."""

import logging
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup
from googleapiclient.discovery import Resource

from .gmail_utils import (
    add_labels_to_email,
    fetch_emails,
    get_email_content,
    get_gmail_client,
    get_or_create_label,
    remove_from_inbox,
)


class EmailProcessor:
    """Handles email fetching and processing operations."""

    def __init__(self, gmail_client: Optional[Resource] = None, lazy_init: bool = False):
        """Initialize email processor with Gmail client.

        Args:
            gmail_client: Optional Gmail API client. If not provided, creates a new client.
            lazy_init: If True, delay Gmail client initialization until first use.
        """
        self.gmail = gmail_client
        self._owns_gmail_client = gmail_client is None
        self._lazy_init = lazy_init
        if self._owns_gmail_client and not lazy_init:
            self.gmail = get_gmail_client(port=8080)

    def _ensure_gmail_client(self):
        """Ensure Gmail client is initialized (for lazy initialization)."""
        if self.gmail is None and self._owns_gmail_client:
            self.gmail = get_gmail_client(port=8080)

    def strip_html(self, html_content: str) -> str:
        """Remove HTML tags and extract text content."""
        soup = BeautifulSoup(html_content, "html.parser")
        text_content = soup.get_text(separator=" ", strip=True)
        text_content = re.sub(r"\s+", " ", text_content).strip()
        return text_content

    def fetch_emails_from_gmail(
        self, query: str = "is:unread", limit: Optional[int] = None
    ) -> List[tuple]:
        """Fetch emails directly from Gmail API and convert to database format."""
        self._ensure_gmail_client()
        messages = fetch_emails(self.gmail, query, max_results=limit)

        emails_data = []
        for msg in messages:
            try:
                email_data = get_email_content(self.gmail, msg["id"])
                # Convert to tuple format matching database structure
                emails_data.append(
                    (
                        msg["id"],
                        email_data.get("subject", ""),
                        email_data.get("from", ""),
                        email_data.get("date", datetime.now().isoformat()),
                        email_data.get("body", ""),
                    )
                )
            except Exception as e:
                logging.error(f"Failed to fetch email {msg['id']}: {e}")
                continue

        return emails_data

    def get_or_create_label(self, label_name: str) -> Optional[str]:
        """Get or create a Gmail label and return its ID."""
        self._ensure_gmail_client()
        return get_or_create_label(self.gmail, label_name)

    def add_labels_to_email(self, email_id: str, label_ids: List[str]) -> bool:
        """Add labels to a specific email."""
        self._ensure_gmail_client()
        return add_labels_to_email(self.gmail, email_id, label_ids)

    def remove_from_inbox(self, email_id: str) -> bool:
        """Remove an email from the inbox."""
        self._ensure_gmail_client()
        return remove_from_inbox(self.gmail, email_id)

    def prepare_email_content(self, email_tuple: tuple) -> str:
        """Prepare email content for categorization."""
        _, subject, sender, _, content = email_tuple
        clean_content = self.strip_html(content)
        return f"Subject: {subject}\nFrom: {sender}\n\n{clean_content}"
