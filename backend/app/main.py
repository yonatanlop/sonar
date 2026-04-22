from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import router as api_router
from app.core.config import settings

app = FastAPI(
    title="SONAR — Monitoreo Reputacional",
    description="Sistema de Observación y Navegación en Ambientes de Redes",
    version="2.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "project": "SONAR"}
