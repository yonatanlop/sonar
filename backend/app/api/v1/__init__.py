from fastapi import APIRouter
from app.api.v1 import auth, users, dashboard, entities, platforms, mentions, alerts, reports, chat, twitter_feeds, youtube_explorer, audit, rizoma

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(users.router)
router.include_router(dashboard.router)
router.include_router(entities.router)
router.include_router(platforms.router)
router.include_router(mentions.router)
router.include_router(alerts.router)
router.include_router(reports.router)
router.include_router(chat.router)
router.include_router(twitter_feeds.router)
router.include_router(youtube_explorer.router)
router.include_router(audit.router)
router.include_router(rizoma.router)
