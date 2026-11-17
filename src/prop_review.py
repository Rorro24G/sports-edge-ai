"""Explain NBA prop risks from verifiable facts, never infer expected value."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .player_props import PlayerQuestion, summarize_prop

LOCAL = ZoneInfo("America/Mexico_City")


def matching_player_game(player: dict, games: list[dict],
                         target: date) -> dict | None:
    """Unique scheduled game containing the ESPN roster team ID."""
    team_id = str(player.get("team_id") or "")
    if not team_id:
        return None
    possible = [
        g for g in games if g.get("sport") == "NBA"
        and team_id in (str(g.get("away_team_id") or ""),
                        str(g.get("home_team_id") or ""))
        and str(g.get("local_date")) == target.isoformat()
    ]
    return possible[0] if len(possible) == 1 else None


def player_prop_review(player: dict, history: list[dict],
                       question: PlayerQuestion, *,
                       game: dict | None, offers: list[dict] | None = None,
                       now: datetime | None = None) -> dict:
    """No unsupported recommendation, even with excellent past hit rate."""
    stats = summarize_prop(history, question)
    risks = []
    quotes = offers or []
    sample = min(len(history), 10)
    if sample < 5:
        risks.append("Muestra inferior a 5 partidos anteriores; insuficiente para una tendencia sólida.")
    if player.get("injuries"):
        risks.append("ESPN publica reportes de lesión para este jugador; revisa su disponibilidad.")
    if not player.get("injuries"):
        risks.append("Sin lesión reportada en esta consulta de plantilla; no confirma disponibilidad ni minutos.")
    status = str(player.get("status") or "").strip()
    if status and status.lower() not in ("active", "activo"):
        risks.append("Estado de plantilla ESPN: " + status + "; no confirma que vaya a jugar.")
    if game is None:
        risks.append("No hay un encuentro NBA único asociado al equipo del jugador para esta fecha.")
    else:
        if game.get("status") in ("POST", "FINAL", "IN", "LIVE"):
            risks.append("Encuentro empezado o terminado; el análisis no es una apuesta prepartido.")
        if not game.get("local_time"):
            risks.append("Hora del partido no contrastada.")
    if question.line is None or question.direction is None:
        risks.append("Falta una línea de Over/Under concreta para comparar.")
    if not quotes:
        risks.append("Sin cotización americana vigente y verificable para el mercado exacto.")
    risks.append(
        "La frecuencia de los últimos encuentros es descriptiva, no una probabilidad "
        "futura calibrada; faltan ajuste por rival, minutos y lesiones."
    )
    return {
        "player_name": player.get("name", ""),
        "stat": question.stat,
        "line": question.line,
        "direction": question.direction,
        "games": stats["games"],
        "last5": stats["last5"],
        "last10": stats["last10"],
        "historical_hits": stats.get("historical_hits"),
        "historical_sample": stats.get("historical_sample"),
        "historical_rate": stats.get("historical_rate"),
        "risk_flags": risks,
        "game": game,
        "offers": quotes,
        "model_probability": None,
        "expected_value": None,
        "recommendation": None,
        "reason_unvalidated": "Sin modelo predictivo validado por resultados fuera de muestra.",
    }

