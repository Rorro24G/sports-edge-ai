"""Recent headlines and on-demand parlay data; no fabricated fallback content."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import json
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .live_board import SPORT_PATH, fetch_scoreboard
from .covers_public import fetch_public_picks
from .daily_picks import build_report


class NewsError(RuntimeError):
    pass


def normalize_news(payload, *, now=None):
    clock = now or datetime.now(timezone.utc)
    articles = payload.get("articles") if isinstance(payload, dict) else None
    if not isinstance(articles, list):
        raise NewsError("La respuesta de noticias no es válida.")
    rows, seen = [], set()
    for article in articles[:50]:
        if not isinstance(article, dict):
            continue
        try:
            headline = article["headline"].strip()
            url = article["links"]["web"]["href"]
            stamp = datetime.fromisoformat(article["published"].replace("Z", "+00:00"))
            host = urlsplit(url)
            if (not headline or stamp.tzinfo is None or stamp > clock
                    or clock - stamp > timedelta(hours=72)
                    or host.scheme != "https" or host.username or host.password
                    or not (host.hostname == "espn.com" or (host.hostname or "").endswith(".espn.com"))
                    or url in seen):
                continue
        except (KeyError, TypeError, ValueError, AttributeError):
            continue
        seen.add(url)
        rows.append({"headline": headline[:240], "url": url,
                     "published_utc": stamp.astimezone(timezone.utc).isoformat()})
    return sorted(rows, key=lambda r: r["published_utc"], reverse=True)[:12]


def fetch_news(league):
    if league not in SPORT_PATH:
        raise ValueError("Liga no compatible")
    category, sport = SPORT_PATH[league]
    url = f"https://site.api.espn.com/apis/site/v2/sports/{category}/{sport}/news?limit=30"
    try:
        with urlopen(Request(url, headers={"User-Agent": "SportsEdgeAI/1.0", "Accept": "application/json"}), timeout=10) as response:
            raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise NewsError("Respuesta demasiado grande.")
        rows = normalize_news(json.loads(raw))
    except (OSError, ValueError) as exc:
        raise NewsError("No se pudieron actualizar las noticias. Intenta nuevamente.") from exc
    return {"articles": rows, "checked_at_utc": datetime.now(timezone.utc).isoformat()}


def live_parlay_report(day, *, covers_fetch=fetch_public_picks, board_fetch=fetch_scoreboard):
    # Fetch the six independent requests concurrently; no per-game summary calls
    # and no paid odds requests just to populate the tab.
    def read(job):
        kind, league = job
        try:
            return (kind, league), (covers_fetch if kind == "picks" else board_fetch)(league, day)
        except (OSError, ValueError, RuntimeError) as exc:
            return (kind, league), exc
    with ThreadPoolExecutor(max_workers=6) as pool:
        responses = dict(pool.map(read, [(kind, league) for league in SPORT_PATH for kind in ("picks", "board")]))
    def cached(kind, league):
        value = responses[kind, league]
        if isinstance(value, Exception):
            raise OSError("Consulta no disponible") from value
        return value
    return build_report(day, covers_fetch=lambda league, _: cached("picks", league),
                        board_fetch=lambda league, _: cached("board", league),
                        summary_fetch=lambda *args: {})
