"""Idempotent seeding of the original IELTS question bank.

Deterministic UUIDs (uuid5 over stable keys) make re-runs safe: existing rows
are left untouched. Applied by migration 0012 and by the IELTS test fixtures.
"""

import uuid

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.modules.ielts.models import IeltsQuestion, IeltsQuestionTag, QuestionTag
from app.modules.ielts.seed_data import SEED_QUESTIONS, SEED_TAGS

_NAMESPACE = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")


def question_id_for(key: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"ai-writing-coach:ielts-question:{key}")


def tag_id_for(slug: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, f"ai-writing-coach:ielts-tag:{slug}")


def seed_ielts(db: Session) -> None:
    now = utcnow()
    db.execute(
        pg_insert(QuestionTag)
        .values(
            [
                {
                    "id": tag_id_for(tag["slug"]),
                    "name": tag["name"],
                    "slug": tag["slug"],
                    "created_at": now,
                }
                for tag in SEED_TAGS
            ]
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    db.execute(
        pg_insert(IeltsQuestion)
        .values(
            [
                {
                    "id": question_id_for(q["key"]),
                    "task_type": q["task_type"],
                    "question_type": q["question_type"],
                    "prompt_text": q["prompt_text"],
                    "prompt_translation": q["prompt_translation"],
                    "difficulty": q["difficulty"],
                    "source_type": "original",
                    "source_title": "AI Writing Coach original practice bank",
                    "license_status": "original",
                    "is_published": True,
                    "created_at": now,
                }
                for q in SEED_QUESTIONS
            ]
        )
        .on_conflict_do_nothing(index_elements=["id"])
    )
    db.execute(
        pg_insert(IeltsQuestionTag)
        .values(
            [
                {"question_id": question_id_for(q["key"]), "tag_id": tag_id_for(slug)}
                for q in SEED_QUESTIONS
                for slug in q["tags"]
            ]
        )
        .on_conflict_do_nothing(index_elements=["question_id", "tag_id"])
    )
