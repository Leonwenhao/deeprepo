"""
LLM Clients for deeprepo.

Root model: Claude Opus 4.6 via Anthropic API
Sub-LLM workers: MiniMax M2.5 via OpenRouter (OpenAI-compatible)
"""

import os
import time
import asyncio
import sys
from dataclasses import dataclass, field

import anthropic
import openai
from dotenv import load_dotenv

from deeprepo.utils import async_retry_with_backoff, retry_with_backoff


# Root model pricing profiles (per million tokens)
ROOT_MODEL_PRICING = {
    "claude-opus-4-6": {"input": 15.0, "output": 75.0, "label": "Opus 4.6"},
    "claude-sonnet-4-5-20250929": {"input": 3.0, "output": 15.0, "label": "Sonnet 4.5"},
    "minimax/minimax-m2.5": {"input": 0.20, "output": 1.10, "label": "MiniMax M2.5"},
}

SUB_MODEL_PRICING = {
    "minimax/minimax-m2.5": {"input": 0.20, "output": 1.10},
    "deepseek/deepseek-chat-v3-0324": {"input": 0.14, "output": 0.28},
    "qwen/qwen-2.5-coder-32b-instruct": {"input": 0.20, "output": 0.20},
    "meta-llama/llama-3.3-70b-instruct": {"input": 0.39, "output": 0.39},
    "google/gemini-2.0-flash-001": {"input": 0.10, "output": 0.40},
}

DEFAULT_SUB_MODEL = "minimax/minimax-m2.5"


@dataclass
class TokenUsage:
    """Track token usage and costs across all API calls."""
    root_input_tokens: int = 0
    root_output_tokens: int = 0
    sub_input_tokens: int = 0
    sub_output_tokens: int = 0
    root_calls: int = 0
    sub_calls: int = 0
    root_latency_ms: list[float] = field(default_factory=list)
    sub_latency_ms: list[float] = field(default_factory=list)

    # Root pricing — set per model via set_root_pricing()
    root_input_price: float = 15.0
    root_output_price: float = 75.0
    root_model_label: str = "Opus 4.6"

    # Sub-LLM pricing — set per model via set_sub_pricing()
    sub_input_price: float = 0.20
    sub_output_price: float = 1.10
    sub_model_label: str = "MiniMax M2.5"

    def set_root_pricing(self, model: str) -> None:
        """Configure root pricing from a model string."""
        pricing = ROOT_MODEL_PRICING.get(model, ROOT_MODEL_PRICING["claude-opus-4-6"])
        self.root_input_price = pricing["input"]
        self.root_output_price = pricing["output"]
        self.root_model_label = pricing["label"]

    def set_sub_pricing(self, model: str) -> None:
        """Configure sub-LLM pricing from a model string."""
        pricing = SUB_MODEL_PRICING.get(model)
        self.sub_model_label = model.split("/")[-1] if "/" in model else model
        if pricing:
            self.sub_input_price = pricing["input"]
            self.sub_output_price = pricing["output"]
        else:
            self.sub_input_price = 1.00
            self.sub_output_price = 1.00
            print(
                f"Warning: Unknown sub-model '{model}' — using fallback pricing $1.00/$1.00 per M tokens",
                file=sys.stderr,
            )

    @property
    def root_cost(self) -> float:
        return (
            (self.root_input_tokens / 1_000_000) * self.root_input_price
            + (self.root_output_tokens / 1_000_000) * self.root_output_price
        )

    @property
    def sub_cost(self) -> float:
        return (
            (self.sub_input_tokens / 1_000_000) * self.sub_input_price
            + (self.sub_output_tokens / 1_000_000) * self.sub_output_price
        )

    @property
    def total_cost(self) -> float:
        return self.root_cost + self.sub_cost

    def summary(self) -> str:
        return (
            f"=== Token Usage & Cost ===\n"
            f"Root ({self.root_model_label}): {self.root_calls} calls, "
            f"{self.root_input_tokens:,} in / {self.root_output_tokens:,} out, "
            f"${self.root_cost:.4f}\n"
            f"Sub ({self.sub_model_label}): {self.sub_calls} calls, "
            f"{self.sub_input_tokens:,} in / {self.sub_output_tokens:,} out, "
            f"${self.sub_cost:.4f}\n"
            f"Total cost: ${self.total_cost:.4f}"
        )


class RootModelClient:
    """Claude Opus 4.6 / Sonnet 4.5 via Anthropic API — the strategic orchestrator."""

    def __init__(self, usage: TokenUsage, model: str = "claude-opus-4-6"):
        load_dotenv()
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file or export it as an environment variable."
            )
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.usage = usage

    def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 8192,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> str:
        """Send a message to the root model and return the text response.

        When tools is provided, returns the full Anthropic response object
        instead of a string, so the caller can inspect tool_use blocks.
        When stream=True, tokens are displayed on stderr in real-time.
        """
        t0 = time.time()

        kwargs = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": messages,
            "temperature": temperature,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        if stream:
            @retry_with_backoff()
            def _stream_call():
                with self.client.messages.stream(**kwargs) as stream_resp:
                    for text in stream_resp.text_stream:
                        sys.stderr.write(text)
                        sys.stderr.flush()
                    sys.stderr.write("\n")
                    return stream_resp.get_final_message()

            try:
                response = _stream_call()
            except Exception as e:
                raise RuntimeError(
                    f"Anthropic API error on {self.model} after retries: {e}"
                ) from e
        else:
            @retry_with_backoff()
            def _call():
                return self.client.messages.create(**kwargs)

            try:
                response = _call()
            except Exception as e:
                raise RuntimeError(
                    f"Anthropic API error on {self.model} after retries: {e}"
                ) from e

        latency_ms = (time.time() - t0) * 1000
        self.usage.root_calls += 1
        self.usage.root_input_tokens += response.usage.input_tokens
        self.usage.root_output_tokens += response.usage.output_tokens
        self.usage.root_latency_ms.append(latency_ms)

        if tools:
            return response

        # Text-only path (backward compatible)
        text_parts = [
            block.text for block in response.content if block.type == "text"
        ]
        return "\n".join(text_parts)


