"""
Shared Anthropic LLM helpers used by both backends.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from anthropic import Anthropic


def load_prompt_from_file(base_dir: Path, filename: str, marker: str) -> str:
    """Load a triple-quoted prompt string from a prompts/*.md file under base_dir."""
    prompt_path = base_dir / "prompts" / filename
    with open(prompt_path, "r", encoding="utf-8") as f:
        content = f.read()

    start_token = f'{marker} = """'
    if start_token not in content:
        raise ValueError(f"Could not find {marker} in {filename}")

    start = content.index(start_token) + len(start_token)
    end = content.rindex('"""')
    return content[start:end]


def strip_json_fences(response_text: str) -> str:
    response_text = re.sub(r"^```(?:json)?\s*\n?", "", response_text)
    response_text = re.sub(r"\n?```$", "", response_text)
    return response_text.strip()


def call_claude_json(
    client: Anthropic,
    prompt: str,
    *,
    model: str = "claude-sonnet-4-5",
    max_tokens: int = 4096,
) -> dict[str, Any]:
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = strip_json_fences(message.content[0].text)
    return json.loads(response_text)
