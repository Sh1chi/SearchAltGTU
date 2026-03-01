"""Сервис парсинга новостей с сайта АлтГТУ (altstu.ru)."""

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.core.config import ALTSTU_BASE_URL

# Регулярка для извлечения даты в формате ДД.ММ.ГГГГ
DATE_RE = re.compile(r"\b(\d{2}\.\d{2}\.\d{4})\b")


@dataclass(frozen=True)
class ArticleMeta:
    """Метаданные одной новостной статьи: ссылка, заголовок, дата, страница-источник."""
    url: str
    title: str
    published_date: str
    page_url: str


def is_article_link(href: str) -> bool:
    """Проверяет, ведёт ли ссылка на страницу статьи (а не на список/пагинацию)."""
    if not href:
        return False
    path = href.split("?")[0].rstrip("/").lower()

    if "?page=" in href or "page=" in path:
        return False

    # основной формат (десктоп)
    if "/structure/unit/" in path and "/news/" in path and path.count("/") >= 5:
        return True

    # мобильная версия: список новостей на /m/n/, а ссылки на статьи — /m/<id>/
    if path.startswith("/m/"):
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2:
            # /m/n, /m/s, /m/e — разделы, не статьи
            if parts[1] in ("n", "s", "e", "to_full"):
                return False
            # /m/27198, /m/27197 — страница статьи (числовой id)
            if parts[1].isdigit():
                return True
        return False

    return False


def extract_date_from_block(block) -> str:
    """Ищет в тексте HTML-блока дату формата ДД.ММ.ГГГГ."""
    text = block.get_text(" ", strip=True) if hasattr(block, "get_text") else ""
    m = DATE_RE.search(text)
    return m.group(1) if m else ""


def extract_article_body(soup: BeautifulSoup) -> str:
    """Достаёт основной текст статьи из HTML (семантика → классы → body)."""
    # 1) Сначала ищем по семантическим тегам
    for tag in soup.find_all(["article", "main"]):
        txt = tag.get_text(separator=" ", strip=True)
        if len(txt) > 150:
            return txt

    # 2) Затем по типичным классам контента
    for cls in ("news-text", "news-content", "content", "article-body", "post-content", "text", "body", "detail"):
        for tag in soup.find_all(class_=re.compile(cls, re.I)):
            txt = tag.get_text(separator=" ", strip=True)
            if len(txt) > 150:
                return txt

    # 3) Запасной вариант: весь body, без скриптов и навигации
    body = soup.find("body")
    if body:
        for skip in body.find_all(["script", "style", "nav", "footer", "aside"]):
            skip.decompose()
        return body.get_text(separator=" ", strip=True)

    return ""


def collect_articles_from_listing(soup: BeautifulSoup, page_url: str) -> list[ArticleMeta]:
    """Собирает из HTML списка новостей метаданные статей (без дубликатов)."""
    articles: list[ArticleMeta] = []
    seen: set[str] = set()  # чтобы не добавлять одну и ту же статью дважды

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not is_article_link(href):
            continue

        full_url = urljoin(ALTSTU_BASE_URL.rstrip("/") + "/", href)
        if full_url in seen:
            continue
        seen.add(full_url)

        # Берём заголовок из текста ссылки
        title = a.get_text(strip=True)
        if len(title) < 10:
            # Ищем заголовок в ближайших h2–h6 выше по дереву
            for prev in a.find_all_previous():
                if prev.name in ("h2", "h3", "h4", "h5", "h6"):
                    t = prev.get_text(strip=True)
                    if len(t) > 6:
                        title = t
                        break

        if len(title) < 5:
            continue

        # Ищем дату в родительских блоках (до 6 уровней вверх)
        date = ""
        block = a
        for _ in range(6):
            block = block.parent if block else None
            if block is None:
                break
            date = extract_date_from_block(block)
            if date:
                break

        articles.append(ArticleMeta(url=full_url, title=title, published_date=date, page_url=page_url))

    return articles


def try_extract_date_from_article(soup: BeautifulSoup) -> str:
    """Пытается найти дату в полном тексте страницы статьи."""
    txt = soup.get_text(" ", strip=True)
    m = DATE_RE.search(txt)
    return m.group(1) if m else ""