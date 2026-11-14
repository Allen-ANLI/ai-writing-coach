"""Rule-first grammar engine (SD §5.3–5.4, FR-02.5).

LanguageTool matches + custom deterministic rules are classified into product
categories with reliability levels. High-confidence hits get rule-template
short explanations and NEVER trigger an LLM call. Only uncertain hits are
batched to the LLM deep checker, and only when one is configured.

Offsets: LanguageTool works in UTF-16 code units; everything internal and in
the API is unicode_codepoint (AGENTS §4). Conversion happens at this boundary.
"""

import re
from dataclasses import dataclass, field

from app.infrastructure.language_tool.client import RuleMatch

# Categories per PRD FR-02.3 (visual mapping is the frontend's job).
CATEGORY_LABELS_ZH = {
    "grammar": "语法",
    "spelling": "拼写",
    "vocabulary": "词汇",
    "collocation": "搭配",
    "naturalness": "表达自然度",
    "style": "风格",
}

_LT_CATEGORY_MAP = {
    "TYPOS": "spelling",
    "GRAMMAR": "grammar",
    "COLLOCATIONS": "collocation",
    "STYLE": "style",
    "REDUNDANCY": "style",
    "CASING": "style",
    "PUNCTUATION": "style",
    "MISC": "vocabulary",
    "CONFUSED_WORDS": "vocabulary",
    "COMPOUNDING": "spelling",
}

# Rule ids we treat as deterministic (no LLM confirmation needed).
_DETERMINISTIC_RULES = {
    "HE_VERB_AGR",
    "VERB_AGR",
    "I_LOWERCASE",
    "A_VS_AN",
    "EN_A_VS_AN",
    "A_AN_AGREEMENT",
    "PLURAL_S",
    "NON3PRS_VERB",
    "PERS_PRONOUN_AGREEMENT",
    "ENGLISH_WORD_REPEAT_RULE",
    "COMMA_PARENTHESIS_WHITESPACE",
    "WHITESPACE_RULE",
    "SENTENCE_START_LOWERCASE",
}

# Chinese short-explanation templates for common deterministic rules.
_RULE_EXPLANATIONS_ZH = {
    "HE_VERB_AGR": "主谓一致：第三人称单数主语后的动词形式需要变化，或根据时间改用过去式。",
    "VERB_AGR": "主谓一致：主语和动词的单复数形式不匹配。",
    "NON3PRS_VERB": "主谓一致：非第三人称单数主语不应使用动词的 -s 形式。",
    "I_LOWERCASE": "人称代词 I 在任何位置都必须大写。",
    "A_VS_AN": "冠词选择：元音音素前用 an，辅音音素前用 a。",
    "EN_A_VS_AN": "冠词选择：元音音素前用 an，辅音音素前用 a。",
    "ENGLISH_WORD_REPEAT_RULE": "词语重复：相邻出现了相同的词，通常只需保留一个。",
    "WHITESPACE_RULE": "空白格式：存在多余或缺失的空格。",
    "COMMA_PARENTHESIS_WHITESPACE": "标点格式：逗号等标点后通常需要一个空格。",
}


@dataclass(frozen=True)
class DetectedIssue:
    category: str
    sub_category: str | None
    source: str  # rule_engine | llm | hybrid
    rule_id: str
    severity: str
    confidence: float | None
    start_offset: int  # unicode_codepoint, absolute in the checked text
    end_offset: int
    anchor_text: str
    short_explanation: str
    suggestions: list[str] = field(default_factory=list)
    needs_llm: bool = False
    rule_message: str = ""


def utf16_to_codepoint(text: str, utf16_offset: int) -> int:
    """Convert a UTF-16 code-unit offset to a Unicode code-point offset."""
    count = 0
    units = 0
    for ch in text:
        if units >= utf16_offset:
            break
        units += len(ch.encode("utf-16-le")) // 2
        count += 1
    return count


