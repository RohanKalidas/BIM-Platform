"""
build.agents.base — shared infrastructure for every agent.

Every agent uses _call_agent(system_prompt, user_prompt, schema, label) to:
  1. Send the prompt to Claude (Sonnet for orchestration-heavy work,
     Haiku for narrow specialists)
  2. Extract JSON from the response (with prefill retry on parse failure)
  3. Validate against the Pydantic schema
  4. Return (parsed_object, AgentRun telemetry record)

This pattern is ported from BIM Studio. Same shape, same JSON-extraction
logic. Agents stay thin — almost all logic lives in their prompts.
"""
from __future__ import annotations
import json
import logging
import os
import re
import time
from typing import Any, Optional, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from ...schemas.pipeline import AgentRun

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Models — Sonnet for orchestrator/Brief, Haiku for specialists.
ORCHESTRATOR_MODEL = "claude-sonnet-4-5"
SPECIALIST_MODEL = "claude-haiku-4-5"

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to your environment before running."
            )
        _client = anthropic.Anthropic(api_key=api_key)
    return _client


def _extract_json(text: str) -> dict:
    """
    Pull the first complete JSON object out of `text`. Robust to:
      - Markdown code fences (```json ... ```)
      - Leading/trailing prose
      - Trailing commas (loose recovery — only if strict parse fails)
    """
    fence = re.search(r"```(?:json)?\s*\n(.*?)\n```", text, re.DOTALL)
    if fence:
        text = fence.group(1)

    start = text.find("{")
    if start < 0:
        raise ValueError("No '{' found in response")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                blob = text[start: i + 1]
                try:
                    return json.loads(blob)
                except json.JSONDecodeError:
                    cleaned = re.sub(r",(\s*[}\]])", r"\1", blob)
                    return json.loads(cleaned)
    raise ValueError("Unbalanced JSON braces in response")


def _call_agent(
    system_prompt: str,
    user_prompt: str,
    schema: Type[T],
    label: str,
    *,
    model: str = SPECIALIST_MODEL,
    max_tokens: int = 8000,
    max_retries: int = 1,
) -> tuple[T, AgentRun]:
    """
    Call an agent and parse its JSON output into the given schema.

    On parse failure or validation error, retries once with a prefill
    that nudges the model toward valid JSON.
    """
    client = _get_client()
    started = time.time()

    messages = [{"role": "user", "content": user_prompt}]

    for attempt in range(max_retries + 1):
        prefill = '{"' if attempt > 0 else None
        msg_kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
        }
        if prefill:
            msg_kwargs["messages"] = messages + [
                {"role": "assistant", "content": prefill}
            ]

        response = client.messages.create(**msg_kwargs)
        text = response.content[0].text if response.content else ""
        if prefill:
            text = prefill + text

        try:
            data = _extract_json(text)
            obj = schema.model_validate(data)
            duration = time.time() - started
            run = AgentRun(
                agent=label,
                duration_s=round(duration, 2),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )
            logger.info(
                "%s: done in %.2fs (%d in / %d out tok)",
                label, duration, response.usage.input_tokens,
                response.usage.output_tokens,
            )
            return obj, run
        except (ValueError, ValidationError, json.JSONDecodeError) as e:
            if attempt < max_retries:
                logger.warning("%s: parse/validate failed (%s), retrying with prefill", label, e)
                continue
            logger.error("%s: gave up after %d attempts: %s\nResponse:\n%s",
                         label, attempt + 1, e, text[:1000])
            raise

    raise RuntimeError("unreachable")
