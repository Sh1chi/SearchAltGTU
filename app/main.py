"""FastAPI-приложение: поиск по ФИО в новостях АлтГТУ (веб-форма и JSON API)."""

from __future__ import annotations

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.core.http_client import HttpClient
from app.services.name_matcher import NatashaNameMatcher
from app.services.search_service import SearchService


app = FastAPI(title="AltSTU News FIO Search")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# Общие зависимости: один HTTP-клиент, матчер и сервис поиска на всё приложение
_http = HttpClient.create()
_matcher = NatashaNameMatcher()
_search_service = SearchService(_http, _matcher)


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    """Главная страница с формой поиска."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/search", response_class=HTMLResponse)
def search_page(
    request: Request,
    q: str = Query("", min_length=0, max_length=200),
):
    """Страница с результатами поиска (HTML)."""
    query = (q or "").strip()
    items = _search_service.search(query) if query else []
    return templates.TemplateResponse(
        "results.html",
        {"request": request, "q": query, "items": items},
    )


@app.get("/api/search")
def api_search(q: str = Query("", min_length=0, max_length=200)):
    """JSON API: поиск по ФИО, возвращает список статей с полями url, title, score и т.д."""
    query = (q or "").strip()
    items = _search_service.search(query) if query else []
    data = [
        {
            "url": it.url,
            "title": it.title,
            "published_date": it.published_date,
            "snippet": it.snippet,
            "score": it.score,
            "match_type": it.match_type,
            "person_normal": it.person_normal,
        }
        for it in items
    ]
    return JSONResponse({"query": query, "count": len(data), "items": data})