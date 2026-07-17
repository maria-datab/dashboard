"""Anthropic Claude helpers for chat intents and material parsing."""

import json
from pathlib import Path
from typing import Any, Dict

from anthropic import Anthropic

import config
from shared.llm_helpers import call_claude_json, load_prompt_from_file as _load_prompt

_LLM_DIR = Path(__file__).resolve().parent


def load_prompt_from_file(filename: str, marker: str) -> str:
    """Load a triple-quoted prompt string from this backend's prompts/*.md files."""
    return _load_prompt(_LLM_DIR, filename, marker)


def parse_material(user_text: str, known_materials: list | None = None) -> str:
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    template = load_prompt_from_file("material-parse-prompt.md", "MATERIAL_PARSE_PROMPT")
    prompt = template.replace("{user_text}", user_text).replace(
        "{known_materials}", json.dumps(known_materials or [])
    )
    return call_claude_json(client, prompt)["material"]


def parse_chat_intent(
    user_message: str,
    chat_step: str,
    parts: list,
    known_materials: list | None = None,
) -> Dict[str, Any]:
    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    template = load_prompt_from_file("chat-intent-prompt.md", "CHAT_INTENT_PROMPT")
    prompt = (
        template.replace("{user_message}", user_message)
        .replace("{chat_step}", chat_step)
        .replace("{parts}", json.dumps(parts))
        .replace("{known_materials}", json.dumps(known_materials or []))
    )
    return call_claude_json(client, prompt)
