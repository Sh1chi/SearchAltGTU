"""HTTP-клиент: сессия с retry, таймаутом и заголовками браузера."""

import time
import logging
from dataclasses import dataclass
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import HEADERS, TIMEOUT_SEC

logger = logging.getLogger("uvicorn.error")


@dataclass
class HttpClient:
    """Обёртка над requests.Session с настройками для вежливого парсинга."""

    session: requests.Session

    @staticmethod
    def create() -> "HttpClient":
        """Создаёт сессию с User-Agent, retry при 5xx/429 и пулом соединений."""
        s = requests.Session()
        s.headers.update(HEADERS)

        retry = Retry(
            total=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET",),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        return HttpClient(session=s)

    def get_text(self, url: str, *, referer: Optional[str] = None) -> Optional[str]:
        """GET url, возвращает текст ответа в UTF-8 или None при ошибке/4xx+."""
        try:
            headers = {"Referer": referer} if referer else None
            r = self.session.get(url, timeout=TIMEOUT_SEC, headers=headers)

            size = len(r.content or b"")
            logger.info("GET %s -> %s (%d bytes)", url, r.status_code, size)

            if r.status_code >= 400:
                return None

            r.encoding = r.apparent_encoding or "utf-8"
            return r.text
        except requests.RequestException as e:
            logger.warning("GET %s failed: %s", url, e)
            return None


def polite_sleep(seconds: float) -> None:
    """Пауза между запросами, чтобы не нагружать сайт."""
    if seconds and seconds > 0:
        time.sleep(seconds)