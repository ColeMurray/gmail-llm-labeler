"""Base classes and data models for the ETL pipeline."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class EmailRecord:
    """Raw email data from extraction."""

    id: str
    subject: str
    sender: str
    content: str
    received_date: str


@dataclass
class EnrichedEmailRecord(EmailRecord):
    """Email with categorization metadata."""

    category: str
    explanation: str
    confidence: float
    processing_time: float


@dataclass
class ActionResult:
    """Result of actions applied to an email."""

    email_id: str
    category: str
    actions_taken: List[str]
    success: bool
    errors: List[str] = field(default_factory=list)


@dataclass
class PipelineContext:
    """Context passed through pipeline stages."""

    run_id: str
    start_time: datetime
    config: Any  # Will be PipelineConfig
    metrics: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    dry_run: bool = False
    preview_mode: bool = False
    test_mode: bool = False

    @classmethod
    def create(
        cls, config: Any, dry_run: bool = False, preview_mode: bool = False, test_mode: bool = False
    ) -> "PipelineContext":
        """Create a new pipeline context."""
        return cls(
            run_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            config=config,
            dry_run=dry_run,
            preview_mode=preview_mode,
            test_mode=test_mode,
        )

    def add_metric(self, key: str, value: Any):
        """Add a metric to the context."""
        if key in self.metrics:
            if isinstance(self.metrics[key], list):
                self.metrics[key].append(value)
            elif isinstance(self.metrics[key], (int, float)):
                self.metrics[key] += value
            else:
                self.metrics[key] = [self.metrics[key], value]
        else:
            self.metrics[key] = value

    def add_error(self, error: str):
        """Add an error to the context."""
        self.errors.append(error)

    def increment_metric(self, key: str, value: int = 1):
        """Increment a numeric metric."""
        self.metrics[key] = self.metrics.get(key, 0) + value


@dataclass
class PipelineRun:
    """Result of a complete pipeline execution."""

    run_id: str
    start_time: datetime
    end_time: datetime
    stages_completed: List[str]
    emails_processed: int
    successful: int
    failed: int
    errors: List[str]
    metrics: Dict[str, Any]


class PipelineStage(ABC):
    """Base interface for all pipeline stages."""

    def __init__(self):
        self.metrics = {}
        self.name = self.__class__.__name__

    @abstractmethod
    def execute(self, input_data: Any, context: PipelineContext) -> Any:
        """Execute the stage logic."""
        pass

    @abstractmethod
    def validate_input(self, input_data: Any) -> bool:
        """Validate stage input."""
        pass

    def get_metrics(self) -> Dict[str, Any]:
        """Return stage-specific metrics."""
        return self.metrics

    def reset_metrics(self):
        """Reset stage metrics."""
        self.metrics = {}
