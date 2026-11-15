"""Unit tests for server-side TipTap range replacement (acceptance path)."""

import pytest

from app.core.exceptions import ApiError
from app.modules.essays import tiptap


def _doc(*paragraphs):
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": p}]} for p in paragraphs
        ],
    }


def test_replace_within_single_text_node():
    doc = _doc("He go to school.")
    result = tiptap.replace_text_range(doc, 3, 5, "went")
    assert tiptap.derive_text(result)[0] == "He went to school."


def test_replace_preserves_marks_outside_range():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "Bold ", "marks": [{"type": "bold"}]},
                    {"type": "text", "text": "go"},
                    {"type": "text", "text": " fast", "marks": [{"type": "italic"}]},
                ],
            }
        ],
    }
    result = tiptap.replace_text_range(doc, 5, 7, "went")
    text, _ = tiptap.derive_text(result)
    assert text == "Bold went fast"
    nodes = result["content"][0]["content"]
    assert nodes[0]["marks"] == [{"type": "bold"}]
    assert nodes[-1]["marks"] == [{"type": "italic"}]


def test_replace_across_paragraphs_rejected():
    """Issue ranges are sentence-local; crossing a block boundary is rejected
    rather than silently corrupting document structure."""
    doc = _doc("Hello", "World")
    with pytest.raises(ApiError):
        tiptap.replace_text_range(doc, 4, 8, "o W")


def test_replace_with_empty_deletes_range():
    doc = _doc("He go to school.")
    result = tiptap.replace_text_range(doc, 2, 5, "")
    assert tiptap.derive_text(result)[0] == "He to school."


def test_replace_emoji_offsets_are_codepoints():
    doc = _doc("🎉 He go")
    result = tiptap.replace_text_range(doc, 5, 7, "went")
    assert tiptap.derive_text(result)[0] == "🎉 He went"


def test_replace_hardbreak_inside_range():
    doc = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {"type": "text", "text": "a"},
                    {"type": "hardBreak"},
                    {"type": "text", "text": "b"},
                ],
            }
        ],
    }
    result = tiptap.replace_text_range(doc, 0, 3, "x")
    assert tiptap.derive_text(result)[0] == "x"


def test_out_of_range_rejected():
    doc = _doc("short")
    with pytest.raises(ApiError):
        tiptap.replace_text_range(doc, 0, 99, "x")
    with pytest.raises(ApiError):
        tiptap.replace_text_range(doc, -1, 2, "x")
    with pytest.raises(ApiError):
        tiptap.replace_text_range(doc, 3, 3, "x")
