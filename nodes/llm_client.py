"""
Shared LLM client factory.
Set LLM_PROVIDER=openrouter in .env to route all calls through OpenRouter.
Default: groq.
"""
import os
import concurrent.futures
from dotenv import load_dotenv

load_dotenv()

_LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "groq").lower()

# Hard wall-clock timeout per LLM call (seconds).
# Kills thinking-bleed runs where qwen3-32b ignores enable_thinking=False.
# The OpenAI client timeout=90s only kills idle TCP connections, not slow streams.
_CALL_TIMEOUT_S = int(os.environ.get("LLM_CALL_TIMEOUT", "120"))
_CALL_MAX_RETRIES = int(os.environ.get("LLM_CALL_MAX_RETRIES", "3"))

# OpenRouter model name map (Groq name → OpenRouter name)
_OPENROUTER_MODEL_MAP = {
    "qwen/qwen3-32b":          "qwen/qwen3-32b",
    "qwen-2.5-coder-32b":      "qwen/qwen2.5-coder-32b-instruct",
    "llama-3.1-8b-instant":    "meta-llama/llama-3.1-8b-instruct",
    "llama-3.3-70b-versatile": "meta-llama/llama-3.3-70b-instruct",
}

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

def resolve_model(groq_model_name: str) -> str:
    """Return the correct model name for the active provider."""
    if _LLM_PROVIDER == "openrouter":
        return _OPENROUTER_MODEL_MAP.get(groq_model_name, groq_model_name)
    return groq_model_name


def extra_kwargs() -> dict:
    """Extra kwargs for chat.completions.create().
    Disables qwen3 chain-of-thought thinking on OpenRouter — cuts latency ~10x."""
    if _LLM_PROVIDER == "openrouter":
        return {"extra_body": {"enable_thinking": False}}
    return {}


def get_client():
    """Return an OpenAI-compatible client for the active provider."""
    if _LLM_PROVIDER == "openrouter":
        from openai import OpenAI
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENROUTER_API_KEY not set.")
        return OpenAI(
            base_url=_OPENROUTER_BASE_URL,
            api_key=api_key,
            timeout=90.0,
        )
    else:
        from groq import Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise EnvironmentError("GROQ_API_KEY not set.")
        return Groq(api_key=api_key)


def timed_completion(client, **kwargs) -> str:
    """
    Call client.chat.completions.create(**kwargs) with a hard wall-clock timeout.

    Returns the response content string.
    Retries up to _CALL_MAX_RETRIES times on timeout or empty response.
    Raises TimeoutError if all retries exhausted.

    This is the primary fix for qwen3-32b thinking-bleed: the OpenAI client
    timeout=90s only kills idle TCP connections. If the model streams slowly
    (thinking out loud), the connection stays alive indefinitely. This wrapper
    enforces a true wall-clock deadline using concurrent.futures.
    """
    last_exc = None
    for attempt in range(1, _CALL_MAX_RETRIES + 1):
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(client.chat.completions.create, **kwargs)
        try:
            response = future.result(timeout=_CALL_TIMEOUT_S)
            content = response.choices[0].message.content or ""
            if content.strip():
                return content
            # Empty response — content filter or model refusal — retry once
            if attempt < _CALL_MAX_RETRIES:
                continue
            return ""
        except concurrent.futures.TimeoutError:
            future.cancel()
            last_exc = TimeoutError(
                f"LLM call exceeded {_CALL_TIMEOUT_S}s wall-clock timeout "
                f"(attempt {attempt}/{_CALL_MAX_RETRIES})"
            )
            if attempt == _CALL_MAX_RETRIES:
                raise last_exc
            # Short pause before retry to let the provider recover
            import time; time.sleep(5)
        except Exception as exc:
            raise exc

    raise last_exc
