"""Утилиты для текста: нормализация, дедупликация, сниппеты и подсветка в HTML."""

from __future__ import annotations

import html
import re

# Неразрывный пробел — заменяем на обычный при нормализации
NBSP = "\u00A0"


def normalize_text(s: str) -> str:
    """Ё→Е, неразрывные пробелы→пробел, схлопывание пробелов, trim."""
    if not s:
        return ""
    s = s.replace("ё", "е").replace("Ё", "Е")
    s = s.replace(NBSP, " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def deduplicate_text(text: str, min_phrase_len: int = 50) -> str:
    """
    Простой "анти-дубль": если на странице повторяется длинный кусок (шапка/подвал),
    отрезаем текст по месту второго появления.
    """
    if len(text) < min_phrase_len * 2:
        return text

    # Перебираем длину фразы от большей к меньшей, шаг по start — ускоряет поиск
    for ln in range(min(160, len(text) // 2), min_phrase_len - 1, -8):
        for start in range(0, min(ln, len(text) - ln), 4):
            phrase = text[start : start + ln]
            if len(phrase.strip()) < min_phrase_len:
                continue
            idx = text.find(phrase, start + ln)
            if idx != -1:
                return text[:idx].strip()

    return text


def make_snippet(text: str, start: int, end: int, max_len: int = 220) -> tuple[str, int, int]:
    """
    Делает сниппет вокруг найденного фрагмента (start/end — индексы в исходном text).
    Возвращает (snippet, local_start, local_end), где local_* — позиции матча уже в сниппете.
    """
    text = deduplicate_text(normalize_text(text))
    if not text:
        return "", 0, 0

    start = max(0, min(start, len(text)))
    end = max(start, min(end, len(text)))

    left = max(0, start - 80)
    right = min(len(text), end + 120)

    snippet = text[left:right].strip()

    # Обрезаем по max_len, центрируя вокруг найденного фрагмента
    if len(snippet) > max_len:
        center = (start + end) // 2
        left2 = max(0, center - max_len // 2)
        right2 = min(len(text), left2 + max_len)
        snippet = text[left2:right2].strip()
        left = left2

    local_start = max(0, start - left)
    local_end = max(local_start, end - left)

    if left > 0:
        snippet = "…" + snippet
        local_start += 1
        local_end += 1
    if right < len(text):
        snippet = snippet + "…"

    return snippet, local_start, local_end


def highlight_snippet_html(snippet: str, local_start: int, local_end: int) -> str:
    """Оборачивает фрагмент [local_start:local_end] в <mark>, остальное экранирует через html.escape."""
    snippet_esc = html.escape(snippet)
    # Режем по позициям в исходной строке, каждую часть escape отдельно — позиции не съезжают
    pre = html.escape(snippet[:local_start])
    mid = html.escape(snippet[local_start:local_end])
    post = html.escape(snippet[local_end:])
    return f"{pre}<mark>{mid}</mark>{post}"