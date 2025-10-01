"""Email Auto-Labeler ETL Pipeline."""

from .base import (
    ActionResult,
    EmailRecord,
    EnrichedEmailRecord,
    PipelineContext,
    PipelineRun,
    PipelineStage,
)
from .config import (
    ExtractConfig,
    LoadConfig,
    MonitoringConfig,
    PipelineConfig,
    SyncConfig,
    TransformConfig,
)
from .extract_stage import ExtractStage
from .load_stage import LoadStage
from .orchestrator import EmailPipeline
from .sync_stage import SyncStage
from .transform_stage import TransformStage

__all__ = [
    # Base classes
    "EmailRecord",
    "EnrichedEmailRecord",
    "ActionResult",
    "PipelineContext",
    "PipelineRun",
    "PipelineStage",
    # Configuration
    "ExtractConfig",
    "TransformConfig",
    "LoadConfig",
    "SyncConfig",
    "MonitoringConfig",
    "PipelineConfig",
    # Stages
    "ExtractStage",
    "TransformStage",
    "LoadStage",
    "SyncStage",
    # Orchestrator
    "EmailPipeline",
]
