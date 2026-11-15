"""User profile business logic (ownership is enforced via the auth context)."""

from fastapi.encoders import jsonable_encoder
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.modules.users.models import User, UserProfile
from app.modules.users.schemas import (
    PatchMeRequest,
    PatchPreferencesRequest,
    PreferencesData,
)


def get_me(db: Session, user: User) -> User:
    # Refresh from the DB so profile edits in this session are visible.
    db.refresh(user)
    return user


def patch_me(db: Session, user: User, payload: PatchMeRequest) -> User:
    profile = user.profile
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(user)
    return user


def get_preferences(db: Session, user: User) -> PreferencesData:
    db.refresh(user)
    stored = user.profile.preferences or {}
    return PreferencesData.model_validate(stored)


def patch_preferences(db: Session, user: User, payload: PatchPreferencesRequest) -> PreferencesData:
    profile = user.profile
    updates = payload.model_dump(exclude_unset=True)
    merged = {**(profile.preferences or {}), **updates}
    validated = PreferencesData.model_validate(merged)
    profile.preferences = validated.model_dump()
    db.commit()
    db.refresh(user)
    return validated


def delete_account(db: Session, user: User) -> None:
    """Irreversibly delete the account and ALL owned data (R9, PRD §9.3).

    Deletes children before parents in FK-safe order within one transaction.
    System-wide reference data (IELTS bank, plans) is never touched.
    """
    from app.core.idempotency import IdempotencyRecord
    from app.modules.analytics.models import AiUsageLog
    from app.modules.auth.models import AuthRefreshToken, AuthSession, PasswordResetToken
    from app.modules.billing.models import (
        PaymentTransaction,
        UsageMeter,
        UserSubscription,
    )
    from app.modules.essays.models import (
        Essay,
        EssayEditEvent,
        EssayVersion,
        EssayWorkingDocument,
    )
    from app.modules.evaluations.models import EssayEvaluation, EssayRewrite
    from app.modules.expressions.models import (
        ExpressionEmbedding,
        ExpressionSource,
        ExpressionSuggestion,
        ExpressionSuggestionItem,
        UserExpression,
    )
    from app.modules.grammar.models import IssueSuggestion, IssueTeaching, WritingIssue
    from app.modules.ielts.models import UserFavoriteQuestion
    from app.modules.learning.models import (
        ExpressionProgress,
        ExpressionReview,
        LearningPlan,
        LearningTask,
        UserWeakness,
    )
    from app.modules.outlines.models import OutlineChatMessage, OutlineNode, WritingOutline
    from app.modules.workflows.models import Workflow, WorkflowEvent
    from app.modules.writing_sessions.models import WritingSession

    uid = user.id
    essay_ids = select(Essay.id).where(Essay.user_id == uid)
    issue_ids = select(WritingIssue.id).where(WritingIssue.essay_id.in_(essay_ids))
    evaluation_ids = select(EssayEvaluation.id).where(EssayEvaluation.user_id == uid)
    suggestion_ids = select(ExpressionSuggestion.id).where(ExpressionSuggestion.user_id == uid)
    expression_ids = select(UserExpression.id).where(UserExpression.user_id == uid)
    progress_ids = select(ExpressionProgress.id).where(ExpressionProgress.user_id == uid)
    outline_ids = select(WritingOutline.id).where(WritingOutline.user_id == uid)
    workflow_ids = select(Workflow.id).where(Workflow.user_id == uid)
    session_ids = select(AuthSession.id).where(AuthSession.user_id == uid)

    # Essays reference their original/final versions circularly; clear first.
    db.execute(
        update(Essay)
        .where(Essay.user_id == uid)
        .values(original_version_id=None, final_version_id=None)
    )
    db.execute(delete(EssayEditEvent).where(EssayEditEvent.essay_id.in_(essay_ids)))
    db.execute(delete(IssueTeaching).where(IssueTeaching.issue_id.in_(issue_ids)))
    db.execute(delete(IssueSuggestion).where(IssueSuggestion.issue_id.in_(issue_ids)))
    db.execute(delete(WritingIssue).where(WritingIssue.essay_id.in_(essay_ids)))
    db.execute(delete(EssayRewrite).where(EssayRewrite.evaluation_id.in_(evaluation_ids)))
    db.execute(delete(EssayEvaluation).where(EssayEvaluation.user_id == uid))
    db.execute(
        delete(ExpressionSuggestionItem).where(
            ExpressionSuggestionItem.suggestion_id.in_(suggestion_ids)
        )
    )
    db.execute(delete(ExpressionSuggestion).where(ExpressionSuggestion.user_id == uid))
    db.execute(delete(ExpressionSource).where(ExpressionSource.expression_id.in_(expression_ids)))
    db.execute(delete(EssayVersion).where(EssayVersion.essay_id.in_(essay_ids)))
    db.execute(delete(EssayWorkingDocument).where(EssayWorkingDocument.essay_id.in_(essay_ids)))
    db.execute(delete(WritingSession).where(WritingSession.user_id == uid))
    db.execute(delete(Essay).where(Essay.user_id == uid))
    db.execute(
        delete(ExpressionEmbedding).where(ExpressionEmbedding.expression_id.in_(expression_ids))
    )
    db.execute(delete(ExpressionReview).where(ExpressionReview.progress_id.in_(progress_ids)))
    db.execute(delete(ExpressionProgress).where(ExpressionProgress.user_id == uid))
    db.execute(delete(UserExpression).where(UserExpression.user_id == uid))
    db.execute(delete(UserWeakness).where(UserWeakness.user_id == uid))
    db.execute(delete(LearningTask).where(LearningTask.user_id == uid))
    db.execute(delete(LearningPlan).where(LearningPlan.user_id == uid))
    db.execute(delete(OutlineChatMessage).where(OutlineChatMessage.user_id == uid))
    db.execute(delete(OutlineNode).where(OutlineNode.outline_id.in_(outline_ids)))
    db.execute(delete(WritingOutline).where(WritingOutline.user_id == uid))
    db.execute(delete(WorkflowEvent).where(WorkflowEvent.workflow_id.in_(workflow_ids)))
    db.execute(delete(Workflow).where(Workflow.user_id == uid))
    db.execute(delete(UserFavoriteQuestion).where(UserFavoriteQuestion.user_id == uid))
    db.execute(delete(PaymentTransaction).where(PaymentTransaction.user_id == uid))
    db.execute(delete(UsageMeter).where(UsageMeter.user_id == uid))
    db.execute(delete(UserSubscription).where(UserSubscription.user_id == uid))
    db.execute(delete(AiUsageLog).where(AiUsageLog.user_id == uid))
    db.execute(delete(IdempotencyRecord).where(IdempotencyRecord.user_id == uid))
    db.execute(delete(AuthRefreshToken).where(AuthRefreshToken.session_id.in_(session_ids)))
    db.execute(delete(AuthSession).where(AuthSession.user_id == uid))
    db.execute(delete(PasswordResetToken).where(PasswordResetToken.user_id == uid))
    db.execute(delete(UserProfile).where(UserProfile.user_id == uid))
    db.execute(delete(User).where(User.id == uid))
    db.commit()


