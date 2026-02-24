"""Manual API connectivity script.

This file intentionally contains no pytest tests and does not execute on import.
Run it directly to validate Anthropic + OpenRouter credentials/network.
"""

import os
import time

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    print("=" * 60)
    print("TEST 1: Anthropic API — Claude Opus 4.6")
    print("=" * 60)

    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    t0 = time.time()
    response = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=100,
        temperature=0.0,
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
    )
    elapsed = time.time() - t0

    print(f"Response: {response.content[0].text}")
    print(f"Input tokens:  {response.usage.input_tokens}")
    print(f"Output tokens: {response.usage.output_tokens}")
    print(f"Latency:       {elapsed:.2f}s")
    print(f"Stop reason:   {response.stop_reason}")
    print()

    print("=" * 60)
    print("TEST 2: OpenRouter API — MiniMax M2.5")
    print("=" * 60)

    import openai

    or_client = openai.OpenAI(
        api_key=os.environ["OPENROUTER_API_KEY"],
        base_url="https://openrouter.ai/api/v1",
    )

    t0 = time.time()
    or_response = or_client.chat.completions.create(
        model="minimax/minimax-m2.5",
        messages=[{"role": "user", "content": "Say hello in one sentence."}],
        max_tokens=100,
        temperature=0.0,
    )
    elapsed = time.time() - t0

    print(f"Response: {or_response.choices[0].message.content}")
    if or_response.usage:
        print(f"Input tokens:  {or_response.usage.prompt_tokens}")
        print(f"Output tokens: {or_response.usage.completion_tokens}")
    else:
        print("(No usage data returned by OpenRouter)")
    print(f"Latency:       {elapsed:.2f}s")
    print(f"Finish reason: {or_response.choices[0].finish_reason}")
    print()

    print("=" * 60)
    print("Both APIs connected successfully!")
    print("=" * 60)


if __name__ == "__main__":
    main()
