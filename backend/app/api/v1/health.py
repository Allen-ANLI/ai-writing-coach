from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.errors import error_response
from app.infrastructure.database import check_database_connection, get_db
from app.schemas.health import ErrorResponse, HealthData, HealthResponse, RequestMeta

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={
        503: {
            "description": "Service is up but the database is unavailable",
            "model": ErrorResponse,
        }
    },
    summary="Infrastructure health check",
)
def health(db: Session = Depends(get_db)) -> HealthResponse | JSONResponse:
    try:
        check_database_connection(db)
    except SQLAlchemyError:
        return error_response(503, "DATABASE_UNAVAILABLE", "Database is not reachable.")
    return HealthResponse(
        data=HealthData(status="ok", database="connected"),
        meta=RequestMeta(request_id=str(uuid4())),
    )
