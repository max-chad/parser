from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Mapping, Optional, Tuple
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag


DEFAULT_BASE_URL = "https://ads.vk.com"
DEFAULT_CASES_URL = f"{DEFAULT_BASE_URL}/cases"
DEFAULT_INPUT_PATH = Path("data/cases.html")
DEFAULT_OUTPUT_PATH = Path("cases.json")
DEFAULT_REQUEST_TIMEOUT = 10.0
DEFAULT_HEADERS: Mapping[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def derive_base_url(url: Optional[str]) -> Optional[str]:
    """Возвращает базовый URL (схема + хост) из произвольной ссылки."""
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        return f"{parsed.scheme}://{parsed.netloc}"
    return None


def fetch_html_from_url(
    url: str,
    *,
    timeout: float = DEFAULT_REQUEST_TIMEOUT,
    headers: Optional[Mapping[str, str]] = None,
) -> str:
    """Скачивает HTML-страницу по URL с нужными заголовками и таймаутом."""
    request_headers: dict[str, str] = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)
    response = requests.get(url, timeout=timeout, headers=request_headers)
    response.raise_for_status()
    response.encoding = response.encoding or response.apparent_encoding
    return response.text


def load_html_source(
    input_path: Path,
    url: Optional[str],
    timeout: float,
) -> Tuple[str, Optional[str]]:
    """Загружает HTML из файла или сети и возвращает исходный текст и URL."""
    if url:
        return fetch_html_from_url(url, timeout=timeout), url

    try:
        html = input_path.read_text(encoding="utf-8")
        return html, None
    except FileNotFoundError:
        if input_path == DEFAULT_INPUT_PATH:
            print(
                f"[parser] Local file {input_path} not found, downloading {DEFAULT_CASES_URL} instead...",
                file=sys.stderr,
            )
            html = fetch_html_from_url(DEFAULT_CASES_URL, timeout=timeout)
            return html, DEFAULT_CASES_URL
        raise

# Сопоставление номера месяца со всеми встречающимися формами написания.
MONTH_ALIASES = {
    1: ("январь", "января", "янв"),
    2: ("февраль", "февраля", "фев", "февр"),
    3: ("март", "марта", "мар"),
    4: ("апрель", "апреля", "апр"),
    5: ("май", "мая"),
    6: ("июнь", "июня", "июн"),
    7: ("июль", "июля", "июл"),
    8: ("август", "августа", "авг"),
    9: ("сентябрь", "сентября", "сен", "сент"),
    10: ("октябрь", "октября", "окт"),
    11: ("ноябрь", "ноября", "ноя", "нояб"),
    12: ("декабрь", "декабря", "дек"),
}


def _normalize_month_token(value: str) -> str:
    """Возвращает нормализованную форму русского названия месяца."""
    return value.strip().lower().replace("ё", "е").rstrip(".")


def _build_month_mapping() -> dict[str, int]:
    """Строит словарь {нормализованное_название: номер_месяца}."""
    mapping: dict[str, int] = {}
    for month_number, aliases in MONTH_ALIASES.items():
        for alias in aliases:
            mapping[_normalize_month_token(alias)] = month_number
    return mapping


# Быстрый доступ к номеру месяца по строковому ключу.
MONTHS_RU = _build_month_mapping()

# Регулярные выражения, покрывающие ISO, dd.mm.yyyy и русские текстовые даты.
ISO_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")
DOT_DATE_RE = re.compile(r"^(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>\d{4})")
RUSSIAN_TEXT_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\s+(?P<month>[А-Яа-яёЁ.\-]+)\s+(?P<year>\d{4})(?:\s*(?:г(?:\.|ода)?))?",
    flags=re.IGNORECASE,
)

# Подборка шаблонных заголовков, которые нужно игнорировать.
GENERIC_TITLE_STRINGS = {
    "подробнее",
    "читать кейс",
    "читать кейс полностью",
    "читать подробнее",
    "узнать больше",
}


def _iter_strings(value: object | None) -> Iterator[str]:
    """Выдаёт по очереди строковые значения из атрибутов BeautifulSoup."""

    if isinstance(value, str):
        yield value
    elif isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str):
                yield item


def _first_string(value: object | None) -> Optional[str]:
    """Возвращает первую строку из атрибута тега (если она есть)."""
    for item in _iter_strings(value):
        return item
    return None


def _clean_text(value: str) -> str:
    """Убирает неразрывные ошибки пробелов и мягкие переносы, нормализуя текст."""
    return (
        value.replace("\u00a0", " ")  # неразрывный пробел
        .replace("\u2009", " ")  # тонкий пробел
        .replace("\xad", "")  # мягкий перенос
        .strip()
    )