def _rows(db: Session, statement) -> list[dict]:
    return [dict(row._mapping) for row in db.execute(statement).all()]


def export_data(db: Session, user: User) -> dict:
    """Full JSON export of the user's own data (R9, PRD §9.3)."""
    from app.modules.analytics.models import AiUsageLog
    from app.modules.auth.models import AuthSession
    from app.modules.billing.models import PaymentTransaction, UsageMeter, UserSubscription
    from app.modules.essays.models import Essay, EssayVersion, EssayWorkingDocument
    from app.modules.evaluations.models import EssayEvaluation, EssayRewrite
    from app.modules.expressions.models import ExpressionSource, UserExpression
    from app.modules.learning.models import (
        ExpressionProgress,
        LearningPlan,
        LearningTask,
        UserWeakness,
    )
    from app.modules.outlines.models import OutlineChatMessage, OutlineNode, WritingOutline
    from app.modules.workflows.models import Workflow
    from app.modules.writing_sessions.models import WritingSession

    uid = user.id
    db.refresh(user)
    essay_ids = select(Essay.id).where(Essay.user_id == uid)
    expression_ids = select(UserExpression.id).where(UserExpression.user_id == uid)
    outline_ids = select(WritingOutline.id).where(WritingOutline.user_id == uid)
    evaluation_ids = select(EssayEvaluation.id).where(EssayEvaluation.user_id == uid)

    payload = {
        "exported_at": jsonable_encoder(user.created_at),
        "account": {
            "id": uid,
            "email": user.email,
            "status": user.status,
            "created_at": user.created_at,
            "profile": {
                "display_name": user.profile.display_name,
                "native_language": user.profile.native_language,
                "english_level": user.profile.english_level,
                "target_exam": user.profile.target_exam,
                "target_writing_score": user.profile.target_writing_score,
                "preferred_english_variant": user.profile.preferred_english_variant,
                "preferences": user.profile.preferences,
            },
        },
        "essays": _rows(db, select(Essay).where(Essay.user_id == uid)),
        "working_documents": _rows(
            db, select(EssayWorkingDocument).where(EssayWorkingDocument.essay_id.in_(essay_ids))
        ),
        "essay_versions": _rows(
            db, select(EssayVersion).where(EssayVersion.essay_id.in_(essay_ids))
        ),
        "writing_sessions": _rows(db, select(WritingSession).where(WritingSession.user_id == uid)),
        "expressions": _rows(db, select(UserExpression).where(UserExpression.user_id == uid)),
        "expression_sources": _rows(
            db, select(ExpressionSource).where(ExpressionSource.expression_id.in_(expression_ids))
        ),
        "expression_progress": _rows(
            db, select(ExpressionProgress).where(ExpressionProgress.user_id == uid)
        ),
        "weaknesses": _rows(db, select(UserWeakness).where(UserWeakness.user_id == uid)),
        "learning_plans": _rows(db, select(LearningPlan).where(LearningPlan.user_id == uid)),
        "learning_tasks": _rows(db, select(LearningTask).where(LearningTask.user_id == uid)),
        "outlines": _rows(db, select(WritingOutline).where(WritingOutline.user_id == uid)),
        "outline_nodes": _rows(
            db, select(OutlineNode).where(OutlineNode.outline_id.in_(outline_ids))
        ),
        "outline_chat_messages": _rows(
            db, select(OutlineChatMessage).where(OutlineChatMessage.user_id == uid)
        ),
        "evaluations": _rows(db, select(EssayEvaluation).where(EssayEvaluation.user_id == uid)),
        "rewrites": _rows(
            db, select(EssayRewrite).where(EssayRewrite.evaluation_id.in_(evaluation_ids))
        ),
        "workflows": _rows(db, select(Workflow).where(Workflow.user_id == uid)),
        "subscription": _rows(db, select(UserSubscription).where(UserSubscription.user_id == uid)),
        "payment_transactions": _rows(
            db, select(PaymentTransaction).where(PaymentTransaction.user_id == uid)
        ),
        "usage_meters": _rows(db, select(UsageMeter).where(UsageMeter.user_id == uid)),
        "ai_usage_logs": _rows(db, select(AiUsageLog).where(AiUsageLog.user_id == uid)),
        "sessions": _rows(
            db,
            select(
                AuthSession.id,
                AuthSession.device_label,
                AuthSession.created_at,
                AuthSession.last_used_at,
                AuthSession.revoked_at,
            ).where(AuthSession.user_id == uid),
        ),
    }
    return jsonable_encoder(payload)
