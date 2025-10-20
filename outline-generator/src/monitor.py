# src/monitor.py
# -*- coding: utf-8 -*-
"""Monitoring module for tracking API usage and performance."""

import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import json
from pathlib import Path
import threading

from src.logger import setup_logging

logger = setup_logging(__name__)


@dataclass
class APICall:
    """Record of a single API call."""
    timestamp: datetime
    model: str
    tokens: int
    duration: float
    success: bool

    def estimated_cost(self) -> float:
        """Estimate cost based on model and tokens."""
        # WARNING: Approximate pricing per 1K tokens (as of 2024/2025)
        # Check OpenAI pricing page for current rates: https://openai.com/pricing
        pricing = {
            "gpt-4.1": 0.01,  # Estimate - verify actual pricing
            "gpt-4.1-mini": 0.0005,  # Estimate - verify actual pricing
            "gpt-4-turbo-preview": 0.01,
            "gpt-4-0125-preview": 0.01,
            "gpt-4-1106-preview": 0.01,
            "gpt-4": 0.03,
            "gpt-4o-mini": 0.00015,
            "gpt-3.5-turbo": 0.001,
            "gpt-3.5-turbo-0125": 0.001,
        }

        rate = pricing.get(self.model, 0.01)

        # Log warning if model not in pricing table
        if self.model not in pricing:
            logger.warning(
                f"Model '{self.model}' not in pricing table. "
                f"Using default rate ${rate} per 1K tokens. "
                "Please verify actual costs."
            )

        return (self.tokens / 1000) * rate


@dataclass
class MonitorStats:
    """Aggregated monitoring statistics."""
    api_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    total_tokens: int = 0
    total_duration: float = 0
    estimated_cost: float = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_attempts: int = 0

    def success_rate(self) -> float:
        """Calculate API call success rate."""
        if self.api_calls == 0:
            return 0
        return (self.successful_calls / self.api_calls) * 100

    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate."""
        if self.cache_attempts == 0:
            return 0
        return (self.cache_hits / self.cache_attempts) * 100

    def avg_duration(self) -> float:
        """Calculate average API call duration."""
        if self.api_calls == 0:
            return 0
        return self.total_duration / self.api_calls


class Monitor:
    """Performance and usage monitor."""

    def __init__(self, save_to_file: bool = True):
        self.save_to_file = save_to_file
        self.calls: List[APICall] = []
        self.stats = MonitorStats()
        self.start_time = None
        self.lock = threading.Lock()

        if save_to_file:
            self.log_dir = Path("logs")
            self.log_dir.mkdir(parents=True, exist_ok=True)

    def start(self):
        """Start monitoring session."""
        self.start_time = datetime.now()
        logger.info("Monitoring started")

    def stop(self):
        """Stop monitoring and save results."""
        if self.save_to_file and self.calls:
            self._save_results()

        duration = (datetime.now() - self.start_time).total_seconds() if self.start_time else 0
        logger.info(f"Monitoring stopped. Session duration: {duration:.2f}s")

    def record_api_call(
        self,
        model: str,
        tokens: int,
        duration: float,
        success: bool
    ):
        """Record an API call."""
        with self.lock:
            call = APICall(
                timestamp=datetime.now(),
                model=model,
                tokens=tokens,
                duration=duration,
                success=success
            )

            self.calls.append(call)

            # Update stats
            self.stats.api_calls += 1
            if success:
                self.stats.successful_calls += 1
            else:
                self.stats.failed_calls += 1

            self.stats.total_tokens += tokens
            self.stats.total_duration += duration
            self.stats.estimated_cost += call.estimated_cost()

            logger.debug(
                f"API call recorded: model={model}, tokens={tokens}, "
                f"duration={duration:.2f}s, success={success}"
            )

    def record_cache_hit(self):
        """Record a cache hit."""
        with self.lock:
            self.stats.cache_hits += 1
            self.stats.cache_attempts += 1
            logger.debug("Cache hit recorded")

    def record_cache_miss(self):
        """Record a cache miss."""
        with self.lock:
            self.stats.cache_misses += 1
            self.stats.cache_attempts += 1
            logger.debug("Cache miss recorded")

    def get_stats(self) -> Dict:
        """Get current statistics."""
        with self.lock:
            return {
                'api_calls': self.stats.api_calls,
                'successful_calls': self.stats.successful_calls,
                'failed_calls': self.stats.failed_calls,
                'success_rate': self.stats.success_rate(),
                'total_tokens': self.stats.total_tokens,
                'total_duration': round(self.stats.total_duration, 2),
                'avg_duration': round(self.stats.avg_duration(), 2),
                'estimated_cost': round(self.stats.estimated_cost, 4),
                'cache_hits': self.stats.cache_hits,
                'cache_misses': self.stats.cache_misses,
                'cache_attempts': self.stats.cache_attempts,
                'cache_hit_rate': self.stats.cache_hit_rate(),
            }

    def _save_results(self):
        """Save monitoring results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_file = self.log_dir / f"monitor_report_{timestamp}.json"

        report = {
            'session': {
                'start_time': self.start_time.isoformat() if self.start_time else None,
                'end_time': datetime.now().isoformat(),
                'duration_seconds': (datetime.now() - self.start_time).total_seconds()
                                   if self.start_time else 0
            },
            'stats': self.get_stats(),
            'calls': [
                {
                    'timestamp': call.timestamp.isoformat(),
                    'model': call.model,
                    'tokens': call.tokens,
                    'duration': call.duration,
                    'success': call.success,
                    'estimated_cost': call.estimated_cost()
                }
                for call in self.calls
            ]
        }

        try:
            with report_file.open('w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"Monitoring report saved to {report_file}")
        except Exception as e:
            logger.error(f"Failed to save monitoring report: {e}")

    def print_summary(self):
        """Print summary to console."""
        stats = self.get_stats()

        print("\n" + "="*50)
        print("MONITORING SUMMARY")
        print("="*50)
        print(f"API Calls: {stats['api_calls']} "
              f"(Success: {stats['successful_calls']}, Failed: {stats['failed_calls']})")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print(f"Total Tokens: {stats['total_tokens']:,}")
        print(f"Avg Duration: {stats['avg_duration']:.2f}s")
        print(f"Estimated Cost: ${stats['estimated_cost']:.4f}")
        print(f"Cache: {stats['cache_hits']} hits, {stats['cache_misses']} misses "
              f"({stats['cache_hit_rate']:.1f}% hit rate)")
        print("="*50 + "\n")
