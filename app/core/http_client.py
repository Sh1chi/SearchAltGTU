# app/http_client.py
import time
import requests
from .config import REQUEST_TIMEOUT, HEADERS, POLITE_SLEEP_SECONDS

class HttpClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def polite_sleep(self):
        if POLITE_SLEEP_SECONDS:
            time.sleep(POLITE_SLEEP_SECONDS)

    def get_text(self, url: str) -> str:
        r = self.session.get(url, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        self.polite_sleep()
        return r.text