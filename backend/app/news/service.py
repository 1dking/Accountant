"""News briefing service — RSS fetching, caching, preferences."""

import json
import logging
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from re import sub as re_sub
from urllib.parse import quote_plus

import httpx
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.news.models import NewsCache
from app.news.schemas import NewsPreferences

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


def _strip_html(text: str) -> str:
    """Remove HTML tags and unescape entities."""
    clean = re_sub(r"<[^>]+>", "", text)
    return unescape(clean).strip()


def _first_sentence(text: str) -> str:
    """Extract the first sentence (up to 200 chars)."""
    text = _strip_html(text)
    for sep in (". ", "! ", "? "):
        idx = text.find(sep)
        if 0 < idx < 200:
            return text[: idx + 1]
    return text[:200]


def _parse_rss_items(xml_text: str) -> list[dict]:
    """Parse RSS XML and return list of article dicts."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        logger.warning("Failed to parse RSS XML")
        return articles

    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pub_date_el = item.find("pubDate")
        source_el = item.find("source")

        title = title_el.text if title_el is not None and title_el.text else ""
        link = link_el.text if link_el is not None and link_el.text else ""
        description = desc_el.text if desc_el is not None and desc_el.text else ""
        source_name = source_el.text if source_el is not None and source_el.text else "Unknown"

        published_at = None
        if pub_date_el is not None and pub_date_el.text:
            try:
                published_at = parsedate_to_datetime(pub_date_el.text)
            except (ValueError, TypeError):
                pass

        if title and link:
            articles.append({
                "title": _strip_html(title),
                "url": link,
                "source": source_name,
                "summary": _first_sentence(description) if description else None,
                "published_at": published_at,
            })

    return articles


async def get_news_preferences(db: AsyncSession, user_id: uuid.UUID) -> dict:
    """Get user's news preferences."""
    stmt = select(User.news_preferences_json).where(User.id == user_id)
    result = await db.execute(stmt)
    raw = result.scalar_one_or_none()
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    return {"industries": [], "topics": []}


async def save_news_preferences(
    db: AsyncSession, user_id: uuid.UUID, prefs: NewsPreferences
) -> dict:
    """Save user's news preferences."""
    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        return {"industries": [], "topics": []}

    data = prefs.model_dump()
    user.news_preferences_json = json.dumps(data)
    await db.commit()
    return data


async def fetch_news_for_user(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Fetch news articles from Google News RSS based on user preferences.

    Returns the number of new articles stored.
    """
    prefs = await get_news_preferences(db, user_id)
    industries = prefs.get("industries", [])
    topics = prefs.get("topics", [])

    if not industries and not topics:
        return 0

    # Build search queries
    queries: list[tuple[str, str]] = []  # (query, category)
    for industry in industries:
        queries.append((f"{industry} business news", "industry"))
    for topic in topics:
        queries.append((f"{topic} news", "topic"))

    all_articles: list[dict] = []
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for query, category in queries:
            url = GOOGLE_NEWS_RSS.format(query=quote_plus(query))
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    items = _parse_rss_items(resp.text)
                    for item in items[:5]:  # Max 5 per query
                        item["category"] = category
                    all_articles.extend(items[:5])
            except Exception as e:
                logger.warning("Failed to fetch RSS for %r: %s", query, e)

    # Dedup by URL and limit to 15
    seen_urls: set[str] = set()
    unique_articles: list[dict] = []
    for article in all_articles:
        if article["url"] not in seen_urls:
            seen_urls.add(article["url"])
            unique_articles.append(article)
        if len(unique_articles) >= 15:
            break

    # Store in DB, skip duplicates
    stored = 0
    for article in unique_articles:
        existing = await db.execute(
            select(NewsCache.id).where(
                and_(
                    NewsCache.user_id == user_id,
                    NewsCache.url == article["url"],
                )
            )
        )
        if existing.scalar_one_or_none():
            continue

        db.add(NewsCache(
            id=uuid.uuid4(),
            user_id=user_id,
            title=article["title"][:500],
            source=article["source"][:255],
            url=article["url"][:1000],
            summary=article.get("summary"),
            published_at=article.get("published_at"),
            category=article.get("category", "industry"),
        ))
        stored += 1

    if stored:
        await db.commit()

    return stored


async def list_news(
    db: AsyncSession,
    user_id: uuid.UUID,
    category: str | None = None,
    limit: int = 20,
) -> list[NewsCache]:
    """List cached news articles for a user."""
    stmt = select(NewsCache).where(NewsCache.user_id == user_id)
    if category and category != "all":
        stmt = stmt.where(NewsCache.category == category)
    stmt = stmt.order_by(NewsCache.published_at.desc().nullslast()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_news_for_briefing(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 3
) -> list[dict]:
    """Get top news articles for the daily briefing."""
    articles = await list_news(db, user_id, limit=limit)
    return [
        {
            "title": a.title,
            "source": a.source,
            "summary": a.summary or "",
            "url": a.url,
        }
        for a in articles
    ]


async def cleanup_old_news(db: AsyncSession, days: int = 7) -> int:
    """Delete news articles older than N days."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    stmt = delete(NewsCache).where(NewsCache.fetched_at < cutoff)
    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount or 0


async def fetch_news_all_users(session_factory) -> int:
    """Fetch news for all users with preferences. Called by scheduler."""
    total = 0
    async with session_factory() as db:
        stmt = select(User.id).where(User.news_preferences_json.is_not(None))
        result = await db.execute(stmt)
        user_ids = [row[0] for row in result.all()]

    for uid in user_ids:
        try:
            async with session_factory() as db:
                count = await fetch_news_for_user(db, uid)
                total += count
        except Exception as e:
            logger.error("Failed to fetch news for user %s: %s", uid, e)

    # Cleanup old articles
    try:
        async with session_factory() as db:
            cleaned = await cleanup_old_news(db)
            if cleaned:
                logger.info("Cleaned up %d old news articles", cleaned)
    except Exception as e:
        logger.error("Failed to cleanup old news: %s", e)

    return total
