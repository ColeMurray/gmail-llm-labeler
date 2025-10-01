"""Transform stage implementation for the ETL pipeline."""

import logging
import time
from datetime import datetime
from typing import List

from ..email_processor import EmailProcessor
from ..llm_service import LLMService
from .base import EmailRecord, EnrichedEmailRecord, PipelineContext, PipelineStage
from .config import TransformConfig

logger = logging.getLogger(__name__)


class TransformStage(PipelineStage):
    """Handles email categorization and enrichment."""

    def __init__(
        self,
        config: TransformConfig,
        llm_service: LLMService = None,
        email_processor: EmailProcessor = None,
    ):
        """Initialize the transform stage.

        Args:
            config: Transform stage configuration.
            llm_service: Optional LLMService instance. If not provided, creates a new one.
            email_processor: Optional EmailProcessor instance. If not provided, creates a new one.
        """
        super().__init__()
        self.config = config
        self.llm_service = llm_service or LLMService()
        self.email_processor = email_processor or EmailProcessor()

    def execute(
        self, input_data: List[EmailRecord], context: PipelineContext
    ) -> List[EnrichedEmailRecord]:
        """Transform emails by adding categorization."""
        if not input_data:
            logger.info("No emails to transform")
            return []

        logger.info(f"Starting transformation of {len(input_data)} emails")
        start_time = datetime.now()

        enriched_emails = []
        success_count = 0
        error_count = 0

        for email in input_data:
            try:
                if context.preview_mode:
                    logger.info(f"PREVIEW: Would categorize email {email.id}: {email.subject}")
                    # Create a mock enriched email for preview
                    enriched = EnrichedEmailRecord(
                        **email.__dict__,
                        category="[Preview Mode]",
                        explanation="[Preview Mode - No actual categorization]",
                        confidence=0.0,
                        processing_time=0.0,
                    )
                elif context.dry_run:
                    logger.info(f"DRY RUN: Would categorize email {email.id}")
                    continue
                else:
                    enriched = self._categorize_email(email, context)

                enriched_emails.append(enriched)
                success_count += 1

            except Exception as e:
                error_count += 1
                error_msg = f"Failed to categorize email {email.id}: {e}"
                logger.error(error_msg)
                context.add_error(error_msg)

                if self.config.skip_on_error:
                    continue
                elif not context.config.continue_on_error:
                    raise

        # Update metrics
        elapsed = (datetime.now() - start_time).total_seconds()
        self.metrics["emails_transformed"] = success_count
        self.metrics["transformation_errors"] = error_count
        self.metrics["transformation_time"] = elapsed

        context.add_metric("transform_success_count", success_count)
        context.add_metric("transform_error_count", error_count)
        context.add_metric("transform_time", elapsed)

        logger.info(
            f"Transformed {success_count} emails in {elapsed:.2f} seconds ({error_count} errors)"
        )

        return enriched_emails

    def _categorize_email(
        self, email: EmailRecord, context: PipelineContext
    ) -> EnrichedEmailRecord:
        """Categorize a single email."""
        start_time = time.time()

        # Prepare content
        clean_content = self.email_processor.strip_html(email.content)

        # Truncate if needed
        if len(clean_content) > self.config.max_content_length:
            clean_content = clean_content[: self.config.max_content_length] + "..."
            logger.debug(f"Truncated email content to {self.config.max_content_length} chars")

        email_content = f"Subject: {email.subject}\nFrom: {email.sender}\n\n{clean_content}"

        # Categorize using LLM
        if context.test_mode:
            # In test mode, use a mock categorization
            category = "Test Category"
            explanation = "Test mode - mock categorization"
        else:
            category, explanation = self.llm_service.categorize_email(email_content)

        # Validate category
        if category not in self.config.categories:
            logger.warning(f"Unknown category '{category}' for email {email.id}, using 'Other'")
            category = "Other"

        # Calculate confidence (simple heuristic based on explanation length)
        confidence = self._calculate_confidence(category, explanation)

        processing_time = time.time() - start_time

        # Create enriched record
        return EnrichedEmailRecord(
            id=email.id,
            subject=email.subject,
            sender=email.sender,
            content=email.content,
            received_date=email.received_date,
            category=category,
            explanation=explanation,
            confidence=confidence,
            processing_time=processing_time,
        )

    def _calculate_confidence(self, category: str, explanation: str) -> float:
        """Calculate confidence score for categorization."""
        # Simple heuristic: longer explanations tend to be more confident
        # Categories like "Other" or empty explanations get lower confidence

        if category == "Other":
            base_confidence = 0.5
        elif category in ["Response Needed / High Priority", "Bills"]:
            base_confidence = 0.9
        else:
            base_confidence = 0.7

        # Adjust based on explanation length
        explanation_factor = min(len(explanation) / 200, 1.0) * 0.2

        confidence = min(base_confidence + explanation_factor, 1.0)
        return round(confidence, 2)

    def validate_input(self, input_data: any) -> bool:
        """Validate stage input."""
        if not isinstance(input_data, list):
            return False

        # Check if all items are EmailRecord instances
        for item in input_data:
            if not isinstance(item, EmailRecord):
                return False

        return True
