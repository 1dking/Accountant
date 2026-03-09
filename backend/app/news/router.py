"""News briefing API router."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.dependencies import get_current_user, get_db
from app.news import service
from app.news.schemas import NewsArticleResponse, NewsPreferences

router = APIRouter()


@router.get("/preferences")
async def get_preferences(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    prefs = await service.get_news_preferences(db, user.id)
    return {"data": prefs}


@router.put("/preferences")
async def save_preferences(
    body: NewsPreferences,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    prefs = await service.save_news_preferences(db, user.id, body)
    return {"data": prefs}


@router.get("/articles")
async def list_articles(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    category: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
):
    articles = await service.list_news(db, user.id, category, limit)
    return {
        "data": [
            NewsArticleResponse.model_validate(a).model_dump()
            for a in articles
        ]
    }


@router.get("/articles/{article_id}")
async def get_article(
    article_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    from sqlalchemy import and_, select
    from app.news.models import NewsCache

    stmt = select(NewsCache).where(
        and_(NewsCache.id == article_id, NewsCache.user_id == user.id)
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()
    if not article:
        from fastapi import HTTPException
        raise HTTPException(404, "Article not found")
    return {"data": NewsArticleResponse.model_validate(article).model_dump()}


@router.post("/refresh")
async def refresh_news(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    count = await service.fetch_news_for_user(db, user.id)
    return {"data": {"fetched": count}}
