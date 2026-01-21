from __future__ import annotations

import os
import time
from typing import Dict, Any, Optional

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

try:
    from openai import OpenAI
except Exception:  # pragma: no cover
    OpenAI = None  # type: ignore


class ProviderError(Exception):
    pass


def _get_model() -> str:
    # default to gpt-5.2, fallback handled by caller upon error
    # Common valid models: gpt-5.2, gpt-4o, gpt-4-turbo, gpt-4
    return os.environ.get("GPT_MODEL", "gpt-5.2")


def _get_temperature() -> float:
    try:
        return float(os.environ.get("GPT_TEMPERATURE", "0.4"))
    except Exception:
        return 0.4


def create_client() -> Any:
    if OpenAI is None:
        raise ProviderError("openai package not available")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ProviderError("OPENAI_API_KEY missing in environment")
    return OpenAI(api_key=api_key)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=20), reraise=True,
       retry=retry_if_exception_type(ProviderError))
def call_llm(messages: list[dict[str, str]], model: Optional[str] = None) -> Dict[str, Any]:
    """Call OpenAI Chat Completions with given messages. Returns dict with text, tokens, timings.

    Robust to models that do not support temperature (e.g. some GPT-5 variants):
    - For models starting with "gpt-5", omit temperature parameter.
    - If API returns unsupported_value for temperature, retry without temperature.
    """
    client = create_client()
    mdl = model or _get_model()
    start = time.time()

    def _create(allow_temp: bool = True):
        kwargs = {
            'model': mdl,
            'messages': messages,
        }
        if allow_temp:
            kwargs['temperature'] = _get_temperature()
        return client.chat.completions.create(**kwargs)

    try:
        # Heuristic: some models don't support temperature parameter
        # Try with temperature first, fallback to without if it fails
        try:
            resp = _create(allow_temp=True)
        except Exception as e:
            # Retry without temperature if it's an unsupported_value error
            msg = str(e).lower()
            if 'unsupported' in msg or 'temperature' in msg or 'parameter' in msg:
                resp = _create(allow_temp=False)
            else:
                raise
    except Exception as e:
        raise ProviderError(str(e))

    elapsed = time.time() - start
    try:
        text = resp.choices[0].message.content  # type: ignore
        usage = getattr(resp, 'usage', None)
        prompt_tokens = getattr(usage, 'prompt_tokens', None) if usage else None
        completion_tokens = getattr(usage, 'completion_tokens', None) if usage else None
    except Exception:
        text = ""
        prompt_tokens = None
        completion_tokens = None
    return {
        'text': text,
        'latency_sec': elapsed,
        'prompt_tokens': prompt_tokens,
        'completion_tokens': completion_tokens,
        'model': mdl,
    }
