"""Unit tests for the rule engine: classification, offsets, custom rules."""

from app.infrastructure.language_tool.client import RuleMatch
from app.modules.grammar import rules


def _match(rule_id="HE_VERB_AGR", category="GRAMMAR", offset=3, length=2, issue_type="grammar"):
    return RuleMatch(
        rule_id=rule_id,
        category_id=category,
        category_name=category,
        message="test message",
        offset=offset,
        length=length,
        replacements=("went", "goes"),
        issue_type=issue_type,
    )


def test_utf16_to_codepoint_with_astral_chars():
    text = "🎉 He go"
    # '🎉' is 2 UTF-16 units but 1 codepoint; space at cp 1; 'He' cp 2..4.
    assert rules.utf16_to_codepoint(text, 0) == 0
    assert rules.utf16_to_codepoint(text, 2) == 1
    assert rules.utf16_to_codepoint(text, 3) == 2
    assert rules.utf16_to_codepoint(text, 6) == 5


def test_classify_grammar_match_is_deterministic():
    text = "He go to school."
    issue = rules.classify_lt_match(_match(), text)
    assert issue is not None
    assert issue.category == "grammar"
    assert issue.needs_llm is False
    assert issue.anchor_text == "go"
    assert issue.start_offset == 3
    assert issue.end_offset == 5
    assert issue.suggestions == ["went", "goes"]
    assert "主谓一致" in issue.short_explanation


def test_classify_misspelling_is_spelling_and_deterministic():
    text = "This is a tset."
    match = _match(
        rule_id="MORFOLOGIK_RULE_EN_US",
        category="TYPOS",
        offset=10,
        length=4,
        issue_type="misspelling",
    )
    issue = rules.classify_lt_match(match, text)
    assert issue.category == "spelling"
    assert issue.needs_llm is False


def test_classify_style_match_needs_llm():
    text = "This is very unique."
    match = _match(rule_id="VERY_UNIQUE", category="STYLE", offset=8, length=11, issue_type="style")
    issue = rules.classify_lt_match(match, text)
    assert issue.category == "style"
    assert issue.needs_llm is True
    assert issue.severity == "low"


def test_classify_offsets_with_emoji_prefix():
    text = "🎉 He go"
    match = _match(offset=6, length=2)  # UTF-16: emoji(2)+space(1)+He(2)+space(1)
    issue = rules.classify_lt_match(match, text)
    assert issue.anchor_text == "go"
    assert issue.start_offset == 5
    assert issue.end_offset == 7


def test_chinese_punctuation_custom_rule():
    text = "Hello，world。"
    issues = rules.custom_rules(text)
    punct = [i for i in issues if i.rule_id == "AWC_CHINESE_PUNCTUATION"]
    assert len(punct) == 2
    assert punct[0].anchor_text == "，"
    assert punct[0].suggestions == [","]
    assert punct[0].start_offset == 5
    assert punct[1].anchor_text == "。"


def test_missing_space_custom_rule():
    text = "Hello,world"
    issues = rules.custom_rules(text)
    assert any(i.rule_id == "AWC_MISSING_SPACE_AFTER_PUNCT" for i in issues)
    match = next(i for i in issues if i.rule_id == "AWC_MISSING_SPACE_AFTER_PUNCT")
    assert match.suggestions == [", w"]


def test_merge_deduplicates_same_position_and_nested():
    a = rules.custom_rules("Hello，world")
    b = rules.custom_rules("Hello，world")
    merged = rules.merge_issues(a, b)
    assert len(merged) == len(a)


def test_zero_length_match_ignored():
    assert rules.classify_lt_match(_match(length=0), "text") is None
