# src/logger.py
# -*- coding: utf-8 -*-
"""Structured logging configuration."""

import logging
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict

try:
    import structlog
except ImportError:
    print("ERROR: structlog not installed. Run: pip install structlog")
    sys.exit(1)


def setup_logging(name: str = None, use_colors: bool = True) -> structlog.BoundLogger:
    """Setup structured logging with structlog."""

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO
    )

    # Use built-in dev console renderer (simpler, more robust)
    console_renderer = structlog.dev.ConsoleRenderer(colors=use_colors) if use_colors else structlog.dev.ConsoleRenderer()

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            console_renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger(name)


class ConsoleRenderer:
    """Custom console renderer for better readability."""

    COLORS = {
        'debug': '\033[36m',    # Cyan
        'info': '\033[32m',     # Green
        'warning': '\033[33m',  # Yellow
        'error': '\033[31m',    # Red
        'critical': '\033[35m', # Magenta
        'reset': '\033[0m'
    }

    def __call__(self, logger, method_name, event_dict):
        """Format log message for console output."""
        timestamp = event_dict.pop('timestamp', datetime.now().isoformat())
        level = event_dict.pop('level', 'info').lower()
        logger_name = event_dict.pop('logger', '')
        event = event_dict.pop('event', '')

        # Color based on level if terminal supports it
        color = self.COLORS.get(level, '')
        reset = self.COLORS['reset'] if color else ''

        # Build message
        parts = [
            f"[{timestamp}]",
            f"{color}[{level.upper()}]{reset}",
        ]

        if logger_name:
            parts.append(f"[{logger_name}]")

        parts.append(event)

        # Add extra fields
        if event_dict:
            extra = json.dumps(event_dict, ensure_ascii=False, default=str)
            parts.append(f"| {extra}")

        return " ".join(parts)


class FileLogger:
    """File logger for persistent logging."""

    def __init__(self, log_dir: Path = Path("logs")):
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Create log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"outline_generator_{timestamp}.log"

        # Setup file handler
        self.file_handler = logging.FileHandler(
            self.log_file,
            encoding='utf-8'
        )
        self.file_handler.setFormatter(
            logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
        )

        # Add to root logger
        logging.getLogger().addHandler(self.file_handler)

    def close(self):
        """Close file handler."""
        if self.file_handler:
            self.file_handler.close()
            logging.getLogger().removeHandler(self.file_handler)
