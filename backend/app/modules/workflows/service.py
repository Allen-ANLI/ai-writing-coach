"""Workflow business logic: create, background run, resume, cancel, events.

The graph runs in a background task; its result pauses at
``awaiting_confirmation`` until the user resumes with a business action.
Confirm applies results through the owning business services (outline save,
expression save) — the workflow never writes user data directly.
"""

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import ApiError
from app.core.time import utcnow
from app.modules.billing import service as billing_service
from app.modules.essays import repository as essay_repository
from app.modules.essays.models import Essay
from app.modules.essays.service import get_essay
from app.modules.expressions import service as expressions_service
from app.modules.expressions.schemas import CreateExpressionRequest
from app.modules.learning import service as learning_service
from app.modules.outlines import service as outlines_service
from app.modules.outlines.models import WritingOutline
from app.modules.users.models import User
from app.modules.workflows import graphs
from app.modules.workflows.models import Workflow, WorkflowEvent
from app.modules.workflows.schemas import CreateWorkflowRequest, ResumeWorkflowRequest

logger = logging.getLogger(__name__)


def _emit(db: Session, workflow: Workflow, step: str, event_type: str, payload: dict) -> None:
    db.add(
        WorkflowEvent(
            workflow_id=workflow.id,
            step=step,
            event_type=event_type,
            payload_json=payload,
            created_at=utcnow(),
        )
    )
    workflow.current_step = step
    workflow.updated_at = utcnow()
    db.commit()


def create_workflow(db: Session, user: User, payload: CreateWorkflowRequest) -> Workflow:
    if payload.workflow_type in ("writing_planner", "learning_extractor"):
        if payload.essay_id is None:
            raise ApiError(422, "VALIDATION_ERROR", "essay_id is required for this workflow.")
        get_essay(db, user, payload.essay_id)
    billing_service.guard_ai_call(db, user.id)
    workflow = Workflow(
        user_id=user.id,
        workflow_type=payload.workflow_type,
        essay_id=payload.essay_id,
        status="running",
        input_json=payload.input,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(workflow)
    db.commit()
    db.refresh(workflow)
    _emit(db, workflow, "created", "step_completed", {"workflow_type": workflow.workflow_type})
    return workflow


def get_workflow(db: Session, user: User, workflow_id: uuid.UUID) -> Workflow:
    workflow = db.execute(
        select(Workflow).where(Workflow.id == workflow_id, Workflow.user_id == user.id)
    ).scalar_one_or_none()
    if workflow is None:
        raise ApiError(404, "RESOURCE_NOT_FOUND", "Workflow not found.")
    return workflow


def list_events(db: Session, user: User, workflow_id: uuid.UUID) -> list[WorkflowEvent]:
    get_workflow(db, user, workflow_id)
    rows = db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_id == workflow_id)
        .order_by(WorkflowEvent.created_at.asc(), WorkflowEvent.id.asc())
    ).scalars()
    return list(rows)


def run_workflow(session_factory: sessionmaker, workflow_id: uuid.UUID) -> None:
    with session_factory() as db:
        workflow = db.get(Workflow, workflow_id)
        if workflow is None or workflow.status != "running":
            return

        def emit(step: str, event_type: str, payload: dict) -> None:
            _emit(db, workflow, step, event_type, payload)

        essay = db.get(Essay, workflow.essay_id) if workflow.essay_id else None
        version = None
        if workflow.workflow_type == "learning_extractor" and essay is not None:
            version_id = workflow.input_json.get("version_id")
            if version_id:
                version = essay_repository.get_version_for_essay(
                    db, essay.id, uuid.UUID(str(version_id))
                )
            if version is None:
                version = essay_repository.latest_version(db, essay.id)
        db.commit()  # no transaction held during graph execution

        try:
            graph = graphs.build_graph(
                workflow.workflow_type, session_factory, workflow.user_id, emit
            )
            state = graphs.initial_state(
                workflow.workflow_type, workflow.input_json, essay, version
            )
            final_state = graph.invoke(state, {"configurable": {"thread_id": str(workflow_id)}})
        except ApiError as exc:
            workflow.status = "failed"
            workflow.error_message = exc.message
            workflow.updated_at = utcnow()
            db.add(
                WorkflowEvent(
                    workflow_id=workflow.id,
                    step="run",
                    event_type="failed",
                    payload_json={"error": exc.message},
                    created_at=utcnow(),
                )
            )
            db.commit()
            return
        except Exception:
            logger.exception("workflow %s failed unexpectedly", workflow_id)
            workflow.status = "failed"
            workflow.error_message = "Workflow failed unexpectedly."
            workflow.updated_at = utcnow()
            db.commit()
            return

        if workflow.status != "running":
            return  # cancelled while running
        workflow.result_json = graphs.result_payload(workflow.workflow_type, final_state)
        workflow.status = "awaiting_confirmation"
        workflow.updated_at = utcnow()
        db.add(
            WorkflowEvent(
                workflow_id=workflow.id,
                step="confirmation",
                event_type="awaiting_confirmation",
                payload_json={},
                created_at=utcnow(),
            )
        )
        db.commit()


