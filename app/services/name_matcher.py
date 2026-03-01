"""
Поиск упоминаний ФИО в тексте: разбор запроса (ФИО/инициалы), NER (Natasha), лемматизация (pymorphy2).
"""

import re
from dataclasses import dataclass
from typing import Optional

from natasha import Segmenter, MorphVocab, NewsEmbedding, NewsNERTagger, Doc

from app.utils.text import normalize_text, make_snippet, highlight_snippet_html

# Морфологический анализатор для приведения слов к начальной форме (опционально)
try:
    import pymorphy2
    _MORPH: Optional["pymorphy2.MorphAnalyzer"] = pymorphy2.MorphAnalyzer()
except Exception:
    _MORPH = None

# Только буквы (кириллица + латиница) для токенизации
_WORD_RE = re.compile(r"[А-Яа-яЁёA-Za-z]+")


def tokenize(s: str) -> list[str]:
    """Разбивает строку на слова (только буквы), приводит к нижнему регистру и ё→е."""
    s = normalize_text(s).lower()
    return [w.replace("ё", "е") for w in _WORD_RE.findall(s)]


def lemmatize_parts(parts: list[str]) -> list[str]:
    """Приводит слова запроса к начальной форме."""
    if not _MORPH or not parts:
        return parts
    result: list[str] = []
    for w in parts:
        p = _MORPH.parse(w)
        if p:
            result.append((p[0].normal_form or w).lower().replace("ё", "е"))
        else:
            result.append(w)
    return result


# Одна буква или буква с точкой — инициал (И., О.)
_INITIAL_RE = re.compile(r"^[А-ЯA-Z]$|^[А-ЯA-Z]\.$", re.I)


@dataclass(frozen=True)
class QueryName:
    """Распарсенный запрос: сырая строка, части слова, фамилия/имя/отчество, инициалы."""
    raw: str
    parts: list[str]
    surname: Optional[str] = None
    name: Optional[str] = None
    patronymic: Optional[str] = None
    name_initial: Optional[str] = None
    patronymic_initial: Optional[str] = None


def parse_query_name(query: str) -> QueryName:
    """Разбирает строку запроса на фамилию, имя, отчество и инициалы."""
    q = normalize_text(query)
    if not q:
        return QueryName(raw="", parts=[])

    # Раскладываем «И.И.» в отдельные буквы для инициалов
    exploded: list[str] = []
    for tok in q.split():
        if "." in tok and len(tok) <= 6:
            letters = [ch for ch in tok if ch.isalpha()]
            if len(letters) >= 2:
                exploded.extend(letters[:3])
            else:
                exploded.append(tok)
        else:
            exploded.append(tok)

    initials = [t for t in exploded if _INITIAL_RE.match(t)]
    words = [t for t in exploded if not _INITIAL_RE.match(t)]

    name_initial = initials[0][0].lower() if len(initials) >= 1 else None
    patronymic_initial = initials[1][0].lower() if len(initials) >= 2 else None

    parts = [w.lower().replace("ё", "е") for w in words]

    surname = parts[0] if len(parts) >= 1 else None
    name = parts[1] if len(parts) >= 2 else None
    patronymic = parts[2] if len(parts) >= 3 else None

    return QueryName(
        raw=q,
        parts=parts,
        surname=surname,
        name=name,
        patronymic=patronymic,
        name_initial=name_initial,
        patronymic_initial=patronymic_initial,
    )


@dataclass(frozen=True)
class MatchResult:
    """Результат совпадения: балл, текст/нормализованное ФИО, позиция, сниппет, тип матча."""
    score: int
    person_text: str
    person_normal: str
    start: int
    end: int
    snippet: str
    snippet_html: str
    match_type: str


