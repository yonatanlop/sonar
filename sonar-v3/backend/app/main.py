from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.shared.config import settings

app = FastAPI(
    title="SONAR V3 — Monitoreo Reputacional",
    description="Sistema de Observación y Navegación en Ambientes de Redes — Arquitectura Hexagonal",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.modules.identity.api.auth_router import router as auth_router
from app.modules.identity.api.users_router import router as users_router
from app.modules.monitoring.api.entities_router import router as entities_router
from app.modules.monitoring.api.twitter_feeds_router import router as twitter_feeds_router
from app.modules.monitoring.api.platforms_router import router as platforms_router
from app.modules.collection.api.mentions_router import router as mentions_router
from app.modules.intelligence.api.intelligence_router import router as intelligence_router
from app.modules.alerting.api.alerts_router import router as alerts_router
from app.modules.reporting.api.reports_router import router as reports_router
from app.modules.legal.api.legal_router import router as legal_router
from app.modules.actor_map.api.actor_map_router import router as actor_map_router

app.include_router(auth_router, prefix="/api/v3")
app.include_router(users_router, prefix="/api/v3")
app.include_router(entities_router, prefix="/api/v3")
app.include_router(twitter_feeds_router, prefix="/api/v3")
app.include_router(platforms_router, prefix="/api/v3")
app.include_router(mentions_router, prefix="/api/v3")
app.include_router(intelligence_router, prefix="/api/v3")
app.include_router(alerts_router, prefix="/api/v3")
app.include_router(reports_router, prefix="/api/v3")
app.include_router(legal_router, prefix="/api/v3")
app.include_router(actor_map_router, prefix="/api/v3")


@app.get("/health", tags=["Sistema"])
def health_check():
    return {"status": "ok", "project": "SONAR", "version": "3.0.0"}
