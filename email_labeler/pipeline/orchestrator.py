"""Main pipeline orchestrator for the ETL pipeline."""

import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..database import EmailDatabase
from ..email_processor import EmailProcessor
from ..llm_service import LLMService
from ..metrics import MetricsTracker
from .base import PipelineContext, PipelineRun, PipelineStage
from .config import PipelineConfig
from .extract_stage import ExtractStage
from .load_stage import LoadStage
from .sync_stage import SyncStage
from .transform_stage import TransformStage

logger = logging.getLogger(__name__)


class EmailPipeline:
    """Main orchestrator for the email processing ETL pipeline."""

    def __init__(
        self,
        config: PipelineConfig,
        email_processor: EmailProcessor = None,
        database: EmailDatabase = None,
        llm_service: LLMService = None,
        metrics_tracker: MetricsTracker = None,
    ):
        """Initialize the pipeline with configuration.

        Args:
            config: Pipeline configuration.
            email_processor: Optional shared EmailProcessor instance.
            database: Optional shared EmailDatabase instance.
            llm_service: Optional shared LLMService instance.
            metrics_tracker: Optional shared MetricsTracker instance.
        """
        self.config = config
        self.stages: OrderedDict[str, PipelineStage] = OrderedDict()

        # Store shared dependencies
        self.email_processor = email_processor
        self.database = database
        self.llm_service = llm_service
        self.metrics_tracker = metrics_tracker

        # Initialize default stages
        self._initialize_default_stages()

        # Configure logging
        self._configure_logging()

    def _initialize_default_stages(self):
        """Initialize the default pipeline stages with dependency injection."""
        # Create shared dependencies if not provided
        if self.email_processor is None:
            self.email_processor = EmailProcessor(lazy_init=True)
        if self.database is None:
            self.database = EmailDatabase()
        if self.llm_service is None:
            self.llm_service = LLMService(lazy_init=True)
        if self.metrics_tracker is None:
            self.metrics_tracker = MetricsTracker()

        # Initialize stages with shared dependencies
        self.stages["extract"] = ExtractStage(
            self.config.extract, email_processor=self.email_processor, database=self.database
        )
        self.stages["transform"] = TransformStage(
            self.config.transform,
            llm_service=self.llm_service,
            email_processor=self.email_processor,
        )
        self.stages["load"] = LoadStage(self.config.load, email_processor=self.email_processor)
        self.stages["sync"] = SyncStage(
            self.config.sync, database=self.database, metrics_tracker=self.metrics_tracker
        )

        logger.info(f"Initialized pipeline with {len(self.stages)} stages")

    def _configure_logging(self):
        """Configure logging based on monitoring config."""
        log_level = getattr(logging, self.config.monitoring.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    def add_stage(
        self,
        name: str,
        stage: PipelineStage,
        after: Optional[str] = None,
        before: Optional[str] = None,
    ):
        """Add a custom stage to the pipeline."""
        if after and before:
            raise ValueError("Cannot specify both 'after' and 'before'")

        if after:
            if after not in self.stages:
                raise ValueError(f"Stage '{after}' not found")
            # Insert after the specified stage
            items = list(self.stages.items())
            index = next(i for i, (k, v) in enumerate(items) if k == after) + 1
            items.insert(index, (name, stage))
            self.stages = OrderedDict(items)

        elif before:
            if before not in self.stages:
                raise ValueError(f"Stage '{before}' not found")
            # Insert before the specified stage
            items = list(self.stages.items())
            index = next(i for i, (k, v) in enumerate(items) if k == before)
            items.insert(index, (name, stage))
            self.stages = OrderedDict(items)

        else:
            # Add at the end
            self.stages[name] = stage

        logger.info(f"Added stage '{name}' to pipeline")

    def remove_stage(self, name: str):
        """Remove a stage from the pipeline."""
        if name not in self.stages:
            raise ValueError(f"Stage '{name}' not found")

        del self.stages[name]
        logger.info(f"Removed stage '{name}' from pipeline")

    def run(
        self, dry_run: Optional[bool] = None, preview_mode: bool = False, test_mode: bool = False
    ) -> PipelineRun:
        """Execute the complete pipeline."""
        # Use config dry_run if not specified
        if dry_run is None:
            dry_run = self.config.dry_run

        # Create pipeline context
        context = PipelineContext.create(
            config=self.config, dry_run=dry_run, preview_mode=preview_mode, test_mode=test_mode
        )

        logger.info(f"Starting pipeline run {context.run_id}")
        if dry_run:
            logger.info("Running in DRY RUN mode - no changes will be made")
        if preview_mode:
            logger.info("Running in PREVIEW mode - showing what would be done")
        if test_mode:
            logger.info("Running in TEST mode - using mock data")

        start_time = datetime.now()
        stages_completed = []
        data = None

        try:
            # Execute each stage in sequence
            for stage_name, stage in self.stages.items():
                logger.info(f"Executing stage: {stage_name}")
                stage_start = datetime.now()

                try:
                    # Validate input
                    if not stage.validate_input(data):
                        raise ValueError(f"Invalid input for stage '{stage_name}'")

                    # Execute stage
                    data = stage.execute(data, context)

                    # Record completion
                    stages_completed.append(stage_name)
                    stage_elapsed = (datetime.now() - stage_start).total_seconds()

                    # Add stage metrics to context
                    context.add_metric(f"{stage_name}_time", stage_elapsed)
                    for key, value in stage.get_metrics().items():
                        context.add_metric(f"{stage_name}_{key}", value)

                    logger.info(f"Stage '{stage_name}' completed in {stage_elapsed:.2f}s")

                    # Check if we should continue (for early exit scenarios)
                    if self._should_stop(data, context):
                        logger.info(f"Stopping pipeline after stage '{stage_name}'")
                        break

                except Exception as e:
                    error_msg = f"Stage '{stage_name}' failed: {str(e)}"
                    logger.error(error_msg)
                    context.add_error(error_msg)

                    if not self.config.continue_on_error:
                        raise

                    # Skip to next stage or stop
                    if stage_name in ["extract", "transform"]:
                        # Critical stages - stop pipeline
                        logger.error("Critical stage failed, stopping pipeline")
                        break

        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            context.add_error(f"Pipeline failed: {str(e)}")

        finally:
            end_time = datetime.now()
            elapsed = (end_time - start_time).total_seconds()

            # Create pipeline run result
            run_result = self._create_run_result(context, start_time, end_time, stages_completed)

            logger.info(f"Pipeline run {context.run_id} completed in {elapsed:.2f}s")
            logger.info(f"Stages completed: {', '.join(stages_completed)}")
            logger.info(f"Emails processed: {run_result.emails_processed}")
            logger.info(f"Success rate: {run_result.successful}/{run_result.emails_processed}")

            if context.errors:
                logger.warning(f"Errors encountered: {len(context.errors)}")
                for error in context.errors[:5]:  # Show first 5 errors
                    logger.warning(f"  - {error}")

            return run_result

    def run_stage(self, stage_name: str, input_data: Any = None, dry_run: bool = False) -> Any:
        """Run a single stage independently (for debugging)."""
        if stage_name not in self.stages:
            raise ValueError(f"Stage '{stage_name}' not found")

        stage = self.stages[stage_name]
        context = PipelineContext.create(config=self.config, dry_run=dry_run)

        logger.info(f"Running stage '{stage_name}' independently")

        try:
            if not stage.validate_input(input_data):
                raise ValueError(f"Invalid input for stage '{stage_name}'")

            result = stage.execute(input_data, context)

            logger.info(f"Stage '{stage_name}' completed successfully")
            return result

        except Exception as e:
            logger.error(f"Stage '{stage_name}' failed: {e}")
            raise

    def _should_stop(self, data: Any, context: PipelineContext) -> bool:
        """Determine if pipeline should stop early."""
        # Stop if no data to process
        if data is None or (isinstance(data, list) and len(data) == 0):
            logger.info("No data to process, stopping pipeline")
            return True

        # Stop if too many errors
        max_errors = 100  # Configurable threshold
        if len(context.errors) > max_errors:
            logger.error(f"Too many errors ({len(context.errors)}), stopping pipeline")
            return True

        return False

    def _create_run_result(
        self,
        context: PipelineContext,
        start_time: datetime,
        end_time: datetime,
        stages_completed: List[str],
    ) -> PipelineRun:
        """Create the pipeline run result."""
        # Extract summary metrics from context
        emails_processed = context.metrics.get("extract_emails_count", 0)
        successful = context.metrics.get("load_success_count", 0)
        failed = context.metrics.get("load_error_count", 0)

        return PipelineRun(
            run_id=context.run_id,
            start_time=start_time,
            end_time=end_time,
            stages_completed=stages_completed,
            emails_processed=emails_processed,
            successful=successful,
            failed=failed,
            errors=context.errors,
            metrics=context.metrics,
        )

    def get_stage_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics from all stages."""
        metrics = {}
        for name, stage in self.stages.items():
            metrics[name] = stage.get_metrics()
        return metrics

    def reset_metrics(self):
        """Reset metrics for all stages."""
        for stage in self.stages.values():
            stage.reset_metrics()
        logger.info("Reset all stage metrics")
