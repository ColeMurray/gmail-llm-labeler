"""Sync stage implementation for the ETL pipeline."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..database import EmailDatabase
from ..metrics import MetricsTracker
from .base import ActionResult, PipelineContext, PipelineStage
from .config import SyncConfig

logger = logging.getLogger(__name__)


class SyncStage(PipelineStage):
    """Handles database synchronization and metrics."""

    def __init__(
        self,
        config: SyncConfig,
        database: Optional[EmailDatabase] = None,
        metrics_tracker: Optional[MetricsTracker] = None,
    ):
        """Initialize the sync stage.

        Args:
            config: Sync stage configuration.
            database: Optional EmailDatabase instance. If not provided, creates a new one.
            metrics_tracker: Optional MetricsTracker instance. If not provided, creates a new one.
        """
        super().__init__()
        self.config = config
        # Note: The original had db_path parameter, but EmailDatabase doesn't support it
        # Using the default database_file parameter instead
        self.database = database or EmailDatabase(
            database_file=getattr(config, "database_path", "email_pipeline.db")
        )
        self.metrics_tracker = metrics_tracker or MetricsTracker()

    def execute(self, input_data: List[ActionResult], context: PipelineContext) -> None:
        """Sync results to database and save metrics."""
        if not input_data:
            logger.info("No results to sync")
            return

        logger.info(f"Starting sync of {len(input_data)} results")
        start_time = datetime.now()

        if context.dry_run:
            logger.info("DRY RUN: Would sync results to database")
            self._log_dry_run_summary(input_data, context)
            return

        success_count = 0
        error_count = 0

        # Process results in batches
        batch_size = self.config.batch_size
        for i in range(0, len(input_data), batch_size):
            batch = input_data[i : i + batch_size]

            try:
                # Sync batch to database
                for result in batch:
                    try:
                        self._sync_email_result(result, context)
                        success_count += 1

                        # Track metrics if enabled
                        if self.config.track_metrics:
                            self.metrics_tracker.add_result(
                                result.email_id, result.category, success=result.success
                            )

                    except Exception as e:
                        error_count += 1
                        error_msg = f"Failed to sync result for email {result.email_id}: {e}"
                        logger.error(error_msg)
                        context.add_error(error_msg)

                        if not context.config.continue_on_error:
                            raise

            except Exception as e:
                logger.error(f"Batch sync failed: {e}")
                if not context.config.continue_on_error:
                    raise

        # Save pipeline metrics if enabled
        if self.config.save_metrics:
            self._save_pipeline_metrics(context, input_data)

        # Update stage metrics
        elapsed = (datetime.now() - start_time).total_seconds()
        self.metrics["results_synced"] = success_count
        self.metrics["sync_errors"] = error_count
        self.metrics["sync_time"] = elapsed

        context.add_metric("sync_success_count", success_count)
        context.add_metric("sync_error_count", error_count)
        context.add_metric("sync_time", elapsed)

        logger.info(
            f"Synced {success_count} results in {elapsed:.2f} seconds ({error_count} errors)"
        )

    def _sync_email_result(self, result: ActionResult, context: PipelineContext):
        """Sync a single email result to database."""
        # Extract label IDs from actions
        label_ids = self._extract_label_ids(result.actions_taken)

        # Update database
        if context.preview_mode:
            logger.info(
                f"PREVIEW: Would update database for email {result.email_id} "
                f"with category '{result.category}'"
            )
        else:
            self.database.update_email_labels(
                email_id=result.email_id, category=result.category, label_ids=label_ids
            )

            # If tracking history, add a history entry
            if self.config.track_history:
                self._add_history_entry(result, context)

    def _extract_label_ids(self, actions_taken: List[str]) -> List[str]:
        """Extract label IDs from actions taken."""
        label_ids = []

        for action in actions_taken:
            # Remove preview/dry-run prefixes
            clean_action = action.replace("[preview] ", "").replace("[dry-run] ", "")

            # Extract label information from actions
            if clean_action.startswith("label:"):
                label_name = clean_action.replace("label:", "")
                # In a real implementation, we'd look up the label ID
                # For now, we'll just use the label name
                label_ids.append(label_name)

        return label_ids

    def _add_history_entry(self, result: ActionResult, context: PipelineContext):
        """Add a history entry for the processed email."""
        try:
            # Create history entry
            history_entry = {
                "email_id": result.email_id,
                "category": result.category,
                "actions": result.actions_taken,
                "success": result.success,
                "errors": result.errors,
                "run_id": context.run_id,
                "timestamp": datetime.now().isoformat(),
            }

            # In a real implementation, this would be stored in a history table
            # For now, we'll just log it
            logger.debug(f"History entry: {history_entry}")

        except Exception as e:
            logger.warning(f"Failed to add history entry: {e}")

    def _save_pipeline_metrics(self, context: PipelineContext, results: List[ActionResult]):
        """Save pipeline metrics to file."""
        try:
            # Compile metrics
            metrics = {
                "run_id": context.run_id,
                "start_time": context.start_time.isoformat(),
                "end_time": datetime.now().isoformat(),
                "pipeline_metrics": context.metrics,
                "stage_metrics": {"sync": self.metrics},
                "summary": {
                    "total_processed": len(results),
                    "successful": sum(1 for r in results if r.success),
                    "failed": sum(1 for r in results if not r.success),
                    "categories": self._count_categories(results),
                    "actions": self._count_actions(results),
                },
                "errors": context.errors[-10:] if context.errors else [],  # Last 10 errors
            }

            # Determine export format
            if context.config.monitoring.metrics_export == "json":
                self._save_json_metrics(metrics, context.config.monitoring.metrics_path)
            elif context.config.monitoring.metrics_export == "csv":
                self._save_csv_metrics(metrics, context.config.monitoring.metrics_path)
            else:
                logger.warning(
                    f"Unknown metrics export format: {context.config.monitoring.metrics_export}"
                )

        except Exception as e:
            logger.error(f"Failed to save pipeline metrics: {e}")
            context.add_error(f"Failed to save metrics: {str(e)}")

    def _save_json_metrics(self, metrics: Dict[str, Any], path: str):
        """Save metrics as JSON."""
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            json.dump(metrics, f, indent=2, default=str)

        logger.info(f"Saved metrics to {output_path}")

    def _save_csv_metrics(self, metrics: Dict[str, Any], path: str):
        """Save metrics as CSV."""
        # For CSV, we'll save a simplified summary
        import csv

        output_path = Path(path).with_suffix(".csv")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Flatten metrics for CSV
        rows = []
        summary = metrics["summary"]

        for category, count in summary["categories"].items():
            rows.append(
                {
                    "run_id": metrics["run_id"],
                    "timestamp": metrics["end_time"],
                    "category": category,
                    "count": count,
                    "type": "category",
                }
            )

        for action, count in summary["actions"].items():
            rows.append(
                {
                    "run_id": metrics["run_id"],
                    "timestamp": metrics["end_time"],
                    "action": action,
                    "count": count,
                    "type": "action",
                }
            )

        # Write CSV
        if rows:
            with open(output_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            logger.info(f"Saved metrics to {output_path}")

    def _count_categories(self, results: List[ActionResult]) -> Dict[str, int]:
        """Count emails by category."""
        categories: Dict[str, int] = {}
        for result in results:
            categories[result.category] = categories.get(result.category, 0) + 1
        return categories

    def _count_actions(self, results: List[ActionResult]) -> Dict[str, int]:
        """Count actions taken."""
        actions: Dict[str, int] = {}
        for result in results:
            for action in result.actions_taken:
                # Clean action name
                clean_action = action.replace("[preview] ", "").replace("[dry-run] ", "")
                actions[clean_action] = actions.get(clean_action, 0) + 1
        return actions

    def _log_dry_run_summary(self, results: List[ActionResult], context: PipelineContext):
        """Log a summary for dry-run mode."""
        categories = self._count_categories(results)
        actions = self._count_actions(results)

        logger.info("=" * 50)
        logger.info("DRY RUN SUMMARY")
        logger.info("=" * 50)
        logger.info(f"Total emails: {len(results)}")
        logger.info(f"Successful: {sum(1 for r in results if r.success)}")
        logger.info(f"Failed: {sum(1 for r in results if not r.success)}")

        logger.info("\nCategories:")
        for category, count in sorted(categories.items()):
            logger.info(f"  {category}: {count}")

        logger.info("\nActions that would be taken:")
        for action, count in sorted(actions.items()):
            logger.info(f"  {action}: {count}")

        if context.errors:
            logger.info(f"\nErrors encountered: {len(context.errors)}")
            for error in context.errors[:5]:  # Show first 5 errors
                logger.info(f"  - {error}")

        logger.info("=" * 50)

    def validate_input(self, input_data: Any) -> bool:
        """Validate stage input."""
        if not isinstance(input_data, list):
            return False

        # Check if all items are ActionResult instances
        for item in input_data:
            if not isinstance(item, ActionResult):
                return False

        return True