class OpenRouterRootClient:
    """MiniMax M2.5 (or other models) via OpenRouter — OpenAI-compatible API."""

    def __init__(self, usage: TokenUsage, model: str = "minimax/minimax-m2.5"):
        load_dotenv()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY not set. Add it to your .env file or export it as an environment variable."
            )
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model
        self.usage = usage

    def complete(
        self,
        messages: list[dict],
        system: str = "",
        max_tokens: int = 8192,
        temperature: float = 0.0,
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> str:
        """Send a message to the root model and return the text response."""
        t0 = time.time()

        # OpenAI SDK: system prompt goes as first message, not a separate param
        api_messages = []
        if system:
            api_messages.append({"role": "system", "content": system})
        api_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if tools:
            # Convert Anthropic tool schema -> OpenAI function-calling format
            openai_tools = []
            for tool in tools:
                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["input_schema"],
                    },
                })
            kwargs["tools"] = openai_tools

        @retry_with_backoff()
        def _call():
            return self.client.chat.completions.create(**kwargs)

        try:
            response = _call()
        except Exception as e:
            raise RuntimeError(f"OpenRouter API error on {self.model} after retries: {e}") from e

        latency_ms = (time.time() - t0) * 1000
        self.usage.root_calls += 1
        if response.usage:
            self.usage.root_input_tokens += response.usage.prompt_tokens or 0
            self.usage.root_output_tokens += response.usage.completion_tokens or 0
        self.usage.root_latency_ms.append(latency_ms)

        if tools:
            return response

        return response.choices[0].message.content or ""


# Models that use OpenRouter instead of Anthropic API
OPENROUTER_ROOT_MODELS = {"minimax/minimax-m2.5"}


def create_root_client(usage: TokenUsage, model: str = "claude-opus-4-6"):
    """Factory: pick the right root client based on model string."""
    if model in OPENROUTER_ROOT_MODELS:
        return OpenRouterRootClient(usage=usage, model=model)
    return RootModelClient(usage=usage, model=model)


class SubModelClient:
    """MiniMax M2.5 via OpenRouter — the cheap, fast worker."""

    def __init__(
        self,
        usage: TokenUsage,
        model: str = DEFAULT_SUB_MODEL,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        load_dotenv()
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENROUTER_API_KEY not set. Add it to your .env file or export it as an environment variable."
            )
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.usage = usage
        self.usage.set_sub_pricing(model)
        self._lock = asyncio.Lock()

    def query(self, prompt: str, system: str = "", max_tokens: int = 4096) -> str:
        """Synchronous single query to the sub-LLM."""
        t0 = time.time()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        @retry_with_backoff()
        def _call():
            return self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
            )

        try:
            response = _call()
        except Exception as e:
            raise RuntimeError(f"Sub-LLM API error on {self.model} after retries: {e}") from e

        latency_ms = (time.time() - t0) * 1000
        self.usage.sub_calls += 1
        if response.usage:
            self.usage.sub_input_tokens += response.usage.prompt_tokens or 0
            self.usage.sub_output_tokens += response.usage.completion_tokens or 0
        self.usage.sub_latency_ms.append(latency_ms)

        return response.choices[0].message.content or ""

    async def _async_query(
        self,
        prompt: str,
        system: str = "",
        max_tokens: int = 4096,
        lock: asyncio.Lock | None = None,
    ) -> str:
        """Async single query for use in batch."""
        t0 = time.time()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        try:
            response = await async_retry_with_backoff(
                self.async_client.chat.completions.create,
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.0,
            )
        except Exception as e:
            raise RuntimeError(f"Sub-LLM API error on {self.model} after retries: {e}") from e

        latency_ms = (time.time() - t0) * 1000
        usage_lock = lock or self._lock
        async with usage_lock:
            self.usage.sub_calls += 1
            if response.usage:
                self.usage.sub_input_tokens += response.usage.prompt_tokens or 0
                self.usage.sub_output_tokens += response.usage.completion_tokens or 0
            self.usage.sub_latency_ms.append(latency_ms)

        return response.choices[0].message.content or ""

    def batch(
        self,
        prompts: list[str],
        system: str = "",
        max_tokens: int = 4096,
        max_concurrent: int = 5,
    ) -> list[str]:
        """
        Parallel batch query — the key RLM advantage.
        Sends multiple prompts concurrently to the sub-LLM.
        """
        async def _run_batch():
            lock = asyncio.Lock()
            semaphore = asyncio.Semaphore(max_concurrent)

            async def _limited_query(prompt: str) -> str:
                async with semaphore:
                    return await self._async_query(
                        prompt,
                        system=system,
                        max_tokens=max_tokens,
                        lock=lock,
                    )

            tasks = [_limited_query(p) for p in prompts]
            return await asyncio.gather(*tasks, return_exceptions=True)

        # Detect if we're already in an async context (Jupyter/FastAPI/etc.).
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            results = asyncio.run(_run_batch())
        else:
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _run_batch())
                results = future.result()

        # Convert exceptions to error strings
        processed = []
        for r in results:
            if isinstance(r, Exception):
                processed.append(f"[ERROR: {type(r).__name__}: {r}]")
            else:
                processed.append(r)
        return processed