def classify_lt_match(match: RuleMatch, text: str) -> DetectedIssue | None:
    if match.length <= 0:
        return None
    start_cp = utf16_to_codepoint(text, match.offset)
    end_cp = utf16_to_codepoint(text, match.offset + match.length)
    if end_cp <= start_cp:
        return None
    anchor = text[start_cp:end_cp]

    category = _LT_CATEGORY_MAP.get(match.category_id, "grammar")
    if match.issue_type == "misspelling":
        category = "spelling"

    deterministic = (
        match.issue_type == "misspelling"
        or match.rule_id in _DETERMINISTIC_RULES
        or (category == "spelling" and bool(match.replacements))
    )
    severity = "high" if category in ("grammar", "spelling") else "medium"
    if category == "style":
        severity = "low"

    explanation = _RULE_EXPLANATIONS_ZH.get(match.rule_id)
    if explanation is None:
        label = CATEGORY_LABELS_ZH.get(category, "语言")
        explanation = f"{label}问题：{match.message}"

    return DetectedIssue(
        category=category,
        sub_category=match.rule_id.lower(),
        source="rule_engine",
        rule_id=match.rule_id,
        severity=severity,
        confidence=0.95 if deterministic else 0.5,
        start_offset=start_cp,
        end_offset=end_cp,
        anchor_text=anchor,
        short_explanation=explanation[:500],
        suggestions=list(match.replacements),
        needs_llm=not deterministic,
        rule_message=match.message,
    )


# --- Custom deterministic rules (high value for Chinese-speaking learners) ---

_CHINESE_PUNCT = {
    "，": ",",
    "。": ".",
    "！": "!",
    "？": "?",
    "；": ";",
    "：": ":",
    "（": "(",
    "）": ")",
    "“": '"',
    "”": '"',
    "‘": "'",
    "’": "'",
}
_CHINESE_PUNCT_RE = re.compile("[" + "".join(_CHINESE_PUNCT) + "]")
_MISSING_SPACE_RE = re.compile(r"[,.!?;:][A-Za-z]")


def custom_rules(text: str) -> list[DetectedIssue]:
    issues: list[DetectedIssue] = []
    for m in _CHINESE_PUNCT_RE.finditer(text):
        replacement = _CHINESE_PUNCT[m.group(0)]
        issues.append(
            DetectedIssue(
                category="style",
                sub_category="chinese_punctuation",
                source="rule_engine",
                rule_id="AWC_CHINESE_PUNCTUATION",
                severity="low",
                confidence=0.99,
                start_offset=m.start(),
                end_offset=m.end(),
                anchor_text=m.group(0),
                short_explanation=f"英文写作中应使用英文标点：建议将「{m.group(0)}」改为「{replacement}」。",
                suggestions=[replacement],
            )
        )
    for m in _MISSING_SPACE_RE.finditer(text):
        issues.append(
            DetectedIssue(
                category="style",
                sub_category="missing_space",
                source="rule_engine",
                rule_id="AWC_MISSING_SPACE_AFTER_PUNCT",
                severity="low",
                confidence=0.9,
                start_offset=m.start(),
                end_offset=m.end(),
                anchor_text=m.group(0),
                short_explanation="标点格式：逗号、句号等标点后应有一个空格。",
                suggestions=[m.group(0)[0] + " " + m.group(0)[1]],
            )
        )
    return issues


def merge_issues(primary: list[DetectedIssue], extra: list[DetectedIssue]) -> list[DetectedIssue]:
    """Merge rule sources, deduplicating identical (rule, span) reports.

    Different rules over overlapping spans are kept: e.g. a custom punctuation
    rule inside a LanguageTool match is a distinct, actionable finding.
    """
    merged = list(primary)
    seen = {(i.rule_id, i.start_offset, i.end_offset) for i in merged}
    for issue in extra:
        key = (issue.rule_id, issue.start_offset, issue.end_offset)
        if key in seen:
            continue
        merged.append(issue)
        seen.add(key)
    merged.sort(key=lambda i: (i.start_offset, i.end_offset))
    return merged
