# src/api_client.py
# -*- coding: utf-8 -*-
"""API client with exponential backoff retry logic."""

import asyncio
from typing import Optional, Dict, Any
import json
from datetime import datetime

try:
    from openai import AsyncOpenAI
    import httpx
except ImportError:
    print("ERROR: openai or httpx not installed. Run: pip install openai httpx")
    import sys
    sys.exit(1)

try:
    import backoff
except ImportError:
    print("ERROR: backoff not installed. Run: pip install backoff")
    import sys
    sys.exit(1)

from src.logger import setup_logging

logger = setup_logging(__name__)


class APIClient:
    """OpenAI API client with retry logic and monitoring."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4.1-mini",
        temperature: float = 0.3,
        max_tokens: int = 6000,
        monitor: Optional[Any] = None,
        timeout: float = 60.0
    ):
        if not api_key:
            raise ValueError("API key is required")

        # Configure HTTP client with timeout and connection pooling
        http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )

        self.client = AsyncOpenAI(
            api_key=api_key,
            http_client=http_client
        )
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.monitor = monitor

        # Known valid models (as of 2024/2025)
        valid_models = [
            "gpt-4.1-mini",
            "gpt-4.1",
            "gpt-4-turbo-preview",
            "gpt-4-0125-preview",
            "gpt-4-1106-preview",
            "gpt-4",
            "gpt-4o-mini",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-0125",
            "gpt-3.5-turbo-1106"
        ]

        if self.model not in valid_models:
            logger.warning(
                f"Model '{self.model}' not in known list. "
                f"API will validate. Known models: {', '.join(valid_models)}"
            )

    @backoff.on_exception(
        backoff.expo,
        Exception,
        max_tries=4,
        max_value=32,
        on_backoff=lambda details: logger.warning(
            f"Retrying API call (attempt {details['tries']}/4)"
        )
    )
    async def generate(self, prompt: str) -> str:
        """Generate completion with exponential backoff retry."""
        start_time = datetime.now()

        try:
            # Use the new OpenAI client
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates structured JSON for YouTube series outlines."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "text"}  # We want text, not JSON mode
            )

            # Extract response
            content = response.choices[0].message.content.strip()

            # Get usage stats
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Record metrics if monitor available
            if self.monitor:
                elapsed = (datetime.now() - start_time).total_seconds()
                self.monitor.record_api_call(
                    model=self.model,
                    tokens=tokens_used,
                    duration=elapsed,
                    success=True
                )

            logger.debug(f"API call successful, used {tokens_used} tokens")
            return content

        except Exception as e:
            error_msg = str(e)

            # Check for specific errors
            if "model" in error_msg.lower():
                logger.error(f"Model error: {error_msg}. Check if model '{self.model}' exists.")
            elif "api" in error_msg.lower() or "key" in error_msg.lower():
                logger.error(f"API key error: {error_msg}. Check your OPENAI_API_KEY.")
            elif "rate" in error_msg.lower():
                logger.error(f"Rate limit error: {error_msg}. Waiting before retry...")
            else:
                logger.error(f"API error: {error_msg}")

            if self.monitor:
                self.monitor.record_api_call(
                    model=self.model,
                    tokens=0,
                    duration=(datetime.now() - start_time).total_seconds(),
                    success=False
                )
            raise

    async def cleanup(self):
        """Cleanup client."""
        # The new AsyncOpenAI client handles cleanup automatically
        pass