def _normalize_title_text(value: Optional[str]) -> Optional[str]:
    """Подчищает текст заголовка и отсеивает слишком общие формулировки."""
    if not value:
        return None
    text = _clean_text(value)
    if not text:
        return None
    if text.lower() in GENERIC_TITLE_STRINGS:
        return None
    return text


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Преобразует известные форматы дат в строку вида YYYY-MM-DD."""

    if not raw:
        return None

    value = _clean_text(raw)
    if not value:
        return None

    match = ISO_DATE_RE.search(value)
    if match:
        return "{year}-{month}-{day}".format(**match.groupdict())

    match = DOT_DATE_RE.search(value)
    if match:
        day = int(match.group("day"))
        month = int(match.group("month"))
        year = int(match.group("year"))
        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            return None

    match = RUSSIAN_TEXT_DATE_RE.search(value)
    if match:
        day = int(match.group("day"))
        month_name = _normalize_month_token(match.group("month"))
        month = MONTHS_RU.get(month_name)
        year = int(match.group("year"))
        if month:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def find_case_nodes(soup: BeautifulSoup) -> List[Tag]:
    """Находит подходящие контейнеры карточек кейсов по нескольким селекторам."""
    selectors = [
        '[data-testid="case-card"]',
        ".CaseCard",
        'a[href*="/cases/"]',
    ]
    for selector in selectors:
        nodes = soup.select(selector)
        if nodes:
            return nodes
    return []


def extract_title(container: Tag, link: Tag) -> Optional[str]:
    """Пытается достать заголовок кейса из разных мест карточки."""
    selectors = [
        '[data-testid="case-card-title"]',
        '[itemprop="headline"]',
        '[itemprop="name"]',
        '[class*="case-card_title"]',
        '[class*="CaseCard__title"]',
        ".CaseCard__title",
        ".vkuiHeadline",
        "h1",
        "h3",
        "h2",
    ]
    for selector in selectors:
        candidate = container.select_one(selector)
        if candidate:
            title = _normalize_title_text(candidate.get_text(" ", strip=True))
            if title:
                return title

    for attr in ("title", "aria-label", "aria-labelledby", "data-title"):
        title = _normalize_title_text(_first_string(link.get(attr)))
        if title:
            return title

    for candidate in container.find_all(True):
        if candidate.name == "button" or candidate.find_parent("button"):
            continue
        role = (_first_string(candidate.get("role")) or "").lower()
        if role == "button":
            continue
        class_tokens = " ".join(_iter_strings(candidate.get("class"))).lower()
        data_test_id = (_first_string(candidate.get("data-testid")) or "").lower()
        if (
            candidate.name in {"h1", "h2", "h3", "h4"}
            or "title" in class_tokens
            or "headline" in class_tokens
            or "title" in data_test_id
        ):
            title = _normalize_title_text(candidate.get_text(" ", strip=True))
            if title:
                return title

    return None


def iter_date_texts(container: Tag) -> Iterable[str]:
    """Генерирует все текстовые кандидаты на дату публикации из карточки."""
    for time_tag in container.find_all("time"):
        for datetime_attr in _iter_strings(time_tag.get("datetime")):
            stripped = _clean_text(datetime_attr)
            if stripped:
                yield stripped
        text = _clean_text(time_tag.get_text())
        if text:
            yield text
    for tag in container.find_all(True):
        attrs = " ".join(_iter_strings(tag.get("class"))).lower()
        data_test_id = (_first_string(tag.get("data-testid")) or "").lower()
        if "date" in attrs or "date" in data_test_id:
            text = _clean_text(tag.get_text())
            if text:
                yield text


def extract_date(container: Tag) -> Optional[str]:
    """Возвращает нормализованную дату публикации, если она найдена."""
    for value in iter_date_texts(container):
        normalized = normalize_date(value)
        if normalized:
            return normalized
    return None


def extract_cases(html: str, base_url: str = DEFAULT_BASE_URL) -> List[dict]:
    """Разбирает HTML-страницу и возвращает список словарей с данными кейсов."""
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_links = set()  # Не допускаем дубликаты ссылок

    for node in find_case_nodes(soup):
        if node.name == "a" and _first_string(node.get("href")):
            link_tag: Optional[Tag] = node
        else:
            link_tag = node.find("a", href=True)
        if not link_tag:
            continue

        href = _first_string(link_tag.get("href"))
        if not href:
            continue

        absolute_url = urljoin(base_url, href)
        if absolute_url in seen_links:
            continue

        title = extract_title(node, link_tag)
        if not title:
            continue

        published_at = extract_date(node)
        results.append(
            {
                "title": title,
                "url": absolute_url,
                "published_at": published_at,
            }
        )
        seen_links.add(absolute_url)

    return results


def persist_json_payload(payload: str, output_path: Path, *, echo: bool) -> None:
    """Записывает JSON на диск и при необходимости дублирует его в stdout."""

    output_dir = output_path.parent
    if output_dir and not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    output_path.write_text(payload, encoding="utf-8")
    if echo:
        print(payload)


def parse_args() -> argparse.Namespace:
    """Создаёт CLI-интерфейс и разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Parse VK Ads cases from a local HTML file or directly from the internet."
    )
    source_group = parser.add_mutually_exclusive_group()
    source_group.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT_PATH,
        metavar="PATH",
        help="Path to the saved HTML file (default: data/cases.html).",
    )
    source_group.add_argument(
        "--url",
        metavar="URL",
        help="URL to download the HTML page from.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Path to save the JSON result. When omitted, cases.json is created and the JSON is also printed."
        ),
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Base URL used to resolve relative links. Defaults to the source host or https://ads.vk.com.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_REQUEST_TIMEOUT,
        help=f"HTTP timeout in seconds when --url is used (default: {DEFAULT_REQUEST_TIMEOUT}).",
    )
    return parser.parse_args()


def main() -> None:
    """Точка входа скрипта: получение источника, парсинг и сохранение JSON."""
    args = parse_args()
    html, source_url = load_html_source(args.input, args.url, args.timeout)
    base_url = args.base_url or derive_base_url(source_url) or DEFAULT_BASE_URL
    cases = extract_cases(html, base_url=base_url)
    payload = json.dumps(cases, ensure_ascii=False, indent=2)

    output_path = args.output or DEFAULT_OUTPUT_PATH
    persist_json_payload(payload, output_path, echo=args.output is None)


if __name__ == "__main__":
    main()
