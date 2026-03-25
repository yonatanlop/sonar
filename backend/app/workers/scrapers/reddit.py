"""
RedditScraper — usa PRAW (Python Reddit API Wrapper).
API oficial, gratuita, 60 req/min sin límite diario.

Credenciales necesarias (.env):
  REDDIT_CLIENT_ID     — obtenido en reddit.com/prefs/apps
  REDDIT_CLIENT_SECRET
  REDDIT_USER_AGENT    — ej: "SONAR Monitor 1.0"
"""
import logging
import time
from datetime import datetime, timezone

import praw
from praw.exceptions import PRAWException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entity import Entity, Keyword
from app.workers.scrapers.base import (
    BaseScraper, build_search_terms, save_mention, upsert_account_profile,
)

logger = logging.getLogger(__name__)

# Número máximo de resultados por búsqueda
MAX_POSTS_PER_SEARCH    = 50
MAX_COMMENTS_PER_POST   = 30
SEARCH_TIME_FILTER      = "day"    # 'hour' | 'day' | 'week' | 'month'
DELAY_BETWEEN_SEARCHES  = 2        # segundos entre búsquedas (respetar rate limit)


class RedditScraper(BaseScraper):
    platform_code = "reddit"

    def __init__(self, db: Session):
        super().__init__(db)
        self.reddit = praw.Reddit(
            client_id=settings.REDDIT_CLIENT_ID,
            client_secret=settings.REDDIT_CLIENT_SECRET,
            user_agent=settings.REDDIT_USER_AGENT,
        )
        self.reddit.read_only = True  # solo lectura, sin autenticación de usuario

    def scrape_entity(self, entity: Entity, keywords: list[Keyword]) -> int:
        saved_total = 0
        search_terms = build_search_terms(entity, keywords)

        for term, keyword_obj in search_terms:
            try:
                saved = self._search_and_save(term, entity, keyword_obj)
                saved_total += saved
                time.sleep(DELAY_BETWEEN_SEARCHES)
            except PRAWException as e:
                logger.warning(f"[Reddit] PRAW error buscando '{term}': {e}")
            except Exception as e:
                logger.error(f"[Reddit] Error inesperado buscando '{term}': {e}")

        return saved_total

    def _search_and_save(self, term: str, entity: Entity, keyword_obj: Keyword) -> int:
        saved = 0
        subreddit = self.reddit.subreddit("all")

        posts = list(subreddit.search(
            query=f'"{term}"',
            limit=MAX_POSTS_PER_SEARCH,
            time_filter=SEARCH_TIME_FILTER,
            sort="new",
        ))

        for post in posts:
            # Guardar perfil del autor
            if post.author:
                try:
                    redditor = post.author
                    upsert_account_profile(
                        db=self.db,
                        platform_id=self.platform.id,
                        username=str(redditor.name),
                        external_user_id=str(redditor.id) if hasattr(redditor, "id") else None,
                        followers_count=getattr(redditor, "link_karma", None),
                        account_created=datetime.fromtimestamp(
                            redditor.created_utc, tz=timezone.utc
                        ).date() if hasattr(redditor, "created_utc") else None,
                        has_profile_photo=bool(getattr(redditor, "icon_img", None)),
                    )
                except Exception:
                    pass  # autor eliminado o suspendido

            # Contenido del post: título + cuerpo
            content = f"{post.title}\n\n{post.selftext}".strip()
            if not content:
                continue

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"post_{post.id}",
                content=content,
                author_username=str(post.author) if post.author else "[deleted]",
                author_ext_id=str(post.author.id) if post.author and hasattr(post.author, "id") else None,
                url=f"https://reddit.com{post.permalink}",
                published_at=datetime.fromtimestamp(post.created_utc, tz=timezone.utc),
                reach=post.score + post.num_comments,
                matched_keywords=[keyword_obj],
            )
            if mention:
                saved += 1

            # Comentarios del post
            saved += self._save_comments(post, entity, keyword_obj, term)

        return saved

    def _save_comments(self, post, entity: Entity, keyword_obj: Keyword, term: str) -> int:
        saved = 0
        try:
            post.comments.replace_more(limit=0)  # no cargar más comentarios anidados
            comments = list(post.comments)[:MAX_COMMENTS_PER_POST]
        except Exception:
            return 0

        for comment in comments:
            if not hasattr(comment, "body"):
                continue
            # Solo guardar comentarios que mencionan el término
            if term.lower() not in comment.body.lower():
                continue

            if comment.author:
                try:
                    upsert_account_profile(
                        db=self.db,
                        platform_id=self.platform.id,
                        username=str(comment.author.name),
                        external_user_id=str(comment.author.id) if hasattr(comment.author, "id") else None,
                    )
                except Exception:
                    pass

            mention = save_mention(
                db=self.db,
                platform_id=self.platform.id,
                entity_id=entity.id,
                external_id=f"comment_{comment.id}",
                content=comment.body,
                author_username=str(comment.author) if comment.author else "[deleted]",
                author_ext_id=str(comment.author.id) if comment.author and hasattr(comment.author, "id") else None,
                url=f"https://reddit.com{comment.permalink}",
                published_at=datetime.fromtimestamp(comment.created_utc, tz=timezone.utc),
                reach=comment.score,
                matched_keywords=[keyword_obj],
            )
            if mention:
                saved += 1

        return saved
