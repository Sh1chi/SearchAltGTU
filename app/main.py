from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI(title="News Person Search (MVP)")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/search", response_class=HTMLResponse)
def search_page(request: Request, q: str = Query("", max_length=200)):
    query = (q or "").strip()
    # MVP: поиск ещё не реализован
    items = []
    return templates.TemplateResponse(
        "results.html",
        {"request": request, "q": query, "items": items},
    )


@app.get("/api/search")
def api_search(q: str = Query("", max_length=200)):
    query = (q or "").strip()
    return JSONResponse({"query": query, "count": 0, "items": []})