class NatashaNameMatcher:
    """Ищет упоминания ФИО в тексте: NER (PER) + сравнение с запросом по леммам/инициалам."""

    def __init__(self) -> None:
        self.segmenter = Segmenter()
        self.morph_vocab = MorphVocab()
        self.emb = NewsEmbedding()
        self.ner = NewsNERTagger(self.emb)

    def _score_by_tokens(
        self,
        q: QueryName,
        person_tokens: list[str],
        parts_lemmas: Optional[list[str]] = None,
    ) -> tuple[int, str]:
        """Оценивает совпадение запроса с токенами персоны (балл и тип: full, two_parts, surname_only и т.д.)."""
        tset = set(person_tokens)
        # Леммы запроса для сравнения с NER (у NER — именительный падеж)
        s_lemma = (parts_lemmas[0] if parts_lemmas and len(parts_lemmas) >= 1 else (q.surname or ""))
        n_lemma = (parts_lemmas[1] if parts_lemmas and len(parts_lemmas) >= 2 else (q.name or ""))
        p_lemma = (parts_lemmas[2] if parts_lemmas and len(parts_lemmas) >= 3 else (q.patronymic or ""))

        # 100 баллов — полное ФИО (все три части совпали)
        if q.surname and q.name and q.patronymic:
            if s_lemma in tset and n_lemma in tset and p_lemma in tset:
                return 100, "full"

        # 85 — фамилия + имя (два слова)
        if len(q.parts) == 2 and parts_lemmas and len(parts_lemmas) >= 2:
            if parts_lemmas[0] in tset and parts_lemmas[1] in tset:
                return 85, "two_parts"
        if len(q.parts) == 2:
            if q.parts[0] in tset and q.parts[1] in tset:
                return 85, "two_parts"

        # 80 — фамилия и инициалы имени/отчества
        if q.surname and (q.name_initial or q.patronymic_initial):
            if s_lemma in tset:
                other = [x for x in person_tokens if x != s_lemma]
                ok = True
                if q.name_initial:
                    ok = ok and any(x and x[0] == q.name_initial for x in other)
                if q.patronymic_initial:
                    ok = ok and any(x and x[0] == q.patronymic_initial for x in other)
                if ok:
                    return 80, "surname+initials"

        # 55 — только фамилия (одно слово в запросе)
        if len(q.parts) == 1 and q.surname and (s_lemma in tset or q.surname in tset):
            return 55, "surname_only"

        return 0, "no"

    def _fallback_plain_text(
        self,
        text: str,
        q: QueryName,
        parts_lemmas: Optional[list[str]] = None,
    ) -> Optional[MatchResult]:
        """Поиск по тексту без NER: все части запроса (леммы) должны встретиться в тексте."""
        lemmas = parts_lemmas if parts_lemmas else q.parts
        if not lemmas:
            return None

        text_n = normalize_text(text)
        text_l = text_n.lower().replace("ё", "е")

        for lemma in lemmas:
            if text_l.find(lemma) == -1:
                return None

        # Сниппет строим вокруг фамилии (первая лемма), ищем по подстроке
        surname_lemma = lemmas[0]
        idx = text_l.find(surname_lemma)
        if idx == -1:
            return None
        start = idx
        end = idx + len(surname_lemma)
        snippet, ls, le = make_snippet(text_n, start, end)
        return MatchResult(
            score=35,
            person_text=surname_lemma,
            person_normal=surname_lemma,
            start=start,
            end=end,
            snippet=snippet,
            snippet_html=highlight_snippet_html(snippet, ls, le),
            match_type="fallback_text",
        )

    def find_best(self, text: str, query: str) -> Optional[MatchResult]:
        """Ищет лучшее совпадение ФИО в тексте: NER-персоны, при отсутствии — поиск по тексту."""
        q = parse_query_name(query)
        if not q.raw:
            return None

        text_n = normalize_text(text)
        if not text_n:
            return None

        parts_lemmas = lemmatize_parts(q.parts)

        doc = Doc(text_n)
        doc.segment(self.segmenter)
        doc.tag_ner(self.ner)

        best: Optional[MatchResult] = None

        for span in doc.spans:
            if span.type != "PER":
                continue

            span.normalize(self.morph_vocab)
            person_normal = (span.normal or span.text or "").strip()
            person_tokens = tokenize(person_normal)

            score, mtype = self._score_by_tokens(q, person_tokens, parts_lemmas)
            if score <= 0:
                continue

            snippet, ls, le = make_snippet(text_n, span.start, span.stop)
            cand = MatchResult(
                score=score,
                person_text=(span.text or "").strip(),
                person_normal=person_normal,
                start=span.start,
                end=span.stop,
                snippet=snippet,
                snippet_html=highlight_snippet_html(snippet, ls, le),
                match_type=mtype,
            )

            if (best is None) or (cand.score > best.score):
                best = cand

        if best is None:
            return self._fallback_plain_text(text_n, q, parts_lemmas)

        return best