"""Deterministic mock provider for development and automated tests.

Produces schema-valid, input-derived responses with zero cost. It performs NO
real language analysis: outputs are labeled "[mock]" and must never be used in
production (config default is mock only because no provider key is configured;
production deployment must set LLM_PROVIDER and credentials).
"""

import json
import time
import types
from typing import Literal, Union, get_args, get_origin

from pydantic import BaseModel

from app.ai.providers.base import LlmResult, LlmUsage

MOCK_MODEL_NAME = "mock-deterministic-v1"


def _mock_value(annotation, field_name: str, seed: str, max_len: int | None = None):
    origin = get_origin(annotation)
    if origin is Literal:
        return get_args(annotation)[0]
    if origin in (Union, types.UnionType):
        args = [arg for arg in get_args(annotation) if arg is not type(None)]
        return _mock_value(args[0], field_name, seed, max_len) if args else None
    if origin is list:
        (item_type,) = get_args(annotation) or (str,)
        # Two items: satisfies every min_length=2 schema in app.ai.schemas.
        return [_mock_value(item_type, field_name, seed), _mock_value(item_type, field_name, seed)]
    if origin is dict:
        return {}
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return build_mock_instance(annotation, seed)
    if annotation is bool:
        return True
    if annotation is int:
        return 1
    if annotation is float:
        return 0.9
    if annotation is str:
        excerpt = seed.strip().replace("\n", " ")[:60]
        value = f"[mock:{field_name}] {excerpt}"
        return value[:max_len] if max_len else value
    return None


def _field_max_length(field) -> int | None:
    for constraint in field.metadata:
        max_length = getattr(constraint, "max_length", None)
        if max_length is not None:
            return max_length
    return None


def build_mock_instance(model: type[BaseModel], seed: str) -> BaseModel:
    kwargs = {
        name: _mock_value(field.annotation, name, seed, _field_max_length(field))
        for name, field in model.model_fields.items()
    }
    return model(**kwargs)


def _mock_polish(user: str):
    """Deterministic fragment polish for E2E: flags 'very like' (Chinglish)
    with valid sentence-relative offsets and 3 drop-in options; any other
    sentence is treated as natural (empty fragments)."""
    from app.ai.schemas import PolishFragment, PolishOption, PolishSentenceResult

    sentence = ""
    for line in user.splitlines():
        if line.startswith("Sentence: "):
            sentence = line[len("Sentence: ") :]
            break
    anchor = "very like"
    start = sentence.find(anchor)
    if start < 0:
        return PolishSentenceResult(fragments=[])
    options = [
        PolishOption(
            text="really like",
            meaning="非常喜欢",
            usage="口语与书面均自然",
            formality="neutral",
        ),
        PolishOption(
            text="am very fond of",
            meaning="十分喜爱",
            usage="更正式、书面化",
            formality="formal",
        ),
        PolishOption(
            text="love",
            meaning="热爱",
            usage="简洁强烈，口语常用",
            formality="informal",
        ),
    ]
    return PolishSentenceResult(
        fragments=[
            PolishFragment(
                anchor_text=anchor,
                start_offset=start,
                end_offset=start + len(anchor),
                note="[mock] very 不能直接修饰动词 like，表达不地道。",
                options=options,
            )
        ]
    )


class MockProvider:
    def complete_json(
        self, *, system: str, user: str, response_model: type[BaseModel]
    ) -> LlmResult:
        started = time.monotonic()
        from app.ai.schemas import PlannerChatResult, PolishSentenceResult, SentenceCheckResult

        # PolishSentenceResult needs exactly 3 options per fragment; the
        # generic builder only makes 2, so handle it before generic build.
        if response_model is PolishSentenceResult:
            instance = _mock_polish(user)
        else:
            instance = build_mock_instance(response_model, user)
            # Deterministic planner-chat special case: the generic builder
            # picks the first Literal value ("discuss"), which would never
            # propose an outline. E2E needs the propose path.
            if isinstance(instance, PlannerChatResult):
                instance = instance.model_copy(update={"action": "propose"})
            if isinstance(instance, SentenceCheckResult):
                # Generic offsets would be invalid spans; the deterministic
                # mock reports no sentence-level findings (rules still run).
                instance = instance.model_copy(update={"issues": []})
        content = instance.model_dump(mode="json")
        latency_ms = int((time.monotonic() - started) * 1000)
        serialized = json.dumps(content, ensure_ascii=False)
        return LlmResult(
            content_json=content,
            usage=LlmUsage(
                provider="mock",
                model_name=MOCK_MODEL_NAME,
                input_tokens=(len(system) + len(user)) // 4,
                output_tokens=len(serialized) // 4,
                latency_ms=latency_ms,
                estimated_cost=0.0,
            ),
        )
