"""
Shared DeepSeek API client. Uses OpenAI-compatible endpoint.
"""

import yaml
import time
from openai import OpenAI

_client = None
_config = None


def get_config() -> dict:
    global _config
    if _config is None:
        with open("config.yaml", "r", encoding="utf-8") as f:
            _config = yaml.safe_load(f)
    return _config


def get_client() -> OpenAI:
    global _client
    if _client is None:
        config = get_config()
        _client = OpenAI(
            api_key=config["deepseek"]["api_key"],
            base_url=config["deepseek"]["base_url"],
            timeout=60.0,
        )
    return _client


def chat(messages: list, temperature: float = 0.7, max_tokens: int = 2000, retries: int = 3) -> str:
    """Send a chat completion request to DeepSeek with retry logic."""
    config = get_config()
    client = get_client()

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model=config["deepseek"]["model"],
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  [API error: {e}. Retrying in {wait}s...]")
                time.sleep(wait)
            else:
                raise RuntimeError(f"DeepSeek API failed after {retries} attempts: {e}")