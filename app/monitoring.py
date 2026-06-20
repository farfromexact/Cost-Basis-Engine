from __future__ import annotations

from research.prompts import IntradayPrompt, PromptAction


def alert_signature(prompt: IntradayPrompt) -> str:
    return f"{prompt.action.value}:{prompt.ts}:{prompt.price}:{prompt.qty}"


def is_actionable_prompt(prompt: IntradayPrompt) -> bool:
    return prompt.action is not PromptAction.HOLD


def should_send_alert(prompt: IntradayPrompt, last_signature: str | None) -> bool:
    if not is_actionable_prompt(prompt):
        return False
    return alert_signature(prompt) != last_signature
