"""User routes (thin): identity comes from the auth context, never the body."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.infrastructure.database import get_db
from app.modules.users import service
from app.modules.users.models import User
from app.modules.users.schemas import MeResponse, PatchMeRequest
from app.schemas.common import new_request_id

router = APIRouter()


def _me_response(user: User) -> MeResponse:
    return MeResponse.model_validate(
        {
            "data": {
                "id": user.id,
                "email": user.email,
                "status": user.status,
                "email_verified_at": user.email_verified_at,
                "created_at": user.created_at,
                "profile": user.profile,
            },
            "meta": {"request_id": new_request_id()},
        }
    )


@router.get("/users/me", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> MeResponse:
    return _me_response(service.get_me(db, user))


@router.patch("/users/me", response_model=MeResponse)
def patch_me(
    payload: PatchMeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    return _me_response(service.patch_me(db, user, payload))
