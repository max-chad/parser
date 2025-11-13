from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from parse_cases import (
    DEFAULT_OUTPUT_PATH,
    derive_base_url,
    extract_cases,
    fetch_html_from_url,
    load_html_source,
    normalize_date,
    persist_json_payload,
)


def test_normalize_date_iso():
    assert normalize_date("2024-03-01") == "2024-03-01"


def test_normalize_date_dot():
    assert normalize_date("17.12.2025") == "2025-12-17"


def test_normalize_date_russian_full():
    assert normalize_date("5 сентября 2024") == "2024-09-05"


def test_normalize_date_russian_abbreviation_with_suffix():
    assert normalize_date("12 сент. 2024 г.") == "2024-09-12"


def test_normalize_date_russian_year_word():
    assert normalize_date("8 февраля 2023 года") == "2023-02-08"


def test_normalize_date_slash():
    assert normalize_date("01/06/2022") == "2022-06-01"


def test_extract_cases_minimal_html():
    html = """
    <div data-testid="case-card">
        <a href="/cases/example-case" data-testid="case-card-title">
            <h3>Сборный кейс</h3>
        </a>
        <time datetime="2024-09-21">21 сентября 2024</time>
    </div>
    """

    cases = extract_cases(html)
    assert len(cases) == 1
    entry = cases[0]
    assert entry["title"] == "Сборный кейс"
    assert entry["url"] == "https://ads.vk.com/cases/example-case"
    assert entry["published_at"] == "2024-09-21"
    json.dumps(cases)


def test_derive_base_url_from_full_url():
    assert derive_base_url("https://ads.vk.com/cases/example") == "https://ads.vk.com"
    assert derive_base_url("not-a-url") is None
    assert derive_base_url(None) is None


def test_fetch_html_from_url(monkeypatch):
    captured = {}

    class DummyResponse:
        def __init__(self) -> None:
            self.encoding = None
            self.apparent_encoding = "utf-8"
            self.text = "<html></html>"

        def raise_for_status(self) -> None:
            return None

    def fake_get(url, timeout, headers):
        captured["url"] = url
        captured["timeout"] = timeout
        captured["headers"] = headers
        return DummyResponse()

    monkeypatch.setattr("parse_cases.requests.get", fake_get)
    html = fetch_html_from_url("https://example.com/cases", timeout=3.5)
    assert html == "<html></html>"
    assert captured["url"] == "https://example.com/cases"
    assert captured["timeout"] == 3.5
    assert "User-Agent" in captured["headers"]


def test_load_html_source_prefers_url(monkeypatch):
    captured = {}

    def fake_fetch(url, timeout, headers=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return "<html></html>"

    monkeypatch.setattr("parse_cases.fetch_html_from_url", fake_fetch)
    html, source_url = load_html_source(Path("data/cases.html"), "https://example.com", 4.0)
    assert html == "<html></html>"
    assert source_url == "https://example.com"
    assert captured["url"] == "https://example.com"
    assert captured["timeout"] == 4.0


def test_load_html_source_fallbacks_to_default_when_missing(monkeypatch):
    def fake_read_text(self, encoding):
        raise FileNotFoundError

    captured = {}

    def fake_fetch(url, timeout, headers=None):
        captured["url"] = url
        captured["timeout"] = timeout
        return "<html></html>"

    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)
    monkeypatch.setattr("parse_cases.fetch_html_from_url", fake_fetch)
    html, source_url = load_html_source(Path("data/cases.html"), None, 2.5)
    assert html == "<html></html>"
    assert source_url == "https://ads.vk.com/cases"
    assert captured["url"] == "https://ads.vk.com/cases"
    assert captured["timeout"] == 2.5


def test_load_html_source_missing_custom_file_propagates(monkeypatch):
    def fake_read_text(self, encoding):
        raise FileNotFoundError

    monkeypatch.setattr(Path, "read_text", fake_read_text, raising=False)
    with pytest.raises(FileNotFoundError):
        load_html_source(Path("custom.html"), None, 1.0)


def test_default_output_path_points_to_cases_json():
    assert DEFAULT_OUTPUT_PATH.name == "cases.json"


def test_persist_json_payload_writes_to_disk_and_prints(tmp_path, capsys):
    payload = '[{"title": "Case"}]'
    output_path = tmp_path / "results.json"
    persist_json_payload(payload, output_path, echo=True)

    assert output_path.read_text(encoding="utf-8") == payload
    captured = capsys.readouterr()
    assert captured.out.strip() == payload


def test_persist_json_payload_creates_parent_dirs(tmp_path, capsys):
    payload = '{"title": "Nested"}'
    nested_path = tmp_path / "exports" / "cases.json"
    persist_json_payload(payload, nested_path, echo=False)

    assert nested_path.exists()
    assert nested_path.read_text(encoding="utf-8") == payload
    captured = capsys.readouterr()
    assert captured.out == ""
