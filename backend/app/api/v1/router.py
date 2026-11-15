from fastapi import APIRouter

from app.api.v1 import (
    auth,
    essays,
    expressions,
    grammar,
    health,
    ielts,
    learning,
    users,
    writing_sessions,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(users.router, tags=["Users"])
api_router.include_router(essays.router, tags=["Essays"])
api_router.include_router(writing_sessions.router, tags=["Writing Sessions"])
api_router.include_router(grammar.router, tags=["Grammar"])
api_router.include_router(expressions.router, tags=["Expressions"])
api_router.include_router(learning.router, tags=["Learning"])
api_router.include_router(ielts.router, tags=["IELTS"])
