"""Load stage implementation for the ETL pipeline."""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..email_processor import EmailProcessor
from ..gmail_utils import add_labels_to_email, mark_as_read
from .base import ActionResult, EnrichedEmailRecord, PipelineContext, PipelineStage
from .config import LoadConfig

logger = logging.getLogger(__name__)


class LoadStage(PipelineStage):
    """Handles applying categorization results to Gmail."""

    def __init__(self, config: LoadConfig, email_processor: Optional[EmailProcessor] = None):
        """Initialize the load stage.

        Args:
            config: Load stage configuration.
            email_processor: Optional EmailProcessor instance. If not provided, creates a new one.
        """
        super().__init__()
        self.config = config
        self.email_processor = email_processor or EmailProcessor()
        self._label_cache: Dict[str, str] = {}

    def execute(
        self, input_data: List[EnrichedEmailRecord], context: PipelineContext
    ) -> List[ActionResult]:
        """Apply labels and actions to categorized emails."""
        if not input_data:
            logger.info("No emails to load")
            return []

        logger.info(f"Starting load of {len(input_data)} categorized emails")
        start_time = datetime.now()

        results = []

        # Initialize labels if needed
        if self.config.apply_labels and not context.dry_run:
            self._ensure_labels_exist(input_data, context)

        success_count = 0
        error_count = 0

        for email in input_data:
            try:
                result = self._process_email(email, context)
                results.append(result)

                if result.success:
                    success_count += 1
                else:
                    error_count += 1

            except Exception as e:
                error_count += 1
                error_msg = f"Failed to process email {email.id}: {e}"
                logger.error(error_msg)
                context.add_error(error_msg)

                # Create failed result
                result = ActionResult(
                    email_id=email.id,
                    category=email.category,
                    actions_taken=[],
                    success=False,
                    errors=[str(e)],
                )
                results.append(result)

                if not context.config.continue_on_error:
                    raise

        # Update metrics
        elapsed = (datetime.now() - start_time).total_seconds()
        self.metrics["emails_loaded"] = success_count
        self.metrics["load_errors"] = error_count
        self.metrics["load_time"] = elapsed
        self.metrics["actions_applied"] = self._count_actions(results)

        context.add_metric("load_success_count", success_count)
        context.add_metric("load_error_count", error_count)
        context.add_metric("load_time", elapsed)

        logger.info(
            f"Loaded {success_count} emails in {elapsed:.2f} seconds ({error_count} errors)"
        )

        return results

    def _ensure_labels_exist(self, emails: List[EnrichedEmailRecord], context: PipelineContext):
        """Ensure all required labels exist in Gmail."""
        if not self.config.create_missing_labels:
            return

        # Get unique categories
        categories = {email.category for email in emails}

        logger.info(f"Ensuring labels exist for {len(categories)} categories")

        for category in categories:
            if category not in self._label_cache:
                try:
                    label_id = self.email_processor.get_or_create_label(category)
                    if label_id is not None:
                        self._label_cache[category] = label_id
                        logger.debug(f"Cached label '{category}': {label_id}")
                    else:
                        logger.error(f"Failed to create label '{category}': returned None")
                        context.add_error(f"Failed to create label '{category}': returned None")
                except Exception as e:
                    logger.error(f"Failed to create label '{category}': {e}")
                    context.add_error(f"Failed to create label '{category}': {str(e)}")

    def _process_email(self, email: EnrichedEmailRecord, context: PipelineContext) -> ActionResult:
        """Apply actions for a single email."""
        actions_taken = []
        errors = []

        # Get actions for category
        category_actions = self.config.category_actions.get(
            email.category, self.config.default_actions
        )

        logger.debug(
            f"Processing email {email.id} with category '{email.category}' "
            f"and actions: {category_actions}"
        )

        # Apply each action
        for action in category_actions:
            try:
                if context.preview_mode:
                    logger.info(f"PREVIEW: Would {action} for email {email.id} ({email.subject})")
                    actions_taken.append(f"[preview] {action}")

                elif context.dry_run:
                    logger.info(f"DRY RUN: Would {action} for email {email.id}")
                    actions_taken.append(f"[dry-run] {action}")

                else:
                    success = self._apply_action(email, action, context)
                    if success:
                        actions_taken.append(action)
                    else:
                        errors.append(f"{action}: failed")

            except Exception as e:
                error_msg = f"{action}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Action failed for email {email.id}: {error_msg}")

        return ActionResult(
            email_id=email.id,
            category=email.category,
            actions_taken=actions_taken,
            success=len(errors) == 0,
            errors=errors,
        )

    def _apply_action(
        self, email: EnrichedEmailRecord, action: str, context: PipelineContext
    ) -> bool:
        """Apply a single action to an email."""
        try:
            if action == "apply_label":
                return self._apply_label(email)

            elif action == "archive":
                return self._archive_email(email)

            elif action == "star":
                return self._star_email(email)

            elif action == "mark_as_read":
                return self._mark_as_read(email)

            else:
                logger.warning(f"Unknown action: {action}")
                return False

        except Exception as e:
            logger.error(f"Failed to apply action '{action}' to email {email.id}: {e}")
            return False

    def _apply_label(self, email: EnrichedEmailRecord) -> bool:
        """Apply category label to email."""
        if not self.config.apply_labels:
            return True

        # Get label ID from cache
        label_id = self._label_cache.get(email.category)
        if not label_id:
            # Try to get or create label
            try:
                label_id = self.email_processor.get_or_create_label(email.category)
                if label_id is None:
                    logger.error(f"Failed to get label for '{email.category}': returned None")
                    return False
                self._label_cache[email.category] = label_id
            except Exception as e:
                logger.error(f"Failed to get label for '{email.category}': {e}")
                return False

        # Apply label
        return self.email_processor.add_labels_to_email(email.id, [label_id])

    def _archive_email(self, email: EnrichedEmailRecord) -> bool:
        """Archive email (remove from inbox)."""
        return self.email_processor.remove_from_inbox(email.id)

    def _star_email(self, email: EnrichedEmailRecord) -> bool:
        """Star an email."""
        # Add STARRED label
        return add_labels_to_email(self.email_processor.gmail, email.id, ["STARRED"], [])

    def _mark_as_read(self, email: EnrichedEmailRecord) -> bool:
        """Mark email as read."""
        return mark_as_read(self.email_processor.gmail, email.id)

    def _count_actions(self, results: List[ActionResult]) -> Dict[str, int]:
        """Count the number of each action type applied."""
        action_counts: Dict[str, int] = {}
        for result in results:
            for action in result.actions_taken:
                # Remove preview/dry-run prefixes for counting
                clean_action = action.replace("[preview] ", "").replace("[dry-run] ", "")
                action_counts[clean_action] = action_counts.get(clean_action, 0) + 1
        return action_counts

    def validate_input(self, input_data: Any) -> bool:
        """Validate stage input."""
        if not isinstance(input_data, list):
            return False

        # Check if all items are EnrichedEmailRecord instances
        for item in input_data:
            if not isinstance(item, EnrichedEmailRecord):
                return False

        return True
