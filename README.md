# VK Ads Case Parser

Этот проект демонстрирует, как с помощью библиотеки [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/) извлечь данные из сохранённой HTML-страницы с кейсами рекламы VK. Скрипт считывает локальный файл, находит карточки бизнес-кейсов и преобразует информацию в удобную структуру данных Python.

## Структура проекта

- `data/cases.html` — сохранённый HTML-файл страницы кейсов.
- `parse_cases.py` — скрипт для извлечения информации о кейсах.
- `requirements.txt` — список зависимостей проекта.
- `.gitignore` — исключает временные файлы и виртуальные окружения из Git.

## Установка

1. Создайте и активируйте виртуальное окружение (по желанию):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # для Windows используйте .venv\Scripts\activate
   ```
2. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```

## Запуск

По умолчанию скрипт ожидает, что файл `data/cases.html` находится в корне репозитория. Запустите его следующей командой:

```bash
python parse_cases.py
```

Параметры командной строки:

- `--input` — путь к сохранённому HTML-файлу (по умолчанию `data/cases.html`).
- `--output` — путь для сохранения результата в JSON-файл. Если параметр не указан, результат выводится в stdout.
- `--base-url` — базовый URL для формирования абсолютных ссылок (по умолчанию `https://ads.vk.com`).

Пример записи результата в файл:

```bash
python parse_cases.py --output cases.json
```

## Пример вывода

```json
[
  {
    "title": "Selgros: промо с лид-формами",
    "url": "https://ads.vk.com/cases/selgros-promo",
    "published_at": "2024-08-20"
  },
  {
    "title": "Foodfox: увеличение продаж на доставку",
    "url": "https://ads.vk.com/cases/foodfox-performance",
    "published_at": "2023-11-15"
  },
  {
    "title": "TechBrand: узнаваемость нового продукта",
    "url": "https://ads.vk.com/cases/techbrand-awareness",
    "published_at": "2022-07-05"
  }
]
```

## Лицензия

Проект распространяется по лицензии MIT. См. файл [LICENSE](LICENSE) (при необходимости).
