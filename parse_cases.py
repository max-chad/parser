from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

MONTHS_RU = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

ISO_DATE_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})")
DOT_DATE_RE = re.compile(r"^(?P<day>\d{1,2})[./](?P<month>\d{1,2})[./](?P<year>\d{4})")
RUSSIAN_TEXT_DATE_RE = re.compile(
    r"^(?P<day>\d{1,2})\s+(?P<month>[а-яА-Я]+)\s+(?P<year>\d{4})",
    flags=re.IGNORECASE,
)


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """Convert known date formats to YYYY-MM-DD."""

    if not raw:
        return None

    value = raw.strip()
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
        month_name = match.group("month").lower()
        month = MONTHS_RU.get(month_name)
        year = int(match.group("year"))
        if month:
            try:
                return datetime(year, month, day).strftime("%Y-%m-%d")
            except ValueError:
                return None
    return None


def find_case_nodes(soup: BeautifulSoup) -> List[Tag]:
    selectors = [
        '[data-testid="case-card"]',
        '.CaseCard',
        'a[href*="/cases/"]',
    ]
    for selector in selectors:
        nodes = soup.select(selector)
        if nodes:
            return nodes
    return []


def extract_title(container: Tag, link: Tag) -> Optional[str]:
    selectors = [
        '[data-testid="case-card-title"]',
        '.CaseCard__title',
        '.vkuiHeadline',
        'h3',
        'h2',
        'span',
        'div',
    ]
    for selector in selectors:
        candidate = container.select_one(selector)
        if candidate and candidate.get_text(strip=True):
            return candidate.get_text(strip=True)
    text = link.get_text(" ", strip=True)
    return text or None


def iter_date_texts(container: Tag) -> Iterable[str]:
    for time_tag in container.find_all("time"):
        datetime_attr = time_tag.get("datetime")
        if datetime_attr:
            yield datetime_attr
        text = time_tag.get_text(strip=True)
        if text:
            yield text
    for tag in container.find_all(True):
        if tag is None:
            continue
        attrs = " ".join(tag.get("class", []))
        data_test_id = tag.get("data-testid", "")
        if "date" in attrs.lower() or "date" in data_test_id.lower():
            text = tag.get_text(strip=True)
            if text:
                yield text


def extract_date(container: Tag) -> Optional[str]:
    for value in iter_date_texts(container):
        normalized = normalize_date(value)
        if normalized:
            return normalized
    return None


def extract_cases(html: str, base_url: str = "https://ads.vk.com") -> List[dict]:
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen_links = set()

    for node in find_case_nodes(soup):
        link_tag: Optional[Tag]
        if node.name == "a" and node.get("href"):
            link_tag = node
        else:
            link_tag = node.find("a", href=True)
        if not link_tag:
            continue

        href = link_tag.get("href")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse VK Ads cases from a saved HTML page."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/cases.html"),
        help="Path to the saved HTML file (default: data/cases.html)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the JSON result. If omitted, the JSON is printed.",
    )
    parser.add_argument(
        "--base-url",
        default="https://ads.vk.com",
        help="Base URL used to resolve relative links.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    html = args.input.read_text(encoding="utf-8")
    cases = extract_cases(html, base_url=args.base_url)
    payload = json.dumps(cases, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
