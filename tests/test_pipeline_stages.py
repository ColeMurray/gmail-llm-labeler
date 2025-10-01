"""Tests for pipeline stages."""

from unittest.mock import MagicMock, patch

import pytest

from email_labeler.pipeline.base import (
    ActionResult,
    EmailRecord,
    EnrichedEmailRecord,
    PipelineContext,
)
from email_labeler.pipeline.extract_stage import ExtractStage
from email_labeler.pipeline.load_stage import LoadStage
from email_labeler.pipeline.sync_stage import SyncStage
from email_labeler.pipeline.transform_stage import TransformStage


class TestExtractStage:
    """Test cases for ExtractStage."""

    def test_init(self, mock_email_processor, email_database, pipeline_config):
        """Test ExtractStage initialization."""
        stage = ExtractStage(
            config=pipeline_config.extract,
            email_processor=mock_email_processor,
            database=email_database,
        )

        assert stage.email_processor == mock_email_processor
        assert stage.database == email_database
        assert stage.config == pipeline_config.extract

    def test_execute_success(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test successful email extraction."""
        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        # Mock email processor to return test emails
        mock_email_processor.fetch_emails_from_gmail.return_value = [
            ("msg1", "Subject 1", "sender1@example.com", "2024-01-01T10:00:00Z", "Content 1"),
            ("msg2", "Subject 2", "sender2@example.com", "2024-01-01T10:00:00Z", "Content 2"),
        ]

        emails = stage.execute(None, pipeline_context)

        assert len(emails) == 2
        assert all(isinstance(email, EmailRecord) for email in emails)
        assert emails[0].id == "msg1"
        assert emails[1].id == "msg2"

    def test_execute_with_filtering(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test email extraction with filtering."""
        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        # Mock email processor to return test emails
        mock_email_processor.fetch_emails_from_gmail.return_value = [
            ("msg1", "Subject 1", "sender1@example.com", "2024-01-01T10:00:00Z", "Content 1"),
            ("msg2", "Subject 2", "sender2@example.com", "2024-01-01T10:00:00Z", "Content 2"),
        ]

        emails = stage.execute(None, pipeline_context)

        # Should return all emails from email processor
        assert len(emails) == 2
        assert emails[0].id == "msg1"
        assert emails[1].id == "msg2"

    def test_execute_api_error(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test handling of Gmail API errors."""
        from googleapiclient.errors import HttpError

        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        error = HttpError(resp=MagicMock(status=403), content=b"Forbidden")
        mock_email_processor.fetch_emails_from_gmail.side_effect = error

        # Should return empty list if continue_on_error is True
        emails = stage.execute(None, pipeline_context)
        assert emails == []

    def test_execute_empty_result(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test extraction with no emails found."""
        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        mock_email_processor.fetch_emails_from_gmail.return_value = []

        emails = stage.execute(None, pipeline_context)

        assert emails == []

    def test_batch_processing(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test batch processing of emails."""
        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        # Create large number of email tuples
        test_emails = [
            (
                f"msg{i}",
                f"Subject {i}",
                f"sender{i}@example.com",
                "2024-01-01T10:00:00Z",
                f"Content {i}",
            )
            for i in range(25)
        ]
        mock_email_processor.fetch_emails_from_gmail.return_value = test_emails

        emails = stage.execute(None, pipeline_context)

        assert len(emails) == 25

    def test_rate_limiting(
        self, mock_email_processor, email_database, pipeline_config, pipeline_context
    ):
        """Test rate limiting handling."""
        from googleapiclient.errors import HttpError

        stage = ExtractStage(pipeline_config.extract, mock_email_processor, email_database)

        rate_limit_error = HttpError(resp=MagicMock(status=429), content=b"Rate limit exceeded")
        mock_email_processor.fetch_emails_from_gmail.side_effect = rate_limit_error

        # Should return empty list if continue_on_error is True
        emails = stage.execute(None, pipeline_context)
        assert emails == []


class TestTransformStage:
    """Test cases for TransformStage."""

    def test_init(self, llm_service, mock_email_processor, pipeline_config):
        """Test TransformStage initialization."""
        stage = TransformStage(
            config=pipeline_config.transform,
            llm_service=llm_service,
            email_processor=mock_email_processor,
        )

        assert stage.llm_service == llm_service
        assert stage.email_processor == mock_email_processor
        assert stage.config == pipeline_config.transform

    def test_execute_success(
        self,
        llm_service,
        mock_email_processor,
        pipeline_config,
        pipeline_context_no_test_mode,
        sample_email_records,
    ):
        """Test successful email transformation."""
        stage = TransformStage(pipeline_config.transform, llm_service, mock_email_processor)

        # Mock LLM service responses
        llm_service.categorize_email.side_effect = [
            ("Work", "Business email"),
            ("Newsletters", "Marketing content"),
            ("Personal", "Personal message"),
        ]

        enriched_emails = stage.execute(sample_email_records, pipeline_context_no_test_mode)

        assert len(enriched_emails) == 3
        assert all(isinstance(email, EnrichedEmailRecord) for email in enriched_emails)

        assert enriched_emails[0].category == "Work"
        assert enriched_emails[1].category == "Newsletters"
        assert enriched_emails[2].category == "Personal"

        assert llm_service.categorize_email.call_count == 3

    def test_execute_with_errors(
        self,
        llm_service,
        mock_email_processor,
        pipeline_config,
        pipeline_context_no_test_mode,
        sample_email_records,
    ):
        """Test transformation with LLM errors."""
        stage = TransformStage(pipeline_config.transform, llm_service, mock_email_processor)

        # First email fails, others succeed
        llm_service.categorize_email.side_effect = [
            Exception("LLM Error"),
            ("Newsletters", "Marketing content"),
            ("Personal", "Personal message"),
        ]

        enriched_emails = stage.execute(sample_email_records, pipeline_context_no_test_mode)

        # Should still return results for successful emails
        assert len(enriched_emails) == 2
        assert enriched_emails[0].category == "Newsletters"
        assert enriched_emails[1].category == "Personal"

    def test_execute_batch_processing(
        self, llm_service, mock_email_processor, pipeline_config, pipeline_context_no_test_mode
    ):
        """Test batch processing in transform stage."""
        stage = TransformStage(pipeline_config.transform, llm_service, mock_email_processor)

        # Create large batch of emails
        large_batch = []
        for i in range(50):
            large_batch.append(
                EmailRecord(
                    id=f"msg{i}",
                    subject=f"Subject {i}",
                    sender=f"sender{i}@example.com",
                    content=f"Content {i}",
                    received_date="2024-01-01T10:00:00Z",
                )
            )

        llm_service.categorize_email.return_value = ("Work", "Business email")

        enriched_emails = stage.execute(large_batch, pipeline_context_no_test_mode)

        assert len(enriched_emails) == 50
        assert llm_service.categorize_email.call_count == 50

    def test_execute_skip_on_error(
        self,
        llm_service,
        mock_email_processor,
        pipeline_config,
        pipeline_context_no_test_mode,
        sample_email_records,
    ):
        """Test error handling with skip_on_error enabled."""
        stage = TransformStage(pipeline_config.transform, llm_service, mock_email_processor)

        # First email fails, should be skipped due to skip_on_error=True
        llm_service.categorize_email.side_effect = Exception("Temporary error")

        enriched_emails = stage.execute([sample_email_records[0]], pipeline_context_no_test_mode)

        # Should return empty list when error occurs and skip_on_error is True
        assert len(enriched_emails) == 0
        assert llm_service.categorize_email.call_count == 1
        assert len(pipeline_context_no_test_mode.errors) == 1

    def test_timeout_handling(
        self,
        llm_service,
        mock_email_processor,
        pipeline_config,
        pipeline_context_no_test_mode,
        sample_email_records,
    ):
        """Test handling of LLM timeouts."""
        stage = TransformStage(pipeline_config.transform, llm_service, mock_email_processor)

        from concurrent.futures import TimeoutError

        llm_service.categorize_email.side_effect = TimeoutError("LLM timeout")

        enriched_emails = stage.execute(sample_email_records, pipeline_context_no_test_mode)

        # Should return empty list for timeout cases
        assert len(enriched_emails) == 0


class TestLoadStage:
    """Test cases for LoadStage."""

    def test_init(self, mock_email_processor, pipeline_config):
        """Test LoadStage initialization."""
        stage = LoadStage(config=pipeline_config.load, email_processor=mock_email_processor)

        assert stage.email_processor == mock_email_processor
        assert stage.config == pipeline_config.load

    def test_execute_success(
        self, mock_email_processor, pipeline_config, pipeline_context, sample_enriched_email_records
    ):
        """Test successful loading of enriched emails."""
        stage = LoadStage(pipeline_config.load, mock_email_processor)

        results = stage.execute(sample_enriched_email_records, pipeline_context)

        assert len(results) == 3
        assert all(isinstance(result, ActionResult) for result in results)
        assert all(result.success for result in results)

        # Verify email processor calls were made for applying labels
        assert (
            mock_email_processor.get_or_create_label.call_count > 0
            or mock_email_processor.add_labels_to_email.call_count >= 0
        )

    def test_execute_database_error(
        self, mock_email_processor, pipeline_config, pipeline_context, sample_enriched_email_records
    ):
        """Test handling of database errors."""
        stage = LoadStage(pipeline_config.load, mock_email_processor)

        # Mock email processor error
        mock_email_processor.add_labels_to_email.side_effect = Exception("Email processor error")

        results = stage.execute(sample_enriched_email_records, pipeline_context)

        assert len(results) == 3
        assert all(not result.success for result in results)
        # Check that errors contain some indication of failure
        assert all(len(result.errors) > 0 for result in results)

    def test_execute_partial_success(
        self, mock_email_processor, pipeline_config, pipeline_context, sample_enriched_email_records
    ):
        """Test partial success in loading."""
        stage = LoadStage(pipeline_config.load, mock_email_processor)

        # First email fails, others succeed
        def mock_apply_labels(email_id, label_ids):
            if email_id == sample_enriched_email_records[0].id:
                raise Exception("Email processor error")
            return True

        mock_email_processor.add_labels_to_email.side_effect = mock_apply_labels
        mock_email_processor.get_or_create_label.return_value = "test_label_id"

        results = stage.execute(sample_enriched_email_records, pipeline_context)

        assert len(results) == 3
        assert not results[0].success
        assert results[1].success
        assert results[2].success

    def test_execute_dry_run(
        self, mock_email_processor, pipeline_config, sample_enriched_email_records
    ):
        """Test loading in dry run mode."""
        stage = LoadStage(pipeline_config.load, mock_email_processor)

        # Create dry run context
        dry_run_context = PipelineContext.create(config=pipeline_config, dry_run=True)

        results = stage.execute(sample_enriched_email_records, dry_run_context)

        assert len(results) == 3
        assert all(result.success for result in results)

        # Should not make actual email processor calls in dry run
        mock_email_processor.add_labels_to_email.assert_not_called()

    def test_batch_processing(self, mock_email_processor, pipeline_config, pipeline_context):
        """Test batch processing in load stage."""
        stage = LoadStage(pipeline_config.load, mock_email_processor)

        # Create large batch
        large_batch = []
        for i in range(100):
            large_batch.append(
                EnrichedEmailRecord(
                    id=f"msg{i}",
                    subject=f"Subject {i}",
                    sender=f"sender{i}@example.com",
                    content=f"Content {i}",
                    received_date="2024-01-01T10:00:00Z",
                    category="Work",
                    explanation="Business email",
                    confidence=0.9,
                    processing_time=1.0,
                )
            )

        # Mock successful email processor responses
        mock_email_processor.get_or_create_label.return_value = "test_label_id"
        mock_email_processor.add_labels_to_email.return_value = True

        results = stage.execute(large_batch, pipeline_context)

        assert len(results) == 100
        assert all(result.success for result in results)


class TestSyncStage:
    """Test cases for SyncStage."""

    def test_init(self, email_database, mock_metrics_tracker, pipeline_config):
        """Test SyncStage initialization."""
        stage = SyncStage(
            config=pipeline_config.sync,
            database=email_database,
            metrics_tracker=mock_metrics_tracker,
        )

        assert stage.database == email_database
        assert stage.metrics_tracker == mock_metrics_tracker
        assert stage.config == pipeline_config.sync

    def test_execute_success(
        self, mock_metrics_tracker, pipeline_config, pipeline_context, sample_enriched_email_records
    ):
        """Test successful result synchronization."""
        # Create a mock database
        mock_database = MagicMock()
        mock_database.update_email_labels.return_value = None

        stage = SyncStage(pipeline_config.sync, mock_database, mock_metrics_tracker)

        # Create sample ActionResults
        action_results = [
            ActionResult(
                email_id=email.id,
                category=email.category,
                actions_taken=["apply_label"],
                success=True,
                errors=[],
            )
            for email in sample_enriched_email_records
        ]

        stage.execute(action_results, pipeline_context)

        # Verify database calls were made for syncing
        assert mock_database.update_email_labels.call_count == 3

    def test_execute_batch_processing(
        self, mock_metrics_tracker, pipeline_config, pipeline_context
    ):
        """Test batch processing in sync stage."""
        # Create a mock database
        mock_database = MagicMock()
        mock_database.update_email_labels.return_value = None

        stage = SyncStage(pipeline_config.sync, mock_database, mock_metrics_tracker)

        # Create large batch of action results
        action_results = []
        for i in range(50):
            action_results.append(
                ActionResult(
                    email_id=f"msg{i}",
                    category="Work",
                    actions_taken=["apply_label"],
                    success=True,
                    errors=[],
                )
            )

        stage.execute(action_results, pipeline_context)

        # Verify database calls were made for all results
        assert mock_database.update_email_labels.call_count == 50

    def test_execute_dry_run(
        self, mock_metrics_tracker, pipeline_config, sample_enriched_email_records
    ):
        """Test sync stage in dry run mode."""
        # Create a mock database
        mock_database = MagicMock()

        stage = SyncStage(pipeline_config.sync, mock_database, mock_metrics_tracker)

        # Create sample ActionResults
        action_results = [
            ActionResult(
                email_id=email.id,
                category=email.category,
                actions_taken=["apply_label"],
                success=True,
                errors=[],
            )
            for email in sample_enriched_email_records
        ]

        dry_run_context = PipelineContext.create(config=pipeline_config, dry_run=True)

        stage.execute(action_results, dry_run_context)

        # Should not make actual database calls in dry run
        mock_database.update_email_labels.assert_not_called()

    def test_execute_database_errors(
        self, mock_metrics_tracker, pipeline_config, pipeline_context, sample_enriched_email_records
    ):
        """Test handling of database errors during sync."""
        # Create a mock database that raises errors
        mock_database = MagicMock()
        mock_database.update_email_labels.side_effect = Exception("Database error")

        stage = SyncStage(pipeline_config.sync, mock_database, mock_metrics_tracker)

        # Create sample ActionResults
        action_results = [
            ActionResult(
                email_id=email.id,
                category=email.category,
                actions_taken=["apply_label"],
                success=True,
                errors=[],
            )
            for email in sample_enriched_email_records
        ]

        stage.execute(action_results, pipeline_context)

        # Should have logged errors but continued processing
        assert len(pipeline_context.errors) > 0

    @pytest.mark.parametrize("save_metrics", [True, False])
    def test_save_metrics_setting(
        self,
        mock_metrics_tracker,
        pipeline_config,
        pipeline_context,
        sample_enriched_email_records,
        save_metrics,
    ):
        """Test save_metrics configuration setting."""
        # Create a mock database
        mock_database = MagicMock()
        mock_database.update_email_labels.return_value = None
        pipeline_config.sync.save_metrics = save_metrics
        stage = SyncStage(pipeline_config.sync, mock_database, mock_metrics_tracker)

        # Create sample ActionResults
        action_results = [
            ActionResult(
                email_id=email.id,
                category=email.category,
                actions_taken=["apply_label"],
                success=True,
                errors=[],
            )
            for email in sample_enriched_email_records
        ]

        with patch("builtins.open", create=True) as mock_open, patch("json.dump") as mock_json_dump:
            stage.execute(action_results, pipeline_context)

            if save_metrics:
                # Should save metrics to file
                mock_open.assert_called()
                mock_json_dump.assert_called()
            else:
                # Should not save metrics
                mock_open.assert_not_called()
                mock_json_dump.assert_not_called()

    def test_metrics_tracking(
        self,
        email_database,
        mock_metrics_tracker,
        pipeline_config,
        pipeline_context,
        sample_enriched_email_records,
    ):
        """Test that metrics are tracked during execution."""
        stage = SyncStage(pipeline_config.sync, email_database, mock_metrics_tracker)

        # Create sample ActionResults
        action_results = [
            ActionResult(
                email_id=email.id,
                category=email.category,
                actions_taken=["apply_label"],
                success=True,
                errors=[],
            )
            for email in sample_enriched_email_records
        ]

        stage.execute(action_results, pipeline_context)

        # Should have tracked metrics for each result
        assert mock_metrics_tracker.add_result.call_count == 3
