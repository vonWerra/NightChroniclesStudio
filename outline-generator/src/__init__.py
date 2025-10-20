# src/__init__.py
"""YouTube Series Outline Generator Package."""

__version__ = "2.0.0"
__author__ = "Your Name"

from .config import Config, load_config
from .models import OutlineJSON, Episode, MSPItem, EpisodeRuntime
from .generator import OutlineGenerator
from .api_client import APIClient
from .cache import CacheManager
from .monitor import Monitor
from .logger import setup_logging

__all__ = [
    "Config",
    "load_config",
    "OutlineJSON",
    "Episode",
    "MSPItem",
    "EpisodeRuntime",
    "OutlineGenerator",
    "APIClient",
    "CacheManager",
    "Monitor",
    "setup_logging"
]
