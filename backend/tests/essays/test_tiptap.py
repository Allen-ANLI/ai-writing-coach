"""Unit tests for server-side TipTap JSON derivation (ERD §6.2)."""

import pytest

from app.core.exceptions import ApiError
from app.modules.essays import tiptap


def _para(text: str) -> dict:
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def _doc(*blocks: dict) -> dict:
    return {"type": "doc", "content": list(blocks)}


def test_empty_document():
    assert tiptap.derive_text(_doc()) == ("", 0)


def test_single_paragraph():
    assert tiptap.derive_text(_doc(_para("Hello world."))) == ("Hello world.", 2)


def test_paragraphs_join_with_blank_line():
    text, count = tiptap.derive_text(_doc(_para("First paragraph."), _para("Second one.")))
    assert text == "First paragraph.\n\nSecond one."
    assert count == 4


def test_hard_break_becomes_newline():
    doc = _doc(
        {
            "type": "paragraph",
            "content": [
                {"type": "text", "text": "line one"},
                {"type": "hardBreak"},
                {"type": "text", "text": "line two"},
            ],
        }
    )
    assert tiptap.derive_text(doc) == ("line one\nline two", 4)


def test_heading_and_marks():
    doc = _doc(
        {
            "type": "heading",
            "attrs": {"level": 1},
            "content": [{"type": "text", "text": "Title", "marks": [{"type": "bold"}]}],
        },
        _para("Body text."),
    )
    assert tiptap.derive_text(doc) == ("Title\n\nBody text.", 3)


def test_bullet_list_items_join_with_newline():
    doc = _doc(
        {
            "type": "bulletList",
            "content": [
                {"type": "listItem", "content": [_para("alpha")]},
                {"type": "listItem", "content": [_para("beta")]},
            ],
        }
    )
    assert tiptap.derive_text(doc) == ("alpha\nbeta", 2)


def test_blockquote_keeps_block_separator():
    doc = _doc(
        {"type": "blockquote", "content": [_para("quoted one"), _para("quoted two")]},
        _para("after"),
    )
    assert tiptap.derive_text(doc) == ("quoted one\n\nquoted two\n\nafter", 5)


def test_unicode_text_preserved_exactly():
    text = "Emoji 🎉 and 中文 mixed with English."
    derived, count = tiptap.derive_text(_doc(_para(text)))
    assert derived == text
    assert count == 7


def test_word_count_whitespace_tokens():
    assert tiptap.count_words("  one\ttwo\n\nthree  ") == 3
    assert tiptap.count_words("") == 0


def test_unknown_container_traversed_generically():
    doc = _doc({"type": "futureWidget", "content": [_para("still visible")]})
    assert tiptap.derive_text(doc) == ("still visible", 2)


@pytest.mark.parametrize(
    "bad",
    [
        None,
        [],
        {"type": "paragraph"},
        {"type": "doc", "content": "not a list"},
        {"type": "doc", "content": [{"no_type": True}]},
        {"type": "doc", "content": [{"type": "text", "text": 42}]},
        {"type": "doc", "content": [5]},
    ],
)
def test_invalid_documents_rejected(bad):
    with pytest.raises(ApiError) as exc:
        tiptap.validate_document(bad)
    assert exc.value.status_code == 422
    assert exc.value.code == "VALIDATION_ERROR"


def test_excessive_nesting_rejected():
    node: dict = _para("deep")
    for _ in range(tiptap._MAX_DEPTH + 2):
        node = {"type": "blockquote", "content": [node]}
    with pytest.raises(ApiError):
        tiptap.validate_document(_doc(node))


def test_excessive_text_rejected():
    doc = _doc(_para("x" * (tiptap.MAX_PLAIN_TEXT_CHARS + 1)))
    tiptap.validate_document(doc)
    with pytest.raises(ApiError) as exc:
        tiptap.derive_text(doc)
    assert exc.value.status_code == 422


def test_client_value_mismatch_rejected():
    with pytest.raises(ApiError) as exc:
        tiptap.check_client_values("wrong", None, "right", 1)
    assert exc.value.status_code == 422
    assert exc.value.details[0]["field"] == "plain_text"

    with pytest.raises(ApiError) as exc:
        tiptap.check_client_values(None, 99, "right", 1)
    assert exc.value.details[0]["field"] == "word_count"


def test_client_values_matching_or_absent_accepted():
    tiptap.check_client_values("right", 1, "right", 1)
    tiptap.check_client_values(None, None, "right", 1)
