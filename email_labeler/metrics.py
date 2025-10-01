"""Metrics and test results tracking."""

import csv
import json
import logging
from collections import Counter
from datetime import datetime
from typing import Dict, Optional

from .config import TEST_OUTPUT_FILE, TEST_SUMMARY_FILE


class MetricsTracker:
    """Tracks metrics and test results for email processing."""

    def __init__(self):
        """Initialize metrics tracker."""
        self.test_results = []
        self.results = []  # For pipeline results

    def add_test_result(
        self,
        email_id: str,
        subject: str,
        sender: str,
        predicted_category: str,
        explanation: str,
        llm_service: str,
        model: str,
        processing_time: float,
    ):
        """Add a test result entry."""
        self.test_results.append(
            {
                "email_id": email_id,
                "subject": subject[:100],  # Truncate long subjects
                "from": sender,
                "predicted_category": predicted_category,
                "explanation": explanation[:200],  # Truncate long explanations
                "llm_service": llm_service,
                "model": model,
                "processing_time": round(processing_time, 3),
                "timestamp": datetime.now().isoformat(),
            }
        )

    def add_result(
        self,
        email_id: str,
        category: str,
        success: bool = True,
        processing_time: Optional[float] = None,
    ):
        """Add a pipeline result entry."""
        self.results.append(
            {
                "email_id": email_id,
                "category": category,
                "success": success,
                "processing_time": processing_time,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def calculate_metrics(self) -> Dict:
        """Calculate performance metrics from test results."""
        if not self.test_results:
            return {}

        # Count predictions by category
        category_counts = Counter(r["predicted_category"] for r in self.test_results)

        # Calculate processing time stats
        processing_times = [
            r.get("processing_time", 0) for r in self.test_results if r.get("processing_time")
        ]
        avg_time = sum(processing_times) / len(processing_times) if processing_times else 0

        return {
            "total_emails": len(self.test_results),
            "categories": dict(category_counts),
            "average_processing_time": round(avg_time, 3),
            "test_date": datetime.now().isoformat(),
            "model_used": self.test_results[0]["model"] if self.test_results else None,
            "llm_service": self.test_results[0]["llm_service"] if self.test_results else None,
        }

    def save_test_results(
        self, output_file: str = TEST_OUTPUT_FILE, summary_file: str = TEST_SUMMARY_FILE
    ):
        """Save test results to CSV and summary to JSON."""
        if not self.test_results:
            logging.warning("No test results to save")
            return

        # Save detailed results to CSV
        with open(output_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=self.test_results[0].keys())
            writer.writeheader()
            writer.writerows(self.test_results)
        logging.info(f"Test results saved to {output_file}")

        # Calculate and save metrics
        metrics = self.calculate_metrics()
        with open(summary_file, "w") as f:
            json.dump(metrics, f, indent=2)
        logging.info(f"Test summary saved to {summary_file}")

        # Return metrics for display
        return metrics

    def print_summary(self):
        """Print test summary to console."""
        metrics = self.calculate_metrics()
        if not metrics:
            return

        print("\n" + "=" * 50)
        print("TEST MODE SUMMARY")
        print("=" * 50)
        print(f"Total emails processed: {metrics['total_emails']}")
        print(f"Average processing time: {metrics['average_processing_time']}s")
        print("\nCategory distribution:")
        for category, count in sorted(metrics["categories"].items()):
            print(f"  {category}: {count}")
        print("=" * 50 + "\n")
