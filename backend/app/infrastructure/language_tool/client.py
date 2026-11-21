"""LanguageTool HTTP client (rule-first grammar checking, SD §5.3).

The rest of the backend never sees LanguageTool's raw response shape: matches
are converted to the internal RuleMatch structure here (FR-02.6 engine
replaceability). Service unavailability maps to GRAMMAR_SERVICE_UNAVAILABLE.
"""

from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.core.exceptions import ApiError


@dataclass(frozen=True)
class RuleMatch:
    rule_id: str
    category_id: str
    category_name: str
    message: str
    offset: int  # UTF-16 code units, as returned by LanguageTool
    length: int
    replacements: tuple[str, ...]
    # LT issue type: "misspelling" | "grammar" | "style" | "typographical" ...
    issue_type: str


def check_text(text: str, *, language: str | None = None) -> list[RuleMatch]:
    settings = get_settings()
    try:
        response = httpx.post(
            f"{settings.language_tool_url}/v2/check",
            data={"text": text, "language": language or settings.language_tool_language},
            timeout=settings.language_tool_timeout_seconds,
            # Local Docker infrastructure must never route through a system
            # proxy (httpx also reads the Windows registry proxy, which may be
            # configured but not running — loopback then fails with 10061).
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ApiError(
            503, "GRAMMAR_SERVICE_UNAVAILABLE", "The grammar checking service is unavailable."
        ) from exc

    matches: list[RuleMatch] = []
    for raw in payload.get("matches", []):
        rule = raw.get("rule", {})
        category = rule.get("category", {})
        matches.append(
            RuleMatch(
                rule_id=rule.get("id", "UNKNOWN"),
                category_id=category.get("id", "UNKNOWN"),
                category_name=category.get("name", ""),
                message=raw.get("message", ""),
                offset=int(raw.get("offset", 0)),
                length=int(raw.get("length", 0)),
                replacements=tuple(
                    replacement.get("value", "") for replacement in raw.get("replacements", [])[:5]
                ),
                issue_type=rule.get("issueType", "grammar"),
            )
        )
    return matches


def is_available() -> bool:
    settings = get_settings()
    try:
        response = httpx.get(
            f"{settings.language_tool_url}/v2/languages",
            timeout=3.0,
            trust_env=False,
        )
        return response.status_code == 200
    except httpx.HTTPError:
        return False
