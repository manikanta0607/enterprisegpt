"""Aggregates all v1 API endpoint routers into a single router.

New endpoint modules (auth, documents, chat, admin, etc.) will be added here
in later phases without touching `main.py`.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import auth, conversations, documents, health, search, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)
