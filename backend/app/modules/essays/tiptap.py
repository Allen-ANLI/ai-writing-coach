"""Server-side derivation of plain text and word count from TipTap JSON.

ERD V1.2 §6.2: the server generates or validates plain text and word count
from the TipTap document; the client's values are never trusted blindly.

Canonical rules (the frontend must mirror them exactly):
- Top-level blocks are joined with "\\n\\n" (TipTap's default block separator).
- hardBreak becomes "\\n".
- List items are joined with "\\n"; nested blocks inside blockquotes keep the
  "\\n\\n" block separator.
- word_count counts whitespace-separated tokens (regex \\S+). CJK runs without
  spaces count as one token per run; IELTS essays are English, and Chinese is
  transient input that gets translated before it counts toward the essay.

Only the documented node types are interpreted; unknown container nodes are
traversed generically so future extensions degrade safely instead of losing
text. Structure is validated defensively (this is a system boundary).
"""

import re

from app.core.exceptions import ApiError

MAX_PLAIN_TEXT_CHARS = 100_000
MAX_DOC_NODES = 50_000
_MAX_DEPTH = 32

_WORD_RE = re.compile(r"\S+")
_LIST_TYPES = {"bulletList", "orderedList"}
_BLOCK_SEPARATOR_TYPES = {"doc", "blockquote"}


def count_words(plain_text: str) -> int:
    return len(_WORD_RE.findall(plain_text))


def _validate_node(node: object, depth: int, counter: list[int]) -> None:
    if depth > _MAX_DEPTH:
        raise ApiError(422, "VALIDATION_ERROR", "Document nesting is too deep.")
    if not isinstance(node, dict):
        raise ApiError(422, "VALIDATION_ERROR", "Document nodes must be objects.")
    counter[0] += 1
    if counter[0] > MAX_DOC_NODES:
        raise ApiError(422, "VALIDATION_ERROR", "Document is too large.")
    node_type = node.get("type")
    if not isinstance(node_type, str) or not node_type:
        raise ApiError(422, "VALIDATION_ERROR", "Document nodes need a string type.")
    if node_type == "text" and not isinstance(node.get("text", ""), str):
        raise ApiError(422, "VALIDATION_ERROR", "Text nodes need string text.")
    content = node.get("content")
    if content is not None:
        if not isinstance(content, list):
            raise ApiError(422, "VALIDATION_ERROR", "Node content must be a list.")
        for child in content:
            _validate_node(child, depth + 1, counter)


def validate_document(content_json: object) -> dict:
    if not isinstance(content_json, dict) or content_json.get("type") != "doc":
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "content_json must be a TipTap document.",
            [{"field": "content_json", "reason": "expected an object with type 'doc'"}],
        )
    _validate_node(content_json, 0, [0])
    return content_json


def _node_text(node: dict) -> str:
    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"
    children = node.get("content") or []
    if node_type in _LIST_TYPES:
        return "\n".join(_node_text(child) for child in children)
    if node_type in _BLOCK_SEPARATOR_TYPES:
        return "\n\n".join(_node_text(child) for child in children)
    return "".join(_node_text(child) for child in children)


def derive_text(content_json: dict) -> tuple[str, int]:
    """Return (plain_text, word_count) for a validated TipTap document."""
    plain_text = _node_text(content_json)
    if len(plain_text) > MAX_PLAIN_TEXT_CHARS:
        raise ApiError(
            422,
            "VALIDATION_ERROR",
            "Document text exceeds the maximum length.",
            [{"field": "content_json", "reason": f"max {MAX_PLAIN_TEXT_CHARS} characters"}],
        )
    return plain_text, count_words(plain_text)


def check_client_values(
    payload_text: str | None, payload_word_count: int | None, plain_text: str, word_count: int
) -> None:
    """When the client supplies plain_text / word_count they must agree with
    the server derivation; divergence means a buggy or tampered client."""
    details = []
    if payload_text is not None and payload_text != plain_text:
        details.append({"field": "plain_text", "reason": "does not match content_json"})
    if payload_word_count is not None and payload_word_count != word_count:
        details.append({"field": "word_count", "reason": "does not match content_json"})
    if details:
        raise ApiError(422, "VALIDATION_ERROR", "Document fields are inconsistent.", details)


def replace_text_range(content_json: dict, start: int, end: int, replacement: str) -> dict:
    """Replace a unicode_codepoint range of the document text with replacement.

    Used for server-side suggestion acceptance: the applied text comes from the
    stored suggestion, never from arbitrary client input. Structure and marks
    outside the range are preserved; hardBreaks inside the range are removed.
    Python str indices are code points, matching offset_unit.
    """
    if start < 0 or end <= start:
        raise ApiError(422, "VALIDATION_ERROR", "Invalid replacement range.")
    total_length = len(_node_text(content_json))
    if end > total_length:
        raise ApiError(422, "VALIDATION_ERROR", "Replacement range is outside the document text.")
    counter = [0]
    inserted = [False]

    def transform(node: dict) -> list[dict]:
        node_type = node.get("type")
        if node_type == "text":
            text = node.get("text", "")
            node_start, node_end = counter[0], counter[0] + len(text)
            counter[0] = node_end
            if node_end <= start or node_start >= end:
                return [node]
            pre = text[: max(0, start - node_start)]
            post = text[max(0, min(len(text), end - node_start)) :]
            out: list[dict] = []
            if pre:
                out.append({**node, "text": pre})
            if not inserted[0] and node_start <= start < node_end:
                if replacement:
                    out.append({"type": "text", "text": replacement})
                inserted[0] = True
            if post:
                out.append({**node, "text": post})
            return out
        if node_type == "hardBreak":
            node_start, node_end = counter[0], counter[0] + 1
            counter[0] = node_end
            if node_end <= start or node_start >= end:
                return [node]
            out = []
            if not inserted[0] and node_start <= start < node_end:
                if replacement:
                    out.append({"type": "text", "text": replacement})
                inserted[0] = True
            return out
        # Block separators contribute code points exactly as derive_text does.
        if node_type in ("doc", "blockquote"):
            separator = 2
        elif node_type in ("bulletList", "orderedList"):
            separator = 1
        else:
            separator = 0
        new_children: list[dict] = []
        for index, child in enumerate(node.get("content") or []):
            if index > 0 and separator:
                sep_start, sep_end = counter[0], counter[0] + separator
                if start < sep_end and end > sep_start:
                    raise ApiError(
                        422,
                        "VALIDATION_ERROR",
                        "Replacement range crosses a paragraph boundary.",
                    )
                counter[0] = sep_end
            new_children.extend(transform(child))
        return [{**node, "content": new_children}]

    result = transform(content_json)
    if not inserted[0]:
        raise ApiError(422, "VALIDATION_ERROR", "Replacement range is outside the document text.")
    return result[0]
