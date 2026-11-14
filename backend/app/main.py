from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.exceptions import ApiError
from app.schemas.common import new_request_id

# Explicit CORS whitelists: the HTTP methods used by the OpenAPI contract and
# the documented request headers (JSON bodies, bearer auth, idempotency key).
CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"]
CORS_ALLOW_HEADERS = ["Content-Type", "Authorization", "Idempotency-Key"]


def _error_envelope(
    status_code: int, code: str, message: str, details: list[dict] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "details": details or []},
            "meta": {"request_id": new_request_id()},
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(title="AI Writing Coach API", version="1.1.1")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=CORS_ALLOW_METHODS,
        allow_headers=CORS_ALLOW_HEADERS,
    )

    @application.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_envelope(exc.status_code, exc.code, exc.message, exc.details)

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or None,
                "reason": err["msg"],
            }
            for err in exc.errors()
        ]
        return _error_envelope(422, "VALIDATION_ERROR", "Request validation failed.", details)

    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
