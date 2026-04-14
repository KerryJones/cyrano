"""LLM client wrapper using LiteLLM for multi-provider support (Claude, OpenAI, etc.)."""

import json
import logging
import time

from litellm import completion

from cyrano.config import ANTHROPIC_API_KEY, LLM_DRAFTING_MODEL, LLM_TEMPERATURE, LLM_MAX_TOKENS

logger = logging.getLogger(__name__)


def chat_completion(prompt: str, model: str | None = None, retries: int = 3) -> dict | None:
    """Send a prompt to the LLM and return a parsed JSON dict.

    Args:
        prompt: The full prompt text.
        model: Override the model (defaults to LLM_DRAFTING_MODEL).
        retries: Number of retry attempts on failure.

    Returns:
        Parsed JSON dict, or None if all attempts fail.
    """
    model = model or LLM_DRAFTING_MODEL

    for attempt in range(retries):
        try:
            response = completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=LLM_MAX_TOKENS,
                temperature=LLM_TEMPERATURE,
                api_key=ANTHROPIC_API_KEY,
            )
            text = response.choices[0].message.content.strip()

            # Strip markdown code fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                # Drop first line (```json or ```) and last line (```)
                inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
                text = "\n".join(inner).strip()

            return json.loads(text)

        except json.JSONDecodeError as e:
            if attempt < retries - 1:
                logger.warning("JSON parse error on attempt %d (%s), retrying...", attempt + 1, e)
                time.sleep(2)
            else:
                logger.error("LLM returned unparseable JSON after %d attempts", retries)
                return None
        except Exception as e:
            if attempt < retries - 1:
                logger.warning("LLM error on attempt %d (%s), retrying...", attempt + 1, e)
                time.sleep(2)
            else:
                logger.error("LLM call failed after %d attempts: %s", retries, e)
                return None

    return None
