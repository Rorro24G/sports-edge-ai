"""Exporta calendario verificado (solo partidos; jamás pronósticos ni momios ficticios).

Fuente: data/calendario_2026-11-13_15.json, con URLs de los calendarios oficiales.
La fecha solicitada se interpreta en horario de los partidos (America/New_York).
Los partidos se muestran también en horario America/Monterrey.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = ROOT / 'data' / 'calendario_2026-11-13_15.json'
FIELDS = ['deporte','fecha_et','hora_et','fecha_monterrey','hora_monterrey',
          'visitante','local','sede_neutral','fuente','estado_cuotas','estado_modelo']


def select_games(fixture: dict, start: date, end: date, sports: set[str] | None = None) -> list[dict]:
    if start > end:
        raise ValueError('La fecha de inicio no puede ser posterior a la fecha final')
    if (end - start).days > 35:
        raise ValueError('Intervalo demasiado amplio (máximo 35 días)')
    result=[]
    for game in fixture['events']:
        day = date.fromisoformat(game['date_et'])
        if not (start <= day <= end) or (sports and game['sport'] not in sports):
            continue
        moment = datetime.fromisoformat(game['date_et'] + 'T' + game['time_et']).replace(
            tzinfo=ZoneInfo('America/New_York'))
        local = moment.astimezone(ZoneInfo('America/Monterrey'))
        result.append({
            'deporte':game['sport'],
            'fecha_et':day.isoformat(),
            'hora_et':game['time_et'],
            'fecha_monterrey':local.date().isoformat(),
            'hora_monterrey':local.strftime('%H:%M'),
            'visitante':game['away'], 'local':game['home'],
            'sede_neutral':'SÍ' if game.get('neutral') else 'NO',
            'fuente':game['source_url'],
            'estado_cuotas':game['market_status'],
            'estado_modelo':game['prediction_status'],
        })
    result.sort(key=lambda item:(item['fecha_et'],item['hora_et'],item['deporte'],item['local']))
    return result


def export_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8-sig') as out:
        writer=csv.DictWriter(out,fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--start',default='2026-11-13',help='Fecha ET YYYY-MM-DD')
    p.add_argument('--end',default='2026-11-14',help='Fecha ET YYYY-MM-DD')
    p.add_argument('--sport',action='append',choices=['NBA','NFL','NHL'],help='Filtro repetible')
    p.add_argument('--source',default=str(DEFAULT_FIXTURE))
    p.add_argument('--output',default='output/calendario_2026-11-13_14.csv')
    args=p.parse_args()
    try:
        start=date.fromisoformat(args.start)
        end=date.fromisoformat(args.end)
        fixture=json.loads(Path(args.source).read_text(encoding='utf-8'))
        rows=select_games(fixture,start,end,set(args.sport) if args.sport else None)
    except (ValueError,KeyError,OSError,json.JSONDecodeError) as exc:
        p.error(str(exc))
    output=Path(args.output)
    export_csv(rows,output)
    counts={f'{d} | {s}':n for (d,s),n in sorted(Counter(
        (r['fecha_et'],r['deporte']) for r in rows).items())}
    output.with_suffix('.metadata.json').write_text(json.dumps({
        'checked_date': fixture.get('checked_date'),
        'generated_at_utc':datetime.now(timezone.utc).isoformat(),
        'date_start_et':start.isoformat(), 'date_end_et':end.isoformat(),
        'totals':counts, 'game_count':len(rows),
        'odds_verified':False,'prediction_model_validated':False,
        'caveat':'Calendario estático; debe verificarse antes de jugar. Sin cuotas ni recomendaciones.'
    },ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'{len(rows)} partidos exportados a {output}; SIN CUOTAS / SIN PREDICCIÓN')


if __name__=='__main__':
    main()
