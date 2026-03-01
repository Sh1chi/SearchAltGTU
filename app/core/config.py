# app/config.py
BASE_URL = "https://www.altstu.ru"
NEWS_LIST_URL = "https://www.altstu.ru/m/n/"

MAX_NEWS_PAGES = 5
MAX_ARTICLES_TO_FETCH = 50

REQUEST_TIMEOUT = 15  # seconds
POLITE_SLEEP_SECONDS = 0.4

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0 Safari/537.36"
}