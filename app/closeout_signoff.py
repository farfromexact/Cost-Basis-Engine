from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from app.end_of_day_review import EndOfDayReviewReport
from app.session_closeout import SessionCloseoutReport


CLOSEOUT_SIGNOFF_REVIEW_TOKEN = "APPROVE_EOD_CLOSEOUT_SIGNOFF"
CLOSEOUT_SIGNOFF_NOTE = (
    "Reviewed EOD snapshot only; no brokerage action, accounting event, or profitability claim is implied."
)


@dataclass(frozen=True)
class CloseoutSignoffCheck:
    check: str
    status: str
    detail: str
    operator_action: str

    def as_dict(self) -> dict:
        return {
            "check": self.check,
            "status": self.status,
            "detail": self.detail,
            "operator_action": self.operator_action,
        }


@dataclass(frozen=True)
class CloseoutSignoffPreview:
    status: str
    summary: str
    symbol: str
    session_date: str
    closeout_status: str
    closeout_countable: bool
    countable_cost_basis_reduction: float
    signoff_path: str
    checks: Sequence[CloseoutSignoffCheck]
    capability_note: str = CLOSEOUT_SIGNOFF_NOTE

    def as_dict(self) -> dict:
        return {
            "status": self.status,
            "summary": self.summary,
            "symbol": self.symbol,
            "session_date": self.session_date,
            "closeout_status": self.closeout_status,
            "closeout_countable": self.closeout_countable,
            "countable_cost_basis_reduction": self.countable_cost_basis_reduction,
            "signoff_path": self.signoff_path,
            "checks": [check.as_dict() for check in self.checks],
            "capability_note": self.capability_note,
        }


def default_closeout_signoff_dir() -> Path:
    return Path(".runtime") / "closeout_signoffs"


def build_closeout_signoff_preview(
    closeout: SessionCloseoutReport,
    review_token: str | None = None,
    directory: str | Path | None = None,
) -> CloseoutSignoffPreview:
    path = _signoff_path(closeout, directory)
    eligible = closeout.status == "NO_ACTION" or (closeout.status == "OK" and closeout.countable)
    checks = [
        CloseoutSignoffCheck(
            check="closeout_gate",
            status="OK" if eligible else "BLOCKED",
            detail=_closeout_gate_detail(closeout),
            operator_action="Resolve closeout blockers before exporting signoff." if not eligible else "Closeout may be signed off.",
        ),
        CloseoutSignoffCheck(
            check="review_token",
            status="OK" if review_token == CLOSEOUT_SIGNOFF_REVIEW_TOKEN else "REVIEW_REQUIRED",
            detail="Valid review token supplied." if review_token == CLOSEOUT_SIGNOFF_REVIEW_TOKEN else "Explicit review token is required before writing a snapshot.",
            operator_action="Pass the closeout signoff review token explicitly in the CLI.",
        ),
    ]
    if not eligible:
        status = "BLOCKED"
        summary = "Closeout signoff export is blocked until closeout is countable or no-action."
    elif review_token != CLOSEOUT_SIGNOFF_REVIEW_TOKEN:
        status = "REVIEW_REQUIRED"
        summary = "Closeout signoff export is ready for review but has not been written."
    else:
        status = "READY"
        summary = "Closeout signoff export is reviewed and ready to write."
    return CloseoutSignoffPreview(
        status=status,
        summary=summary,
        symbol=closeout.symbol,
        session_date=str(closeout.session_date),
        closeout_status=closeout.status,
        closeout_countable=closeout.countable,
        countable_cost_basis_reduction=float(closeout.countable_cost_basis_reduction),
        signoff_path=str(path),
        checks=tuple(checks),
    )


def write_closeout_signoff_after_review(
    closeout: SessionCloseoutReport,
    end_of_day_review: EndOfDayReviewReport,
    review_token: str,
    directory: str | Path | None = None,
    reviewer_note: str = "",
) -> Path:
    preview = build_closeout_signoff_preview(closeout, review_token=review_token, directory=directory)
    if preview.status != "READY":
        raise ValueError(preview.summary)
    path = Path(preview.signoff_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "signed_off_at": datetime.now(timezone.utc).isoformat(),
        "review_token_confirmed": True,
        "reviewer_note": reviewer_note,
        "preview": preview.as_dict(),
        "closeout": closeout.as_dict(),
        "end_of_day_review": end_of_day_review.as_dict(),
        "capability_note": CLOSEOUT_SIGNOFF_NOTE,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return path


def _signoff_path(closeout: SessionCloseoutReport, directory: str | Path | None) -> Path:
    base_dir = Path(directory) if directory is not None else default_closeout_signoff_dir()
    return base_dir / f"eod-signoff-{_safe_token(closeout.symbol)}-{_safe_token(str(closeout.session_date))}.json"


def _safe_token(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.strip())
    return cleaned.strip("-") or "unknown"


def _closeout_gate_detail(closeout: SessionCloseoutReport) -> str:
    if closeout.status == "NO_ACTION":
        return "No manual fills were present; no cost-basis reduction is counted."
    if closeout.status == "OK" and closeout.countable:
        return "Closeout is countable after broker match, restored inventory, and deducted fees/slippage."
    return f"Closeout status is {closeout.status}; countable={closeout.countable}."

