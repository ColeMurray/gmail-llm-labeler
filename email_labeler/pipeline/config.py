"""Configuration classes for the ETL pipeline."""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import yaml


@dataclass
class ExtractConfig:
    """Configuration for the Extract stage."""

    source: str = "gmail"  # Options: "gmail", "database"
    gmail_query: str = "is:unread"
    batch_size: int = 100
    max_results: Optional[int] = None


@dataclass
class TransformConfig:
    """Configuration for the Transform stage."""

    llm_service: str = "openai"  # Options: "openai", "ollama"
    model: str = "gpt-4o-mini"
    max_content_length: int = 4000
    timeout: int = 30
    skip_on_error: bool = True
    categories: List[str] = field(
        default_factory=lambda: [
            "Marketing",
            "Response Needed / High Priority",
            "Bills",
            "Subscriptions",
            "Newsletters",
            "Personal",
            "Work",
            "Events",
            "Travel",
            "Receipts",
            "Low quality",
            "Notifications",
            "Other",
        ]
    )


@dataclass
class LoadConfig:
    """Configuration for the Load stage."""

    apply_labels: bool = True
    create_missing_labels: bool = True
    category_actions: Dict[str, List[str]] = field(
        default_factory=lambda: {
            "Marketing": ["apply_label", "archive"],
            "Response Needed / High Priority": ["apply_label", "star"],
            "Bills": ["apply_label", "star"],
            "Newsletters": ["apply_label", "archive"],
            "Low quality": ["apply_label", "archive", "mark_as_read"],
            "Notifications": ["apply_label", "mark_as_read"],
        }
    )
    default_actions: List[str] = field(default_factory=lambda: ["apply_label"])


@dataclass
class SyncConfig:
    """Configuration for the Sync stage."""

    database_path: str = "email_pipeline.db"
    save_metrics: bool = True
    track_history: bool = True
    batch_size: int = 100
    track_metrics: bool = True


@dataclass
class MonitoringConfig:
    """Configuration for monitoring and observability."""

    log_level: str = "INFO"
    metrics_export: str = "json"  # Options: "json", "csv", "prometheus"
    metrics_path: str = "pipeline_metrics.json"
    enable_tracing: bool = False


@dataclass
class PipelineConfig:
    """Main pipeline configuration."""

    extract: ExtractConfig = field(default_factory=ExtractConfig)
    transform: TransformConfig = field(default_factory=TransformConfig)
    load: LoadConfig = field(default_factory=LoadConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    dry_run: bool = False
    continue_on_error: bool = True
    max_retries: int = 3

    @classmethod
    def from_yaml(cls, path: str) -> "PipelineConfig":
        """Load configuration from YAML file."""
        with open(path) as f:
            data = yaml.safe_load(f)

        pipeline_data = data.get("pipeline", {})

        # Create configs from nested dictionaries
        extract_config = ExtractConfig(**pipeline_data.get("extract", {}))
        transform_config = TransformConfig(**pipeline_data.get("transform", {}))
        load_config = LoadConfig(**pipeline_data.get("load", {}))
        sync_config = SyncConfig(**pipeline_data.get("sync", {}))
        monitoring_config = MonitoringConfig(**pipeline_data.get("monitoring", {}))

        return cls(
            extract=extract_config,
            transform=transform_config,
            load=load_config,
            sync=sync_config,
            monitoring=monitoring_config,
            dry_run=pipeline_data.get("dry_run", False),
            continue_on_error=pipeline_data.get("continue_on_error", True),
            max_retries=pipeline_data.get("max_retries", 3),
        )

    @classmethod
    def from_env(cls) -> "PipelineConfig":
        """Create configuration from environment variables and defaults."""
        config = cls()

        # Override with environment variables if present
        if os.getenv("LLM_SERVICE"):
            config.transform.llm_service = os.getenv("LLM_SERVICE").lower()

        if os.getenv("OPENAI_MODEL"):
            config.transform.model = os.getenv("OPENAI_MODEL")
        elif os.getenv("OLLAMA_MODEL"):
            config.transform.model = os.getenv("OLLAMA_MODEL")

        if os.getenv("DATABASE_PATH"):
            config.sync.database_path = os.getenv("DATABASE_PATH")

        if os.getenv("LOG_LEVEL"):
            config.monitoring.log_level = os.getenv("LOG_LEVEL")

        return config

    def to_yaml(self, path: str):
        """Save configuration to YAML file."""
        data = {
            "pipeline": {
                "dry_run": self.dry_run,
                "continue_on_error": self.continue_on_error,
                "max_retries": self.max_retries,
                "extract": {
                    "source": self.extract.source,
                    "gmail_query": self.extract.gmail_query,
                    "batch_size": self.extract.batch_size,
                    "max_results": self.extract.max_results,
                },
                "transform": {
                    "llm_service": self.transform.llm_service,
                    "model": self.transform.model,
                    "max_content_length": self.transform.max_content_length,
                    "timeout": self.transform.timeout,
                    "skip_on_error": self.transform.skip_on_error,
                    "categories": self.transform.categories,
                },
                "load": {
                    "apply_labels": self.load.apply_labels,
                    "create_missing_labels": self.load.create_missing_labels,
                    "category_actions": self.load.category_actions,
                    "default_actions": self.load.default_actions,
                },
                "sync": {
                    "database_path": self.sync.database_path,
                    "save_metrics": self.sync.save_metrics,
                    "track_history": self.sync.track_history,
                    "batch_size": self.sync.batch_size,
                    "track_metrics": self.sync.track_metrics,
                },
                "monitoring": {
                    "log_level": self.monitoring.log_level,
                    "metrics_export": self.monitoring.metrics_export,
                    "metrics_path": self.monitoring.metrics_path,
                    "enable_tracing": self.monitoring.enable_tracing,
                },
            }
        }

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
