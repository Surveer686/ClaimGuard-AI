"""User history risk context."""

from __future__ import annotations

from .data_loader import UserHistory


def format_user_history(history: UserHistory | None) -> str:
    if history is None:
        return "No prior claim history on file."
    return (
        f"Past claims: {history.past_claim_count} total "
        f"({history.accept_claim} accepted, {history.manual_review_claim} manual review, "
        f"{history.rejected_claim} rejected). "
        f"Last 90 days: {history.last_90_days_claim_count}. "
        f"Flags: {history.history_flags}. "
        f"Summary: {history.history_summary}"
    )


def history_risk_flags(history: UserHistory | None) -> list[str]:
    if history is None:
        return []
    flags: list[str] = []
    for part in history.history_flags.split(";"):
        part = part.strip()
        if part and part != "none":
            flags.append(part)
    if history.rejected_claim >= 3 and "user_history_risk" not in flags:
        flags.append("user_history_risk")
    return flags


def merge_history_flags(model_flags: list[str], history: UserHistory | None) -> list[str]:
    merged = []
    for flag in model_flags + history_risk_flags(history):
        flag = flag.strip()
        if flag and flag != "none" and flag not in merged:
            merged.append(flag)
    if "manual_review_required" in history_risk_flags(history) and "manual_review_required" not in merged:
        merged.append("manual_review_required")
    return merged
