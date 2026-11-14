"""Grammar routes (thin). Mode enforcement, ownership and revision checks live
in the service; unrevealed answers never leave it."""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.grammar import service
from app.modules.grammar.schemas import (
    GrammarCheckRequest,
    GrammarCheckResponse,
    IgnoreIssueRequest,
    IssueListResponse,
    IssueResponse,
    IssueValidationRequest,
    IssueValidationResponse,
    RevealResponse,
    TeachingRequest,
    TeachingResponse,
)
from app.modules.users.models import User
from app.schemas.common import new_request_id

router = APIRouter()


@router.post("/essays/{essay_id}/grammar-check", response_model=GrammarCheckResponse)
def grammar_check(
    essay_id: uuid.UUID,
    payload: GrammarCheckRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> GrammarCheckResponse:
    data = service.grammar_check(db, user, essay_id, payload)
    return GrammarCheckResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.get("/essays/{essay_id}/issues", response_model=IssueListResponse)
def list_issues(
    essay_id: uuid.UUID,
    revision: int | None = Query(default=None, ge=1),
    status: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueListResponse:
    items = service.list_issues(db, user, essay_id, revision=revision, status=status)
    return IssueListResponse.model_validate(
        {"data": {"items": items}, "meta": {"request_id": new_request_id()}}
    )


@router.post("/essays/{essay_id}/issues/validate", response_model=IssueValidationResponse)
def validate_issue(
    essay_id: uuid.UUID,
    payload: IssueValidationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueValidationResponse:
    data = service.validate_issue(db, user, essay_id, payload)
    return IssueValidationResponse.model_validate(
        {"data": data, "meta": {"request_id": new_request_id()}}
    )


@router.get("/essays/{essay_id}/issues/{issue_id}", response_model=IssueResponse)
def get_issue(
    essay_id: uuid.UUID,
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueResponse:
    data = service.get_issue(db, user, essay_id, issue_id)
    return IssueResponse.model_validate({"data": data, "meta": {"request_id": new_request_id()}})


@router.patch("/essays/{essay_id}/issues/{issue_id}", response_model=IssueResponse)
def ignore_issue(
    essay_id: uuid.UUID,
    issue_id: uuid.UUID,
    payload: IgnoreIssueRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> IssueResponse:
    data = service.ignore_issue(db, user, essay_id, issue_id)
    return IssueResponse.model_validate({"data": data, "meta": {"request_id": new_request_id()}})


@router.post("/essays/{essay_id}/issues/{issue_id}/reveal", response_model=RevealResponse)
def reveal_issue(
    essay_id: uuid.UUID,
    issue_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RevealResponse:
    data = service.reveal_issue(db, user, essay_id, issue_id)
    return RevealResponse.model_validate({"data": data, "meta": {"request_id": new_request_id()}})


@router.post("/essays/{essay_id}/issues/{issue_id}/teaching", response_model=TeachingResponse)
def request_teaching(
    essay_id: uuid.UUID,
    issue_id: uuid.UUID,
    payload: TeachingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TeachingResponse:
    data = service.request_teaching(db, user, essay_id, issue_id, payload)
    return TeachingResponse.model_validate({"data": data, "meta": {"request_id": new_request_id()}})
