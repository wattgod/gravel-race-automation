"""Optional, fail-closed TypeSafe helpers for advisory audits."""

from __future__ import annotations

import os
from typing import Any


class _FallbackQuestion:
    def __init__(self, **fields: Any) -> None:
        self.__dict__.update(fields)


class _FallbackChoice(_FallbackQuestion):
    pass


class _FallbackScore(_FallbackQuestion):
    pass


class _FallbackNoul(_FallbackQuestion):
    pass


def get_client() -> Any | None:
    if not os.environ.get("TYPESAFE_API_KEY", "").strip():
        return None
    try:
        from typesafe_sdk import TypeSafeClient

        return TypeSafeClient()
    except Exception:
        return None


def ask(state: dict[str, Any], questions: dict[str, Any]) -> Any | None:
    client = get_client()
    if client is None:
        return None
    try:
        return client.system_one(state=state, questions=questions)
    except Exception:
        return None


def choice(response: Any | None, key: str) -> Any | None:
    return (getattr(response, "choices", {}) or {}).get(key) if response else None


def noul(response: Any | None, key: str) -> Any | None:
    return (getattr(response, "nouls", {}) or {}).get(key) if response else None


def score(response: Any | None, key: str) -> Any | None:
    return (getattr(response, "scores", {}) or {}).get(key) if response else None


def probability(answer: Any | None) -> float | None:
    if answer is None:
        return None
    try:
        value = getattr(answer, "noul", answer)
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def confidence(answer: Any | None) -> float | None:
    if answer is None:
        return None
    try:
        value = getattr(answer, "confidence", None)
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def probabilities(answer: Any | None) -> dict[str, float]:
    values = getattr(answer, "probabilities", {}) or {} if answer else {}
    result: dict[str, float] = {}
    for key, value in values.items():
        try:
            result[str(key)] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def model(response: Any | None) -> Any | None:
    return getattr(response, "model", None) if response else None


def question_types() -> tuple[type[Any], type[Any], type[Any]]:
    try:
        from typesafe_sdk import Choice, Score, Noul

        return Choice, Score, Noul
    except Exception:
        return _FallbackChoice, _FallbackScore, _FallbackNoul


def base_report(response: Any | None, available: bool | None = None) -> dict[str, Any]:
    return {
        "schema_version": "jev-audit/v1",
        "model": model(response),
        "advisory": True,
        "guardrail": (
            "Advisory only. Flags require a human decision; nothing here changes "
            "a score, tier, explanation, or page."
        ),
        "jev_available": response is not None if available is None else available,
    }