def _confirm_planner(db: Session, user: User, workflow: Workflow) -> dict:
    outline_data = (workflow.result_json or {}).get("outline")
    if not outline_data:
        raise ApiError(409, "VALIDATION_ERROR", "No outline result to confirm.")
    essay = get_essay(db, user, workflow.essay_id)
    next_no = (
        db.execute(
            select(WritingOutline.version_no)
            .where(WritingOutline.essay_id == essay.id)
            .order_by(WritingOutline.version_no.desc())
            .limit(1)
        ).scalar_one_or_none()
        or 0
    ) + 1
    outline = WritingOutline(
        essay_id=essay.id,
        user_id=user.id,
        version_no=next_no,
        status="draft",
        source_context={"workflow_id": str(workflow.id)},
        workflow_id=workflow.id,
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(outline)
    db.flush()
    outlines_service.save_generated_outline(
        db, outline, outline_data["thesis_statement"], outline_data["sections"]
    )
    outline.status = "confirmed"
    outline.confirmed_at = utcnow()
    db.commit()
    return {"outline_id": str(outline.id)}


def _confirm_extractor(db: Session, user: User, workflow: Workflow, action_input: dict) -> dict:
    candidates = (workflow.result_json or {}).get("candidates", [])
    selected = action_input.get("candidate_indices")
    if selected is not None:
        candidates = [candidates[i] for i in selected if 0 <= i < len(candidates)]
    saved: list[str] = []
    skipped = 0
    for candidate in candidates:
        try:
            expression = expressions_service.create_expression(
                db,
                user,
                CreateExpressionRequest(
                    english_text=candidate["english_text"],
                    chinese_meaning=candidate.get("chinese_meaning"),
                    original_text=candidate.get("original_text"),
                    learning_value_reason=candidate.get("learning_value_reason"),
                    usage_context=candidate.get("usage_context"),
                    topic=candidate.get("topic"),
                    grammar_pattern=candidate.get("grammar_pattern"),
                    source_type="essay",
                    essay_id=workflow.essay_id,
                ),
            )
            saved.append(str(expression.id))
        except ApiError as exc:
            if exc.status_code == 409:
                skipped += 1
            else:
                raise
    return {"saved_expression_ids": saved, "skipped_duplicates": skipped}


def _confirm_study_planner(db: Session, user: User, workflow: Workflow) -> dict:
    plan_data = (workflow.result_json or {}).get("plan") or {}
    suggestions = plan_data.get("suggestions", [])
    if not suggestions:
        raise ApiError(409, "VALIDATION_ERROR", "No study suggestions to confirm.")
    goal = workflow.input_json.get("goal")
    plan = learning_service.create_plan_from_suggestions(db, user, goal, suggestions, workflow.id)
    return {"accepted": True, "plan_id": str(plan.id), "task_count": len(suggestions)}


def resume_workflow(
    db: Session, user: User, workflow_id: uuid.UUID, payload: ResumeWorkflowRequest
) -> tuple[Workflow, bool]:
    """Returns (workflow, needs_rerun). Revise re-runs the graph in background."""
    workflow = get_workflow(db, user, workflow_id)
    if workflow.status != "awaiting_confirmation":
        raise ApiError(409, "VALIDATION_ERROR", "This workflow is not awaiting confirmation.")

    if payload.action in ("confirm", "continue"):
        if workflow.workflow_type == "writing_planner":
            outcome = _confirm_planner(db, user, workflow)
        elif workflow.workflow_type == "learning_extractor":
            outcome = _confirm_extractor(db, user, workflow, payload.input)
        else:
            outcome = _confirm_study_planner(db, user, workflow)
        workflow.status = "completed"
        workflow.result_json = {**(workflow.result_json or {}), "outcome": outcome}
        workflow.updated_at = utcnow()
        _emit(db, workflow, "confirmation", "completed", {"action": payload.action, **outcome})
        return workflow, False

    if payload.action == "reject":
        workflow.status = "completed"
        workflow.result_json = {**(workflow.result_json or {}), "outcome": {"rejected": True}}
        workflow.updated_at = utcnow()
        _emit(db, workflow, "confirmation", "completed", {"action": "reject"})
        return workflow, False

    # revise: merge feedback and re-run
    workflow.input_json = {**workflow.input_json, **payload.input}
    workflow.status = "running"
    workflow.result_json = None
    workflow.updated_at = utcnow()
    _emit(db, workflow, "confirmation", "resumed", {"action": "revise"})
    return workflow, True


def cancel_workflow(db: Session, user: User, workflow_id: uuid.UUID) -> Workflow:
    workflow = get_workflow(db, user, workflow_id)
    if workflow.status not in ("running", "awaiting_confirmation"):
        raise ApiError(409, "VALIDATION_ERROR", "This workflow can no longer be cancelled.")
    workflow.status = "cancelled"
    workflow.updated_at = utcnow()
    _emit(db, workflow, "cancel", "cancelled", {})
    return workflow
