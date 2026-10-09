"""One place for the LLM connection (Ollama by default, any OpenAI-compatible API).

Every other file calls ask(). Switching models or providers means
changing .env, not the code.
"""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def model_name() -> str:
    return os.getenv("LLM_MODEL", "qwen3:8b")


def ask(prompt: str, max_tokens: int = 4000) -> str:
    """Send one prompt, return the raw text of the answer."""
    client = OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
        api_key=os.getenv("LLM_API_KEY", "ollama"),
    )
    response = client.chat.completions.create(
        model=model_name(),
        messages=[{"role": "user", "content": prompt}],
        temperature=0,  # same input -> (almost) same output; easier to debug
        max_tokens=max_tokens,  # room for qwen3's hidden "thinking" + the answer
    )
    choice = response.choices[0]
    text = choice.message.content or ""
    if not text.strip():
        # "length" means the model ran out of tokens (often while thinking)
        print(f"  (LLM returned no text, finish_reason={choice.finish_reason})")
    return text
