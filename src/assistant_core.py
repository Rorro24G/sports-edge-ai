"""Asistente verificable de consultas deportivas en español, sin API de IA.

Es un enrutador de análisis estructurado (NO un LLM). Recupera datos de ESPN
y Covers, recuerda el jugador/fecha de la conversación local y distingue
frecuencias históricas de probabilidades futuras y cuotas de casa.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .web_query import interpret_request, normalized
from .prop_review import matching_player_game, player_prop_review
from .odds_api import OddsAPIError
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
from .team_form import fetch_team_schedule
from .independent_picks import build_slate, evaluate_game, add_covers_price
from .picks_feed import live_picks_catalog
from .model_audit_ui import load_model_audits

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
        repo_audit = (
            host == "github.com" and re.fullmatch(
                r"/Rorro24G/sports-edge-ai/actions/runs/\d+/?", info.path
            ) and not info.query and not info.fragment
        )
        if info.scheme != "https" or not (
            host == "espn.com" or host.endswith(".espn.com")
            or host == "covers.com" or host.endswith(".covers.com")
            or repo_audit
        ):
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
    # Only a short, unambiguous follow-up inherits the complete market.
    risk_followup = re.fullmatch(
        r"(?:y )?(?:(?:las?|los?|su|sus|que) )?"
        r"(?:lesiones?|riesgos?|disponibilidad|esta lesionado|va a jugar)"
        r"[?¿! .]*", q.lstrip("¿ ")
    )
    if risk_followup and previous.get("player_stat") in _PROP_LABEL:
        market = _PROP_LABEL[previous["player_stat"]]
        if previous.get("player_direction") in ("over", "under") and previous.get("player_line") is not None:
            market = f"{previous['player_direction']} {previous['player_line']} {market}"
        return market + " de " + previous_player + " NBA"
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
    team_fetch=fetch_team_schedule,
    report_loader=load_today_snapshot, backtest_loader=load_backtest,
    prop_odds_fetch=None, prop_api_key: str = "",
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
    if re.search(r"\bayer\b", q):
        target = clock.date() - timedelta(days=1)
    if not _is_explicit_date(expanded) and context.get("date_cdmx"):
        try:
            target = date.fromisoformat(context["date_cdmx"])
        except ValueError:
            target = request.target_date
    context["date_cdmx"] = target.isoformat()

    # Answer about OUR model from recorded ESPN walk-forward audits, not from
    # the Covers reference backtest or any implied market odds.
    asks_model_accuracy = bool(
        re.search(r"\b(?:aciertos?|acerto|acertaron|acertamos|pegaron|ganaron|resultados?|"
                  r"rendimiento|desempeno|brier|calibracion|pruebas?|"
                  r"backtest|efectividad|fiable|confiable)\b", q)
        and re.search(r"\b(?:cerebro|seai|sports edge|modelo|"
                      r"picks? propios?|tus picks?|sus picks?)\b", q)
        and not re.search(r"\b(?:mi historial|mis apuestas|bank)\b", q)
    )
    if asks_model_accuracy:
        reports = load_model_audits()
        requested = [
            sport for sport in ("NBA", "NFL", "NHL")
            if re.search(r"\b" + sport.lower() + r"\b", q)
        ]
        if requested:
            reports = [r for r in reports if r["sport"] in requested]
        if not reports:
            return {
                "reply": "No hay auditoría histórica verificable de esta "
                         "versión del cerebro para la liga solicitada.",
                "sources": [], "context": context,
            }
        lines = [
            "Resultados históricos del modelo propio Sports Edge AI "
            "(prueba ESPN anterior a cada partido, sin usar Covers para decidir):"
        ]
        for report in reports:
            count = report["candidate_count"]
            rate = (f"{report['candidate_accuracy_observed']:.1%}"
                    if count else "sin selecciones")
            lines.append(
                "- " + report["sport"] + " " + report["period"]["end"][:4] +
                ": " + str(report["correct_candidates"]) + "/" + str(count) +
                " selecciones acertadas (" + rate + ") de " +
                str(report["evaluated_count"]) + " partidos evaluados; Brier " +
                f"{report['brier_all_evaluated']:.3f}."
            )
        lines.append(
            "Brier 0.250 equivale a una estimación constante de 50/50. "
            "NFL tiene muestras limitadas y NHL varía entre temporadas. "
            "El modelo NO está calibrado para producción y no existe "
            "un ROI histórico verificable con momios a la misma hora."
        )
        urls = [r.get("audit_run_url", "") for r in reports]
        return {
            "reply": "\n".join(lines),
            "sources": _trusted_sources(urls), "context": context,
        }

    # Resultados históricos de REFERENCIAS públicas, nunca el historial privado.
    about_audit = bool(re.search(
        r"\b(?:acierto|aciertos|acertaron|pegaron|ganaron|perdieron|rendimiento|"
        r"resultados|roi|rentabilidad|retroceso|backtest)\b", q
    ) and re.search(r"\b(?:covers|referencias?)\b", q)
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
                f"Auditoría de referencias de Covers: {n} " +
                ("encuentro " if n == 1 else "encuentros ") +
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
        # Session memory identifies the subject, never current availability.
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
        matchup = matching_player_game(player, board["games"], target)
        offers = []
        if (prop_api_key and prop_odds_fetch and matchup
                and parsed.line is not None and parsed.direction):
            try:
                offers = prop_odds_fetch(
                    prop_api_key, matchup, target, player["name"],
                    parsed.stat, parsed.direction, parsed.line,
                )
            except (OddsAPIError, ValueError, TypeError, OSError):
                offers = []
        review = player_prop_review(player, rows, parsed,
                                    game=matchup, offers=offers, now=clock)
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
        response += "\n\nConsulta del historial ESPN: " + str(source.get("checked_at_utc") or "hora no disponible") + "."
        if matchup:
            response += (
                "\n\nPartido ESPN: " + matchup["away"] + " @ " + matchup["home"]
                + " · " + str(matchup.get("local_time") or "hora no confirmada")
                + " CDMX."
            )
        if offers:
            price = offers[0]
            response += ("\n\nPrecio publicado para exactamente esta línea: " +
                         price["casa"] + " " + str(price["momio_americano"]) +
                         " (actualizado " + price["actualizado_utc"] + " UTC). "
                         "Sujeto a cambios; confirma en la casa.")
        response += ("\n\nFactores a revisar:\n" +
                     "\n".join("• " + flag for flag in review["risk_flags"]))
        response += (
            "\n\nEsto es historial, NO probabilidad predictiva ni pick validado. "
            "ESPN no confirmó una cuota de apuesta para ese prop. "
            "Revisa también lesiones y disponibilidad antes de decidir."
        )
        context.update({
            "player_id": player["id"], "player_name": player["name"],
            "player_team_id": player.get("team_id", ""),
            "player_injuries": player.get("injuries") or [],
            "player_status": player.get("status"),
            "player_stat": parsed.stat,
            "player_line": parsed.line,
            "player_direction": parsed.direction,
            "sport": "NBA",
        })
        return {
            "reply": response,
            "sources": _trusted_sources([
                "https://www.espn.com/nba/player/gamelog/_/id/" + player["id"],
                board.get("url", ""),
                "https://www.covers.com/sport/basketball/nba/player-props",
            ]),
            "context": context,
        }

    if re.search(r"\b(?:ayuda|que puedes hacer|como te pregunto)\b", q):
        return {
            "reply": "Prueba «Picks NBA hoy», «Analiza Charlotte vs Lakers», "
                     "«Over de 24.5 puntos de Luka Doncic NBA», "
                     "«Dame 3 parlays de 2 selecciones». "
                     "Mis selecciones propias se basan en históricos ESPN; Covers da los momios. "
                     "Para registrar apuestas debes usar Mi historial.",
            "sources": [], "context": context,
        }

    # Sports Edge AI owns its picks: historical ESPN -> independent model;
    # Covers is consulted only AFTER the team is selected, for optional prices.
    broad_picks = bool(re.search(r"\b(?:picks?|pronosticos?|selecciones)\b", q))
    has_matchup = bool(re.search(r"\b(?:vs|versus|contra|@)\b", q))
    if broad_picks and not has_matchup:
        leagues = [x for x in request.sports if x in _SPORTS]
        if not leagues:
            leagues = list(_SPORTS)
        boards, prices = {}, []
        for league in leagues:
            try:
                boards[league] = board_fetch(league, target)["games"]
            except (CalendarSourceError, OSError, KeyError, ValueError):
                boards[league] = []
            try:
                prices.extend(covers_fetch(league, target).get("events", []))
            except (CoversSourceError, OSError, ValueError):
                continue
        slate = build_slate(
            boards, target, team_fetch=team_fetch,
            covers_events=prices, now=clock, per_league=5,
        )
        picks = slate["picks"]
        if not picks:
            return {"reply": (
                "Sports Edge AI no encontró una selección propia suficientemente "
                "definida para esa jornada. "
                "Puede faltar historial ESPN, no haber juegos por empezar o "
                "resultar demasiado equilibrados. "
                "No elijo al favorito de Covers para rellenar la lista."
                ), "sources": [], "context": context}
        lines = [
            "Selecciones experimentales del cerebro Sports Edge AI "
            "(modelo propio basado en resultados previos de ESPN):"
        ]
        urls = []
        for item in picks:
            price = (" · Momio publicado por Covers " + item["market_price"]
                     if item.get("market_price") else " · sin momio verificable")
            lines.append(
                "- " + item["sport"] + " · " + item["away"] + " vs " +
                item["home"] + " · " + item["team"] + " ML · estimación "
                f"{item['probability_experimental']:.1%}" +
                price + " · " + item["time"] + " CDMX"
            )
            urls.extend([item.get("espn_url"), item.get("market_source")])
        lines.append(
            "El ganador lo decide SEAI con varias comprobaciones: historial, "
            "últimos cinco partidos, valores extremos, localía y sensibilidad. "
            "Si aparecen señales contradictorias, descarta el juego. "
            "Modelo NO calibrado ni validado fuera de muestra; "
            "sin apuestas ni importe recomendado."
        )
        return {"reply": "\n".join(lines),
                "sources": _trusted_sources([x for x in urls if x]), "context": context}

    # A specific matchup is found in ESPN too; a Covers pick is NEVER the
    # substitute for the model decision.
    query = message
    if not has_matchup and context.get("matchup") and re.search(
        r"\b(?:momios?|total|spread|handicap|lesiones|de ese partido)\b", q
    ):
        query = context["matchup"]
    leagues = [x for x in request.sports if x in _SPORTS]
    if not leagues:
        leagues = list(_SPORTS)
    if context.get("sport") in _SPORTS and not re.search(
        r"\b(?:nba|nfl|nhl)\b", normalized(query)
    ):
        leagues = [context["sport"]]

    external, boards, errors = [], {}, []
    for league in leagues:
        try:
            boards[league] = board_fetch(league, target)["games"]
        except (CalendarSourceError, OSError, ValueError, KeyError):
            boards[league] = []
        try:
            external.extend(covers_fetch(league, target).get("events", []))
        except (CoversSourceError, OSError, ValueError):
            errors.append(league)
    events = live_picks_catalog(external, boards, target)
    exact, was_specific = relevant_matches(events, query)
    if not exact:
        return {"reply": (
            "No encontré un partido inequívoco en ESPN/Covers para la fecha indicada. "
            "Escribe ambos equipos y la liga para ubicar el juego exacto."
            ), "sources": [], "context": context}
    if was_specific and len(exact) > 1:
        return {"reply": "Encontré varios encuentros compatibles. Escribe ambos "
                         "equipos y la liga para no confundirme de partido.",
                "sources": [], "context": context}

    game = exact[0]
    verified = next((
        row for row in boards.get(game["liga"], [])
        if str(row.get("event_id")) == str(game.get("espn_event_id"))
    ), None)
    if verified is None:
        verified = match_espn_event(game, boards.get(game["liga"], []))
    lines = [game["liga"] + " · " + game["partido"] +
             " · " + game["hora_cdmx"] + " CDMX."]
    sources = [game.get("fuente", "")]
    if verified is None:
        lines.append("No tengo un evento ESPN inequívoco: no emitiré un pick propio.")
    else:
        own = evaluate_game(verified, target, team_fetch=team_fetch, now=clock)
        own = add_covers_price(own, verified, external, target)
        sources.append(own.get("espn_url", ""))
        if own["status"] == "CANDIDATO_EXPERIMENTAL":
            lines.append(
                "SELECCIÓN SPORTS EDGE AI (experimental): " + own["team"] +
                " ML. Estimación exploratoria " +
                f"{own['probability_experimental']:.1%}" +
                " basada en " + str(own["away_games"]) +
                "/" + str(own["home_games"]) + " resultados ESPN previos. " +
                "Veredictos internos: " + str(len(own.get("evidence", {}))) +
                " contrastes; estabilidad " + f"{own.get('stability',0):.0%}" +
                " frente a cambios de muestra (no es tasa de acierto)."
            )
        elif own["status"] == "PASAR":
            lines.append("Decisión Sports Edge AI: PASAR. " + own["reason"] + ".")
        else:
            lines.append("Decisión Sports Edge AI: sin selección. " +
                         own.get("reason", "Faltan datos"))
        if own.get("market_price"):
            lines.append("Momio de Covers para la selección SEAI: " +
                         own["market_price"] +
                         " (precio publicado, sujeto a cambios).")
            sources.append(own.get("market_source", ""))
    for label, value in (("Spread Covers", game.get("spreads_publicados")),
                         ("Total Covers", game.get("totales_publicados"))):
        if value:
            lines.append(label + ": " + str(value))
    lines.append("Modelo propio estadístico, aún NO calibrado ni validado. "
                 "No garantiza rentabilidad ni propone importe de apuesta.")
    context.update({"matchup": game["partido"], "sport": game["liga"]})
    return {"reply": "\n\n".join(lines),
            "sources": _trusted_sources([url for url in sources if url]),
            "context": context}

