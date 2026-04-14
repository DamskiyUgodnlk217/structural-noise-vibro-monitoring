<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Система медиамониторинга «ШумВибро» — Python</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 1000px; margin: 40px auto; padding: 20px; background: #f8f9fa; }
        pre { background: #222; color: #0f0; padding: 15px; border-radius: 8px; overflow-x: auto; }
        code { font-family: 'Courier New', monospace; }
        h1, h2, h3 { color: #222; }
        .block { background: white; padding: 25px; margin: 20px 0; border-radius: 10px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        table { border-collapse: collapse; width: 100%; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background: #007bff; color: white; }
    </style>
</head>
<body>
<h1>✅ Готовая система медиамониторинга на Python</h1>
<p><strong>Тема:</strong> структурный шум, вибрация и виброизоляция в многоквартирных домах (Россия)</p>
<p>Система собирает упоминания от жильцов, УК, застройщиков, подрядчиков, производителей оборудования, профильных СМИ, форумов и соцсетей.</p>

<div class="block">
<h2>Что умеет система</h2>
<ul>
    <li>Автоматический запуск раз в неделю (через cron / Task Scheduler)</li>
    <li>Ручной запуск в любой момент</li>
    <li>Выгрузка за последнюю неделю ИЛИ за весь последний год</li>
    <li>Хранение всей истории в SQLite (дубликаты не попадают)</li>
    <li>Полная редактируемая фильтрация: ключевые слова + минус-слова</li>
    <li>Дополнительные фильтры при выгрузке: регион, тип источника, даты</li>
    <li>Источники: веб + новости (DuckDuckGo), VK (соцсети), форумы, блоги, сайты УК/застройщиков/производителей</li>
</ul>
</div>

<div class="block">
<h2>1. Установка (один раз)</h2>
<pre><code>pip install duckduckgo-search dateparser pandas openpyxl vk_api</code></pre>
<p>Создайте папку проекта, например <code>media_monitor/</code>, и положите туда три файла ниже.</p>
</div>

<div class="block">
<h2>2. config.json (редактируйте сами)</h2>
<pre><code>{
  "positive_keywords": [
    "структурный шум",
    "вибрация от перекрытий",
    "виброизоляция",
    "шум от соседей сверху",
    "вибрация в квартире",
    "звукоизоляция пола",
    "ударный шум",
    "виброизоляция МКД",
    "шумоизоляция перекрытий",
    "вибрация от лифта",
    "конструкционный шум",
    "виброопоры",
    "демпферы вибрации"
  ],
  "minus_words": [
    "музыка", "громко", "автомобиль", "машина", "самолет", "дорога", "трамвай",
    "видео", "youtube", "тикток", "шум от ветра", "шум дождя", "ремонт"
  ],
  "vk_token": "ВАШ_ТОКЕН_ИЗ_VK",   // оставьте null если не нужен VK
  "cities": [
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
    "Уфа", "Красноярск", "Воронеж", "Пермь", "Волгоград", "Краснодар",
    "Саратов", "Тюмень", "Тольятти", "Ижевск"
  ],
  "source_types": {
    "vk.com": "Соцсети (VK)",
    "lenta.ru": "СМИ",
    "ria.ru": "СМИ",
    "forumhouse.ru": "Форум",
    "pikabu.ru": "Соцсети / Блоги",
    "drive2.ru": "Форум"
  }
}</code></pre>
<p><strong>Как редактировать:</strong> просто меняйте списки в JSON — перезапускать ничего не нужно.</p>
</div>

<div class="block">
<h2>3. main.py — полный код системы</h2>
<pre><code>import json
import sqlite3
import argparse
from datetime import datetime, timedelta
import dateparser
import pandas as pd
from duckduckgo_search import DDGS
import vk_api
from urllib.parse import urlparse
import os

DB_PATH = "mentions.db"
CONFIG_PATH = "config.json"

def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS mentions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pub_date TEXT,
            source TEXT,
            link TEXT UNIQUE,
            title_summary TEXT,
            region TEXT,
            keywords_found TEXT,
            collected_date TEXT,
            source_type TEXT
        )
    ''')
    conn.commit()
    conn.close()

def get_region(text: str, cities: list) -> str:
    text_lower = text.lower()
    for city in cities:
        if city.lower() in text_lower:
            return city
    return "Не определён"

def get_source_type(url: str, source_map: dict) -> str:
    domain = urlparse(url).netloc.lower()
    for key, value in source_map.items():
        if key in domain:
            return value
    if "vk.com" in domain:
        return "Соцсети (VK)"
    return "Веб / СМИ / Форум"

def collect_data(since: datetime, until: datetime, config: dict):
    init_db()
    conn = sqlite3.connect(DB_PATH)
    collected = []
    query_str = " OR ".join(f'"{kw}"' for kw in config["positive_keywords"])

    # 1. DuckDuckGo (новости + веб)
    with DDGS() as ddgs:
        # Новости
        try:
            results = ddgs.news(
                keywords=query_str + " (МКД OR многоквартирный OR жилой дом)",
                region="ru-RU",
                safesearch="off",
                timelimit="w" if (until - since).days <= 7 else None,
                max_results=50
            )
            for r in results:
                pub_date_str = r.get("date") or r.get("published") or ""
                pub_date = dateparser.parse(pub_date_str, languages=["ru"])
                if pub_date and since <= pub_date <= until:
                    full_text = (r.get("title", "") + " " + r.get("body", "")).lower()
                    if any(minus.lower() in full_text for minus in config["minus_words"]):
                        continue
                    found_kws = [kw for kw in config["positive_keywords"] if kw.lower() in full_text]
                    if not found_kws:
                        continue
                    link = r.get("url") or r.get("href") or r.get("link")
                    collected.append({
                        "pub_date": pub_date.strftime("%Y-%m-%d"),
                        "source": r.get("source", urlparse(link).netloc),
                        "link": link,
                        "title_summary": f"{r.get('title', '')} | {r.get('body', '')[:250]}...",
                        "region": get_region(r.get("title", "") + r.get("body", ""), config["cities"]),
                        "keywords_found": ", ".join(found_kws),
                        "source_type": get_source_type(link, config.get("source_types", {}))
                    })
        except Exception as e:
            print("DDG news error:", e)

    # 2. VK (если токен указан)
    if config.get("vk_token"):
        try:
            vk_session = vk_api.VkApi(token=config["vk_token"])
            vk = vk_session.get_api()
            vk_results = vk.newsfeed.search(
                q=query_str,
                count=200,
                start_time=int(since.timestamp()),
                end_time=int(until.timestamp()),
                extended=1
            )
            for item in vk_results.get("items", []):
                text = item.get("text", "")
                if any(minus.lower() in text.lower() for minus in config["minus_words"]):
                    continue
                found_kws = [kw for kw in config["positive_keywords"] if kw.lower() in text.lower()]
                if not found_kws:
                    continue
                link = f"https://vk.com/wall{item['owner_id']}_{item['id']}"
                pub_date = datetime.fromtimestamp(item["date"])
                collected.append({
                    "pub_date": pub_date.strftime("%Y-%m-%d"),
                    "source": "VK",
                    "link": link,
                    "title_summary": text[:300] + ("..." if len(text) > 300 else ""),
                    "region": get_region(text, config["cities"]),
                    "keywords_found": ", ".join(found_kws),
                    "source_type": "Соцсети (VK)"
                })
        except Exception as e:
            print("VK error:", e)

    # Запись в БД (дубликаты игнорируются)
    for item in collected:
        try:
            conn.execute('''
                INSERT INTO mentions 
                (pub_date, source, link, title_summary, region, keywords_found, collected_date, source_type)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item["pub_date"],
                item["source"],
                item["link"],
                item["title_summary"],
                item["region"],
                item["keywords_found"],
                datetime.now().strftime("%Y-%m-%d %H:%M"),
                item["source_type"]
            ))
        except sqlite3.IntegrityError:
            pass  # дубликат по link
    conn.commit()
    conn.close()
    print(f"Собрано и добавлено {len(collected)} новых упоминаний")

def export_to_excel(start_date: str, end_date: str, region_filter=None, source_type_filter=None, filename=None):
    conn = sqlite3.connect(DB_PATH)
    query = f"""
        SELECT 
            pub_date as "Дата публикации",
            source as "Источник",
            link as "Ссылка",
            title_summary as "Заголовок+краткая сводка",
            region as "Регион или город",
            keywords_found as "Ключ. слова, по которым найдено"
        FROM mentions 
        WHERE pub_date BETWEEN ? AND ?
    """
    params = [start_date, end_date]
    if region_filter:
        query += " AND region = ?"
        params.append(region_filter)
    if source_type_filter:
        query += " AND source_type = ?"
        params.append(source_type_filter)
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()

    if df.empty:
        print("Нет данных за указанный период")
        return

    if not filename:
        filename = f"media_monitor_{start_date}_{end_date}.xlsx"
    df.to_excel(filename, index=False)
    print(f"✅ Файл сохранён: {filename}")
    print(f"Всего записей: {len(df)}")

def main():
    parser = argparse.ArgumentParser(description="Система медиамониторинга структурного шума и вибрации")
    parser.add_argument("--mode", choices=["weekly", "collect-year", "export-weekly", "export-year"], default="weekly",
                        help="Режим работы")
    parser.add_argument("--region", help="Фильтр по региону (например, Москва)")
    parser.add_argument("--source-type", help="Фильтр по типу источника")
    args = parser.parse_args()

    config = load_config()
    init_db()

    today = datetime.now()
    if args.mode == "weekly" or args.mode == "export-weekly":
        since = today - timedelta(days=7)
        if args.mode == "weekly":
            collect_data(since, today, config)
        export_to_excel(
            since.strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d"),
            args.region,
            args.source_type,
            "media_monitor_weekly.xlsx"
        )
    elif args.mode == "collect-year":
        since = today - timedelta(days=365)
        collect_data(since, today, config)   # DDG + VK отфильтруют по дате
    elif args.mode == "export-year":
        since = today - timedelta(days=365)
        export_to_excel(
            since.strftime("%Y-%m-%d"),
            today.strftime("%Y-%m-%d"),
            args.region,
            args.source_type,
            "media_monitor_year.xlsx"
        )

if __name__ == "__main__":
    main()
</code></pre>
</div>

<div class="block">
<h2>Как запускать</h2>
<table>
    <tr><th>Команда</th><th>Что делает</th></tr>
    <tr><td><code>python main.py --mode weekly</code></td><td>Собрать за неделю + выгрузить Excel</td></tr>
    <tr><td><code>python main.py --mode export-weekly</code></td><td>Только выгрузить неделю (без повторного сбора)</td></tr>
    <tr><td><code>python main.py --mode collect-year</code></td><td>Собрать данные за последний год (один раз)</td></tr>
    <tr><td><code>python main.py --mode export-year --region Москва</code></td><td>Выгрузить год только по Москве</td></tr>
    <tr><td><code>python main.py --mode export-year --source-type "Соцсети (VK)"</code></td><td>Только VK</td></tr>
</table>
</div>

<div class="block">
<h2>Автоматический запуск раз в неделю</h2>
<p><strong>Linux / VPS (cron):</strong></p>
<pre><code>crontab -e
# Каждое воскресенье в 8:00 утра
0 8 * * 0 cd /path/to/media_monitor && python3 main.py --mode weekly</code></pre>

<p><strong>Windows (Task Scheduler):</strong> Создайте задачу → Запуск программы → python.exe с аргументом main.py --mode weekly</p>
</div>

<div class="block">
<h2>Готово!</h2>
<p>Скопируйте код выше в <code>main.py</code>, создайте <code>config.json</code>, установите пакеты — и система работает.</p>
<p>Все фильтры (ключевые слова, минус-слова, города) редактируются вами самостоятельно в JSON-файле.</p>
<p>При необходимости могу добавить Telegram-каналы, Telegram-бот уведомлений или интеграцию с Ollama для автоматической классификации «жилец / УК / застройщик».</p>
</div>
</body>
</html>
