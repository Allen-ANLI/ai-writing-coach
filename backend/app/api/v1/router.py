from fastapi import APIRouter

from app.api.v1 import (
    analytics,
    auth,
    billing,
    essays,
    evaluations,
    expressions,
    grammar,
    health,
    ielts,
    learning,
    outlines,
    users,
    workflows,
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
api_router.include_router(evaluations.router, tags=["Evaluations"])
api_router.include_router(outlines.router, tags=["Outlines"])
api_router.include_router(workflows.router, tags=["Workflows"])
api_router.include_router(analytics.router, tags=["Analytics"])
api_router.include_router(billing.router, tags=["Billing"])
