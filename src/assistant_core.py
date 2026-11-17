"""Asistente verificable de consultas deportivas en español, sin API de IA.

Es un enrutador de análisis estructurado (NO un LLM). Recupera datos de ESPN
y Covers, recuerda el jugador/fecha de la conversación local y distingue
frecuencias históricas de probabilidades futuras y cuotas de casa.
"""
from __future__ import annotations

from datetime import date, datetime
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .web_query import interpret_request, normalized
from .player_props import (
    PlayerSourceError, parse_player_question, resolve_player_in_games,
    fetch_roster, fetch_gamelog, parse_gamelog, summarize_prop,
)
from .brain_dashboard import load_today_snapshot, morning_covers_picks, load_backtest
from .parlay_research import build_reference_parlays
from .covers_public import fetch_public_picks, CoversSourceError
from .live_board import fetch_scoreboard, CalendarSourceError
from .match_report import relevant_matches
from .pick_reference import covers_projection
from .pick_context import match_espn_event

MX = ZoneInfo("America/Mexico_City")
_PROP_LABEL = {"PTS": "puntos", "REB": "rebotes",
               "AST": "asistencias", "3PM": "triples"}
_SPORTS = ("NBA", "NHL", "NFL")


def _trusted_sources(urls: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in urls:
        if not isinstance(value, str) or len(value) > 600:
            continue
        info = urlsplit(value)
        host = (info.hostname or "").lower()
        if info.scheme != "https" or not (host == "espn.com" or host.endswith(".espn.com")
                                           or host == "covers.com" or host.endswith(".covers.com")):
            continue
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result[:6]


def _is_explicit_date(text: str) -> bool:
    q = normalized(text)
    return bool(re.search(
        r"\b(?:hoy|manana|pasado manana|ayer|20\d{2}-\d{2}-\d{2}|"
        r"\d{1,2}/\d{1,2}/20\d{2}|\d{1,2}\s+de\s+"
        r"(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|"
        r"octubre|noviembre|diciembre))\b", q
    ))


def _adapt_followup(question: str, previous: dict) -> str:
    """Carry the last player's identity and stat, not any invented game facts."""
    q = normalized(question)
    previous_player = previous.get("player_name")
    if not previous_player:
        return question
    # Restrict context carryover to prop follow-ups. Do not append a player to
    # new unrelated matchup or parlay questions.
    if re.search(r"\b(?:parlay|parlays|combinadas?|bank|historial|mi apuesta)\b", q):
        return question
    if re.search(r"\b(?:vs|versus|contra|@)\b", q):
        return question
    if not re.search(r"\b(?:over|under|mas de|menos de|puntos?|pts|rebotes?|"
                     r"asistencias?|triples?|otra linea|y si)\b", q):
        return question
    if parse_player_question(question) is None:
        stat = previous.get("player_stat")
        if stat not in _PROP_LABEL:
            return question
        question += " " + _PROP_LABEL[stat]
    if normalized(previous_player) not in normalized(question):
        question += " de " + previous_player
    return question


def answer_query(
    question: str, *, context: dict | None = None, now: datetime | None = None,
    board_fetch=fetch_scoreboard, covers_fetch=fetch_public_picks,
    roster_fetch=fetch_roster, gamelog_fetch=fetch_gamelog,
    report_loader=load_today_snapshot, backtest_loader=load_backtest,
) -> dict:
    """Returns a text answer with traceable sources and conversation context."""
    context = dict(context or {})
    clock = now or datetime.now(MX)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=MX)
    clock = clock.astimezone(MX)
    message = str(question or "").strip()
    if not message:
        return {"reply": "Escríbeme qué partido, jugador o mercado quieres revisar.",
                "sources": [], "context": context}
    if len(message) > 1200:
        return {"reply": "La consulta es demasiado larga. Resume la apuesta en una frase.",
                "sources": [], "context": context}
    q = normalized(message)
    expanded = _adapt_followup(message, context)
    request = interpret_request(expanded, now=clock)
    target = request.target_date
    if not _is_explicit_date(expanded) and context.get("date_cdmx"):
        try:
            target = date.fromisoformat(context["date_cdmx"])
        except ValueError:
            target = request.target_date
    context["date_cdmx"] = target.isoformat()

    # Resultados históricos de REFERENCIAS públicas, nunca el historial privado.
    about_audit = bool(re.search(
        r"\b(?:acierto|aciertos|acertaron|pegaron|ganaron|perdieron|rendimiento|"
        r"resultados|roi|rentabilidad|retroceso|backtest)\b", q
    ) and re.search(r"\b(?:covers|picks?|pronosticos?|referencias?)\b", q)
        and not re.search(r"\b(?:mi historial|bank|mis apuestas)\b", q))
    if about_audit:
        audit = backtest_loader(clock.date())
        if audit is None:
            return {
                "reply": "Aún no tengo un reporte de auditoría de hoy. "
                         "La app guarda las referencias antes de los partidos "
                         "y comprueba sus resultados al día siguiente con ESPN. "
                         "No se calcularán aciertos con pronósticos obtenidos "
                         "después del resultado.",
                "sources": [], "context": context,
            }
        filtered = list(audit.get("grades", {}).values())
        # Al solicitar ayer/una fecha, mostrar exclusivamente esa fecha,
        # sin transformar la tasa global en la de una jornada concreta.
        if _is_explicit_date(message):
            filtered = [x for x in filtered if x.get("fecha") == target.isoformat()]
        filtered = [x for x in filtered if x.get("resultado") in ("ganado", "perdido")]
        if not filtered:
            return {
                "reply": "No hay referencias de Covers con resultado FINAL de ESPN "
                         "verificado para " +
                         (target.isoformat() if _is_explicit_date(message)
                          else "las jornadas archivadas") +
                         ". No se pueden presentar porcentajes todavía.",
                "sources": [], "context": context,
            }
        wins = sum(row["resultado"] == "ganado" for row in filtered)
        from decimal import Decimal
        profit = sum((Decimal(row["beneficio_unidad"]) for row in filtered),
                     Decimal("0"))
        n = len(filtered)
        pct = 100 * wins / n
        roi = 100 * profit / n
        return {
            "reply": (
                f"Auditoría de referencias de Covers: {n} encuentros "
                f"verificados por ID con resultado FINAL ESPN. "
                f"Ganadas {wins}; perdidas {n-wins}; "
                f"acierto observado {pct:.1f}%. "
                f"Resultado hipotético de 1 unidad por partido: "
                f"{profit:+.2f} unidades; ROI retrospectivo {roi:+.1f}%. "
                "NO son apuestas que hayas hecho, ni ganancias reales, "
                "ni la tasa de acierto futura del modelo. "
                "Las cuotas proceden de capturas Covers prepartido, "
                "no de una casa que garantice aceptarlas."
            ),
            "sources": _trusted_sources([
                row.get("fuente_espn_resultado", "") for row in filtered[-6:]
            ]),
            "context": context,
        }

    if re.search(r"\b(?:bank|historial|registrar|voy a meter|apostar)\b", q):
        return {
            "reply": "Para consultar el bank o guardar una apuesta abre «Mi historial» "
                     "e introduce tu clave privada. Escribe ahí «Voy a meter NBA, "
                     "partido: Lakers vs Warriors; pick: Lakers ML; momio: -110; con $100». "
                     "Te pedirá confirmación. No tengo acceso a tu saldo desde este chat "
                     "ni registraré apuestas automáticamente.",
            "sources": [], "context": context,
        }
    if re.search(r"\b(?:parlay|parlays|combinadas?|combinados?)\b", q):
        count_match = re.search(r"\b([23])\s*(?:parlays|combinadas?)\b", q)
        count = int(count_match.group(1)) if count_match else 3
        legs_match = re.search(r"\b(\d{1,2})\s*(?:picks|selecciones|piernas|legs)\b", q)
        legs = int(legs_match.group(1)) if legs_match else 3
        if legs > 30:
            return {"reply": "Puedo revisar como máximo 30 selecciones en un borrador. "
                             "Pide una combinación más corta.",
                    "sources": [], "context": context}
        report = report_loader(target)
        if report is None:
            return {"reply": "No tengo un informe del día verificable para esas combinadas. "
                             "No mezclaré cuotas viejas con encuentros nuevos. "
                             "Abre «Parlays» cuando aparezcan juegos futuros en Covers.",
                    "sources": [], "context": context}
        proposals = build_reference_parlays(
            report, count=count, legs_per_parlay=legs,
            more_than_ten=legs > 10, now=clock,
        )
        if not proposals:
            return {"reply": "No hay suficientes encuentros futuros con momios "
                             "Covers y equipos confirmados por ESPN para formar parlays.",
                    "sources": [], "context": context}
        lines = ["Estas son ALTERNATIVAS DE REFERENCIA, no parlays con EV validado:"]
        urls = []
        for proposal in proposals:
            lines.append(
                proposal["nombre"] + " (" + str(proposal["num_selecciones"]) +
                " selecciones): " +
                "; ".join(leg["seleccion"] + " " + leg["momio_covers"]
                          for leg in proposal["selecciones"]) +
                ". Producto matemático de momios: " +
                proposal["cuota_decimal_teorica"] + " decimal."
            )
            urls.extend(leg["fuente"] for leg in proposal["selecciones"])
        lines.append("Los momios pueden venir de distintas casas. "
                     "No es una cuota combinada ofrecida, ni está "
                     "verificada la independencia entre partidos. "
                     "Ve a la pestaña Parlays para discutirlos uno por uno.")
        return {"reply": "\n\n".join(lines), "sources": _trusted_sources(urls),
                "context": context}

    parsed = parse_player_question(expanded)
    if parsed is not None:
        if ("NHL" in request.sports or "NFL" in request.sports) and "NBA" not in request.sports:
            return {"reply": "De momento tengo historial individual de puntos, "
                             "rebotes, asistencias y triples para NBA. "
                             "En NFL/NHL no mostraré estadísticas NBA como si "
                             "correspondieran al deportista preguntado.",
                    "sources": [], "context": context}
        try:
            board = board_fetch("NBA", target)
        except (CalendarSourceError, ValueError, OSError):
            return {"reply": "ESPN no entregó el calendario NBA de esta fecha. "
                             "No puedo confirmar el jugador ni sus promedios.",
                    "sources": [], "context": context}
        player = None
        if context.get("player_name") and context.get("player_id") and (
                normalized(context["player_name"]) in normalized(expanded)):
            player = {
                "id": context["player_id"], "name": context["player_name"],
                "team_id": context.get("player_team_id") or "",
            }
        else:
            player = resolve_player_in_games(
                expanded, board["games"], roster_fetch=roster_fetch
            )
        if player is None:
            return {"reply": "No pude identificar al jugador de forma única "
                             "en las plantillas NBA de hoy. Dime su nombre "
                             "completo y, si es necesario, el equipo.",
                    "sources": [board.get("url", "")], "context": context}
        try:
            source = gamelog_fetch(player["id"], target)
            rows = parse_gamelog(source["payload"], parsed.stat, target)
        except (PlayerSourceError, OSError, ValueError, TypeError, KeyError):
            return {"reply": "ESPN no devolvió un historial individual verificable "
                             "para " + player["name"] + ". No calcularé "
                             "estadísticas de otro jugador.",
                    "sources": [], "context": context}
        if not rows:
            return {"reply": "No hay partidos de temporada regular previos "
                             "utilizables para " + player["name"] +
                             " en esta estadística.", "sources": [
                                 "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"]
                             ], "context": context}
        stats = summarize_prop(rows, parsed)
        label = _PROP_LABEL[parsed.stat]
        response = (
            player["name"] + " — " + label + ". " +
            "Promedio últimos 5: " + str(stats["last5"]) +
            "; últimos 10: " + str(stats["last10"]) +
            f". Partidos anteriores con dato: {stats['games']}."
        )
        if parsed.line is not None and parsed.direction:
            side = "Over" if parsed.direction == "over" else "Under"
            response += (
                f"\n\n{side} {parsed.line:g} {label}: "
                f"{stats['historical_hits']} aciertos en "
                f"{stats['historical_sample']} encuentros previos "
                f"({stats['historical_rate']}% descriptivo)."
                if stats["historical_rate"] is not None else
                "\n\nSin encuentros resolubles para esa línea."
            )
        else:
            response += ("\n\nPara evaluar un Over/Under necesito que indiques "
                         "la línea: «over 24.5 puntos» o «under 8.5 rebotes».")
        response += (
            "\n\nEsto es historial, NO probabilidad predictiva ni pick validado. "
            "ESPN no confirmó una cuota de apuesta para ese prop. "
            "Revisa también lesiones y disponibilidad antes de decidir."
        )
        context.update({
            "player_id": player["id"], "player_name": player["name"],
            "player_team_id": player.get("team_id", ""),
            "player_stat": parsed.stat,
            "sport": "NBA",
        })
        return {
            "reply": response,
            "sources": _trusted_sources([
                "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"],
                board.get("url", ""),
            ]),
            "context": context,
        }

    if re.search(r"\b(?:ayuda|que puedes hacer|como te pregunto)\b", q):
        return {
            "reply": "Prueba «Picks NBA hoy», «Analiza Charlotte vs Lakers», "
                     "«Over de 24.5 puntos de Luka Doncic NBA», "
                     "«Dame 3 parlays de 2 selecciones». "
                     "Solo presentaré datos verificables de Covers y ESPN. "
                     "Para registrar apuestas debes usar Mi historial.",
            "sources": [], "context": context,
        }

    # When asking only for picks, use the daily report for an instant reply.
    broad_picks = bool(re.search(r"\b(?:picks?|pronosticos?|selecciones)\b", q))
    has_matchup = bool(re.search(r"\b(?:vs|versus|contra|@)\b", q))
    if broad_picks and not has_matchup and target == clock.date():
        report = report_loader(target)
        if report:
            references = morning_covers_picks(report, now=clock, per_league=3)
            selected = [r for r in references if r["Liga"] in request.sports]
            if selected:
                lines = ["Referencias prepartido de Covers (no picks propios):"]
                for r in selected:
                    lines.append(
                        "- " + r["Liga"] + " · " + r["Partido"] +
                        " · " + r["Referencia ML (Covers)"] +
                        " a " + r["Momio publicado"] +
                        " · " + r["Hora CDMX"] + " CDMX"
                    )
                lines.append("Seleccionadas por diferencia de marcador, "
                             "NO por probabilidad de ganar. Precios capturados "
                             "por el informe, no momios en vivo.")
                return {"reply": "\n".join(lines), "sources": _trusted_sources(
                    [r["Fuente"] for r in selected]), "context": context}

    # For a specific matchup (including follow-ups), check Covers for that date.
    query = message
    if not has_matchup and context.get("matchup") and re.search(
        r"\b(?:momios?|total|spread|handicap|lesiones|de ese partido)\b", q
    ):
        query = context["matchup"]
    leagues = [s for s in request.sports if s in _SPORTS]
    if not leagues:
        leagues = list(_SPORTS)
    if context.get("sport") in _SPORTS and not re.search(
        r"\b(?:nba|nfl|nhl)\b", normalized(query)
    ):
        leagues = [context["sport"]]
    candidates = []
    errors = []
    for league in leagues:
        try:
            batch = covers_fetch(league, target)
            candidates.extend(batch.get("events", []))
        except (CoversSourceError, ValueError, OSError) as exc:
            errors.append(league + " (" + str(exc) + ")")
    exact, was_specific = relevant_matches(candidates, query)
    if not exact:
        return {"reply": (
            "No encontré un partido inequívoco en Covers para la fecha indicada. "
            "No voy a enseñarte un encuentro distinto al que pediste. "
            "Escribe ambos equipos y la liga."
            + (" Fuentes con fallos: " + ", ".join(errors) if errors else "")
        ), "sources": [], "context": context}
    game = exact[0]
    if was_specific and len(exact) > 1:
        return {"reply": "Encontré varios encuentros compatibles. Escribe ambos "
                         "equipos y la liga para no confundirme de partido.",
                "sources": [], "context": context}
    reference = covers_projection(game, now=clock)
    lines = [
        game["liga"] + " · " + game["partido"] + " · " +
        game["hora_cdmx"] + " CDMX."
    ]
    if reference:
        lines.append(
            "Marcador proyectado por Covers: " +
            reference["marcador_proyectado"] + " (visitante/local). "
            "Favorece a " + reference["equipo_proyectado"] + "."
        )
        if reference["momio_covers"]:
            lines.append(
                "Moneyline de referencia del equipo favorecido: " +
                reference["momio_covers"] + " publicado por Covers. "
                "No es cotización vigente confirmada de una casa."
            )
    else:
        lines.append("Sin marcador completo proyectado por Covers.")
    for label, value in (("Spread", game.get("spreads_publicados")),
                         ("Total", game.get("totales_publicados"))):
        if value:
            lines.append(label + " publicado: " + str(value))
    lines.append("Esto es una lectura de datos de terceros, NO un pick propio "
                 "con valor esperado validado.")
    context.update({"matchup": game["partido"], "sport": game["liga"]})
    return {"reply": "\n\n".join(lines),
            "sources": _trusted_sources([game.get("fuente", "")]),
            "context": context}
