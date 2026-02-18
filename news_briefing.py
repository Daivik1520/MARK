"""
MARK — News Briefing Engine
Fetches top headlines using NewsAPI, weather from wttr.in, and combines
with pending reminders for a comprehensive morning briefing.
"""

import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

NEWSAPI_URL = "https://newsapi.org/v2/top-headlines"
WEATHER_URL = "https://wttr.in/{}?format=j1"


def _get_api_key():
    return os.environ.get("NEWSAPI_KEY", "")


def get_news_briefing(topic=""):
    """Get a comprehensive briefing: top news, weather, and reminders."""
    sections = []
    now = datetime.now()
    greeting = "Good morning" if now.hour < 12 else "Good afternoon" if now.hour < 17 else "Good evening"
    sections.append("📰 {} Briefing — {}".format(greeting, now.strftime("%A, %B %d")))
    sections.append("═" * 40)

    # ── News ──
    news = _fetch_news(topic)
    if news:
        sections.append("\n🗞️ TOP HEADLINES" + (" — " + topic if topic else ""))
        sections.append("─" * 30)
        for i, article in enumerate(news[:8], 1):
            title = article.get("title", "").split(" - ")[0]  # Remove source suffix
            source = article.get("source", {}).get("name", "")
            sections.append("{}. {} [{}]".format(i, title, source))
    else:
        sections.append("\n🗞️ NEWS: Could not fetch headlines." +
                       (" Set NEWSAPI_KEY env var." if not _get_api_key() else ""))

    # ── Weather ──
    weather = _fetch_weather()
    if weather:
        sections.append("\n🌤️ WEATHER")
        sections.append("─" * 30)
        sections.append(weather)

    # ── Reminders ──
    reminders = _get_pending_reminders()
    if reminders:
        sections.append("\n⏰ PENDING REMINDERS")
        sections.append("─" * 30)
        for r in reminders[:5]:
            sections.append("• {} (at {})".format(r["message"], r["time"]))

    sections.append("\n" + "═" * 40)
    return "\n".join(sections)


def get_news(topic="general", count="5"):
    """Get just the news headlines for a specific topic."""
    n = int(count) if str(count).isdigit() else 5
    articles = _fetch_news(topic)
    if not articles:
        return "Could not fetch news." + (" Set NEWSAPI_KEY." if not _get_api_key() else "")
    lines = ["📰 News: {} ({} articles)".format(topic or "Top Headlines", min(n, len(articles))),
             "─" * 30]
    for i, a in enumerate(articles[:n], 1):
        title = a.get("title", "").split(" - ")[0]
        source = a.get("source", {}).get("name", "")
        desc = (a.get("description") or "")[:100]
        lines.append("{}. {} [{}]".format(i, title, source))
        if desc:
            lines.append("   {}".format(desc))
    return "\n".join(lines)


def _fetch_news(topic=""):
    """Fetch headlines from NewsAPI."""
    key = _get_api_key()
    if not key:
        return _fetch_news_fallback(topic)
    try:
        params = {
            "apiKey": key,
            "language": "en",
            "pageSize": 10,
        }
        if topic and topic.lower() not in ("general", "top", "headlines", ""):
            params["q"] = topic
            url = "https://newsapi.org/v2/everything"
        else:
            params["country"] = "us"
            url = NEWSAPI_URL
        r = requests.get(url, params=params, timeout=8)
        data = r.json()
        return data.get("articles", [])
    except Exception:
        return _fetch_news_fallback(topic)


def _fetch_news_fallback(topic=""):
    """Fallback: use free RSS-to-JSON for news when no API key."""
    try:
        feed_url = "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en"
        if topic:
            feed_url = "https://news.google.com/rss/search?q={}&hl=en-US".format(topic)
        r = requests.get(
            "https://api.rss2json.com/v1/api.json",
            params={"rss_url": feed_url, "count": 10},
            timeout=8
        )
        data = r.json()
        items = data.get("items", [])
        return [{"title": i["title"], "source": {"name": i.get("author", "Google News")},
                 "description": i.get("description", "")[:150]} for i in items]
    except Exception:
        return []


def _fetch_weather(city="auto"):
    """Fetch weather from wttr.in (auto-detects location by IP)."""
    try:
        url = "https://wttr.in/{}?format=%l:+%c+%t+%h+humidity,+%w+wind".format(
            "" if city == "auto" else city
        )
        r = requests.get(url, timeout=5, headers={"User-Agent": "MARK/1.0"})
        if r.status_code == 200:
            return r.text.strip()
    except Exception:
        pass
    return None


def _get_pending_reminders():
    """Read pending reminders from reminders.json."""
    try:
        rfile = os.path.join(os.path.dirname(__file__), "reminders.json")
        if os.path.exists(rfile):
            with open(rfile, "r") as f:
                reminders = json.load(f)
            return [r for r in reminders if not r.get("fired", False)]
    except Exception:
        pass
    return []
