"""Extract stage implementation for the ETL pipeline."""

import logging
from datetime import datetime
from typing import Any, List, Optional

from ..database import EmailDatabase
from ..email_processor import EmailProcessor
from .base import EmailRecord, PipelineContext, PipelineStage
from .config import ExtractConfig

logger = logging.getLogger(__name__)


class ExtractStage(PipelineStage):
    """Handles email extraction from various sources."""

    def __init__(
        self,
        config: ExtractConfig,
        email_processor: Optional[EmailProcessor] = None,
        database: Optional[EmailDatabase] = None,
    ):
        """Initialize the extract stage.

        Args:
            config: Extract stage configuration.
            email_processor: Optional EmailProcessor instance. If not provided, creates a new one.
            database: Optional EmailDatabase instance. If not provided, creates a new one.
        """
        super().__init__()
        self.config = config
        self.email_processor = email_processor or EmailProcessor()
        self.database = database or EmailDatabase()

    def execute(self, input_data: None, context: PipelineContext) -> List[EmailRecord]:
        """Extract emails based on configuration."""
        logger.info(f"Starting extraction from source: {self.config.source}")
        start_time = datetime.now()

        try:
            if self.config.source == "gmail":
                emails = self._extract_from_gmail(context)
            elif self.config.source == "database":
                emails = self._extract_from_database(context)
            else:
                raise ValueError(f"Unknown source: {self.config.source}")

            # Update metrics
            elapsed = (datetime.now() - start_time).total_seconds()
            self.metrics["emails_extracted"] = len(emails)
            self.metrics["extraction_time"] = elapsed
            self.metrics["source"] = self.config.source

            context.add_metric("extract_emails_count", len(emails))
            context.add_metric("extract_time", elapsed)

            logger.info(f"Extracted {len(emails)} emails in {elapsed:.2f} seconds")
            return emails

        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            context.add_error(f"Extract stage failed: {str(e)}")
            if not context.config.continue_on_error:
                raise
            return []

    def _extract_from_gmail(self, context: PipelineContext) -> List[EmailRecord]:
        """Extract emails from Gmail API."""
        logger.debug(f"Fetching emails from Gmail with query: {self.config.gmail_query}")

        if context.dry_run:
            logger.info("DRY RUN: Would fetch emails from Gmail")
            return []

        raw_emails = self.email_processor.fetch_emails_from_gmail(
            query=self.config.gmail_query, limit=self.config.max_results or self.config.batch_size
        )

        emails = []
        for raw_email in raw_emails:
            try:
                email = self._normalize_email(raw_email)
                emails.append(email)
            except Exception as e:
                logger.warning(f"Failed to normalize email: {e}")
                context.add_error(f"Failed to normalize email: {str(e)}")
                if not self.skip_on_error:
                    raise

        return emails

    def _extract_from_database(self, context: PipelineContext) -> List[EmailRecord]:
        """Extract unprocessed emails from database."""
        logger.debug("Fetching unprocessed emails from database")

        if context.dry_run:
            logger.info("DRY RUN: Would fetch emails from database")
            return []

        raw_emails = self.database.get_unprocessed_emails(limit=self.config.batch_size)

        emails = []
        for raw_email in raw_emails:
            try:
                email = self._normalize_email(raw_email)
                emails.append(email)
            except Exception as e:
                logger.warning(f"Failed to normalize email: {e}")
                context.add_error(f"Failed to normalize email: {str(e)}")
                if not self.skip_on_error:
                    raise

        return emails

    def _normalize_email(self, raw_email: tuple) -> EmailRecord:
        """Convert raw email data to EmailRecord."""
        if len(raw_email) != 5:
            raise ValueError(f"Expected 5 elements in raw email tuple, got {len(raw_email)}")

        email_id, subject, sender, date, content = raw_email

        # Ensure date is a string
        if isinstance(date, datetime):
            date = date.isoformat()
        elif date is None:
            date = datetime.now().isoformat()
        else:
            date = str(date)

        return EmailRecord(
            id=email_id,
            subject=subject or "",
            sender=sender or "",
            content=content or "",
            received_date=date,
        )

    def validate_input(self, input_data: Any) -> bool:
        """Validate stage input."""
        # Extract stage doesn't require input data
        return input_data is None or isinstance(input_data, list)

    @property
    def skip_on_error(self) -> bool:
        """Whether to skip emails that fail to process."""
        # Look for skip_on_error in config, default to True
        return getattr(self.config, "skip_on_error", True)
