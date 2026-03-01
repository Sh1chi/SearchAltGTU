"""
Сервис поиска: обходит страницы новостей АлтГТУ, качает статьи, ищет в них ФИО через NameMatcher.
"""

from dataclasses import dataclass
from typing import Any, Optional

from bs4 import BeautifulSoup

import logging
logger = logging.getLogger("uvicorn.error")

from app.core.config import (
    NEWS_LIST_URL,
    NEWS_LIST_URL_PAGE,
    MAX_NEWS_PAGES,
    MAX_ARTICLES_TO_FETCH,
    REQUEST_DELAY_SEC,
)
from app.core.http_client import HttpClient, polite_sleep
from app.services.altstu import (
    collect_articles_from_listing,
    extract_article_body,
    try_extract_date_from_article,
)
from app.services.name_matcher import NatashaNameMatcher


@dataclass(frozen=True)
class SearchItem:
    """Один результат поиска: ссылка на статью, заголовок, дата, сниппет с подсветкой, балл и тип матча."""
    url: str
    title: str
    published_date: str
    snippet: str
    snippet_html: str
    score: int
    match_type: str
    person_normal: str


class SearchService:
    """Обход списков новостей, загрузка статей и поиск упоминаний ФИО в тексте."""

    def __init__(self, http: HttpClient, matcher: NatashaNameMatcher) -> None:
        self.http = http
        self.matcher = matcher

    def search(self, query: str, *, max_pages: int = MAX_NEWS_PAGES, max_articles: int = MAX_ARTICLES_TO_FETCH) -> list[SearchItem]:
        """Ищет по запросу (ФИО) в новостях: страницы списка → статьи → матчер, возвращает отсортированные по score."""
        q = (query or "").strip()
        logger.info("SEARCH query=%r", q)
        if not q:
            return []

        results: list[SearchItem] = []
        seen_urls: set[str] = set()  # одна статья не попадает в ответ дважды

        for page_num in range(1, max_pages + 1):
            page_url = NEWS_LIST_URL if page_num == 1 else NEWS_LIST_URL_PAGE.format(page=page_num)
            html = self.http.get_text(page_url, referer=NEWS_LIST_URL)
            if not html:
                break

            soup = BeautifulSoup(html, "lxml")
            articles = collect_articles_from_listing(soup, page_url=page_url)  # ссылки на статьи с этой страницы
            logger.info("Listing %s: %d article links", page_url, len(articles))
            polite_sleep(REQUEST_DELAY_SEC)

            if not articles:
                break

            for art in articles:
                if len(results) >= max_articles:
                    return sorted(results, key=lambda x: x.score, reverse=True)

                if art.url in seen_urls:
                    continue
                seen_urls.add(art.url)

                art_html = self.http.get_text(art.url, referer=page_url)
                polite_sleep(REQUEST_DELAY_SEC)
                if not art_html:
                    logger.info("Skip article (no html): %s", art.url)
                    continue

                art_soup = BeautifulSoup(art_html, "lxml")
                body_text = extract_article_body(art_soup)
                if not body_text or len(body_text) < 80:
                    body_text = art_soup.get_text(" ", strip=True)

                logger.info("Article text len=%d: %s", len(body_text or ""), art.url)

                match = self.matcher.find_best(body_text, q)
                if not match:
                    continue

                logger.info("MATCH score=%d type=%s url=%s", match.score, match.match_type, art.url)

                published = art.published_date or try_extract_date_from_article(art_soup)  # дата из списка или из текста статьи

                results.append(
                    SearchItem(
                        url=art.url,
                        title=art.title,
                        published_date=published,
                        snippet=match.snippet,
                        snippet_html=match.snippet_html,
                        score=match.score,
                        match_type=match.match_type,
                        person_normal=match.person_normal,
                    )
                )

        return sorted(results, key=lambda x: x.score, reverse=True)