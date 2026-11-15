"""Auth routes (thin): delegate to the auth service, manage the refresh cookie.

The refresh token is never returned in a JSON body — Set-Cookie only.
"""

import ipaddress
import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import AuthContext, get_auth_context, verify_refresh_origin
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.core.rate_limit import enforce_auth_rate_limit
from app.infrastructure.database import get_db
from app.modules.auth import service
from app.modules.auth.schemas import (
    AuthResponse,
    LoginRequest,
    LogoutAllResponse,
    PasswordResetConfirmedResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    PasswordResetRequestedResponse,
    RegisterRequest,
    SessionItem,
    SessionsResponse,
)
from app.schemas.common import new_request_id

router = APIRouter()


def _set_refresh_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=True,
        samesite="strict",
        path=settings.refresh_cookie_path,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        path=settings.refresh_cookie_path,
        httponly=True,
        secure=True,
        samesite="strict",
    )


def _device_info(request: Request) -> service.DeviceInfo:
    # Client-supplied connection info is untrusted: only store a valid IP in
    # the INET column; anything else (proxies, test clients) becomes NULL.
    ip_address = None
    if request.client is not None:
        try:
            ip_address = str(ipaddress.ip_address(request.client.host))
        except ValueError:
            ip_address = None
    return service.DeviceInfo(
        device_label=None,
        user_agent=request.headers.get("user-agent"),
        ip_address=ip_address,
    )


def _auth_response(result: service.AuthResult) -> AuthResponse:
    return AuthResponse.model_validate(
        {
            "data": {
                "access_token": result.access_token,
                "token_type": "bearer",
                "expires_in": result.expires_in,
                "user": {
                    "id": result.user.id,
                    "email": result.user.email,
                    "display_name": result.user.profile.display_name,
                },
            },
            "meta": {"request_id": new_request_id()},
        }
    )


@router.post("/auth/register", status_code=201, response_model=AuthResponse)
def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    enforce_auth_rate_limit(request, "register")
    result = service.register(
        db,
        email=str(payload.email),
        password=payload.password,
        display_name=payload.display_name,
        device=_device_info(request),
    )
    _set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post("/auth/login", response_model=AuthResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> AuthResponse:
    enforce_auth_rate_limit(request, "login")
    result = service.login(
        db,
        email=str(payload.email),
        password=payload.password,
        device=_device_info(request),
    )
    _set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post(
    "/auth/refresh",
    response_model=AuthResponse,
    dependencies=[Depends(verify_refresh_origin)],
)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    token = request.cookies.get(get_settings().refresh_cookie_name)
    if not token:
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "Refresh cookie is missing.")
    result = service.refresh(db, refresh_token=token)
    _set_refresh_cookie(response, result.refresh_token)
    return _auth_response(result)


@router.post("/auth/logout", status_code=204)
def logout(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    service.logout(db, session_id=context.session.id)
    # FastAPI does not merge the injected response into a returned Response,
    # so the cookie clearing must be set on the object actually returned.
    response = Response(status_code=204)
    _clear_refresh_cookie(response)
    return response


@router.post("/auth/logout-all", response_model=LogoutAllResponse)
def logout_all(
    response: Response,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> LogoutAllResponse:
    count = service.logout_all(db, user_id=context.user.id)
    _clear_refresh_cookie(response)
    return LogoutAllResponse.model_validate(
        {"data": {"revoked_sessions": count}, "meta": {"request_id": new_request_id()}}
    )


@router.get("/auth/sessions", response_model=SessionsResponse)
def list_sessions(
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> SessionsResponse:
    sessions = service.list_sessions(db, user_id=context.user.id)
    items = [
        SessionItem.model_validate(s).model_copy(update={"is_current": s.id == context.session.id})
        for s in sessions
    ]
    return SessionsResponse(data=items, meta={"request_id": new_request_id()})


@router.delete("/auth/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: uuid.UUID,
    context: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
) -> Response:
    service.revoke_session(db, user_id=context.user.id, session_id=session_id)
    return Response(status_code=204)


@router.post(
    "/auth/password-reset/request", status_code=202, response_model=PasswordResetRequestedResponse
)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetRequestedResponse:
    enforce_auth_rate_limit(request, "password_reset")
    service.request_password_reset(db, email=str(payload.email))
    return PasswordResetRequestedResponse(
        data={"accepted": True}, meta={"request_id": new_request_id()}
    )


@router.post("/auth/password-reset/confirm", response_model=PasswordResetConfirmedResponse)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> PasswordResetConfirmedResponse:
    enforce_auth_rate_limit(request, "password_reset_confirm")
    service.confirm_password_reset(db, token=payload.token, new_password=payload.new_password)
    return PasswordResetConfirmedResponse(
        data={"password_updated": True}, meta={"request_id": new_request_id()}
    )
