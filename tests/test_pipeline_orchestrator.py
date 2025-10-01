"""Tests for pipeline orchestrator."""

from unittest.mock import Mock

from email_labeler.pipeline.base import (
    ActionResult,
    EmailRecord,
    EnrichedEmailRecord,
)
from email_labeler.pipeline.orchestrator import EmailPipeline


class TestEmailPipeline:
    """Test cases for EmailPipeline orchestrator."""

    def test_init(
        self,
        mock_email_processor,
        email_database,
        llm_service,
        mock_metrics_tracker,
        pipeline_config,
    ):
        """Test EmailPipeline initialization."""
        pipeline = EmailPipeline(
            config=pipeline_config,
            email_processor=mock_email_processor,
            database=email_database,
            llm_service=llm_service,
            metrics_tracker=mock_metrics_tracker,
        )

        assert pipeline.email_processor == mock_email_processor
        assert pipeline.database == email_database
        assert pipeline.llm_service == llm_service
        assert pipeline.config == pipeline_config

        # Check that stages are initialized
        assert "extract" in pipeline.stages
        assert "transform" in pipeline.stages
        assert "load" in pipeline.stages
        assert "sync" in pipeline.stages

    def test_run_full_pipeline_success(
        self,
        mock_email_processor,
        email_database,
        llm_service,
        mock_metrics_tracker,
        pipeline_config,
    ):
        """Test successful full pipeline execution."""
        pipeline = EmailPipeline(
            config=pipeline_config,
            email_processor=mock_email_processor,
            database=email_database,
            llm_service=llm_service,
            metrics_tracker=mock_metrics_tracker,
        )

        # Mock stage executions
        sample_emails = [
            EmailRecord(
                id="msg1",
                subject="Test Email",
                sender="test@example.com",
                content="Test content",
                received_date="2024-01-01T10:00:00Z",
            )
        ]

        sample_enriched = [
            EnrichedEmailRecord(
                **sample_emails[0].__dict__,
                category="Work",
                explanation="Business email",
                confidence=0.9,
                processing_time=1.5,
            )
        ]

        sample_load_results = [
            ActionResult(
                email_id="msg1", category="Work", actions_taken=["saved_to_database"], success=True
            )
        ]

        sample_sync_results = [
            ActionResult(
                email_id="msg1", category="Work", actions_taken=["label_applied"], success=True
            )
        ]

        # Mock each stage
        for stage_name in ["extract", "transform", "load", "sync"]:
            pipeline.stages[stage_name].validate_input = Mock(return_value=True)  # type: ignore[method-assign]
            pipeline.stages[stage_name].get_metrics = Mock(return_value={})  # type: ignore[method-assign]

        # Mock extract stage to add metrics to context
        def mock_extract_execute(input_data, context):
            context.add_metric("extract_emails_count", 1)
            return sample_emails

        # Mock load stage to add metrics to context
        def mock_load_execute(input_data, context):
            context.add_metric("load_success_count", 1)
            context.add_metric("load_error_count", 0)
            return sample_load_results

        pipeline.stages["extract"].execute = Mock(side_effect=mock_extract_execute)  # type: ignore[method-assign]
        pipeline.stages["transform"].execute = Mock(return_value=sample_enriched)  # type: ignore[method-assign]
        pipeline.stages["load"].execute = Mock(side_effect=mock_load_execute)  # type: ignore[method-assign]
        pipeline.stages["sync"].execute = Mock(return_value=sample_sync_results)  # type: ignore[method-assign]

        # Execute pipeline
        run_result = pipeline.run()

        assert len(run_result.stages_completed) == 4
        assert run_result.emails_processed == 1
        assert run_result.successful == 1  # Now properly mocked
        assert run_result.failed == 0
        assert len(run_result.errors) == 0

        # Verify all stages were called
        pipeline.stages["extract"].execute.assert_called_once()
        pipeline.stages["transform"].execute.assert_called_once()
        pipeline.stages["load"].execute.assert_called_once()
        pipeline.stages["sync"].execute.assert_called_once()

    def test_run_extract_stage_failure(
        self,
        mock_email_processor,
        email_database,
        llm_service,
        mock_metrics_tracker,
        pipeline_config,
    ):
        """Test pipeline with extract stage failure."""
        pipeline = EmailPipeline(
            config=pipeline_config,
            email_processor=mock_email_processor,
            database=email_database,
            llm_service=llm_service,
            metrics_tracker=mock_metrics_tracker,
        )

        # Mock extract stage failure
        pipeline.stages["extract"].validate_input = Mock(return_value=True)  # type: ignore[method-assign]
        pipeline.stages["extract"].execute = Mock(side_effect=Exception("Extract failed"))  # type: ignore[method-assign]
        pipeline.stages["extract"].get_metrics = Mock(return_value={})  # type: ignore[method-assign]

        run_result = pipeline.run()

        assert len(run_result.errors) > 0
        assert "Extract failed" in str(run_result.errors)
        assert run_result.emails_processed == 0
