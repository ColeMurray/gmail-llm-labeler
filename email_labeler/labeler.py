"""Main EmailAutoLabeler orchestrator class."""

import logging
import time
from typing import List, Optional

from .config import LLM_SERVICE, OLLAMA_MODEL, OPENAI_MODEL, PROCESSED_LABEL
from .database import EmailDatabase
from .email_processor import EmailProcessor
from .llm_service import LLMService
from .metrics import MetricsTracker


class EmailAutoLabeler:
    """Main orchestrator for email auto-labeling process."""

    def __init__(
        self,
        categories: List[str],
        database: EmailDatabase = None,
        llm_service: LLMService = None,
        email_processor: EmailProcessor = None,
        metrics_tracker: MetricsTracker = None,
        test_mode: bool = False,
        preview_mode: bool = False,
    ):
        """Initialize the email auto-labeler.

        Args:
            categories: List of category labels for email classification.
            database: Optional EmailDatabase instance. If not provided, creates a new one.
            llm_service: Optional LLMService instance. If not provided, creates a new one.
            email_processor: Optional EmailProcessor instance. If not provided, creates a new one.
            metrics_tracker: Optional MetricsTracker instance. If not provided, creates one in test mode.
            test_mode: Whether to run in test mode.
            preview_mode: Whether to run in preview mode.
        """
        self.categories = categories
        self.test_mode = test_mode
        self.preview_mode = preview_mode

        # Initialize components with dependency injection
        self.database = database or EmailDatabase()
        self.llm_service = llm_service or LLMService(categories=categories)
        self.email_processor = email_processor or EmailProcessor()
        self.metrics = metrics_tracker or (MetricsTracker() if test_mode else None)

        # Cache for label IDs
        self.label_ids_cache = {}

        logging.info(f"EmailAutoLabeler initialized - Test: {test_mode}, Preview: {preview_mode}")

    def _get_label_ids(self):
        """Get or create all required Gmail labels."""
        if not self.label_ids_cache:
            self.label_ids_cache["processed"] = self.email_processor.get_or_create_label(
                PROCESSED_LABEL
            )
            for label in self.categories:
                self.label_ids_cache[label] = self.email_processor.get_or_create_label(label)
        return self.label_ids_cache

    def _add_labels_with_preview(self, email_id: str, label_ids: List[str]) -> bool:
        """Add labels to email with preview/test mode support."""
        if self.preview_mode or self.test_mode:
            logging.info(
                f"{'Test' if self.test_mode else 'Preview'}: Would add labels {label_ids} to email {email_id}"
            )
            return True

        if self.email_processor.add_labels_to_email(email_id, label_ids):
            logging.info(f"Labels added to email {email_id}")
            return True
        else:
            logging.error(f"Failed to add labels to email {email_id}")
            return False

    def _remove_from_inbox_with_preview(self, email_id: str) -> bool:
        """Remove email from inbox with preview/test mode support."""
        if self.preview_mode or self.test_mode:
            logging.info(
                f"{'Test' if self.test_mode else 'Preview'}: Would remove email {email_id} from inbox"
            )
            return True

        if self.email_processor.remove_from_inbox(email_id):
            logging.info(f"Email {email_id} removed from inbox")
            return True
        else:
            logging.error(f"Failed to remove email {email_id} from inbox")
            return False

    def process_single_email(self, email_tuple: tuple) -> Optional[str]:
        """Process a single email and return its category."""
        start_time = time.time()
        email_id, subject, sender, _, content = email_tuple

        # Prepare email content for categorization
        email_content = self.email_processor.prepare_email_content(email_tuple)

        # Categorize the email
        category, explanation = self.llm_service.categorize_email(email_content)
        processing_time = time.time() - start_time

        # Track test metrics if in test mode
        if self.test_mode and self.metrics:
            self.metrics.add_test_result(
                email_id,
                subject,
                sender,
                category,
                explanation,
                LLM_SERVICE,
                OLLAMA_MODEL if LLM_SERVICE == "Ollama" else OPENAI_MODEL,
                processing_time,
            )

        # Log warning if categorization failed
        if category == "Other":
            logging.warning(f"Could not categorize email {email_id}: {explanation}")
            if not self.test_mode:
                return None

        # Get label IDs
        label_ids = self._get_label_ids()
        label_ids_to_add = [label_ids["processed"], label_ids[category]]

        # Apply labels
        self._add_labels_with_preview(email_id, label_ids_to_add)

        # Update database if not in test mode
        if not self.test_mode:
            self.database.update_email_labels(email_id, category, label_ids_to_add)

        # Remove from inbox for certain categories
        if category in ["Marketing", "Newsletters", "Low quality"]:
            self._remove_from_inbox_with_preview(email_id)

        logging.info(
            f"Processed email {email_id}, {subject} -> {category} ({processing_time:.2f}s)"
        )
        return category

    def process_emails(
        self, limit: Optional[int] = None, use_gmail_api: bool = False, query: str = "is:unread"
    ):
        """Process multiple emails."""
        # Fetch emails
        if use_gmail_api:
            logging.info(f"Fetching emails from Gmail API with query: {query}")
            emails = self.email_processor.fetch_emails_from_gmail(query, limit)
        else:
            logging.info(f"Fetching unprocessed emails from database (limit: {limit})")
            emails = self.database.get_unprocessed_emails(limit or 100)

        if not emails:
            logging.info("No unprocessed emails found")
            return

        logging.info(f"Found {len(emails)} emails to process")

        # Process each email
        processed_count = 0
        for email in emails:
            category = self.process_single_email(email)
            if category:
                processed_count += 1

        logging.info(f"Successfully processed {processed_count}/{len(emails)} emails")

        # Save test results if in test mode
        if self.test_mode and self.metrics:
            self.metrics.save_test_results()
            self.metrics.print_summary()

    def run(
        self, limit: Optional[int] = None, use_gmail_api: bool = False, query: str = "is:unread"
    ):
        """Run the email auto-labeling process."""
        mode_str = (
            "TEST MODE"
            if self.test_mode
            else "PREVIEW MODE"
            if self.preview_mode
            else "PRODUCTION MODE"
        )
        source_str = "Gmail API" if use_gmail_api else "Database"

        logging.info(f"Starting email auto-labeling in {mode_str} using {source_str}")

        try:
            self.process_emails(limit, use_gmail_api, query)
            logging.info("Email auto-labeling process completed")
        except Exception as e:
            logging.error(f"Error during email processing: {e}")
            raise

    def close(self):
        """Clean up resources."""
        self.database.close()
        logging.info("EmailAutoLabeler closed")
