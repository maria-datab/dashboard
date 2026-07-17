import json
import os
from pathlib import Path
from typing import Any, Dict

from anthropic import Anthropic

import config
from shared.llm_helpers import call_claude_json, load_prompt_from_file, strip_json_fences

_LLM_DIR = Path(__file__).resolve().parent


def _load_prompt_from_file(filename: str, marker: str) -> str:
    return load_prompt_from_file(_LLM_DIR, filename, marker)


def _load_output_schema() -> Dict[str, Any]:
    schema_path = os.getenv("OUTPUT_SCHEMA") or "assets/schema.json"
    schema_file = _LLM_DIR / schema_path
    with open(schema_file, "r", encoding="utf-8") as f:
        return json.load(f)


def _call_claude_json(client: Anthropic, prompt: str) -> Dict[str, Any]:
    return call_claude_json(client, prompt)


class CSVAnalyzer:
    """Normalizes messy CSV via Anthropic Claude."""

    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.prompt_template = _load_prompt_from_file("base-prompt.md", "ANALYSIS_PROMPT")
        self.output_schema = _load_output_schema()

    def analyze(self, csv_text: str) -> Dict[str, Any]:
        """Return { inputLists, variationNames } from Claude."""
        formatted_prompt = self.prompt_template.replace(
            "{reference_schema}", json.dumps(self.output_schema, indent=2)
        ).replace("{csv_text}", csv_text)

        return _call_claude_json(self.client, formatted_prompt)


def analyze_image(image_b64: str, media_type: str) -> Dict[str, Any]:
    """Return { inputLists, variationNames } from a handwritten table or sketch photo."""
    return _analyze_image_with_prompt(
        image_b64, media_type, "image-table-prompt.md", "IMAGE_TABLE_PROMPT"
    )


def _analyze_image_with_prompt(
    image_b64: str, media_type: str, prompt_file: str, prompt_marker: str
) -> Dict[str, Any]:
    if not config.ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set")

    client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    prompt_template = _load_prompt_from_file(prompt_file, prompt_marker)
    output_schema = _load_output_schema()
    prompt = prompt_template.replace(
        "{reference_schema}", json.dumps(output_schema, indent=2)
    )

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    response_text = strip_json_fences(message.content[0].text)
    return json.loads(response_text)


class BoxCommandParser:
    """Parses chat messages into add / update / delete / clear commands."""

    def __init__(self):
        if not config.ANTHROPIC_API_KEY:
            raise ValueError("ANTHROPIC_API_KEY is not set")

        self.client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
        self.prompt_template = _load_prompt_from_file("box-command-prompt.md", "BOX_COMMAND_PROMPT")
        schema_file = _LLM_DIR / "assets" / "chat-command-schema.json"
        with open(schema_file, "r", encoding="utf-8") as f:
            self.output_schema = json.load(f)

    def parse(self, user_message: str, existing_boxes: list) -> Dict[str, Any]:
        formatted_prompt = (
            self.prompt_template.replace(
                "{reference_schema}", json.dumps(self.output_schema, indent=2)
            )
            .replace("{user_message}", user_message)
            .replace("{existing_boxes}", json.dumps(existing_boxes, indent=2))
        )

        return _call_claude_json(self.client, formatted_prompt)
