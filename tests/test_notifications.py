from app.monitoring import alert_signature, should_send_alert
from app.notifications import format_prompt_notification
from research.prompts import IntradayPrompt, PromptAction


def test_format_prompt_notification_contains_trade_fields() -> None:
    prompt = _prompt(PromptAction.SB_OPEN)

    title, body = format_prompt_notification("eastmoney:603236", prompt)

    assert "603236" in title
    assert "SB_OPEN" in title
    assert "price: 53.99" in body
    assert "buyback_target: 53.88" in body


def test_should_send_alert_only_for_new_actionable_prompt() -> None:
    prompt = _prompt(PromptAction.BS_OPEN)
    signature = alert_signature(prompt)

    assert should_send_alert(prompt, None)
    assert not should_send_alert(prompt, signature)
    assert not should_send_alert(_prompt(PromptAction.HOLD), None)


def _prompt(action: PromptAction) -> IntradayPrompt:
    return IntradayPrompt(
        action=action,
        ts="2026-06-18 10:14:00",
        price=53.99,
        qty=15100,
        confidence=88,
        reason="test",
        vwap=53.35,
        vwap_deviation_pct=1.2,
        amount_ratio=2.0,
        day_return_pct=-0.9,
        day_position_pct=56.0,
        planned_zone={"buyback_target": 53.88},
        warnings=[],
    )
