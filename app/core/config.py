"""Настройки приложения: URL АлтГТУ, лимиты парсинга, HTTP-заголовки."""

ALTSTU_BASE_URL = "https://www.altstu.ru"
NEWS_LIST_URL = "https://www.altstu.ru/m/n/"
NEWS_LIST_URL_PAGE = "https://www.altstu.ru/m/n/?page={page}"

# Ограничения (чтобы не перегружать сайт и не ждать слишком долго)
MAX_NEWS_PAGES = 15
MAX_ARTICLES_TO_FETCH = 60

# Сеть: таймаут запроса и пауза между запросами
TIMEOUT_SEC = 20
REQUEST_DELAY_SEC = 0.35

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
    "Connection": "keep-alive",
}