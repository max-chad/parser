# VK Ads Case Parser

Small, typed CLI utility that extracts case studies from https://ads.vk.com/cases, normalizes their publish dates, and emits clean JSON that can be ingested by dashboards, CMSs, or internal tooling. Under the hood it relies on `requests` for fetching pages and BeautifulSoup for resilient HTML traversal.

## Features
- Always writes the parsed payload to `cases.json` (or a custom `--output` path) and mirrors it to stdout for piping.
- Parses saved HTML files or downloads the page on demand with retry-friendly headers and timeouts.
- Dedupe logic keyed by absolute case URLs to avoid duplicates across columns/sections.
- Smart Russian date normalizer that accepts ISO, dotted, slashed, and textual formats.
- Optional CLI flags for overriding base URLs, output paths, and HTTP timeouts.
- Comes with pytest coverage that mocks the network layer for deterministic runs.

## Requirements
- Python **3.10+**
- `pip` or any PEP-517 compatible installer

## Installation
```bash
python -m venv .venv
.venv\Scripts\activate          # On PowerShell; use source .venv/bin/activate on *nix
pip install -r requirements.txt   # or: pip install .[dev]
```

## Usage
### Parse a saved HTML dump
```bash
python parse_cases.py --input data/cases.html --output cases.json
```
If `--output` is omitted the JSON payload is still printed *and* written to `cases.json` in the current directory.

### Fetch straight from VK Ads
```bash
python parse_cases.py --url https://ads.vk.com/cases --timeout 15 --output custom.json
```
When `--input` is missing and no URL is supplied, the script automatically downloads https://ads.vk.com/cases and keeps working. The base URL is derived from the response host, so relative links always get resolved correctly.

### Example payload
```json
[
  {
    "title": "Сборный кейс",
    "url": "https://ads.vk.com/cases/example-case",
    "published_at": "2024-09-21"
  }
]
```

## Running the tests
```bash
pip install .[dev]
pytest
```

## Project layout
- parse_cases.py — CLI entry point plus all parsing helpers.
- tests/ — pytest suite covering parsing helpers and I/O fallbacks.
- requirements.txt / pyproject.toml — dependency declarations for pip and PEP-621 installers.
- LICENSE — MIT license.

## Publishing checklist
1. Update pyproject.toml with the desired version number.
2. Run pytest to make sure the parsing helpers still behave.
3. Build and upload (optional):
   ```bash
   pip install build twine
   python -m build
   python -m twine upload dist/*
   ```

## License
The project is distributed under the MIT License. See LICENSE for the full text.
