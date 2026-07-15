from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, desktop, health, meta, personas, tts
from app.core.config import get_settings
from app.db.sqlite import Database


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Database()  # ensure schema
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Local multi-capability agent: chat, desktop, office, research, meetings, skills.",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, tags=["health"])
    app.include_router(meta.router, prefix="/api", tags=["meta"])
    app.include_router(chat.router, prefix="/api")
    app.include_router(personas.router, prefix="/api")
    app.include_router(tts.router, prefix="/api")
    app.include_router(desktop.router, prefix="/api")

    return app


app = create_app()
